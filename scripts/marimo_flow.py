"""marimo アプリのセル依存関係・関数呼び出しを Mermaid フロー図として出力する
-> GUI 層は自動テストで網羅しないため、人間のレビューを補助する目的で使う。

アプリは実行せず ast で静的に解析する。marimo の .py 形式ではセル関数の
引数が参照変数 (refs)、return のタプルが定義変数 (defs) を表すため、それをそのまま用いる。
"""

import argparse
import ast
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_APPS_DIR = Path("src/apps")
DEFAULT_OUT_DIR = Path("docs/flows")
# GitHub の本文幅で文字が縮小されないよう、浅く広い DAG は横向きに描く
DEFAULT_DIRECTION = "LR"
# ラベルを折り返す表示幅 (半角 1・全角 2 で数える)
DEFAULT_WRAP_WIDTH = 30

# 行頭に置かない文字 (行頭禁則)
_NO_LINE_START = frozenset("、。，．,.）)」』】〕！？!?ー")

# Mermaid のラベル内で特別な意味を持つ文字を数値エンティティへ置換する
_MERMAID_ESCAPES = {"#": "#35;", '"': "#34;", "&": "#38;", "<": "#60;", ">": "#62;"}

LEGEND = """\
| 形 | 意味 |
|---|---|
| 四角 | 処理を行うセル |
| 角丸 (スタジアム形) | 何も定義せず画面表示だけを行うセル |
| 枠 (サブグラフ) | UI 要素を定義するセル |
| 平行四辺形 | UI 要素 (`mo.ui.*`) |
| 二重枠 | プロジェクト内の関数・クラスの呼び出し (点線) |
| ⏳ | async セル |
| 実線の矢印 | 変数の受け渡し (ラベルは変数名) |
"""


@dataclass
class UIElement:
    """セル内で定義された UI 要素。"""

    name: str
    kind: str
    label: str | None


@dataclass
class CallTarget:
    """プロジェクト内の関数・クラスへの呼び出し。"""

    qualname: str
    summary: str | None

    @property
    def short_name(self) -> str:
        """修飾なしの名前。"""
        return self.qualname.rsplit(".", 1)[-1]


@dataclass
class Cell:
    """解析済みの marimo セル。"""

    index: int
    kind: str  # "cell" / "function" / "class" / "setup"
    name: str
    lineno: int
    summary: str | None = None
    is_async: bool = False
    refs: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)
    module_imports: set[str] = field(default_factory=set)
    ui_elements: list[UIElement] = field(default_factory=list)
    calls: list[CallTarget] = field(default_factory=list)
    loads: set[str] = field(default_factory=set)
    value_accesses: set[str] = field(default_factory=set)
    is_view: bool = False

    @property
    def node_id(self) -> str:
        """Mermaid のノード ID。"""
        return f"c{self.index}"


@dataclass
class Issue:
    """レビューで指摘すべき問題。"""

    lineno: int
    message: str


@dataclass
class Notebook:
    """解析済みの marimo ノートブック。"""

    path: Path
    cells: list[Cell]


def first_line(docstring: str | None) -> str | None:
    """DocString の 1 行目を返す。空なら None。"""
    if not docstring or not docstring.strip():
        return None
    return docstring.strip().splitlines()[0].strip()


def dotted_name(node: ast.expr) -> str | None:
    """`a.b.c` 形式の式をドット区切りの文字列にする。それ以外は None。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _decorator_kind(decorator: ast.expr) -> str | None:
    """`@app.cell` / `@app.cell(...)` などからセルの種類を判定する。"""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if not isinstance(target, ast.Attribute):
        return None
    return {"cell": "cell", "function": "function", "class_definition": "class"}.get(target.attr)


def _is_setup_block(node: ast.stmt) -> bool:
    """`with app.setup:` ブロックかどうか。"""
    if not isinstance(node, ast.With) or len(node.items) != 1:
        return False
    expr = node.items[0].context_expr
    target = expr.func if isinstance(expr, ast.Call) else expr
    return isinstance(target, ast.Attribute) and target.attr == "setup"


def _bound_names(stmts: list[ast.stmt]) -> list[str]:
    """文のリストがトップレベルで束縛する名前を出現順に返す。"""
    names: list[str] = []
    for stmt in stmts:
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            names += [(alias.asname or alias.name).split(".")[0] for alias in stmt.names]
        elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(stmt.name)
        else:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    names.append(node.id)
    return list(dict.fromkeys(names))


def _return_names(stmt: ast.stmt) -> list[str]:
    """セル末尾の return 文が返す変数名。"""
    if not isinstance(stmt, ast.Return) or stmt.value is None:
        return []
    values = stmt.value.elts if isinstance(stmt.value, ast.Tuple) else [stmt.value]
    return [v.id for v in values if isinstance(v, ast.Name)]


def _body_without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    """先頭の DocString を除いた本文。"""
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def _collect_body_info(cell: Cell, stmts: list[ast.stmt]) -> None:
    """セル本文から import・読み込み変数・`.value` 参照を収集する。"""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Import):
                cell.module_imports |= {(a.asname or a.name).split(".")[0] for a in node.names}
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                cell.loads.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr == "value" and isinstance(node.value, ast.Name):
                cell.value_accesses.add(node.value.id)


def _parse_cell(index: int, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> Cell:
    """`@app.cell` などで修飾された関数をセルとして解析する。"""
    cell = Cell(
        index=index,
        kind=kind,
        name=node.name,
        lineno=node.lineno,
        summary=first_line(ast.get_docstring(node)),
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )
    body = _body_without_docstring(node.body)
    if kind == "cell":
        cell.refs = [arg.arg for arg in node.args.args]
        if body and isinstance(body[-1], ast.Return):
            cell.defs = _return_names(body[-1])
            body = body[:-1]
        cell.is_view = not cell.defs and bool(body) and isinstance(body[-1], ast.Expr)
        _collect_body_info(cell, body)
    else:
        cell.defs = [node.name]
        _collect_body_info(cell, [node])
    return cell


def parse_notebook(path: Path) -> Notebook:
    """marimo ノートブックを静的に解析する。

    Args:
        path: marimo アプリの .py ファイル。

    Returns:
        セル一覧を持つ Notebook。refs の補完・呼び出し解決は行わない。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    cells: list[Cell] = []
    for node in tree.body:
        if _is_setup_block(node):
            assert isinstance(node, ast.With)
            cell = Cell(index=len(cells), kind="setup", name="setup", lineno=node.lineno)
            cell.defs = _bound_names(node.body)
            _collect_body_info(cell, node.body)
            cells.append(cell)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            kind = next((k for d in node.decorator_list if (k := _decorator_kind(d))), None)
            if kind is None:
                continue
            if isinstance(node, ast.ClassDef):
                cell = Cell(
                    index=len(cells),
                    kind=kind,
                    name=node.name,
                    lineno=node.lineno,
                    summary=first_line(ast.get_docstring(node)),
                    defs=[node.name],
                )
                _collect_body_info(cell, [node])
                cells.append(cell)
            else:
                cells.append(_parse_cell(len(cells), node, kind))

    # @app.function / setup などは引数を持たないため、読み込み変数から参照を補う
    all_defs = {name for c in cells for name in c.defs}
    for cell in cells:
        if cell.kind != "cell":
            cell.refs = sorted((cell.loads & all_defs) - set(cell.defs))
    return Notebook(path=path, cells=cells)


class SymbolResolver:
    """プロジェクト内モジュールの関数・クラスを探し、DocString 1 行目を得る。"""

    def __init__(self, root: Path) -> None:
        """探索のルートディレクトリを指定する。"""
        self.root = root
        self._cache: dict[Path, ast.Module | None] = {}

    def _module_file(self, module: str) -> Path | None:
        base = self.root.joinpath(*module.split("."))
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            if candidate.is_file():
                return candidate
        return None

    def _load(self, path: Path) -> ast.Module | None:
        if path not in self._cache:
            try:
                self._cache[path] = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                self._cache[path] = None
        return self._cache[path]

    def resolve(self, qualname: str) -> CallTarget | None:
        """`pkg.mod.func` を解決する。プロジェクト外なら None。"""
        parts = qualname.split(".")
        for i in range(len(parts) - 1, 0, -1):
            path = self._module_file(".".join(parts[:i]))
            if path is None:
                continue
            return CallTarget(qualname=qualname, summary=self._summary(path, parts[i:]))
        return None

    def _summary(self, path: Path, attrs: list[str]) -> str | None:
        tree = self._load(path)
        scope: list[ast.stmt] = tree.body if tree else []
        found: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None = None
        for attr in attrs:
            found = next(
                (
                    n
                    for n in scope
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and n.name == attr
                ),
                None,
            )
            if found is None:
                return None
            scope = found.body
        return first_line(ast.get_docstring(found)) if found else None


def _import_table(tree: ast.Module) -> tuple[dict[str, str], set[str]]:
    """ノートブック全体の import から「束縛名 → 完全修飾名」と marimo の別名を得る。"""
    table: dict[str, str] = {}
    marimo_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                table[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    table[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    table[head] = head
                if alias.name == "marimo":
                    marimo_aliases.add(alias.asname or "marimo")
    return table, marimo_aliases


def resolve_references(notebook: Notebook, root: Path) -> None:
    """各セルの UI 要素とプロジェクト内関数の呼び出しを解決する。"""
    tree = ast.parse(notebook.path.read_text(encoding="utf-8"))
    table, marimo_aliases = _import_table(tree)
    resolver = SymbolResolver(root)
    cell_nodes = {
        node.lineno: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.With)
    }
    for cell in notebook.cells:
        node = cell_nodes.get(cell.lineno)
        if node is None:
            continue
        seen: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                ui = _ui_element(sub.targets[0].id, sub.value, marimo_aliases)
                if ui:
                    cell.ui_elements.append(ui)
            if not isinstance(sub, ast.Call):
                continue
            name = dotted_name(sub.func)
            if name is None:
                continue
            head, _, rest = name.partition(".")
            if head not in table:
                continue
            qualname = table[head] + (f".{rest}" if rest else "")
            if qualname in seen:
                continue
            target = resolver.resolve(qualname)
            if target:
                seen.add(qualname)
                cell.calls.append(target)


def _ui_element(name: str, value: ast.expr, marimo_aliases: set[str]) -> UIElement | None:
    """`x = mo.ui.<kind>(...)` を UI 要素として認識する。"""
    if not isinstance(value, ast.Call):
        return None
    func = dotted_name(value.func)
    if func is None:
        return None
    parts = func.split(".")
    if len(parts) != 3 or parts[0] not in marimo_aliases or parts[1] != "ui":
        return None
    label = next(
        (
            kw.value.value
            for kw in value.keywords
            if kw.arg == "label" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
        ),
        None,
    )
    return UIElement(name=name, kind=parts[2], label=label)


def find_issues(notebook: Notebook) -> list[Issue]:
    """レビューで見落としやすい問題を検出する。"""
    issues: list[Issue] = []
    referenced = {ref for c in notebook.cells for ref in c.refs}
    value_accessed = {name for c in notebook.cells for name in c.value_accesses}
    for cell in notebook.cells:
        if cell.kind == "setup":
            continue
        if cell.kind == "cell" and cell.name == "_":
            issues.append(Issue(cell.lineno, "セル名がありません (def _)"))
        if cell.summary is None:
            issues.append(Issue(cell.lineno, f"{cell.name}: DocString がありません"))
        for ui in cell.ui_elements:
            if ui.name not in referenced and ui.name not in cell.loads:
                issues.append(Issue(cell.lineno, f"{cell.name}: UI 要素 {ui.name} がどこからも参照されていません"))
            if ui.kind == "run_button" and ui.name not in value_accessed:
                issues.append(Issue(cell.lineno, f"{cell.name}: run_button {ui.name} の .value が参照されていません"))
    return issues


def escape_label(text: str) -> str:
    """Mermaid の引用ラベル内で安全な文字列にする。"""
    return re.sub(r'[#"&<>]', lambda m: _MERMAID_ESCAPES[m.group()], text)


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "FW" else 1 for ch in text)


def _greedy_wrap(tokens: list[str], width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in tokens:
        if current.strip() and token not in _NO_LINE_START and _display_width(current + token) > width:
            lines.append(current.rstrip())
            current = token.lstrip()
        else:
            current += token
    if current.strip():
        lines.append(current.rstrip())
    return lines


def wrap_label(text: str, width: int) -> str:
    """表示幅 width を超えないよう折り返し、エスケープして `<br/>` で連結する。

    末尾に 1〜2 文字だけの行が残らないよう、行数を保ったまま各行の幅を均す。
    英数字の単語は途中で分割しない。width が 0 以下なら折り返さない。
    """
    if width <= 0:
        return escape_label(text)
    tokens = re.findall(r"[A-Za-z0-9_.:/()\-]+|\s+|.", text)
    lines = _greedy_wrap(tokens, width)
    target = -(-_display_width(text) // len(lines)) if lines else width
    while target < width:
        balanced = _greedy_wrap(tokens, target)
        if len(balanced) <= len(lines):
            lines = balanced
            break
        target += 1
    return "<br/>".join(escape_label(line) for line in lines)


def _cell_title(cell: Cell, separator: str, wrap: int) -> str:
    prefix = {"function": "@app.function ", "class": "@app.class_definition "}.get(cell.kind, "")
    title = ("⏳ " if cell.is_async else "") + escape_label(prefix + cell.name)
    if cell.summary:
        title += separator + wrap_label(cell.summary, wrap)
    return title


def render_mermaid(
    notebook: Notebook,
    *,
    compact: bool = False,
    show_imports: bool = False,
    direction: str = DEFAULT_DIRECTION,
    wrap: int = DEFAULT_WRAP_WIDTH,
) -> str:
    """Notebook を Mermaid の flowchart に変換する。

    Args:
        notebook: 解析済みの Notebook。
        compact: True ならセル単位の簡易図 (UI 要素・呼び出しを省略) にする。
        show_imports: True なら `import x` で得たモジュール変数 (mo, os など) の受け渡しも描く。
        direction: 図の向き (LR / TD など)。
        wrap: ラベルを折り返す表示幅。0 以下なら折り返さない。

    Returns:
        Mermaid のソース。
    """
    lines = [f"flowchart {direction}"]
    owner: dict[str, Cell] = {}
    ui_ids: dict[str, str] = {}
    for cell in notebook.cells:
        for name in cell.defs:
            owner.setdefault(name, cell)

    # ノード
    call_ids: dict[str, str] = {}
    call_edges: list[str] = []
    for cell in notebook.cells:
        if not compact and cell.ui_elements:
            # サブグラフの見出し欄は 3 行目以降が見切れるため、DocString は折り返さない
            lines.append(f'  subgraph {cell.node_id}["{_cell_title(cell, "<br/>", 0)}"]')
            for j, ui in enumerate(cell.ui_elements):
                ui_id = f"{cell.node_id}_u{j}"
                ui_ids[ui.name] = ui_id
                label = escape_label(f"{ui.name}: {ui.kind}")
                if ui.label:
                    label += "<br/>" + wrap_label(f"「{ui.label}」", wrap)
                lines.append(f'    {ui_id}[/"{label}"/]')
            lines.append("  end")
        else:
            title = _cell_title(cell, "<br/>", wrap)
            lines.append(f'  {cell.node_id}(["{title}"])' if cell.is_view else f'  {cell.node_id}["{title}"]')
        if compact:
            continue
        for call in cell.calls:
            if call.qualname not in call_ids:
                call_ids[call.qualname] = f"f{len(call_ids)}"
                label = escape_label(f"{call.short_name}()")
                if call.summary:
                    label += "<br/>" + wrap_label(call.summary, wrap)
                lines.append(f'  {call_ids[call.qualname]}[["{label}"]]')
            call_edges.append(f"  {cell.node_id} -.-> {call_ids[call.qualname]}")

    # 変数の受け渡し (同じ始点・終点の組はまとめる)
    edges: dict[tuple[str, str], list[str]] = {}
    for cell in notebook.cells:
        for ref in cell.refs:
            source = owner.get(ref)
            if source is None or source is cell:
                continue
            if not show_imports and ref in source.module_imports:
                continue
            if not compact and ref in ui_ids:
                edges.setdefault((ui_ids[ref], cell.node_id), [])
            else:
                edges.setdefault((source.node_id, cell.node_id), []).append(ref)
    for (src, dst), names in edges.items():
        label = f'|"{escape_label(", ".join(names))}"|' if names else ""
        lines.append(f"  {src} -->{label} {dst}")
    lines += call_edges
    return "\n".join(lines) + "\n"


def render_markdown(notebook: Notebook, mermaid: str, issues: list[Issue], source: str) -> str:
    """フロー図・凡例・検査結果をまとめた Markdown を生成する。"""
    parts = [
        f"# {notebook.path.stem} フロー図",
        "",
        f"`task flow` による自動生成ファイルです。手動で編集しないでください。ソース: `{source}`",
        "",
        "```mermaid",
        mermaid.rstrip("\n"),
        "```",
        "",
        "## 凡例",
        "",
        LEGEND.rstrip("\n"),
        "",
        "## 検査結果",
        "",
    ]
    if issues:
        parts += [f"* L{i.lineno}: {i.message}" for i in issues]
    else:
        parts.append("指摘なし")
    return "\n".join(parts) + "\n"


def _default_targets(apps_dir: Path) -> list[Path]:
    return sorted(p for p in apps_dir.glob("*.py") if p.name != "__init__.py")


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    """コマンドライン引数の定義。"""
    parser = argparse.ArgumentParser(description="marimo アプリの依存関係を Mermaid フロー図として出力する")
    parser.add_argument("paths", nargs="*", type=Path, help=f"対象ファイル (省略時は {DEFAULT_APPS_DIR}/*.py)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="出力先ディレクトリ")
    parser.add_argument("--root", type=Path, default=Path(), help="import 解決に使うプロジェクトルート")
    parser.add_argument("--compact", action="store_true", help="セル単位の簡易図にする")
    parser.add_argument(
        "--direction", choices=["LR", "TD"], default=DEFAULT_DIRECTION, help="図の向き (既定: %(default)s)"
    )
    parser.add_argument(
        "--wrap", type=int, default=DEFAULT_WRAP_WIDTH, help="ラベルを折り返す表示幅。0 で無効 (既定: %(default)s)"
    )
    parser.add_argument("--show-imports", action="store_true", help="mo, os などモジュール変数の受け渡しも描く")
    parser.add_argument("--stdout", action="store_true", help="ファイルに書かず標準出力へ出す")
    parser.add_argument("--check", action="store_true", help="出力ファイルが最新か検査するだけで書き込まない")
    parser.add_argument("--warn-only", action="store_true", help="検査結果をエラーではなく警告として扱う")
    return parser


def main(argv: list[str] | None = None) -> int:
    """フロー図を生成する。問題があれば 1 を返す。"""
    args = build_parser().parse_args(argv)
    targets = args.paths or _default_targets(args.root / DEFAULT_APPS_DIR)
    severity = "warning" if args.warn_only else "error"
    failed = False

    for path in targets:
        source = _display_path(path, args.root)
        notebook = parse_notebook(path)
        resolve_references(notebook, args.root)
        issues = find_issues(notebook)
        for issue in issues:
            print(f"{source}:{issue.lineno}: [{severity}] {issue.message}", file=sys.stderr)
        failed |= bool(issues) and not args.warn_only

        mermaid = render_mermaid(
            notebook,
            compact=args.compact,
            show_imports=args.show_imports,
            direction=args.direction,
            wrap=args.wrap,
        )
        content = render_markdown(notebook, mermaid, issues, source)
        if args.stdout:
            print(content, end="")
            continue

        out = args.out_dir / f"{path.stem}.md"
        if args.check:
            current = out.read_text(encoding="utf-8").replace("\r\n", "\n") if out.is_file() else None
            if current != content:
                print(f"{out.as_posix()}: 最新ではありません。`task flow` で再生成してください", file=sys.stderr)
                failed = True
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8", newline="\n")
        print(f"Created {out.as_posix()}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

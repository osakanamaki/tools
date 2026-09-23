"""marimo_flow スクリプトのテスト。"""

import builtins
import textwrap
from pathlib import Path

import pytest
from marimo._ast.compiler import compile_cell
from marimo._ast.load import get_notebook_status
from marimo._types.ids import CellId_t

from scripts.marimo_flow import (
    Notebook,
    escape_label,
    find_issues,
    main,
    parse_notebook,
    render_markdown,
    render_mermaid,
    resolve_references,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NOTEBOOK = '''\
import marimo

app = marimo.App()


@app.cell
def imports():
    """共通モジュールの読み込み"""
    import marimo as mo

    return (mo,)


@app.cell
def inputs(mo):
    """入力フォーム

    2 行目以降は図に出さない。
    """
    name_input = mo.ui.text(label="名前")
    go = mo.ui.run_button(label="実行")
    return go, name_input


@app.cell
def execution(go, mo, name_input):
    """挨拶の生成"""
    from src.core.greet import greet

    message = mo.md("")
    if go.value:
        message = mo.md(greet(name_input.value))
    return (message,)


@app.cell
def view(message, mo, name_input, go):
    """表示"""
    mo.vstack([name_input, go, message])
    return


@app.cell
async def fetch(mo):
    """非同期取得"""
    import src.core.greet as g

    g.Greeter.hello()
    print("外部関数は図に出さない")
    return


if __name__ == "__main__":
    app.run()
'''

GREET_MODULE = '''\
"""挨拶モジュール。"""


def greet(name: str) -> str:
    """名前付きの挨拶を返す。

    詳細説明。
    """
    return f"こんにちは {name}"


class Greeter:
    """挨拶クラス。"""

    @staticmethod
    def hello() -> str:
        """固定の挨拶を返す。"""
        return "hello"
'''


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """アプリと core モジュールを持つ最小プロジェクト。"""
    (tmp_path / "src" / "apps").mkdir(parents=True)
    (tmp_path / "src" / "core").mkdir(parents=True)
    (tmp_path / "src" / "apps" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "apps" / "greeting.py").write_text(NOTEBOOK, encoding="utf-8")
    (tmp_path / "src" / "core" / "greet.py").write_text(GREET_MODULE, encoding="utf-8")
    return tmp_path


def load(project: Path, name: str = "greeting") -> Notebook:
    """解析と参照解決を済ませた Notebook を返す。"""
    notebook = parse_notebook(project / "src" / "apps" / f"{name}.py")
    resolve_references(notebook, project)
    return notebook


def write_app(project: Path, name: str, body: str) -> Path:
    """テスト用のアプリを追加する。"""
    path = project / "src" / "apps" / f"{name}.py"
    path.write_text("import marimo\n\napp = marimo.App()\n\n" + textwrap.dedent(body), encoding="utf-8")
    return path


def test_parses_cells_refs_defs_and_summary(project: Path) -> None:
    """セル名・参照・定義・DocString 1 行目を抽出することを検証する。"""
    cells = load(project).cells
    assert [c.name for c in cells] == ["imports", "inputs", "execution", "view", "fetch"]
    inputs = cells[1]
    assert inputs.refs == ["mo"]
    assert inputs.defs == ["go", "name_input"]
    assert inputs.summary == "入力フォーム"
    assert cells[0].module_imports == {"mo"}


def test_detects_view_and_async_cells(project: Path) -> None:
    """表示専用セルと async セルを判別することを検証する。"""
    cells = {c.name: c for c in load(project).cells}
    assert cells["view"].is_view is True
    assert cells["execution"].is_view is False
    assert cells["fetch"].is_async is True
    # print() で終わる何も返さないセルも表示専用扱いになる
    assert cells["fetch"].is_view is True


def test_extracts_ui_elements_with_labels(project: Path) -> None:
    """mo.ui.* の種類とラベルを抽出することを検証する。"""
    inputs = load(project).cells[1]
    assert [(u.name, u.kind, u.label) for u in inputs.ui_elements] == [
        ("name_input", "text", "名前"),
        ("go", "run_button", "実行"),
    ]


def test_resolves_project_calls_with_docstring(project: Path) -> None:
    """プロジェクト内の関数・メソッド呼び出しを DocString 付きで解決し、外部関数は無視することを検証する。"""
    cells = {c.name: c for c in load(project).cells}
    assert [(c.qualname, c.summary) for c in cells["execution"].calls] == [
        ("src.core.greet.greet", "名前付きの挨拶を返す。"),
    ]
    assert [(c.short_name, c.summary) for c in cells["fetch"].calls] == [("hello", "固定の挨拶を返す。")]


def test_unresolvable_symbol_has_no_summary(project: Path) -> None:
    """モジュールは存在するが定義が見つからない呼び出しは説明なしで残すことを検証する。"""
    write_app(
        project,
        "missing",
        '''\
        @app.cell
        def call_missing():
            """存在しない関数を呼ぶ"""
            from src.core.greet import nothing

            nothing()
            return
        ''',
    )
    calls = load(project, "missing").cells[0].calls
    assert [(c.short_name, c.summary) for c in calls] == [("nothing", None)]


def test_broken_module_is_tolerated(project: Path) -> None:
    """構文エラーのモジュールを呼んでも解析が止まらないことを検証する。"""
    (project / "src" / "core" / "broken.py").write_text("def (:\n", encoding="utf-8")
    write_app(
        project,
        "broken",
        '''\
        @app.cell
        def call_broken():
            """壊れたモジュールを呼ぶ"""
            from src.core.broken import f

            f()
            return
        ''',
    )
    calls = load(project, "broken").cells[0].calls
    assert [(c.short_name, c.summary) for c in calls] == [("f", None)]


def test_parses_setup_function_and_class_definition(project: Path) -> None:
    """setup ブロック・@app.function・@app.class_definition を扱えることを検証する。"""
    write_app(
        project,
        "extras",
        '''\
        with app.setup:
            import marimo as mo
            LIMIT = 3


        @app.function
        def double(x):
            """2 倍にする"""
            return x * LIMIT


        @app.class_definition
        class Box:
            """箱"""

            size = LIMIT


        @app.cell
        def use(mo):
            """利用"""
            mo.md(str(double(Box.size)))
            return


        def not_a_cell():
            return
        ''',
    )
    cells = {c.name: c for c in load(project, "extras").cells}
    assert list(cells) == ["setup", "double", "Box", "use"]
    assert cells["setup"].defs == ["mo", "LIMIT"]
    assert cells["double"].refs == ["LIMIT"]
    assert cells["Box"].refs == ["LIMIT"]
    assert cells["Box"].summary == "箱"
    # @app.function などは引数を持たないため、グローバル参照は ast から補う
    assert "double" in cells["use"].loads


def test_find_issues_reports_review_points(project: Path) -> None:
    """名前なしセル・DocString なし・未参照の UI 要素・未使用の run_button を検出することを検証する。"""
    write_app(
        project,
        "bad",
        """\
        @app.cell
        def _():
            import marimo as mo

            return (mo,)


        @app.cell
        def lonely(mo):
            \"\"\"孤立した UI\"\"\"
            unused = mo.ui.text()
            button = mo.ui.run_button()
            return (button,)


        @app.cell
        def show(button):
            \"\"\"ボタンを置くだけ\"\"\"
            button
            return
        """,
    )
    messages = [i.message for i in find_issues(load(project, "bad"))]
    assert messages == [
        "セル名がありません (def _)",
        "_: DocString がありません",
        "lonely: UI 要素 unused がどこからも参照されていません",
        "lonely: run_button button の .value が参照されていません",
    ]


def test_find_issues_accepts_clean_notebook(project: Path) -> None:
    """問題のないノートブックでは指摘がないことを検証する。"""
    assert find_issues(load(project)) == []


def test_ui_element_displayed_in_own_cell_is_not_reported(project: Path) -> None:
    """定義したセル自身で表示している UI 要素は未参照扱いしないことを検証する。"""
    write_app(
        project,
        "self_view",
        '''\
        @app.cell
        def slider():
            """その場で表示するスライダー"""
            import marimo as mo

            s = mo.ui.slider(1, 10)
            s
            return
        ''',
    )
    assert find_issues(load(project, "self_view")) == []


def test_escape_label() -> None:
    """Mermaid で特別な意味を持つ文字をエスケープすることを検証する。"""
    assert escape_label('a "b" <c> & #d [e]') == "a #34;b#34; #60;c#62; #38; #35;d [e]"


def test_render_detailed(project: Path) -> None:
    """詳細図に UI 要素・呼び出し・変数ラベル付きの矢印が含まれることを検証する。"""
    mermaid = render_mermaid(load(project))
    assert mermaid.startswith("flowchart TD\n")
    assert '  subgraph c1["inputs — 入力フォーム"]' in mermaid
    assert '    c1_u0[/"name_input: text「名前」"/]' in mermaid
    assert '    c1_u1[/"go: run_button「実行」"/]' in mermaid
    assert '  c3(["view<br/>表示"])' in mermaid
    assert '  c4(["⏳ fetch<br/>非同期取得"])' in mermaid
    assert '  f0[["greet()<br/>名前付きの挨拶を返す。"]]' in mermaid
    assert "  c1_u0 --> c2" in mermaid
    assert '  c2 -->|"message"| c3' in mermaid
    assert "  c2 -.-> f0" in mermaid
    # モジュール変数 (mo) の受け渡しは既定で描かない
    assert "c0 -->" not in mermaid
    # 色指定はライト/ダークモードを壊しうるため使わない
    assert "fill" not in mermaid
    assert "classDef" not in mermaid
    assert "style" not in mermaid


def test_render_shared_call_node_once(project: Path) -> None:
    """同じ関数を複数セルから呼んでもノードは 1 つにまとめることを検証する。"""
    write_app(
        project,
        "shared",
        '''\
        @app.cell
        def first():
            """1 回目"""
            from src.core.greet import greet

            greet("a")
            greet("b")
            return (greet,)


        @app.cell
        def second(greet):
            """2 回目"""
            greet("c")
            return
        ''',
    )
    mermaid = render_mermaid(load(project, "shared"))
    assert mermaid.count("[[") == 1
    assert "  c0 -.-> f0" in mermaid
    assert "  c1 -.-> f0" in mermaid
    assert '  c0 -->|"greet"| c1' in mermaid


def test_render_compact(project: Path) -> None:
    """簡易図ではセル単位の矢印だけを描くことを検証する。"""
    mermaid = render_mermaid(load(project), compact=True)
    assert "subgraph" not in mermaid
    assert "[[" not in mermaid
    assert '  c1["inputs<br/>入力フォーム"]' in mermaid
    assert '  c1 -->|"go, name_input"| c2' in mermaid


def test_render_show_imports(project: Path) -> None:
    """show_imports でモジュール変数の受け渡しも描くことを検証する。"""
    mermaid = render_mermaid(load(project), show_imports=True)
    assert '  c0 -->|"mo"| c1' in mermaid


def test_render_markdown(project: Path) -> None:
    """Markdown に図・凡例・検査結果が含まれることを検証する。"""
    notebook = load(project)
    ok = render_markdown(notebook, "flowchart TD\n", [], "src/apps/greeting.py")
    assert ok.startswith("# greeting フロー図\n")
    assert "```mermaid\nflowchart TD\n```" in ok
    assert "## 凡例" in ok
    assert ok.endswith("## 検査結果\n\n指摘なし\n")


def test_main_writes_markdown(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """既定で src/apps 配下を処理して Markdown を書き出すことを検証する。"""
    out = project / "flows"
    assert main(["--root", str(project), "--out-dir", str(out)]) == 0
    assert [p.name for p in out.iterdir()] == ["greeting.md"]
    content = (out / "greeting.md").read_text(encoding="utf-8")
    assert "ソース: `src/apps/greeting.py`" in content
    assert "\r\n" not in (out / "greeting.md").read_bytes().decode("utf-8")
    assert "Created" in capsys.readouterr().out


def test_main_fails_on_issues_unless_warn_only(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """検査の指摘は既定でエラー、--warn-only で警告になることを検証する。"""
    app = write_app(project, "bad", "@app.cell\ndef _():\n    return\n")
    out = project / "flows"
    assert main(["--root", str(project), "--out-dir", str(out), str(app)]) == 1
    assert "[error] セル名がありません" in capsys.readouterr().err
    assert main(["--root", str(project), "--out-dir", str(out), "--warn-only", str(app)]) == 0
    assert "[warning] セル名がありません" in capsys.readouterr().err
    # エラーがあっても図自体は出力する
    assert (out / "bad.md").is_file()


def test_main_check(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--check は書き込まずに鮮度を検査し、改行コードの違いは許容することを検証する。"""
    out = project / "flows"
    args = ["--root", str(project), "--out-dir", str(out)]
    assert main([*args, "--check"]) == 1
    assert not out.exists()
    assert "最新ではありません" in capsys.readouterr().err

    assert main(args) == 0
    target = out / "greeting.md"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert main([*args, "--check"]) == 0

    target.write_text("古い内容\n", encoding="utf-8")
    assert main([*args, "--check"]) == 1


def test_main_stdout(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--stdout はファイルを書かずに標準出力へ出すことを検証する。"""
    out = project / "flows"
    app = project / "src" / "apps" / "greeting.py"
    assert main(["--root", str(project), "--out-dir", str(out), "--stdout", "--compact", str(app)]) == 0
    assert not out.exists()
    assert "```mermaid" in capsys.readouterr().out


def test_main_path_outside_root(project: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """ルート外のファイルは与えられたパスのまま表示することを検証する。"""
    other = tmp_path_factory.mktemp("other") / "outside.py"
    other.write_text((project / "src" / "apps" / "greeting.py").read_text(encoding="utf-8"), encoding="utf-8")
    out = project / "flows"
    assert main(["--root", str(project), "--out-dir", str(out), str(other)]) == 0
    assert f"ソース: `{other.as_posix()}`" in (out / "outside.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("app_path", sorted((PROJECT_ROOT / "src" / "apps").glob("[!_]*.py")), ids=lambda p: p.stem)
def test_matches_marimo_compiler(app_path: Path) -> None:
    """実アプリの refs / defs が marimo 本体の解析結果と一致することを検証する。

    marimo の非公開 API を使うため、marimo の更新で仕様がずれた場合の検知を目的とする。
    """
    notebook = get_notebook_status(str(app_path)).notebook
    assert notebook is not None
    ours = [c for c in parse_notebook(app_path).cells if c.kind == "cell"]
    assert len(ours) == len(notebook.cells)
    for cell, ir in zip(ours, notebook.cells, strict=True):
        compiled = compile_cell(ir.code, cell_id=CellId_t(cell.node_id))
        # marimo は組み込み名 (OSError など) も refs に含める
        assert set(cell.refs) == compiled.refs - set(dir(builtins)), cell.name
        assert set(cell.defs) <= compiled.defs, cell.name

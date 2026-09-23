"""背景色付きヘッダーコンポーネント。"""

from html import escape

import marimo as mo


def header(
    title: str,
    description: str = "",
    start_color: str = "#e7e7eb",
    end_color: str = "#aacf53",
    text_color: str = "#000000",
) -> mo.Html:
    """背景色付き（グラデーション）のヘッダーを生成する。

    Args:
        title: 見出しに表示するタイトル。
        description: タイトル下に表示する説明文。空文字の場合は表示しない。
        start_color: グラデーションの開始色。CSS の色指定形式。
        end_color: グラデーションの終了色。CSS の色指定形式。
        text_color: 文字色。CSS の色指定形式。

    Returns:
        marimo で表示可能な Html オブジェクト。
    """
    description_html = f'<p style="margin: 0.5rem 0 0; opacity: 0.85;">{escape(description)}</p>' if description else ""

    # CSSのlinear-gradientを使ってグラデーションを指定
    bg_style = f"background: linear-gradient(135deg, {escape(start_color)}, {escape(end_color)});"

    return mo.Html(
        f'<div style="{bg_style} color: {escape(text_color)}; '
        f'padding: 1.25rem 1.5rem; border-radius: 0.75rem;">'
        f'<h1 style="margin: 0; color: inherit; font-size: 1.75rem;">{escape(title)}</h1>'
        f"{description_html}"
        f"</div>"
    )

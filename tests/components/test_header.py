"""header モジュールのテスト。"""

import marimo as mo

from src.components.header import header


def test_header_returns_marimo_html() -> None:
    """marimo の Html オブジェクトを返すことを検証する。"""
    assert isinstance(header("タイトル"), mo.Html)


def test_header_contains_title_and_description() -> None:
    """タイトルと説明文が出力に含まれることを検証する。"""
    html = header("タイトル", "説明文").text
    assert "タイトル" in html
    assert "説明文" in html


def test_header_omits_description_when_empty() -> None:
    """説明文が空の場合は説明文の要素を出力しないことを検証する。"""
    html = header("タイトル").text
    assert "<p" not in html


def test_header_applies_colors() -> None:
    """グラデーションの開始色・終了色と文字色が style に反映されることを検証する。"""
    html = header("タイトル", start_color="#123456", end_color="#654321", text_color="#abcdef").text
    assert "linear-gradient(135deg, #123456, #654321)" in html
    assert "color: #abcdef" in html


def test_header_escapes_html() -> None:
    """タイトル・説明文・色に含まれる HTML がエスケープされることを検証する。"""
    html = header("<script>", "<b>x</b>", start_color='red"><script>', end_color='blue"><script>').text
    assert "<script>" not in html
    assert "<b>" not in html
    assert "&lt;script&gt;" in html

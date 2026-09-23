"""ingest スクリプトのテスト。"""

from pathlib import Path
from unittest.mock import patch

from gitingest import ingest

from scripts.ingest import apply_gitingest_patch, decodes_allowing_truncation, main

# gitingest が判定に使う先頭チャンクのサイズ
CHUNK_SIZE = 1024


def test_decodes_complete_utf8() -> None:
    """完全な UTF-8 バイト列をデコード可能と判定することを検証する。"""
    assert decodes_allowing_truncation("日本語".encode(), "utf-8") is True


def test_decodes_utf8_truncated_mid_character() -> None:
    """末尾でマルチバイト文字が途切れていてもデコード可能と判定することを検証する。"""
    chunk = "あ".encode()[:2]
    assert decodes_allowing_truncation(b"abc" + chunk, "utf-8") is True


def test_rejects_invalid_bytes() -> None:
    """末尾以外に不正なバイトを含む場合はデコード不可と判定することを検証する。"""
    assert decodes_allowing_truncation(b"\xff\xfeabc", "utf-8") is False


def test_patched_ingest_reads_file_split_at_chunk_boundary(tmp_path: Path) -> None:
    """チャンク境界でマルチバイト文字が分断されるファイルを本文として読めることを検証する。"""
    text = "a" * (CHUNK_SIZE - 1) + "あいう\n"
    (tmp_path / "sample.md").write_text(text, encoding="utf-8")

    apply_gitingest_patch()
    _, _, content = ingest(str(tmp_path))

    assert "[Binary file]" not in content
    assert "あいう" in content


def test_main_excludes_lock_files_and_writes_timestamped_digest() -> None:
    """main が除外パターンと日時付きの出力先で gitingest を呼び出すことを検証する。"""
    with patch("scripts.ingest.ingest") as mock_ingest:
        main()
    mock_ingest.assert_called_once()
    args, kwargs = mock_ingest.call_args
    assert args == (".",)
    assert kwargs["exclude_patterns"] == {"uv.lock", ".python-version"}
    assert kwargs["output"].startswith("digest_")
    assert kwargs["output"].endswith(".txt")

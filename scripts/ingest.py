"""開発環境の全体像をファイル出力する
-> Taskfile.yamlそのままでは日付取得(date, Get-Date)にOS間表記ゆれがあるため"""

import codecs
import datetime

import gitingest.schemas.filesystem
from gitingest import ingest
from gitingest.utils.file_utils import _get_preferred_encodings


def decodes_allowing_truncation(chunk: bytes, encoding: str) -> bool:
    """末尾で途切れたマルチバイト文字を許容してデコード可否を判定する。

    gitingest 0.3.1 はファイル先頭 1024 バイトを厳密にデコードしてテキスト判定するため、
    境界でマルチバイト文字が分断されると UTF-8 のファイルを "[Binary file]" と誤判定する。

    Args:
        chunk: ファイル先頭から読み出したバイト列。
        encoding: 判定に用いるエンコーディング名。

    Returns:
        末尾の未完了シーケンスを除きデコードできる場合 True。
    """
    try:
        codecs.getincrementaldecoder(encoding)().decode(chunk, final=False)
    except UnicodeDecodeError:
        return False
    return True


def preferred_encodings_utf8_first() -> list[str]:
    """UTF-8 を最優先にしたデコード候補を返す。

    gitingest 0.3.1 はロケールのエンコーディング (日本語 Windows では cp932) を最優先するため、
    UTF-8 の日本語が偶然 cp932 として解釈でき、読み込みエラーや文字化けを起こす。

    Returns:
        先頭を UTF-8 とし、以降に gitingest 既定の候補を続けたエンコーディング名のリスト。
    """
    return list(dict.fromkeys(["utf-8", *_get_preferred_encodings()]))


def apply_gitingest_patch() -> None:
    """gitingest のテキスト判定とエンコーディング優先順位を差し替える。"""
    gitingest.schemas.filesystem._decodes = decodes_allowing_truncation
    gitingest.schemas.filesystem._get_preferred_encodings = preferred_encodings_utf8_first


def main() -> None:
    """gitingest でリポジトリのダイジェストを日時付きファイルに出力する。"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"digest_{timestamp}.txt"

    apply_gitingest_patch()
    ingest(".", exclude_patterns={"uv.lock", ".python-version"}, output=filename)

    print("-" * 20)
    print(f"Created {filename}")
    print("-" * 20)


if __name__ == "__main__":
    main()

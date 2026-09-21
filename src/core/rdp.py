"""RDP 疎通確認モジュール。"""

import socket


def check_rdp(host: str, port: int = 3389, timeout: float = 3.0) -> bool:
    """TCP 接続で RDP 疎通を確認する。

    Args:
        host: 接続先ホスト名または IP アドレス。
        port: RDP ポート番号。デフォルトは 3389。
        timeout: 接続タイムアウト秒数。デフォルトは 3.0。

    Returns:
        接続成功時 True、タイムアウト・拒否時 False。
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


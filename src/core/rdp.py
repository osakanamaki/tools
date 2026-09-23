"""RDP 疎通確認モジュール。"""

import asyncio
import contextlib

RDP_PORT = 3389
"""RDP の標準 TCP ポート番号。"""


async def check_rdp(host: str, port: int = RDP_PORT, timeout: float = 3.0) -> bool:
    """TCP 接続で RDP 疎通を非同期に確認する。

    Args:
        host: 接続先ホスト名または IP アドレス。
        port: RDP ポート番号。デフォルトは RDP_PORT (3389)。
        timeout: 接続タイムアウト秒数。デフォルトは 3.0。

    Returns:
        接続成功時 True、タイムアウト・拒否時 False。
    """
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    except OSError:
        # TimeoutError も OSError のサブクラス
        return False

    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return True

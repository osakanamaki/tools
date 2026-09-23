"""Wake-on-LAN Magic Packet 送信モジュール。"""

import re
import socket


def send_magic_packet(
    mac_address: str,
    broadcast_address: str = "255.255.255.255",
    port: int = 9,
) -> None:
    """Magic Packet を生成して UDP ブロードキャストで送信する。

    Args:
        mac_address: 対象の MAC アドレス。"AA:BB:CC:DD:EE:FF" または "AA-BB-CC-DD-EE-FF" 形式。
        broadcast_address: ブロードキャストアドレス。デフォルトは "255.255.255.255"。
        port: 送信先 UDP ポート番号。デフォルトは 9。

    Raises:
        ValueError: MAC アドレスの形式が不正な場合。
    """
    normalized = mac_address.upper().replace("-", ":")
    if not re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", normalized):
        raise ValueError(f"不正な MAC アドレス形式: {mac_address!r}")

    mac_bytes = bytes.fromhex(normalized.replace(":", ""))
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_address, port))

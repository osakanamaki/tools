"""wol モジュールのテスト。"""

import socket
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from src.core.wol import send_magic_packet

EXPECTED_PACKET = b"\xff" * 6 + bytes.fromhex("AABBCCDDEEFF") * 16


@pytest.fixture
def mock_sock() -> Iterator[MagicMock]:
    """送信に使われるソケットのモックを提供する。"""
    with patch("src.core.wol.socket.socket") as mock_cls:
        sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = sock
        yield sock


def test_magic_packet_bytes_are_correct(mock_sock: MagicMock) -> None:
    """送信する Magic Packet のバイト列が正しいことを検証する。"""
    send_magic_packet("AA:BB:CC:DD:EE:FF")
    sent_data, _ = mock_sock.sendto.call_args[0]
    assert sent_data == EXPECTED_PACKET


def test_broadcast_address_and_port_are_passed(mock_sock: MagicMock) -> None:
    """指定したブロードキャストアドレスとポートが使われることを検証する。"""
    send_magic_packet("AA:BB:CC:DD:EE:FF", broadcast_address="192.168.1.255", port=7)
    _, addr = mock_sock.sendto.call_args[0]
    assert addr == ("192.168.1.255", 7)


def test_so_broadcast_option_is_set(mock_sock: MagicMock) -> None:
    """SO_BROADCAST ソケットオプションが設定されることを検証する。"""
    send_magic_packet("AA:BB:CC:DD:EE:FF")
    mock_sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)


def test_mac_with_hyphen_separator_is_accepted(mock_sock: MagicMock) -> None:
    """ハイフン区切りの MAC アドレスも受け付けることを検証する。"""
    send_magic_packet("AA-BB-CC-DD-EE-FF")
    sent_data, _ = mock_sock.sendto.call_args[0]
    assert sent_data == EXPECTED_PACKET


def test_mac_with_lowercase_is_accepted(mock_sock: MagicMock) -> None:
    """小文字 MAC アドレスも受け付けることを検証する。"""
    send_magic_packet("aa:bb:cc:dd:ee:ff")
    sent_data, _ = mock_sock.sendto.call_args[0]
    assert sent_data == EXPECTED_PACKET


def test_invalid_mac_raises_value_error() -> None:
    """不正な MAC アドレスで ValueError が発生することを検証する。"""
    with pytest.raises(ValueError):
        send_magic_packet("not-a-mac-address")


def test_too_short_mac_raises_value_error() -> None:
    """短すぎる MAC アドレスで ValueError が発生することを検証する。"""
    with pytest.raises(ValueError):
        send_magic_packet("AA:BB:CC:DD:EE")

"""wol モジュールのテスト。"""

import socket
from unittest.mock import MagicMock, patch

import pytest

from src.core.wol import send_magic_packet


def test_magic_packet_bytes_are_correct() -> None:
    """送信する Magic Packet のバイト列が正しいことを検証する。"""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")
    expected = b"\xff" * 6 + mac_bytes * 16

    with patch("src.core.wol.socket.socket") as mock_cls:
        mock_sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_sock
        send_magic_packet(mac)
        sent_data, _ = mock_sock.sendto.call_args[0]
        assert sent_data == expected


def test_broadcast_address_and_port_are_passed() -> None:
    """指定したブロードキャストアドレスとポートが使われることを検証する。"""
    with patch("src.core.wol.socket.socket") as mock_cls:
        mock_sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_sock
        send_magic_packet("AA:BB:CC:DD:EE:FF", broadcast_address="192.168.1.255", port=7)
        _, addr = mock_sock.sendto.call_args[0]
        assert addr == ("192.168.1.255", 7)


def test_so_broadcast_option_is_set() -> None:
    """SO_BROADCAST ソケットオプションが設定されることを検証する。"""
    with patch("src.core.wol.socket.socket") as mock_cls:
        mock_sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_sock
        send_magic_packet("AA:BB:CC:DD:EE:FF")
        mock_sock.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )


def test_mac_with_hyphen_separator_is_accepted() -> None:
    """ハイフン区切りの MAC アドレスも受け付けることを検証する。"""
    mac = "AA-BB-CC-DD-EE-FF"
    mac_bytes = bytes.fromhex("AABBCCDDEEFF")
    expected = b"\xff" * 6 + mac_bytes * 16

    with patch("src.core.wol.socket.socket") as mock_cls:
        mock_sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_sock
        send_magic_packet(mac)
        sent_data, _ = mock_sock.sendto.call_args[0]
        assert sent_data == expected


def test_mac_with_lowercase_is_accepted() -> None:
    """小文字 MAC アドレスも受け付けることを検証する。"""
    mac = "aa:bb:cc:dd:ee:ff"
    mac_bytes = bytes.fromhex("aabbccddeeff")
    expected = b"\xff" * 6 + mac_bytes * 16

    with patch("src.core.wol.socket.socket") as mock_cls:
        mock_sock = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_sock
        send_magic_packet(mac)
        sent_data, _ = mock_sock.sendto.call_args[0]
        assert sent_data == expected


def test_invalid_mac_raises_value_error() -> None:
    """不正な MAC アドレスで ValueError が発生することを検証する。"""
    with pytest.raises(ValueError):
        send_magic_packet("not-a-mac-address")


def test_too_short_mac_raises_value_error() -> None:
    """短すぎる MAC アドレスで ValueError が発生することを検証する。"""
    with pytest.raises(ValueError):
        send_magic_packet("AA:BB:CC:DD:EE")


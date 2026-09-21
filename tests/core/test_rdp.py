"""rdp モジュールのテスト。"""

from unittest.mock import MagicMock, patch

from src.core.rdp import check_rdp


def test_rdp_returns_true_when_connected() -> None:
    """接続成功時に True を返すことを検証する。"""
    with patch("src.core.rdp.socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        result = check_rdp("192.168.1.100")
        assert result is True


def test_rdp_returns_false_on_timeout() -> None:
    """タイムアウト時に False を返すことを検証する。"""
    with patch("src.core.rdp.socket.create_connection") as mock_conn:
        mock_conn.side_effect = TimeoutError
        result = check_rdp("192.168.1.100")
        assert result is False


def test_rdp_returns_false_on_connection_refused() -> None:
    """接続拒否時に False を返すことを検証する。"""
    with patch("src.core.rdp.socket.create_connection") as mock_conn:
        mock_conn.side_effect = OSError
        result = check_rdp("192.168.1.100")
        assert result is False


def test_rdp_passes_custom_port_and_timeout() -> None:
    """カスタムポートとタイムアウトが正しく渡されることを検証する。"""
    with patch("src.core.rdp.socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        check_rdp("192.168.1.100", port=3390, timeout=5.0)
        mock_conn.assert_called_once_with(("192.168.1.100", 3390), timeout=5.0)


def test_rdp_uses_default_port_3389() -> None:
    """デフォルトポートが 3389 であることを検証する。"""
    with patch("src.core.rdp.socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        check_rdp("192.168.1.100")
        mock_conn.assert_called_once_with(("192.168.1.100", 3389), timeout=3.0)


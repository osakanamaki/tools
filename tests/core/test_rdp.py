"""rdp モジュールのテスト。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rdp import RDP_PORT, check_rdp


def _mock_connection() -> tuple[MagicMock, MagicMock]:
    """open_connection の戻り値 (reader, writer) を生成する。"""
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    return MagicMock(), writer


@pytest.mark.asyncio
async def test_rdp_returns_true_when_connected() -> None:
    """接続成功時に True を返し、接続を閉じることを検証する。"""
    reader, writer = _mock_connection()
    with patch("src.core.rdp.asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        result = await check_rdp("192.168.1.100")
    assert result is True
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_rdp_returns_false_on_timeout() -> None:
    """タイムアウト時に False を返すことを検証する。"""
    with patch("src.core.rdp.asyncio.open_connection", AsyncMock(side_effect=TimeoutError)):
        result = await check_rdp("192.168.1.100")
    assert result is False


@pytest.mark.asyncio
async def test_rdp_returns_false_when_wait_for_times_out() -> None:
    """接続が応答しないまま timeout を超えた場合に False を返すことを検証する。"""

    async def _hang(*_args: object) -> None:
        await asyncio.sleep(10)

    with patch("src.core.rdp.asyncio.open_connection", _hang):
        result = await check_rdp("192.168.1.100", timeout=0.01)
    assert result is False


@pytest.mark.asyncio
async def test_rdp_returns_false_on_connection_refused() -> None:
    """接続拒否時に False を返すことを検証する。"""
    with patch("src.core.rdp.asyncio.open_connection", AsyncMock(side_effect=ConnectionRefusedError)):
        result = await check_rdp("192.168.1.100")
    assert result is False


@pytest.mark.asyncio
async def test_rdp_ignores_error_on_close() -> None:
    """接続成功後のクローズ時エラーは無視して True を返すことを検証する。"""
    reader, writer = _mock_connection()
    writer.wait_closed.side_effect = ConnectionResetError
    with patch("src.core.rdp.asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        result = await check_rdp("192.168.1.100")
    assert result is True


@pytest.mark.asyncio
async def test_rdp_passes_custom_port_and_timeout() -> None:
    """カスタムポートとタイムアウトが正しく渡されることを検証する。"""
    mock_conn = AsyncMock(return_value=_mock_connection())
    with (
        patch("src.core.rdp.asyncio.open_connection", mock_conn),
        patch("src.core.rdp.asyncio.wait_for", wraps=asyncio.wait_for) as mock_wait,
    ):
        await check_rdp("192.168.1.100", port=3390, timeout=5.0)
    mock_conn.assert_called_once_with("192.168.1.100", 3390)
    assert mock_wait.call_args.kwargs["timeout"] == 5.0


@pytest.mark.asyncio
async def test_rdp_uses_default_port_3389() -> None:
    """デフォルトポートが RDP_PORT (3389) であることを検証する。"""
    mock_conn = AsyncMock(return_value=_mock_connection())
    with patch("src.core.rdp.asyncio.open_connection", mock_conn):
        await check_rdp("192.168.1.100")
    assert RDP_PORT == 3389
    mock_conn.assert_called_once_with("192.168.1.100", RDP_PORT)

"""Magic Packet 送信 / RDP 疎通確認ツール"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def imports():
    """共通モジュールの読み込み"""
    import os

    import marimo as mo

    return mo, os


@app.cell
def page_header():
    """ページ上部のヘッダー"""
    from src.components.header import header

    header(
        title="🔌 Magic Packet / RDP 疎通確認",
        description="対象 PC を Wake-on-LAN で起動し、RDP で接続可能になったかを確認します。",
    )
    return


@app.cell
def wol_inputs(mo, os):
    """Wake-on-LAN 用の UI 入力フォーム"""
    mac_input = mo.ui.text(
        label="MACアドレス",
        placeholder="AA:BB:CC:DD:EE:FF",
        value=os.getenv("WOL_MAC_ADDRESS", ""),
    )
    broadcast_input = mo.ui.text(
        label="ブロードキャストアドレス",
        placeholder="255.255.255.255",
        value=os.getenv("WOL_BROADCAST_ADDRESS", "255.255.255.255"),
    )
    wol_button = mo.ui.run_button(label="Magic Packet 送信")
    return broadcast_input, mac_input, wol_button


@app.cell
def wol_execution(broadcast_input, mac_input, mo, wol_button):
    """Magic Packet の送信処理"""
    from src.core.wol import send_magic_packet

    wol_result = mo.md("")
    if wol_button.value:
        try:
            send_magic_packet(mac_input.value, broadcast_input.value)
            wol_result = mo.callout(mo.md("✅ Magic Packet を送信しました"), kind="success")
        except ValueError as e:
            wol_result = mo.callout(mo.md(f"❌ エラー: {e}"), kind="danger")
        except OSError as e:
            wol_result = mo.callout(mo.md(f"❌ 送信失敗: {e}"), kind="danger")
    return (wol_result,)


@app.cell
def wol_view(broadcast_input, mac_input, mo, wol_button, wol_result):
    """Wake-on-LAN セクションの表示"""
    mo.vstack(
        [
            mo.md("## ⚡ Wake-on-LAN"),
            mac_input,
            broadcast_input,
            wol_button,
            wol_result,
        ]
    )
    return


@app.cell
def rdp_inputs(mo, os):
    """RDP 疎通確認用の UI 入力フォーム"""
    rdp_host_input = mo.ui.text(
        label="ホスト名 / IPアドレス",
        placeholder="192.168.1.100",
        value=os.getenv("RDP_HOST", ""),
    )
    rdp_refresh = mo.ui.refresh(
        label="RDP 疎通確認",
        options=["5s", "10s", "30s"],
        default_interval="30s",
    )
    return rdp_host_input, rdp_refresh


@app.cell
def rdp_view(mo, rdp_host_input, rdp_refresh, rdp_result):
    """RDP 疎通確認セクションの表示"""
    mo.vstack(
        [
            mo.md("## 🖥️ RDP 疎通確認"),
            rdp_host_input,
            rdp_refresh,
            rdp_result,
        ]
    )
    return


@app.cell
async def rdp_execution(mo, rdp_host_input, rdp_refresh):
    """RDP ポートへの疎通確認処理"""
    from datetime import datetime

    from src.core.rdp import RDP_PORT, check_rdp

    rdp_refresh
    host = rdp_host_input.value.strip()
    if not host:
        rdp_result = mo.callout(mo.md("ホスト名 / IPアドレスを入力してください"), kind="neutral")
    else:
        with mo.status.spinner(title=f"{host} に接続確認中…"):
            ok = await check_rdp(host)
        checked_at = datetime.now().strftime("%H:%M:%S")
        if ok:
            rdp_result = mo.callout(mo.md(f"✅ RDP 応答あり (TCP {RDP_PORT}) — {checked_at}"), kind="success")
        else:
            rdp_result = mo.callout(mo.md(f"❌ RDP 応答なし (TCP {RDP_PORT}) — {checked_at}"), kind="danger")
    return (rdp_result,)


if __name__ == "__main__":
    app.run()

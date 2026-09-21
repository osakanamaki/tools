"""Magic Packet 送信 / RDP 疎通確認ツール。"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import os

    import marimo as mo

    return mo, os


@app.cell
def _(mo, os):
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
def _(broadcast_input, mac_input, mo, wol_button):
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

    mo.vstack(
        [
            mo.md("## 🔌 Wake-on-LAN"),
            mac_input,
            broadcast_input,
            wol_button,
            wol_result,
        ]
    )
    return


@app.cell
def _(mo, os):
    rdp_host_input = mo.ui.text(
        label="ホスト名 / IPアドレス",
        placeholder="192.168.1.100",
        value=os.getenv("RDP_HOST", ""),
    )
    rdp_button = mo.ui.run_button(label="RDP 疎通確認")
    return rdp_button, rdp_host_input


@app.cell
def _(mo, rdp_button, rdp_host_input):
    from src.core.rdp import check_rdp

    rdp_result = mo.md("")
    if rdp_button.value:
        ok = check_rdp(rdp_host_input.value)
        if ok:
            rdp_result = mo.callout(mo.md("✅ RDP 応答あり (TCP 3389)"), kind="success")
        else:
            rdp_result = mo.callout(mo.md("❌ RDP 応答なし (TCP 3389)"), kind="danger")

    mo.vstack(
        [
            mo.md("## 🖥️ RDP 疎通確認"),
            rdp_host_input,
            rdp_button,
            rdp_result,
        ]
    )
    return


if __name__ == "__main__":
    app.run()

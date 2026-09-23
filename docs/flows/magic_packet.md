# magic_packet フロー図

`task flow` による自動生成ファイルです。手動で編集しないでください。ソース: `src/apps/magic_packet.py`

```mermaid
flowchart TD
  c0["imports<br/>共通モジュールの読み込み"]
  c1(["page_header<br/>ページ上部のヘッダー"])
  f0[["header()<br/>背景色付き（グラデーション）のヘッダーを生成する。"]]
  subgraph c2["wol_inputs — Wake-on-LAN 用の UI 入力フォーム"]
    c2_u0[/"mac_input: text「MACアドレス」"/]
    c2_u1[/"broadcast_input: text「ブロードキャストアドレス」"/]
    c2_u2[/"wol_button: run_button「Magic Packet 送信」"/]
  end
  c3["wol_execution<br/>Magic Packet の送信処理"]
  f1[["send_magic_packet()<br/>Magic Packet を生成して UDP ブロードキャストで送信する。"]]
  c4(["wol_view<br/>Wake-on-LAN セクションの表示"])
  subgraph c5["rdp_inputs — RDP 疎通確認用の UI 入力フォーム"]
    c5_u0[/"rdp_host_input: text「ホスト名 / IPアドレス」"/]
    c5_u1[/"rdp_refresh: refresh「RDP 疎通確認」"/]
  end
  c6(["rdp_view<br/>RDP 疎通確認セクションの表示"])
  c7["⏳ rdp_execution<br/>RDP ポートへの疎通確認処理"]
  f2[["check_rdp()<br/>TCP 接続で RDP 疎通を非同期に確認する。"]]
  c2_u1 --> c3
  c2_u0 --> c3
  c2_u2 --> c3
  c2_u1 --> c4
  c2_u0 --> c4
  c2_u2 --> c4
  c3 -->|"wol_result"| c4
  c5_u0 --> c6
  c5_u1 --> c6
  c7 -->|"rdp_result"| c6
  c5_u0 --> c7
  c5_u1 --> c7
  c1 -.-> f0
  c3 -.-> f1
  c7 -.-> f2
```

## 凡例

| 形 | 意味 |
|---|---|
| 四角 | 処理を行うセル |
| 角丸 (スタジアム形) | 何も定義せず画面表示だけを行うセル |
| 枠 (サブグラフ) | UI 要素を定義するセル |
| 平行四辺形 | UI 要素 (`mo.ui.*`) |
| 二重枠 | プロジェクト内の関数・クラスの呼び出し (点線) |
| ⏳ | async セル |
| 実線の矢印 | 変数の受け渡し (ラベルは変数名) |

## 検査結果

指摘なし

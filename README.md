# README

* 環境構築: `uv sync`
* アーキテクチャ: `pyproject.toml` を参照すること
* やれること: `Taskfile.yaml` を参照すること

## `.env` について

記述例

```ini
# Magic Packet 送信先 MAC アドレスの初期値
WOL_MAC_ADDRESS=AA:BB:CC:DD:EE:FF

# ブロードキャストアドレスの初期値
WOL_BROADCAST_ADDRESS=192.168.1.255

# RDP 疎通確認先ホストの初期値
RDP_HOST=192.168.1.100
```

## 開発

* `src/core` -> ロジックを記述する。
* `src/apps` -> GUIを記述する。core機能を注入する。
* ドキュメント
  * **What / How**: ソースコード上Docstring
  * **Why / Context**: `docs/adr_*.md`
  * **必要な環境変数**: `README.md`
* AIエージェントによるテスト開発駆動
  * AIは、RED確認後にその内容を `git add` する。その後は `git add` も `git commit` も使用しない。
  * レビュアー(人間)がstageをもとにRED->Refactoringを評価する。
  * レビュアー(人間)が`git commit`を行う。

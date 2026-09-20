# README

* 環境構築: `uv sync`
* アーキテクチャ: `pyproject.toml` を参照すること
* やれること: `Taskfile.yaml` を参照すること

## `.env` について

|環境変数名|記載例|内容|
|---|---|---|
|MAGIC_PACKET_DEST_MAC|`MAGIC_PACKET_DEST_MAC=00:1A:2B:3C:4D:5E`|マジックパケット宛先MACアドレスの初期値|

## 開発

* `src/core` -> ロジックを記述する。
* `src/apps` -> GUIを記述する。core機能を注入する。
* **ドキュメント**
  * 仕様はソースコード冒頭に記載する。
  * 必要な環境変数は本READMEに記載する。
* **AIエージェントによるテスト開発駆動**
  * AIは、RED確認後にその内容を `git add` する。その後は `git add` も `git commit` も使用しない。
  * レビュアー(人間)がstageをもとにRED->Refactoringを評価する。
  * レビュアー(人間)が`git commit`を行う。

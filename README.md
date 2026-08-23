# SAPPORO CENTRAL INFO Ver.2.1

札幌市中央区の飲食店「開店・閉店」とイベントを自動収集し、
毎朝09:00 JSTにLINEへ通知する構成です。

## ファイル

- `index.html` : 閲覧画面（`data/items.json` を自動で読み込んで表示）
- `collector.py` : 自動収集＋重複除外＋LINE通知
- `data/items.json` : 収集済みデータの永続ストア（ワークフローが自動更新）
- `.github/workflows/daily.yml` : 毎朝09:00 JSTの自動実行
- `LINE_SETUP.md` : LINE設定手順

## 動作

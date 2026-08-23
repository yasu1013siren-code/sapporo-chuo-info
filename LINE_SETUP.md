# LINE通知セットアップ

## 必要なもの

LINE DevelopersでMessaging APIチャネルを作成し、LINE公式アカウントを自分のLINEで友だち追加します。

GitHub Actionsには次の2つをSecretsとして登録します。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO_USER_ID`

### LINE_TO_USER_ID

自分自身のユーザーIDはLINE Developers Consoleのチャネル基本設定にある「あなたのユーザーID」で確認できます。

### LINE_CHANNEL_ACCESS_TOKEN

Messaging APIのチャネルアクセストークンを発行して登録します。

## GitHubへの登録

Repository:
Settings → Secrets and variables → Actions → New repository secret

以下を登録:

`LINE_CHANNEL_ACCESS_TOKEN`
→ LINEのチャネルアクセストークン

`LINE_TO_USER_ID`
→ 自分のLINE user ID

## 実行時間

GitHub ActionsのcronはUTCです。

`0 0 * * *`

なので、日本時間では毎日09:00です。

GitHub Actionsの仕様上、実行時刻には多少の遅延が発生する場合があります。

## 手動テスト

Actions → Sapporo Chuo Info - 09:00 JST → Run workflow

これでその場で収集・LINE送信できます。

## LINEの仕様上の注意

Push messageはLINE Messaging APIの `/v2/bot/message/push` を使用します。
送信先はユーザーIDで指定します。

アクセストークンは絶対にHTMLやGitHubリポジトリへ直接書かず、GitHub Secretsに入れてください。

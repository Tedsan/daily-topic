# Slack Bot OAuth Scopes

## 必要なスコープ

Daily topicシステムで必要なSlack Bot OAuth Scopesを以下に定義します。

### 基本スコープ

| スコープ            | 説明                                   | 用途                                               |
| ------------------- | -------------------------------------- | -------------------------------------------------- |
| `channels:history`  | 公開チャネルのメッセージ履歴を読み取り | #rss-feed チャネルから過去24時間のメッセージを取得 |
| `channels:read`     | 公開チャネルの基本情報を読み取り       | チャネル情報の取得                                 |
| `chat:write`        | メッセージの投稿                       | #daily-topic チャネルに要約を投稿                  |
| `chat:write.public` | 公開チャネルへのメッセージ投稿         | Bot招待なしでの投稿                                |

### 追加スコープ（Phase 2で検討）

| スコープ         | 説明                     | 用途                                  |
| ---------------- | ------------------------ | ------------------------------------- |
| `commands`       | スラッシュコマンドの実行 | `/daily_topic rerun` 手動実行コマンド |
| `files:read`     | ファイルの読み取り       | 添付ファイルがある場合の処理          |
| `reactions:read` | リアクションの読み取り   | 記事の評価分析（将来機能）            |

## 実装時の注意点

### Bot Token vs User Token

- **Bot Token**: メッセージの投稿に使用
- **User Token**: 履歴の読み取りに使用（必要に応じて）

### チャネルアクセス

- `channels:history` は公開チャネルの履歴読み取りに必要
- Bot が対象チャネルに招待されている必要がある
- `chat:write.public` があれば招待なしで投稿可能

### レート制限

- Slack API は 1秒間に1メッセージの制限
- bulk投稿時は適切な間隔を設ける必要がある

## 設定手順

### 1. Slack App作成

1. [Slack API](https://api.slack.com/apps) にアクセス
2. "Create New App" をクリック
3. "From scratch" を選択
4. App名とworkspaceを設定

### 2. OAuth Scopesの設定

1. "OAuth & Permissions" ページに移動
2. "Bot Token Scopes" セクションで以下を追加:
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `chat:write.public`

### 3. インストール

1. "Install App" をクリック
2. ワークスペースへのインストールを承認
3. Bot User OAuth Access Token を取得

### 4. 環境変数設定

```bash
# .env ファイルに設定
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here  # Socket Mode用（必要に応じて）
```

## チャネル設定

### 必要なチャネル

1. **#rss-feed** (RSS取得用)

   - Bot を招待
   - RSS フィードがここに投稿される

2. **#daily-topic** (投稿用)
   - Bot を招待
   - 要約がここに投稿される

### Bot招待コマンド

```
/invite @daily-topic-bot
```

## セキュリティ考慮事項

### Token管理

- Bot Token は GitHub Secrets に保存
- 本番環境では環境変数として設定
- 定期的なローテーション（90日）を実施

### スコープ最小化

- 必要最小限のスコープのみ付与
- 機能追加時に段階的にスコープを追加
- 定期的なスコープ監査

## トラブルシューティング

### よくあるエラー

1. **missing_scope**: 必要なスコープが不足

   ```json
   {
     "error": "missing_scope",
     "needed": "channels:history",
     "provided": "channels:read"
   }
   ```

2. **not_in_channel**: Bot がチャネルに招待されていない
   ```json
   {
     "error": "not_in_channel"
   }
   ```

### 対処方法

1. スコープ不足 → OAuth設定を確認し、必要なスコープを追加
2. チャネルアクセス不可 → Bot をチャネルに招待
3. レート制限 → 適切な間隔での API 呼び出し

## 参考資料

- [Slack API OAuth Scopes](https://api.slack.com/scopes)
- [Slack Bot Token Types](https://api.slack.com/concepts/token-types)
- [Slack Rate Limits](https://api.slack.com/docs/rate-limits)

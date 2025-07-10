# Daily Topic システム

[![Daily Topic Summary](https://github.com/Tedsan/daily-topic/actions/workflows/daily-topic.yml/badge.svg)](https://github.com/Tedsan/daily-topic/actions/workflows/daily-topic.yml)
[![CI](https://github.com/Tedsan/daily-topic/actions/workflows/ci.yml/badge.svg)](https://github.com/Tedsan/daily-topic/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Poetry](https://img.shields.io/badge/poetry-dependency--manager-blue.svg)](https://python-poetry.org/)

SlackのRSSフィードから記事を取得し、Claude Code SDKを使って要約を生成してSlackに投稿するシステムです。

## 概要

このシステムは以下の処理を自動で実行します：

1. **RSS取得**: Slackチャネル「#rss-feed」から過去24時間のメッセージからURLを抽出
2. **本文抽出**: 各URLをfetchしてMarkdown形式に変換
3. **カテゴリ分類**: 記事をC1-C6のカテゴリに分類
4. **要約生成**: Claude Code SDKで500文字以内の要約を生成
5. **Slack投稿**: 「#daily-topic」チャネルにBlock Kitで投稿

## 実行時刻

毎日 **08:00 JST** (GitHub Actions: 23:00 UTC) に自動実行されます。

## セットアップ

### 本番環境（GitHub Actions）

1. **リポジトリをクローン**またはフォークしてGitHubアカウントに追加

2. **GitHub Secrets設定**

   - リポジトリの **Settings** > **Secrets and variables** > **Actions**
   - 以下のSecretsを追加：

     ```bash
     SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
     ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
     ```

3. **自動実行の有効化**
   - **Actions** タブで **Daily Topic Summary** ワークフローを有効化
   - 毎日08:00 JST（23:00 UTC）に自動実行されます

### 開発環境

1. **依存関係のインストール**

```bash
# Poetry を使用（推奨）
poetry install

# または pip
pip install -r requirements.txt
```

2. **環境変数の設定**

```bash
# .env ファイルを作成
cp .env.example .env

# 必要な環境変数を設定
# SLACK_BOT_TOKEN=xoxb-...
# ANTHROPIC_API_KEY=sk-...
```

3. **開発環境の準備**

```bash
# 開発用依存関係のインストール
make dev

# pre-commit フックの設定
pre-commit install
```

## 使い方

### 基本的な実行

```bash
# メインプログラムを実行
make run

# または
python src/main.py
```

### テストの実行

```bash
# 全テストを実行
make test

# ユニットテストのみ
make test-unit

# 統合テストのみ
make test-integration

# E2Eテストのみ
make test-e2e
```

### コード品質チェック

```bash
# Lint実行
make lint

# フォーマット
make format

# 型チェック
make type-check
```

## 必要な環境変数

| 変数名                  | 説明                        | 必須 |
| ----------------------- | --------------------------- | ---- |
| `SLACK_BOT_TOKEN`       | Slack Bot Token             | ✓    |
| `ANTHROPIC_API_KEY`     | Claude API Key              | ✓    |
| `RSS_FEED_CHANNEL`      | RSS取得チャネル             | ✓    |
| `DAILY_TOPIC_CHANNEL`   | 投稿先チャネル              | ✓    |
| `AWS_ACCESS_KEY_ID`     | AWS Access Key (統計保存用) | -    |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Key (統計保存用) | -    |
| `S3_BUCKET_NAME`        | S3バケット名 (統計保存用)   | -    |

## Slack Bot 設定

### 必要な OAuth Scopes

- `channels:history` - チャネル履歴の読み取り
- `channels:read` - チャネル情報の読み取り
- `chat:write` - メッセージの投稿
- `chat:write.public` - 公開チャネルへの投稿

詳細は [docs/slack-oauth-scopes.md](docs/slack-oauth-scopes.md) を参照してください。

### チャネル設定

1. **#rss-feed** チャネルにBotを招待
2. **#daily-topic** チャネルにBotを招待

```bash
/invite @daily-topic-bot
```

## 記事カテゴリ

| ID  | カテゴリ                 | 代表キーワード                                                                         |
| --- | ------------------------ | -------------------------------------------------------------------------------------- |
| C1  | Software-Defined Vehicle | SDV, AUTOSAR, Adaptive AUTOSAR, 車載ソフト                                             |
| C2  | Industrial IoT & Edge    | Industrial IoT, IIoT, スマートファクトリー, Edge Computing                             |
| C3  | Industrial Protocols     | MQTT, OPC UA, OPC UA FX, open62541, TSN, openPLC                                       |
| C4  | Generative AI Tech       | Gemini CLI, Gemini 1.5, Claude 3, Claude Code, OpenAI, Anthropic, Mistral AI, DeepMind |
| C5  | Gen-AI Use Cases         | 生成AI 活用事例, LLM ユースケース, RAG, AI agent, 導入事例, Case Study                 |
| C6  | Other                    | 上記いずれにも当てはまらない場合                                                       |

## 手動実行

### GitHub Actionsでの手動実行

1. GitHubリポジトリの **Actions** タブにアクセス
2. **Daily Topic Summary** ワークフローを選択
3. **Run workflow** ボタンをクリック
4. オプションでパラメータを指定：
   - **カテゴリ**: 対象カテゴリ（C1-C6 or All）
   - **時間範囲**: 過去何時間のメッセージを取得するか（デフォルト: 24時間）

### ローカルでの手動実行

```bash
# 基本実行
make run

# または環境変数を指定して実行
LOOKBACK_HOURS=12 python src/main.py
```

## 技術仕様

- **言語**: Python 3.12
- **依存関係管理**: Poetry
- **テスト**: pytest + coverage
- **Lint**: ruff, black, isort, mypy
- **CI/CD**: GitHub Actions
- **デプロイ**: 23:00 UTC (08:00 JST) スケジュール実行

## 制限事項

- **処理時間**: End-to-End ≤ 5分（GitHub Actions制限）
- **Slack API**: 1秒間に1メッセージ
- **要約長**: 500文字以内
- **カバレッジ**: ユニット80%以上、統合70%以上

## 統計・監視

- 処理統計は `stats/` ディレクトリに保存
- 月次コスト集計は `stats/{yyyy-mm}.csv` に記録
- S3へのバックアップ（設定時）

## 開発ガイドライン

詳細な開発情報は [CLAUDE.md](CLAUDE.md) を参照してください。

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。

## 注意事項

- API使用量とコストを定期的に監視することを推奨します
- GitHub ActionsのSecretsに機密情報を適切に設定してください

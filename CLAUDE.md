# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

このリポジトリは、SlackのRSSフィードから記事を取得し、Claude Code SDKを使って要約を生成してSlackに投稿するDaily Topicシステムです。GitHub Actionsによる完全自動化された本番システムです。

## 主要な開発コマンド

### Poetry環境セットアップ

```bash
# 開発環境のセットアップ（推奨）
make dev

# 本番環境のインストール
make install
```

### テスト実行

```bash
# 全テスト実行（カバレッジ付き）
make test

# 特定のテストタイプ
make test-unit           # ユニットテストのみ
make test-integration    # 統合テストのみ
make test-e2e           # E2Eテストのみ

# 単一テストファイル
poetry run pytest tests/unit/test_specific.py -v

# 特定のテスト関数
poetry run pytest tests/unit/test_file.py::test_function_name -v
```

### コード品質

```bash
# Lint + 型チェック
make quality

# 個別実行
make lint          # ruff + flake8
make format        # black + isort + ruff --fix
make type-check    # mypy
```

### システム実行

```bash
# ローカル実行
make run

# GitHub Actions環境変数での実行
GITHUB_ACTIONS=true TARGET_CATEGORY=C4 LOOKBACK_HOURS=12 make run
```

## システムアーキテクチャ

### 処理フロー（7ステップ）

1. **RSS取得** (`slack/rss_fetcher.py`): #rss-feedチャネルから過去24時間のURLを抽出
2. **コンテンツ処理** (`content/fetcher.py`, `content/parser.py`): URL→HTML→Markdown変換
3. **カテゴリ分類** (`content/categorizer.py`): C1-C6カテゴリに分類、C6は別途処理
4. **要約生成** (`summarizer/`): Claude Code SDKで500文字要約生成
5. **レポート作成** (`models.py`): DailyTopicReportオブジェクト作成
6. **Slack投稿** (`slack/message_poster.py`): Block Kit形式で#daily-topicに投稿
7. **統計保存** (`stats/`): トークン使用量・コストをCSV/JSON保存

### 主要コンポーネント

#### データフロー

- **エントリーポイント**: `src/main.py::DailyTopicProcessor.process_daily_topic()`
- **設定管理**: `src/config.py` (Pydantic v2 + 環境変数)
- **データモデル**: `src/models.py` (Pydantic v2, カテゴリ定義含む)

#### 外部API統合

- **Claude Code SDK**: `summarizer/claude_client.py` (非同期、エラーハンドリング付き)
- **Slack Web API**: `slack/client.py` (レート制限1sec/msg対応)
- **コンテンツ取得**: `content/fetcher.py` (aiohttp、リトライ機能)

#### GitHub Actions統合

- **自動実行**: 毎日23:00 UTC (08:00 JST)、5分タイムアウト
- **手動実行**: workflow_dispatch（カテゴリ・時間範囲指定可能）
- **環境変数**: `GITHUB_ACTIONS=true`で検出、パラメータ取得

### 記事カテゴリシステム

C1-C6の6カテゴリで分類、各カテゴリは独立して処理：

- **C1-C5**: 要約生成対象（Claude Code SDK使用）
- **C6 (Other)**: URL一覧のみSlack投稿、要約なし

重要な実装パターン：

```python
# カテゴリ分類後の分岐処理
categorized_articles, other_articles = await self._step_categorize_articles(articles)
# C6は別途other_articlesとして処理される
```

## 重要な実装要件

### Claude Code SDK統合

- **バージョン**: 1.0以上必須
- **モデル指定**: 環境変数経由（`ANTHROPIC_MODEL`）のみ対応
- **エラーハンドリング**: レスポンスのusage情報がNone対応済み
- **プロンプト構造**: システム+ユーザープロンプト、3000文字制限

### テスト・モック戦略

- **外部API**: responsesライブラリでモック
- **時刻固定**: freezegunでJST 08:00固定
- **Claude API**: `mock_claude()`で固定レスポンス、課金回避
- **Slack投稿**: payload.jsonでアサート
- **カバレッジ**: ユニット80%以上、統合70%以上

### GitHub Actions運用

- **Secrets管理**: `SLACK_BOT_TOKEN`, `ANTHROPIC_API_KEY`必須
- **失敗時Slack通知**: ワークフロー失敗時に自動通知
- **アーティファクト**: stats/ディレクトリを30日保持
- **CI/CD**: プッシュ時自動テスト・Lint実行

### セキュリティ要件

- **機密情報**: .envファイルは.gitignoreで除外済み
- **API制限**: Slack 1秒1メッセージ、Claude APIレート制限対応
- **エラー情報**: スタックトレース含む詳細ログをSlack通知

### 性能・制約

- **処理時間**: GitHub Actions 5分制限
- **メモリ効率**: 大量記事処理時のメモリ管理
- **非同期処理**: aiohttp + asyncio活用
- **統計管理**: 日次・月次CSV + リアルタイムJSON

## 開発時の注意点

### モデル変更の影響

- `src/models.py`のPydantic v2モデル変更時はテスト更新必須
- カテゴリ追加時は`CATEGORY_INFO`とテストケース更新

### Claude Code SDK制限事項

- `ClaudeCodeOptions`ではモデル指定不可
- 環境変数`ANTHROPIC_MODEL`での指定のみ
- レスポンス構造の変更に注意（usage情報の有無）

### GitHub Actions対応

- ローカル開発時は`GITHUB_ACTIONS`環境変数をfalseに
- 手動実行パラメータは`TARGET_CATEGORY`, `LOOKBACK_HOURS`で制御
- ワークフロー修正時は.github/workflows/の両ファイル同期

### 統計・ログ管理

- stats/ディレクトリは.gitignoreで除外
- 月次集計ファイルは上書きされる設計
- エラー時のSlack通知は無限ループ防止済み

# テスト実行手順

## 概要

このプロジェクトは pytest を使用してテストを実行します。
モック戦略により、外部APIへの課金を回避しながら高品質なテストを実現しています。

## テスト実行

### 全テストの実行

```bash
# 全テストを実行（カバレッジ付き）
pytest --cov=src

# または make コマンド
make test
```

### 個別テストの実行

```bash
# ユニットテストのみ
pytest tests/unit/

# 統合テストのみ
pytest tests/integration/

# E2Eテストのみ
pytest tests/e2e/

# 特定のファイル
pytest tests/unit/test_slack/test_client.py

# 特定のテスト関数
pytest tests/unit/test_slack/test_client.py::test_fetch_rss_messages
```

### 詳細出力

```bash
# 詳細な出力
pytest -v

# 失敗したテストのみ表示
pytest --tb=short

# 最初の失敗で停止
pytest -x
```

## テストカバレッジ

### カバレッジ基準

- **ユニットテスト**: 80%以上
- **統合テスト**: 70%以上
- **E2Eテスト**: 主要シナリオ網羅（全カテゴリ1件ずつ）

### カバレッジレポート

```bash
# HTMLレポート生成
pytest --cov=src --cov-report=html

# レポートを開く
open htmlcov/index.html
```

## モック戦略

### 1. Claude API

```python
# fixtures/prompt_samples/ にプロンプト例を配置
# mock_claude() フィクスチャで固定文字列を返す
def test_summary_generation(mock_claude_client):
    # トークン課金を回避
    result = generate_summary("テスト記事")
    assert len(result) <= 500
```

### 2. Slack API

```python
# chat_postMessage をスタブ化
# payload.json をアサートで検証
def test_slack_posting(mock_slack_client):
    response = post_to_slack(message)
    mock_slack_client.chat_postMessage.assert_called_once()
```

### 3. HTTP通信

```python
# responses ライブラリでスタブ化
@responses.activate
def test_fetch_article():
    responses.add(
        responses.GET,
        "https://example.com/article",
        body="<html>...</html>",
        status=200
    )
```

### 4. 時刻固定

```python
# freezegun で JST 08:00 に固定
@freeze_time("2025-07-09 08:00:00")
def test_scheduled_execution():
    # タイムゾーン依存バグを防止
    pass
```

## テストディレクトリ構造

```
tests/
├── unit/                    # 純粋ユニットテスト
│   ├── test_slack/         # Slack関連
│   ├── test_content/       # コンテンツ処理
│   ├── test_summarizer/    # 要約生成
│   └── test_utils/         # ユーティリティ
├── integration/            # 外部API モック統合テスト
│   ├── test_slack_integration.py
│   ├── test_content_integration.py
│   └── test_summarizer_integration.py
├── e2e/                    # エンドツーエンドテスト
│   └── test_daily_topic_pipeline.py
├── fixtures/               # テストデータ
│   ├── sample_articles.json
│   └── sample_responses.json
├── prompt_samples/         # プロンプト例
│   ├── categorization.txt
│   └── summarization.txt
├── conftest.py             # 共通フィクスチャ
└── README.md               # このファイル
```

## CI統合

GitHub Actions の `test` ジョブで以下を実行：

1. **Lint**: `ruff check .`
2. **Unit + Integration**: `pytest tests/unit/ tests/integration/`
3. **Coverage**: `pytest --cov=src --cov-fail-under=80`
4. **E2E**: `pytest tests/e2e/` (環境変数設定時のみ)

## ローカル開発

### 環境変数設定

```bash
# .env.example をコピー
cp .env.example .env

# 必要な環境変数を設定
# SLACK_BOT_TOKEN=xoxb-...
# ANTHROPIC_API_KEY=sk-...
```

### 依存関係インストール

```bash
# Poetry を使用
poetry install

# または pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### pre-commit設定

```bash
# pre-commit フックをインストール
pre-commit install

# 手動実行
pre-commit run --all-files
```

## トラブルシューティング

### よくある問題

1. **インポートエラー**: `PYTHONPATH` が設定されていない

   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **モックが効かない**: `responses.activate` デコレータを忘れていない

   ```python
   @responses.activate
   def test_http_request():
       # ...
   ```

3. **時刻関連のテストが失敗**: `freeze_time` デコレータを使用
   ```python
   @freeze_time("2025-07-09 08:00:00")
   def test_time_dependent():
       # ...
   ```

### デバッグ

```bash
# pytest のデバッグモード
pytest --pdb

# 標準出力を表示
pytest -s

# ログレベルを設定
pytest --log-cli-level=DEBUG
```

## 参考資料

- [pytest公式ドキュメント](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [responses](https://github.com/getsentry/responses)
- [freezegun](https://github.com/spulec/freezegun)

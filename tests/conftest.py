"""共通テスト設定とフィクスチャ"""
import os
from collections.abc import Generator
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest
import responses
from freezegun import freeze_time

# テスト用の固定時刻（JST 08:00）
TEST_DATETIME = datetime(2025, 7, 9, 8, 0, 0)


@pytest.fixture
def mock_env_vars() -> Generator[dict[str, str], None, None]:
    """テスト用環境変数を設定"""
    test_env = {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "RSS_FEED_CHANNEL": "rss-feed",
        "DAILY_TOPIC_CHANNEL": "daily-topic",
        "AWS_ACCESS_KEY_ID": "test-aws-key",
        "AWS_SECRET_ACCESS_KEY": "test-aws-secret",
        "AWS_REGION": "us-east-1",
        "S3_BUCKET_NAME": "test-bucket",
    }

    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.getenv(key)
        os.environ[key] = value

    yield test_env

    # 環境変数を元に戻す
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_slack_client() -> Mock:
    """モックSlackクライアント"""
    client = Mock()
    client.conversations_history.return_value = {
        "ok": True,
        "messages": [
            {
                "type": "message",
                "text": "新しい記事: https://example.com/article1",
                "ts": "1625097600.000100",
                "user": "U1234567890",
            },
            {
                "type": "message",
                "text": "参考になる記事: https://example.com/article2",
                "ts": "1625184000.000200",
                "user": "U1234567891",
            },
        ],
    }
    client.chat_postMessage.return_value = {"ok": True, "ts": "1625270400.000300"}
    return client


@pytest.fixture
def mock_claude_client() -> Mock:
    """モックClaude APIクライアント"""
    client = Mock()
    client.messages.create.return_value = Mock(
        content=[
            Mock(
                type="text",
                text="これは要約されたテキストです。500文字以内で記事の要点をまとめています。",
            )
        ],
        usage=Mock(input_tokens=100, output_tokens=50),
    )
    return client


@pytest.fixture
def frozen_time() -> Generator[None, None, None]:
    """時刻をJST 08:00に固定"""
    with freeze_time(TEST_DATETIME):
        yield


@pytest.fixture
def mock_responses() -> Generator[responses.RequestsMock, None, None]:
    """HTTPリクエストをモック"""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def sample_article_html() -> str:
    """テスト用記事HTML"""
    return """
    <html>
    <head>
        <title>テスト記事タイトル</title>
        <meta name="description" content="テスト記事の説明">
    </head>
    <body>
        <article>
            <h1>テスト記事タイトル</h1>
            <p>これはテスト用の記事内容です。</p>
            <p>複数の段落があります。</p>
            <blockquote>
                <p>重要な引用文がここにあります。</p>
            </blockquote>
            <p>記事の結論部分です。</p>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_article_markdown() -> str:
    """テスト用記事Markdown"""
    return """# テスト記事タイトル

これはテスト用の記事内容です。

複数の段落があります。

> 重要な引用文がここにあります。

記事の結論部分です。"""


@pytest.fixture
def sample_categories() -> dict[str, Any]:
    """テスト用カテゴリデータ"""
    return {
        "C1": {
            "label": "Software-Defined Vehicle",
            "keywords": ["SDV", "AUTOSAR", "Adaptive AUTOSAR", "車載ソフト"],
        },
        "C2": {
            "label": "Industrial IoT & Edge",
            "keywords": ["Industrial IoT", "IIoT", "スマートファクトリー", "Edge Computing"],
        },
        "C3": {
            "label": "Industrial Protocols",
            "keywords": ["MQTT", "OPC UA", "OPC UA FX", "open62541", "TSN", "openPLC"],
        },
        "C4": {
            "label": "Generative AI Tech",
            "keywords": [
                "Gemini CLI",
                "Gemini 1.5",
                "Claude 3",
                "Claude Code",
                "OpenAI",
                "Anthropic",
                "Mistral AI",
                "DeepMind",
            ],
        },
        "C5": {
            "label": "Gen-AI Use Cases",
            "keywords": [
                "生成AI 活用事例",
                "LLM ユースケース",
                "RAG",
                "AI agent",
                "導入事例",
                "Case Study",
            ],
        },
        "C6": {
            "label": "Other",
            "keywords": ["その他"],
        },
    }


@pytest.fixture
def sample_rss_messages() -> list:
    """テスト用RSSメッセージ"""
    return [
        {
            "type": "message",
            "text": "新しい記事: https://example.com/sdv-article",
            "ts": "1625097600.000100",
            "user": "U1234567890",
        },
        {
            "type": "message",
            "text": "IoT記事: https://example.com/iot-article",
            "ts": "1625184000.000200",
            "user": "U1234567891",
        },
        {
            "type": "message",
            "text": "AI記事: https://example.com/ai-article",
            "ts": "1625270400.000300",
            "user": "U1234567892",
        },
    ]


@pytest.fixture
def sample_token_stats() -> dict[str, Any]:
    """テスト用トークン統計"""
    return {
        "summary_id": "test-summary-001",
        "generated_at": "2025-07-09T08:00:00Z",
        "tokens_used": 150,
        "cost_usd": 0.0025,
        "model": "claude-3-sonnet-20240229",
        "article_count": 3,
    }

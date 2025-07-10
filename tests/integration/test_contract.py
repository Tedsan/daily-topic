"""Contract Test - 実API疎通確認"""
import os

import pytest

from src.config import get_config
from src.slack.client import SlackClient
from src.summarizer.claude_client import ClaudeClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Contract testは実APIを使用するため、環境変数が必要
pytestmark = pytest.mark.skipif(
    not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("ANTHROPIC_API_KEY"),
    reason="Contract test requires actual API tokens",
)


class TestClaudeContract:
    """Claude API Contract Test"""

    def test_claude_api_connection(self):
        """Claude APIの基本接続テスト"""
        config = get_config()

        # 実際のAPIキーを使用
        claude_client = ClaudeClient()

        # 接続テスト
        assert claude_client.test_connection(), "Claude API connection failed"

        logger.info("Claude API contract test passed")

    def test_claude_summary_generation(self):
        """Claude API要約生成テスト"""
        claude_client = ClaudeClient()

        # テスト用のコンテンツ
        test_content = """
        # Software-Defined Vehicle (SDV) の最新動向

        近年、自動車業界ではSoftware-Defined Vehicle（SDV）という概念が注目を集めています。
        SDVは、ソフトウェアによって車両の機能や性能を定義し、制御する新しいアプローチです。

        ## 主要な特徴

        1. **ソフトウェア中心の設計**: 従来のハードウェア中心から、ソフトウェア中心の設計へ
        2. **Over-the-Air (OTA) 更新**: 遠隔からのソフトウェア更新が可能
        3. **AUTOSAR Adaptive Platform**: 次世代車載ソフトウェアプラットフォーム
        4. **セキュリティ**: 車載システムのセキュリティ強化

        ## 技術的な課題

        - リアルタイム処理の要求
        - 機能安全（ISO 26262）への対応
        - サイバーセキュリティの確保
        - 従来システムとの互換性

        これらの技術により、自動車の価値創出の方法が根本的に変わることが期待されています。
        """

        # 要約生成テスト
        result = claude_client.generate_summary(content=test_content, category="C1")

        # 基本的な検証
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "category" in result, "Result should contain category"
        assert "summary" in result, "Result should contain summary"
        assert "usage" in result, "Result should contain usage information"

        assert (
            result["category"] == "C1"
        ), f"Expected category C1, got {result['category']}"
        assert (
            len(result["summary"]) <= 500
        ), f"Summary too long: {len(result['summary'])} characters"
        assert len(result["summary"]) > 0, "Summary should not be empty"

        # 使用量情報の検証
        usage = result["usage"]
        assert "input_tokens" in usage, "Usage should contain input_tokens"
        assert "output_tokens" in usage, "Usage should contain output_tokens"
        assert "cost_usd" in usage, "Usage should contain cost_usd"

        assert usage["input_tokens"] > 0, "Input tokens should be greater than 0"
        assert usage["output_tokens"] > 0, "Output tokens should be greater than 0"
        assert usage["cost_usd"] > 0, "Cost should be greater than 0"

        logger.info(
            f"Claude summary generation test passed: {result['category']}, {len(result['summary'])} chars, ${usage['cost_usd']:.4f}"
        )


class TestSlackContract:
    """Slack API Contract Test"""

    def test_slack_api_connection(self):
        """Slack APIの基本接続テスト"""
        config = get_config()

        # 実際のBot tokenを使用
        slack_client = SlackClient()

        # 接続テスト
        assert slack_client.test_connection(), "Slack API connection failed"

        logger.info("Slack API contract test passed")

    def test_slack_channel_access(self):
        """Slackチャネルアクセステスト"""
        config = get_config()
        slack_client = SlackClient()

        # テスト用チャネルの確認
        test_channels = [
            config.slack.rss_feed_channel,
            config.slack.daily_topic_channel,
        ]

        for channel in test_channels:
            channel_id = slack_client.get_channel_id(channel)
            assert (
                channel_id is not None
            ), f"Channel #{channel} not found or not accessible"

            logger.info(f"Channel access test passed: #{channel} -> {channel_id}")

    def test_slack_message_posting(self):
        """Slackメッセージ投稿テスト"""
        config = get_config()
        slack_client = SlackClient()

        # テスト用メッセージ
        test_message = "🧪 Contract Test: Daily Topic システムの疎通確認"

        # 投稿テスト
        response = slack_client.post_message(
            channel=config.slack.daily_topic_channel, text=test_message
        )

        assert response["ok"] is True, "Message posting failed"
        assert "ts" in response, "Response should contain timestamp"

        logger.info(f"Message posting test passed: {response['ts']}")


class TestIntegrationContract:
    """統合Contract Test"""

    def test_end_to_end_basic_flow(self):
        """基本的なエンドツーエンド疎通テスト"""
        config = get_config()

        # 各コンポーネントの初期化
        claude_client = ClaudeClient()
        slack_client = SlackClient()

        # 1. Claude API疎通確認
        claude_test_result = claude_client.test_connection()
        assert claude_test_result, "Claude API connection failed"

        # 2. Slack API疎通確認
        slack_test_result = slack_client.test_connection()
        assert slack_test_result, "Slack API connection failed"

        # 3. 簡単な要約生成テスト
        test_content = "This is a test article about generative AI technology."
        summary_result = claude_client.generate_summary(
            content=test_content, category="C4"
        )

        assert summary_result["category"] == "C4", "Summary generation failed"
        assert len(summary_result["summary"]) > 0, "Summary should not be empty"

        # 4. テスト結果をSlackに投稿
        test_message = f"""
🧪 **Contract Test Results**

✅ Claude API: Connected
✅ Slack API: Connected
✅ Summary Generation: Working
- Category: {summary_result['category']}
- Summary Length: {len(summary_result['summary'])} characters
- Tokens Used: {summary_result['usage']['input_tokens']} + {summary_result['usage']['output_tokens']}
- Cost: ${summary_result['usage']['cost_usd']:.4f}

Contract test completed successfully! 🎉
        """

        post_result = slack_client.post_message(
            channel=config.slack.daily_topic_channel, text=test_message
        )

        assert post_result["ok"] is True, "Test result posting failed"

        logger.info("End-to-end contract test passed")

    def test_api_version_compatibility(self):
        """API バージョン互換性テスト"""
        config = get_config()

        # Claude API バージョン確認
        claude_client = ClaudeClient()
        assert claude_client.model == config.claude.model, "Claude model mismatch"

        # Slack API バージョン確認（基本的な機能が動作するか）
        slack_client = SlackClient()

        # auth.test で基本情報を取得
        auth_response = slack_client._call_api_with_retry("auth_test")
        assert "user" in auth_response, "Slack auth test failed"
        assert "team" in auth_response, "Slack auth test failed"

        logger.info(
            f"API version compatibility test passed - Claude: {claude_client.model}, Slack: {auth_response['user']}@{auth_response['team']}"
        )


# pytest実行時のヘルパー
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

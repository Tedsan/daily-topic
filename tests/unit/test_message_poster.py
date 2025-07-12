"""MessagePosterのテスト"""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl

from src.models import ArticleMetadata
from src.slack.message_poster import MessagePoster
from src.utils.error_handler import SlackAPIError


class TestMessagePoster:
    """MessagePosterクラスのテスト"""

    @pytest.fixture
    def mock_slack_client(self) -> MagicMock:
        """モックSlackクライアント"""
        mock_client = MagicMock()
        mock_client.post_message.return_value = {"ts": "1234567890.123456", "ok": True}
        return mock_client

    @pytest.fixture
    def message_poster(self, mock_slack_client: MagicMock) -> MessagePoster:
        """MessagePosterインスタンス"""
        return MessagePoster(slack_client=mock_slack_client)

    @pytest.fixture
    def sample_categorized_articles(self) -> dict:
        return {
            "C1": [
                ArticleMetadata(
                    article_url=HttpUrl("https://example.com/c1-1"),
                    title="SDV関連記事1",
                    content="Software-Defined Vehicleに関する記事です。" * 20,
                    category="C1",
                ),
                ArticleMetadata(
                    article_url=HttpUrl("https://example.com/c1-2"),
                    title="AUTOSAR Adaptive記事",
                    content="AUTOSAR Adaptiveプラットフォームについて。" * 20,
                    category="C1",
                ),
            ],
            "C4": [
                ArticleMetadata(
                    article_url=HttpUrl("https://example.com/c4-1"),
                    title="Claude 3.5の新機能について",
                    content="Claude 3.5の最新機能について説明します。" * 20,
                    category="C4",
                )
            ],
        }

    @pytest.fixture
    def sample_other_articles(self) -> list:
        return [
            ArticleMetadata(
                article_url=HttpUrl("https://example.com/other-1"),
                title="その他の技術記事",
                content="カテゴリに分類されない技術記事です。" * 20,
                category="C6",
            )
        ]

    def test_post_url_list_success(
        self,
        message_poster,
        mock_slack_client,
        sample_categorized_articles,
        sample_other_articles,
    ):
        """URLリスト投稿の成功テスト"""
        # 実行
        result = message_poster.post_url_list(
            sample_categorized_articles, sample_other_articles
        )

        # 検証
        assert result == {"ts": "1234567890.123456", "ok": True}
        mock_slack_client.post_message.assert_called_once()

        # 呼び出し引数の検証
        call_args = mock_slack_client.post_message.call_args
        assert call_args[1]["channel"] == "#daily-topic"
        assert call_args[1]["text"] == "📋 RSS-feedから取得したURL一覧"

        # ブロック構造の基本検証
        blocks = call_args[1]["blocks"]
        assert len(blocks) > 0
        assert blocks[0]["type"] == "header"
        assert "📋 RSS-feedから取得したURL一覧" in blocks[0]["text"]["text"]

    def test_post_url_list_without_other_articles(
        self, message_poster, mock_slack_client, sample_categorized_articles
    ):
        """OtherカテゴリなしでのURLリスト投稿テスト"""
        # 実行
        result = message_poster.post_url_list(sample_categorized_articles)

        # 検証
        assert result == {"ts": "1234567890.123456", "ok": True}
        mock_slack_client.post_message.assert_called_once()

    def test_post_url_list_empty_categories(self, message_poster, mock_slack_client):
        """空のカテゴリでのURLリスト投稿テスト"""
        # 実行
        result = message_poster.post_url_list({})

        # 検証
        assert result == {"ts": "1234567890.123456", "ok": True}

        # ブロック構造の検証
        call_args = mock_slack_client.post_message.call_args
        blocks = call_args[1]["blocks"]

        # ヘッダーとフッターのみ存在することを確認
        assert any(block["type"] == "header" for block in blocks)
        assert any(block["type"] == "context" for block in blocks)

    def test_create_url_list_blocks_structure(
        self, message_poster, sample_categorized_articles, sample_other_articles
    ):
        """URLリストブロック構造のテスト"""
        # 実行
        blocks = message_poster._create_url_list_blocks(
            sample_categorized_articles, sample_other_articles
        )

        # 検証
        assert len(blocks) > 0

        # ヘッダーブロックの確認
        header_block = blocks[0]
        assert header_block["type"] == "header"
        assert "📋 RSS-feedから取得したURL一覧" in header_block["text"]["text"]

        # フッターブロック（統計情報）の確認
        footer_block = blocks[-1]
        assert footer_block["type"] == "context"
        assert "📊 総URL数:" in footer_block["elements"][0]["text"]

    def test_create_url_list_blocks_categories(
        self, message_poster, sample_categorized_articles
    ):
        """カテゴリ情報の正しい表示テスト"""
        # 実行
        blocks = message_poster._create_url_list_blocks(sample_categorized_articles)

        # C1カテゴリの確認
        c1_blocks = [block for block in blocks if "C1:" in str(block)]
        assert len(c1_blocks) > 0

        # C4カテゴリの確認
        c4_blocks = [block for block in blocks if "C4:" in str(block)]
        assert len(c4_blocks) > 0

    def test_create_url_list_blocks_url_format(
        self, message_poster, sample_categorized_articles
    ):
        """URL表示形式のテスト"""
        # 実行
        blocks = message_poster._create_url_list_blocks(sample_categorized_articles)

        # URLを含むブロックを検索
        url_blocks = [
            block
            for block in blocks
            if block.get("type") == "section"
            and block.get("text", {}).get("text", "").startswith("• <")
        ]

        assert len(url_blocks) > 0

        # URL形式の確認（例: • <URL|タイトル> (カテゴリ)）
        for block in url_blocks:
            text = block["text"]["text"]
            lines = text.split("\n")
            for line in lines:
                if line.startswith("• <"):
                    assert "|" in line  # タイトルが含まれている
                    assert ">" in line  # URLが閉じられている
                    assert "(" in line and ")" in line  # カテゴリIDが含まれている

    def test_truncate_url_list_blocks(self, message_poster):
        """URLリストブロック短縮のテスト"""
        # 長いブロックリストを作成
        long_blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "ヘッダー"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "説明"}},
            {"type": "divider"},
        ]

        # 多数の詳細ブロックを追加
        for i in range(20):
            long_blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"詳細{i}"}}
            )

        # フッター
        long_blocks.extend(
            [
                {"type": "divider"},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": "統計"}]},
            ]
        )

        # 実行
        truncated = message_poster._truncate_url_list_blocks(long_blocks)

        # 検証
        assert len(truncated) < len(long_blocks)
        assert truncated[0]["type"] == "header"  # ヘッダー保持
        assert truncated[-1]["type"] == "context"  # フッター保持

        # 短縮メッセージの確認
        warning_blocks = [
            block for block in truncated if "⚠️ URL一覧が長すぎるため" in str(block)
        ]
        assert len(warning_blocks) > 0

    def test_post_url_list_payload_too_large(self, message_poster, mock_slack_client):
        """ペイロードサイズ超過時の短縮テスト"""
        # 非常に大きなデータを作成
        large_categorized_articles = {}
        for category in ["C1", "C2", "C3", "C4", "C5"]:
            large_categorized_articles[category] = []
            for i in range(100):  # 各カテゴリに100記事
                large_categorized_articles[category].append(
                    ArticleMetadata(
                        article_url=HttpUrl(f"https://example.com/{category}-{i}"),
                        title="非常に長いタイトル" * 10,  # 長いタイトル
                        content="コンテンツ" * 100,
                        category=category,
                    )
                )

        # 実行
        result = message_poster.post_url_list(large_categorized_articles)

        # 検証
        assert result == {"ts": "1234567890.123456", "ok": True}
        mock_slack_client.post_message.assert_called_once()

    def test_post_url_list_slack_api_error(
        self, message_poster, mock_slack_client, sample_categorized_articles
    ):
        """Slack API エラー時のテスト"""
        # Slack APIエラーをシミュレート
        mock_slack_client.post_message.side_effect = Exception("Slack API Error")

        # 実行と検証
        with pytest.raises(SlackAPIError, match="Failed to post URL list"):
            message_poster.post_url_list(sample_categorized_articles)

    @patch("src.slack.message_poster.logger")
    def test_post_url_list_logging(
        self,
        mock_logger,
        message_poster,
        mock_slack_client,
        sample_categorized_articles,
    ):
        """ログ出力のテスト"""
        # 実行
        message_poster.post_url_list(sample_categorized_articles)

        # ログ出力の確認
        mock_logger.info.assert_any_call("Posting URL list to Slack")
        mock_logger.info.assert_any_call(
            "URL list posted successfully: 1234567890.123456"
        )

    def test_total_url_count_calculation(
        self, message_poster, sample_categorized_articles, sample_other_articles
    ):
        """総URL数計算のテスト"""
        # 実行
        blocks = message_poster._create_url_list_blocks(
            sample_categorized_articles, sample_other_articles
        )

        # フッターブロックから総URL数を取得
        footer_block = blocks[-1]
        footer_text = footer_block["elements"][0]["text"]

        # 期待される総数（C1: 2記事 + C4: 1記事 + Other: 1記事 = 4記事）
        assert "📊 総URL数: 4件" in footer_text

    def test_title_truncation(self, message_poster):
        """タイトル短縮のテスト"""
        # 長いタイトルの記事を作成
        long_title_articles = {
            "C1": [
                ArticleMetadata(
                    article_url=HttpUrl("https://example.com/long-title"),
                    title="これは非常に長いタイトルです。" * 10,  # 50文字を超える
                    content="コンテンツ" * 50,
                    category="C1",
                )
            ]
        }

        # 実行
        blocks = message_poster._create_url_list_blocks(long_title_articles)

        # タイトル短縮の確認
        url_blocks = [
            block
            for block in blocks
            if block.get("type") == "section" and "• <" in str(block)
        ]

        assert len(url_blocks) > 0

        # "..." が含まれていることを確認（タイトルが短縮されている）
        for block in url_blocks:
            text = block["text"]["text"]
            if "これは非常に長い" in text:
                assert "..." in text

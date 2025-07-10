"""RSS取得機能"""
import re
from typing import Optional
from urllib.parse import urlparse

from src.config import get_config
from src.models import SlackMessage
from src.slack.client import SlackClient
from src.utils.error_handler import SlackAPIError
from src.utils.logger import get_logger
from src.utils.time_utils import (
    datetime_to_slack_timestamp,
    get_lookback_time,
    is_within_lookback_period,
)

logger = get_logger(__name__)


class RSSFetcher:
    """RSS取得クラス"""

    def __init__(self, slack_client: Optional[SlackClient] = None):
        self.config = get_config()
        self.slack_client = slack_client or SlackClient()

        # URL抽出用の正規表現パターン
        # Slackの <https://example.com|title> 形式と通常のURLに対応
        self.url_patterns = [
            # Slack形式: <https://example.com|title> または <https://example.com>
            r"<(https?://[^>|]+)(?:\|[^>]*)?>",
            # 通常のURL形式
            r'https?://[^\s<>"\'\]\)\}]+',
            # markdown形式: [title](https://example.com)
            r"\[([^\]]*)\]\((https?://[^\)]+)\)",
        ]

        # 除外するドメイン（内部リンクなど）
        self.excluded_domains = {
            "slack.com",
            "localhost",
            "127.0.0.1",
            "192.168.",
            "10.",
            "172.",
        }

        logger.info("RSS fetcher initialized")

    def _is_valid_url(self, url: str) -> bool:
        """URLが有効かどうか判定"""
        try:
            parsed = urlparse(url)

            # スキームとホストが必要
            if not parsed.scheme or not parsed.netloc:
                return False

            # HTTPSまたはHTTPのみ
            if parsed.scheme not in ["http", "https"]:
                return False

            # 除外ドメインチェック
            for excluded in self.excluded_domains:
                if excluded in parsed.netloc:
                    return False

            return True

        except Exception:
            return False

    def extract_urls_from_text(self, text: str) -> set[str]:
        """テキストからURLを抽出"""
        urls = set()

        for pattern in self.url_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                url = None

                if pattern.startswith(r"\["):
                    # markdown形式の場合、グループ2がURL
                    if match.lastindex and match.lastindex >= 2:
                        url = match.group(2)
                elif pattern.startswith(r"<"):
                    # Slack形式の場合、グループ1がURL
                    if match.lastindex and match.lastindex >= 1:
                        url = match.group(1)
                else:
                    # 通常のURL形式の場合、マッチ全体がURL
                    url = match.group(0)

                if url:
                    # URLの正規化
                    url = url.strip()

                    # 有効性チェック
                    if self._is_valid_url(url):
                        urls.add(url)
                        logger.debug(f"Extracted URL: {url}")

        return urls

    def fetch_rss_messages(
        self, channel: Optional[str] = None, lookback_hours: Optional[int] = None
    ) -> list[SlackMessage]:
        """RSSフィードチャネルからメッセージを取得"""
        try:
            # デフォルトはrss-feedチャネル
            channel = channel or f"#{self.config.slack.rss_feed_channel}"

            # 過去の指定時間分を取得
            if lookback_hours:
                from datetime import timedelta

                from src.utils.time_utils import now_jst

                lookback_time = now_jst() - timedelta(hours=lookback_hours)
            else:
                lookback_time = get_lookback_time()

            oldest_ts = datetime_to_slack_timestamp(lookback_time)

            logger.info(
                f"Fetching messages from {channel} since {lookback_time.strftime('%Y-%m-%d %H:%M:%S JST')}"
            )

            # メッセージ取得
            messages = self.slack_client.get_channel_history(
                channel=channel, oldest=oldest_ts, limit=200  # 十分な数を取得
            )

            # 時間範囲内のメッセージのみフィルタ
            filtered_messages = [
                msg for msg in messages if is_within_lookback_period(msg.ts)
            ]

            logger.info(
                f"Retrieved {len(filtered_messages)} messages within lookback period "
                f"(total: {len(messages)})"
            )

            return filtered_messages

        except Exception as e:
            logger.error(f"Error fetching RSS messages: {e}")
            raise SlackAPIError(f"Failed to fetch RSS messages: {e}")

    def extract_urls_from_messages(self, messages: list[SlackMessage]) -> list[str]:
        """メッセージリストからURLを抽出"""
        all_urls = set()

        for message in messages:
            urls = self.extract_urls_from_text(message.text)
            all_urls.update(urls)

            if urls:
                logger.debug(f"Message {message.ts}: extracted {len(urls)} URLs")

        # リストに変換（順序保持のため）
        url_list = list(all_urls)

        logger.info(f"Total unique URLs extracted: {len(url_list)}")

        # 想定件数の確認（要件: ±10%）
        expected_count = self.config.system.max_articles_per_category * 6  # 6カテゴリ
        if url_list:
            deviation = abs(len(url_list) - expected_count) / expected_count
            if deviation > 0.1:  # 10%超過
                logger.warning(
                    f"URL count deviation: {deviation:.1%} "
                    f"(expected: ~{expected_count}, actual: {len(url_list)})"
                )

        return url_list

    def fetch_rss_urls(
        self, channel: Optional[str] = None, lookback_hours: Optional[int] = None
    ) -> list[str]:
        """RSSフィードからURLを取得（メイン機能）"""
        try:
            logger.info("Starting RSS URL extraction")

            # メッセージ取得
            messages = self.fetch_rss_messages(channel, lookback_hours)

            if not messages:
                logger.warning("No messages found in RSS feed channel")
                return []

            # URL抽出
            urls = self.extract_urls_from_messages(messages)

            logger.info(f"RSS URL extraction completed: {len(urls)} URLs found")
            return urls

        except Exception as e:
            logger.error(f"RSS URL extraction failed: {e}")
            raise

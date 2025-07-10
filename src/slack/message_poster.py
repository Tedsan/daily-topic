"""Slack投稿機能"""
import json
from typing import Optional

from src.config import get_config
from src.models import DailyTopicReport, SlackBlockKitMessage, SummaryLog
from src.slack.client import SlackClient
from src.utils.error_handler import SlackAPIError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MessagePoster:
    """Slack投稿クラス"""

    def __init__(self, slack_client: Optional[SlackClient] = None):
        self.config = get_config()
        self.slack_client = slack_client or SlackClient()

        # Block Kit制限
        self.max_payload_size = 4000  # 4KB制限
        self.max_blocks_per_message = 50  # Block数制限

        logger.info("Message poster initialized")

    def post_daily_report(self, report: DailyTopicReport) -> dict:
        """日次レポートをSlackに投稿"""
        try:
            logger.info(f"Posting daily report with {len(report.summaries)} summaries")

            # Block Kitメッセージを作成
            block_kit_message = SlackBlockKitMessage.create_daily_report(report)

            # ペイロード長対策
            if self._is_payload_too_large(block_kit_message):
                logger.warning("Payload too large, splitting into multiple messages")
                return self._post_split_messages(report)

            # 通常の投稿
            channel = self.config.slack.daily_topic_channel
            if not channel.startswith("#"):
                channel = f"#{channel}"

            response = self.slack_client.post_message(
                channel=channel,
                text=block_kit_message.text,
                blocks=block_kit_message.blocks,
            )

            logger.info(f"Daily report posted successfully: {response.get('ts')}")
            return response

        except Exception as e:
            logger.error(f"Error posting daily report: {e}")
            raise SlackAPIError(f"Failed to post daily report: {e}")

    def post_error_message(
        self,
        error_message: str,
        job_id: Optional[str] = None,
        step: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> dict:
        """エラーメッセージをSlackに投稿"""
        try:
            logger.info(f"Posting error message: {error_message}")

            # エラーメッセージのBlock Kitを作成
            blocks = self._create_error_blocks(error_message, job_id, step, stack_trace)

            # エラーメッセージは通常サイズを超えないが、念のためチェック
            if len(json.dumps(blocks)) > self.max_payload_size:
                # スタックトレースを短縮
                if stack_trace:
                    stack_trace = stack_trace[:500] + "..."
                blocks = self._create_error_blocks(
                    error_message, job_id, step, stack_trace
                )

            channel = self.config.slack.daily_topic_channel
            if not channel.startswith("#"):
                channel = f"#{channel}"

            response = self.slack_client.post_message(
                channel=channel,
                text=f"❌ Daily Topic Error: {error_message}",
                blocks=blocks,
            )

            logger.info(f"Error message posted successfully: {response.get('ts')}")
            return response

        except Exception as e:
            logger.error(f"Error posting error message: {e}")
            raise SlackAPIError(f"Failed to post error message: {e}")

    def _is_payload_too_large(self, message: SlackBlockKitMessage) -> bool:
        """ペイロードサイズが制限を超えているかチェック"""
        payload_size = len(json.dumps(message.blocks))
        block_count = len(message.blocks)

        if payload_size > self.max_payload_size:
            logger.warning(
                f"Payload size too large: {payload_size} bytes > {self.max_payload_size}"
            )
            return True

        if block_count > self.max_blocks_per_message:
            logger.warning(
                f"Too many blocks: {block_count} > {self.max_blocks_per_message}"
            )
            return True

        return False

    def _post_split_messages(self, report: DailyTopicReport) -> list[dict]:
        """レポートを分割して投稿"""
        responses = []

        # ヘッダーメッセージ
        header_blocks = self._create_header_blocks(report)
        responses.append(self._post_blocks(header_blocks, "Daily Topic Report"))

        # カテゴリごとに投稿
        for summary in report.summaries:
            if summary.category != "C6":  # "other"以外
                category_blocks = self._create_category_blocks(summary)
                responses.append(
                    self._post_blocks(category_blocks, f"Category {summary.category}")
                )

        # フッターメッセージ（統計情報）
        footer_blocks = self._create_footer_blocks(report)
        responses.append(self._post_blocks(footer_blocks, "Daily Topic Statistics"))

        return responses

    def _create_header_blocks(self, report: DailyTopicReport) -> list[dict]:
        """ヘッダーブロックを作成"""
        date_str = report.date.strftime("%Y年%m月%d日")

        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📰 Daily Topic - {date_str}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"今日は{len(report.summaries)}カテゴリの要約をお届けします。",
                },
            },
            {"type": "divider"},
        ]

    def _create_category_blocks(self, summary: SummaryLog) -> list[dict]:
        """カテゴリブロックを作成"""
        from src.models import CATEGORY_INFO

        category_info = CATEGORY_INFO[summary.category]
        blocks = []

        # カテゴリ見出し
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"## {summary.category}: {category_info['label']}",
                },
            }
        )

        # 要約内容
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": summary.summary}}
        )

        # 元記事URL
        if summary.article_urls:
            url_links = []
            for i, url in enumerate(summary.article_urls[:5], 1):  # 最大5件
                url_links.append(f"<{url}|記事{i}>")

            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"📎 参考記事: {' | '.join(url_links)}"}
                    ],
                }
            )

        blocks.append({"type": "divider"})

        return blocks

    def _create_footer_blocks(self, report: DailyTopicReport) -> list[dict]:
        """フッターブロックを作成"""
        return [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"📊 処理統計: {report.total_articles}記事 | "
                            f"{report.total_tokens}トークン | "
                            f"${report.total_cost_usd:.4f} | "
                            f"{report.processing_time_seconds:.1f}秒"
                        ),
                    }
                ],
            }
        ]

    def _create_error_blocks(
        self,
        error_message: str,
        job_id: Optional[str] = None,
        step: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> list[dict]:
        """エラーブロックを作成"""
        blocks = []

        # エラーヘッダー
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "❌ Daily Topic Error"},
            }
        )

        # エラーメッセージ
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Message:*\n{error_message}",
                },
            }
        )

        # 詳細情報
        details = []
        if job_id:
            details.append(f"*Job ID:* {job_id}")
        if step:
            details.append(f"*Failed Step:* {step}")

        if details:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "\n".join(details)},
                }
            )

        # スタックトレース（短縮版）
        if stack_trace:
            # 最初の500文字のみ
            short_trace = stack_trace[:500]
            if len(stack_trace) > 500:
                short_trace += "..."

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Stack Trace:*\n```\n{short_trace}\n```",
                    },
                }
            )

        # タイムスタンプ
        from src.utils.time_utils import now_jst

        timestamp = now_jst().strftime("%Y-%m-%d %H:%M:%S JST")
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"🕐 {timestamp}"}],
            }
        )

        return blocks

    def _post_blocks(self, blocks: list[dict], fallback_text: str) -> dict:
        """ブロックを投稿"""
        channel = self.config.slack.daily_topic_channel
        if not channel.startswith("#"):
            channel = f"#{channel}"

        return self.slack_client.post_message(
            channel=channel, text=fallback_text, blocks=blocks
        )

    def upload_long_content(
        self, content: str, filename: str, title: str, channel: Optional[str] = None
    ) -> dict:
        """長いコンテンツをファイルとしてアップロード"""
        try:
            if channel is None:
                channel = self.config.slack.daily_topic_channel

            response = self.slack_client.upload_file(
                channels=channel, content=content, filename=filename, title=title
            )

            logger.info(f"Long content uploaded as file: {filename}")
            return response

        except Exception as e:
            logger.error(f"Error uploading long content: {e}")
            raise SlackAPIError(f"Failed to upload long content: {e}")

    def create_preview_url(self, blocks: list[dict]) -> str:
        """Block Kit Preview URLを生成"""
        # Block Kit Builderへのリンクを生成
        import base64

        blocks_json = json.dumps(blocks)
        encoded_blocks = base64.b64encode(blocks_json.encode()).decode()

        # URL長制限のため、簡略化
        if len(encoded_blocks) > 2000:
            # 簡略版のプレビューURL
            return "https://app.slack.com/block-kit-builder/"

        preview_url = f"https://app.slack.com/block-kit-builder/{encoded_blocks}"
        return preview_url

"""Slack APIクライアント"""
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import get_config
from src.models import SlackMessage
from src.utils.error_handler import SlackAPIError, retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SlackClient:
    """Slack APIクライアント"""

    def __init__(self, token: str | None = None):
        config = get_config()
        self.token = token or config.slack.bot_token
        self.client = WebClient(token=self.token)
        self.rate_limit_delay = config.slack.rate_limit_delay
        self.max_retries = config.slack.max_retries

        logger.info("Slack client initialized")

    def _handle_rate_limit(self) -> None:
        """Rate limit対応の待機"""
        time.sleep(self.rate_limit_delay)

    def _call_api_with_retry(self, method: str, **kwargs) -> dict:
        """API呼び出しをリトライ付きで実行"""

        def api_call():
            try:
                response = getattr(self.client, method)(**kwargs)
                self._handle_rate_limit()
                return response
            except SlackApiError as e:
                logger.error(f"Slack API error: {e.response['error']}")
                raise SlackAPIError(
                    f"Slack API error: {e.response['error']}", response=e.response
                )

        return retry_with_backoff(
            api_call,
            max_retries=self.max_retries,
            exceptions=(SlackApiError, SlackAPIError),
            step="slack_api_call",
        )

    def get_channel_id(self, channel_name: str) -> str | None:
        """チャネル名からチャネルIDを取得"""
        try:
            # '#'を除去
            channel_name = channel_name.lstrip("#")

            response = self._call_api_with_retry(
                "conversations_list", types="public_channel", limit=200
            )

            for channel in response.get("channels", []):
                if channel["name"] == channel_name:
                    logger.info(
                        f"Found channel ID for #{channel_name}: {channel['id']}"
                    )
                    return channel["id"]

            logger.warning(f"Channel #{channel_name} not found")
            return None

        except Exception as e:
            logger.error(f"Error getting channel ID for #{channel_name}: {e}")
            raise SlackAPIError(f"Failed to get channel ID: {e}")

    def get_channel_history(
        self,
        channel: str,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 100,
    ) -> list[SlackMessage]:
        """チャネル履歴を取得"""
        try:
            # チャネル名の場合はIDに変換
            if channel.startswith("#"):
                channel_id = self.get_channel_id(channel)
                if not channel_id:
                    raise SlackAPIError(f"Channel {channel} not found")
                channel = channel_id

            response = self._call_api_with_retry(
                "conversations_history",
                channel=channel,
                oldest=oldest,
                latest=latest,
                limit=limit,
            )

            messages = []
            for msg_data in response.get("messages", []):
                if msg_data.get("type") == "message" and "text" in msg_data:
                    message = SlackMessage(
                        type=msg_data["type"],
                        text=msg_data["text"],
                        ts=msg_data["ts"],
                        user=msg_data.get("user"),
                        channel=channel,
                    )
                    messages.append(message)

            logger.info(f"Retrieved {len(messages)} messages from channel {channel}")
            return messages

        except Exception as e:
            logger.error(f"Error getting channel history: {e}")
            if isinstance(e, SlackAPIError):
                raise
            raise SlackAPIError(f"Failed to get channel history: {e}")

    def post_message(
        self,
        channel: str,
        text: str | None = None,
        blocks: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        """メッセージを投稿"""
        try:
            # チャネル名の場合はIDに変換
            if channel.startswith("#"):
                channel_id = self.get_channel_id(channel)
                if not channel_id:
                    raise SlackAPIError(f"Channel {channel} not found")
                channel = channel_id

            post_kwargs = {"channel": channel, **kwargs}

            if blocks:
                post_kwargs["blocks"] = blocks
            if text:
                post_kwargs["text"] = text

            response = self._call_api_with_retry("chat_postMessage", **post_kwargs)

            logger.info(f"Message posted to channel {channel}: {response.get('ts')}")
            return response

        except Exception as e:
            logger.error(f"Error posting message: {e}")
            if isinstance(e, SlackAPIError):
                raise
            raise SlackAPIError(f"Failed to post message: {e}")

    def upload_file(
        self,
        channels: str,
        content: str,
        filename: str,
        title: str | None = None,
        **kwargs,
    ) -> dict:
        """ファイルをアップロード"""
        try:
            response = self._call_api_with_retry(
                "files_upload",
                channels=channels,
                content=content,
                filename=filename,
                title=title,
                **kwargs,
            )

            logger.info(f"File uploaded: {filename}")
            return response

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            if isinstance(e, SlackAPIError):
                raise
            raise SlackAPIError(f"Failed to upload file: {e}")

    def test_connection(self) -> bool:
        """接続テスト"""
        try:
            response = self._call_api_with_retry("auth_test")
            user = response.get("user", "Unknown")
            team = response.get("team", "Unknown")
            logger.info(f"Slack connection test successful. User: {user}, Team: {team}")
            return True

        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False

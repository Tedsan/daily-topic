"""設定管理"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SlackConfig(BaseModel):
    """Slack設定"""

    bot_token: str = Field(..., description="Slack Bot Token")
    app_token: str | None = Field(None, description="Slack App Token (Socket Mode用)")
    rss_feed_channel: str = Field(default="rss-feed", description="RSS取得チャネル")
    daily_topic_channel: str = Field(default="daily-topic", description="投稿先チャネル")

    # Rate limiting
    rate_limit_delay: float = Field(default=1.0, description="API呼び出し間隔（秒）")
    max_retries: int = Field(default=3, description="最大リトライ回数")


class ClaudeConfig(BaseModel):
    """Claude設定"""

    api_key: str = Field(..., description="Anthropic API Key")
    model: str = Field(default="claude-3-sonnet-20240229", description="使用モデル")
    max_tokens: int = Field(default=500, description="最大トークン数")
    temperature: float = Field(default=0.3, description="temperature設定")

    # Cost tracking
    cost_per_input_token: float = Field(default=0.000003, description="入力トークン単価（USD）")
    cost_per_output_token: float = Field(default=0.000015, description="出力トークン単価（USD）")


class AWSConfig(BaseModel):
    """AWS設定（統計保存用）"""

    access_key_id: str | None = None
    secret_access_key: str | None = None
    region: str = Field(default="us-east-1")
    s3_bucket_name: str | None = None


class SystemConfig(BaseModel):
    """システム設定"""

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    timezone: str = Field(default="Asia/Tokyo")

    # Processing settings
    lookback_hours: int = Field(default=24, description="過去何時間のメッセージを取得するか")
    min_content_length: int = Field(default=200, description="最小本文長")
    max_articles_per_category: int = Field(default=10, description="カテゴリあたりの最大記事数")

    # Test settings
    test_mode: bool = Field(default=False)
    mock_external_apis: bool = Field(default=True)


class GitHubConfig(BaseModel):
    """GitHub設定（CI/CD用）"""

    token: str | None = None
    repository: str | None = None


class AppConfig(BaseSettings):
    """アプリケーション設定"""

    # Slack設定
    slack_bot_token: str = Field(...)
    slack_app_token: str | None = Field(None)
    rss_feed_channel: str = Field(default="rss-feed")
    daily_topic_channel: str = Field(default="daily-topic")

    # Claude設定
    anthropic_api_key: str = Field(...)
    claude_model: str = Field(default="claude-3-sonnet-20240229")
    max_tokens: int = Field(default=500)

    # AWS設定
    aws_access_key_id: str | None = Field(None)
    aws_secret_access_key: str | None = Field(None)
    aws_region: str = Field(default="us-east-1")
    s3_bucket_name: str | None = Field(None)

    # システム設定
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    timezone: str = Field(default="Asia/Tokyo")

    # テスト設定
    test_mode: bool = Field(default=False)
    mock_external_apis: bool = Field(default=True)

    # GitHub設定
    github_token: str | None = Field(None)
    github_repository: str | None = Field(None)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def slack(self) -> SlackConfig:
        """Slack設定を取得"""
        return SlackConfig(
            bot_token=self.slack_bot_token,
            app_token=self.slack_app_token,
            rss_feed_channel=self.rss_feed_channel,
            daily_topic_channel=self.daily_topic_channel,
        )

    @property
    def claude(self) -> ClaudeConfig:
        """Claude設定を取得"""
        return ClaudeConfig(
            api_key=self.anthropic_api_key,
            model=self.claude_model,
            max_tokens=self.max_tokens,
        )

    @property
    def aws(self) -> AWSConfig:
        """AWS設定を取得"""
        return AWSConfig(
            access_key_id=self.aws_access_key_id,
            secret_access_key=self.aws_secret_access_key,
            region=self.aws_region,
            s3_bucket_name=self.s3_bucket_name,
        )

    @property
    def system(self) -> SystemConfig:
        """システム設定を取得"""
        return SystemConfig(
            environment=self.environment,
            log_level=self.log_level,
            timezone=self.timezone,
            test_mode=self.test_mode,
            mock_external_apis=self.mock_external_apis,
        )

    @property
    def github(self) -> GitHubConfig:
        """GitHub設定を取得"""
        return GitHubConfig(
            token=self.github_token,
            repository=self.github_repository,
        )

    def is_production(self) -> bool:
        """本番環境かどうか"""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """開発環境かどうか"""
        return self.environment.lower() == "development"

    def is_test(self) -> bool:
        """テスト環境かどうか"""
        return self.test_mode or self.environment.lower() == "test"


# グローバル設定インスタンス
def _create_config() -> AppConfig:
    """設定インスタンスを作成"""
    return AppConfig()


def get_config() -> AppConfig:
    """設定を取得"""
    return _create_config()


def reload_config() -> AppConfig:
    """設定を再読み込み"""
    return _create_config()

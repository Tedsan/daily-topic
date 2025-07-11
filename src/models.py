"""データモデル定義（pydantic v2対応）"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl

# 型安全なカテゴリ定義
Category = Literal["C1", "C2", "C3", "C4", "C5", "C6"]

# カテゴリ情報マッピング
CATEGORY_INFO = {
    "C1": {
        "label": "Software-Defined Vehicle",
        "keywords": ["SDV", "AUTOSAR", "Adaptive AUTOSAR", "車載ソフト", "Classic AUTOSAR"],
    },
    "C2": {
        "label": "Industrial IoT & Edge",
        "keywords": [
            "Industrial IoT",
            "IIoT",
            "スマートファクトリー",
            "Edge Computing",
            "エッジコンピューティング",
            "産業用IoT",
            "PLM",
        ],
    },
    "C3": {
        "label": "Industrial Protocols",
        "keywords": [
            "MQTT",
            "OPC UA",
            "OPC UA FX",
            "open62541",
            "TSN",
            "openPLC",
            "ソフトウェアPLC",
        ],
    },
    "C4": {
        "label": "Generative AI Tech",
        "keywords": [
            "Gemini CLI",
            "Gemini",
            "Claude",
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
            "LLM",
        ],
    },
    "C6": {
        "label": "Other",
        "keywords": ["その他"],
    },
}


class BaseAppModel(BaseModel):
    """アプリケーション共通のベースモデル"""

    model_config = {"from_attributes": True}


class ArticleMetadata(BaseAppModel):
    """記事メタデータ（DR-001）"""

    article_url: HttpUrl
    title: str
    published_at: datetime | None = None
    content: str = Field(..., min_length=200, description="抽出本文（200字以上）")
    raw_html: str | None = None

    # 分類情報
    category: Category | None = None
    category_confidence: float | None = Field(None, ge=0.0, le=1.0)


class SummaryLog(BaseAppModel):
    """要約ログ（DR-002）"""

    summary_id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    tokens_used: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    model: str = "claude-3-sonnet-20240229"
    article_count: int = Field(..., ge=0)

    # 要約内容
    category: Category
    summary: str = Field(..., max_length=500, description="要約内容（500字以内）")
    article_urls: list[HttpUrl] = Field(default_factory=list)


class SlackMessage(BaseAppModel):
    """Slackメッセージ"""

    type: str = "message"
    text: str
    ts: str  # Slack timestamp
    user: str | None = None
    channel: str | None = None


class DailyTopicReport(BaseAppModel):
    """日次レポート"""

    date: datetime = Field(default_factory=datetime.utcnow)
    summaries: list[SummaryLog] = Field(default_factory=list)
    other_articles: list[ArticleMetadata] = Field(default_factory=list)
    total_articles: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    processing_time_seconds: float | None = None

    def add_summary(self, summary: SummaryLog) -> None:
        """要約を追加し、統計を更新"""
        self.summaries.append(summary)
        self.total_articles += summary.article_count
        self.total_tokens += summary.tokens_used
        self.total_cost_usd += summary.cost_usd

    def add_other_articles(self, articles: list[ArticleMetadata]) -> None:
        """Otherカテゴリの記事を追加"""
        self.other_articles.extend(articles)


class CategorySummaryRequest(BaseAppModel):
    """カテゴリ要約リクエスト"""

    category: Category
    articles: list[ArticleMetadata]
    max_length: int = Field(default=500, le=500)


class CategorySummaryResponse(BaseAppModel):
    """カテゴリ要約レスポンス（Claude APIからのJSON形式）"""

    category: Category
    summary: str = Field(..., max_length=500)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    key_points: list[str] | None = None


class SlackBlockKitMessage(BaseAppModel):
    """Slack Block Kitメッセージ"""

    channel: str
    blocks: list[Any]
    text: str | None = None  # fallback text

    @classmethod
    def create_daily_report(cls, report: DailyTopicReport) -> "SlackBlockKitMessage":
        """日次レポートからBlock Kitメッセージを生成"""
        blocks = []

        # 日付見出し
        date_str = report.date.strftime("%Y年%m月%d日")
        blocks.append(
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📰 Daily Topic - {date_str}"},
            }
        )

        # 各カテゴリの要約
        for summary in report.summaries:
            if summary.category != "C6":  # "other"以外のみ
                category_info = CATEGORY_INFO[summary.category]

                # テーマ見出し
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"## {summary.category}: {category_info['label']}",
                        },
                    }
                )

                # 要約
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": summary.summary},
                    }
                )

                # 元記事URL
                if summary.article_urls:
                    url_links = []
                    # 最大5件
                    for i, url in enumerate(summary.article_urls[:5], 1):
                        url_links.append(f"<{url}|記事{i}>")

                    blocks.append(
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"📎 参考記事: {' | '.join(url_links)}",
                                }
                            ],
                        }
                    )

                # 区切り線
                blocks.append({"type": "divider"})

        # Otherカテゴリ記事（URL一覧）
        if report.other_articles:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"## C6: Other ({len(report.other_articles)}記事)",
                    },
                }
            )

            # URL一覧を5件ずつに分割して表示
            other_urls = [str(article.article_url) for article in report.other_articles]
            for i in range(0, len(other_urls), 5):
                chunk_urls = other_urls[i : i + 5]
                url_links = [f"<{url}|記事{i+j+1}>" for j, url in enumerate(chunk_urls)]

                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"📎 参考記事: {' | '.join(url_links)}",
                            }
                        ],
                    }
                )

            # 区切り線
            blocks.append({"type": "divider"})

        # 統計情報
        blocks.append(
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
        )

        return cls(
            channel="#daily-topic",
            blocks=blocks,
            text=f"Daily Topic - {date_str}: {len(report.summaries)}カテゴリの要約",
        )


class ProcessingError(BaseAppModel):
    """処理エラー情報"""

    step: str
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    job_id: str | None = None
    stack_trace: str | None = None

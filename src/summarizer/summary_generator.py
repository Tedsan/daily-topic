"""要約生成機能"""
import csv
import json
import os
from typing import Optional

from src.config import get_config
from src.models import ArticleMetadata, Category, SummaryLog
from src.summarizer.claude_client import ClaudeClient
from src.utils.error_handler import ClaudeAPIError
from src.utils.logger import get_logger
from src.utils.time_utils import get_monthly_stats_filename, now_jst

logger = get_logger(__name__)


class SummaryGenerator:
    """要約生成クラス"""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.config = get_config()
        self.claude_client = claude_client or ClaudeClient()

        # 統計情報
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.generation_stats = []

        logger.info("Summary generator initialized")

    def generate_category_summary(
        self,
        category: Category,
        articles: list[ArticleMetadata],
        max_articles: Optional[int] = None,
    ) -> SummaryLog:
        """カテゴリ別要約を生成"""
        try:
            logger.info(
                f"Generating summary for category {category} with {len(articles)} articles"
            )

            # 記事数制限
            if max_articles and len(articles) > max_articles:
                # 信頼度の高い順でソート
                articles = sorted(
                    articles, key=lambda a: a.category_confidence or 0.0, reverse=True
                )[:max_articles]
                logger.info(
                    f"Limited to {max_articles} articles for category {category}"
                )

            # 記事内容を結合
            combined_content = self._combine_articles_content(articles)

            # プロンプトサンプルを読み込み
            system_prompt = self._load_prompt_sample("summarization", category)

            # Claude APIで要約生成（async対応）
            import asyncio

            response = asyncio.run(
                self.claude_client.generate_summary(
                    content=combined_content,
                    category=category,
                    system_prompt=system_prompt,
                )
            )

            # SummaryLogを作成
            summary_log = SummaryLog(
                category=category,
                summary=response["summary"],
                article_count=len(articles),
                tokens_used=response["usage"]["input_tokens"]
                + response["usage"]["output_tokens"],
                cost_usd=response["usage"]["cost_usd"],
                article_urls=[article.article_url for article in articles],
            )

            # 統計情報を更新
            self.total_tokens_used += summary_log.tokens_used
            self.total_cost_usd += summary_log.cost_usd
            self.generation_stats.append(
                {
                    "category": category,
                    "timestamp": summary_log.generated_at,
                    "tokens_used": summary_log.tokens_used,
                    "cost_usd": summary_log.cost_usd,
                    "article_count": summary_log.article_count,
                }
            )

            logger.info(
                f"Summary generated for category {category}: "
                f"{summary_log.tokens_used} tokens, "
                f"${summary_log.cost_usd:.4f}, "
                f"{summary_log.article_count} articles"
            )

            return summary_log

        except Exception as e:
            logger.error(f"Error generating summary for category {category}: {e}")
            raise ClaudeAPIError(
                f"Failed to generate summary for category {category}: {e}"
            )

    def generate_multiple_summaries(
        self, categorized_articles: dict[Category, list[ArticleMetadata]]
    ) -> list[SummaryLog]:
        """複数カテゴリの要約を生成"""
        summaries = []

        logger.info(f"Generating summaries for {len(categorized_articles)} categories")

        for category, articles in categorized_articles.items():
            try:
                summary = self.generate_category_summary(category, articles)
                summaries.append(summary)

            except ClaudeAPIError as e:
                logger.error(f"Failed to generate summary for category {category}: {e}")
                # 個別の失敗は無視して続行
                continue

        logger.info(
            f"Generated {len(summaries)} summaries. "
            f"Total tokens: {self.total_tokens_used}, "
            f"Total cost: ${self.total_cost_usd:.4f}"
        )

        return summaries

    def _combine_articles_content(self, articles: list[ArticleMetadata]) -> str:
        """記事内容を結合"""
        content_parts = []

        for i, article in enumerate(articles, 1):
            content_parts.append(f"## 記事 {i}: {article.title}")
            content_parts.append(f"URL: {article.article_url}")
            content_parts.append(f"内容: {article.content}")
            content_parts.append("---")

        return "\n\n".join(content_parts)

    def _load_prompt_sample(
        self, prompt_type: str, category: Optional[Category] = None
    ) -> Optional[str]:
        """プロンプトサンプルを読み込み"""
        try:
            # プロンプトファイルのパス
            if category:
                filename = f"tests/prompt_samples/{prompt_type}_{category.lower()}.txt"
            else:
                filename = f"tests/prompt_samples/{prompt_type}.txt"

            # ファイルが存在しない場合は汎用プロンプト
            if not os.path.exists(filename):
                filename = f"tests/prompt_samples/{prompt_type}.txt"
                if not os.path.exists(filename):
                    return None

            with open(filename, encoding="utf-8") as f:
                prompt = f.read().strip()

            logger.debug(f"Loaded prompt sample: {filename}")
            return prompt

        except Exception as e:
            logger.warning(f"Failed to load prompt sample: {e}")
            return None

    def save_stats_to_csv(self, filename: Optional[str] = None) -> str:
        """統計情報をCSVファイルに保存"""
        try:
            if filename is None:
                filename = get_monthly_stats_filename()

            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            # ファイルが存在しない場合はヘッダーを書く
            write_header = not os.path.exists(filename)

            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                if write_header:
                    writer.writerow(
                        [
                            "timestamp",
                            "category",
                            "tokens_used",
                            "cost_usd",
                            "article_count",
                        ]
                    )

                # 統計情報を書き込み
                for stat in self.generation_stats:
                    writer.writerow(
                        [
                            stat["timestamp"].isoformat(),
                            stat["category"],
                            stat["tokens_used"],
                            stat["cost_usd"],
                            stat["article_count"],
                        ]
                    )

            logger.info(f"Statistics saved to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
            raise

    def save_stats_to_json(self, filename: Optional[str] = None) -> str:
        """統計情報をJSONファイルに保存"""
        try:
            if filename is None:
                current_time = now_jst()
                filename = f"stats/{current_time.strftime('%Y%m%d_%H%M%S')}.json"

            # ディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            stats_data = {
                "timestamp": now_jst().isoformat(),
                "total_tokens_used": self.total_tokens_used,
                "total_cost_usd": self.total_cost_usd,
                "generation_count": len(self.generation_stats),
                "details": self.generation_stats,
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Statistics saved to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
            raise

    def get_total_stats(self) -> dict:
        """総統計情報を取得"""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "generation_count": len(self.generation_stats),
            "average_tokens_per_summary": (
                self.total_tokens_used / len(self.generation_stats)
                if self.generation_stats
                else 0
            ),
            "average_cost_per_summary": (
                self.total_cost_usd / len(self.generation_stats)
                if self.generation_stats
                else 0
            ),
        }

    def reset_stats(self):
        """統計情報をリセット"""
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.generation_stats = []
        logger.info("Statistics reset")

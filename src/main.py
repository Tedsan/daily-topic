"""Daily Topic システム - メインプログラム"""

import argparse
import asyncio
import os
import sys
import time

from src.config import get_config
from src.content.categorizer import CategoryClassifier
from src.content.fetcher import ContentFetcher
from src.content.parser import ContentParser
from src.models import ArticleMetadata, DailyTopicReport
from src.slack.message_poster import MessagePoster
from src.slack.rss_fetcher import RSSFetcher
from src.summarizer.summary_generator import SummaryGenerator
from src.utils.error_handler import DailyTopicError, handle_exception
from src.utils.logger import get_logger
from src.utils.time_utils import now_jst

logger = get_logger(__name__)


class DailyTopicProcessor:
    """Daily Topic処理クラス"""

    def __init__(self) -> None:
        self.config = get_config()
        self.start_time = time.time()

        # GitHub Actions環境変数の確認
        self._check_github_actions_env()

        # 各コンポーネントの初期化
        self.rss_fetcher = RSSFetcher()
        self.content_fetcher = ContentFetcher()
        self.content_parser = ContentParser()
        self.categorizer = CategoryClassifier()
        self.summary_generator = SummaryGenerator()
        self.message_poster = MessagePoster()

        logger.info("Daily Topic processor initialized")

    def _check_github_actions_env(self) -> None:
        """GitHub Actions環境変数のチェック"""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            logger.info("Running in GitHub Actions environment")

            # 手動実行パラメータの取得
            target_category = os.environ.get("TARGET_CATEGORY", "All")
            lookback_hours = int(os.environ.get("LOOKBACK_HOURS", "24"))

            if target_category != "All":
                logger.info(f"Target category specified: {target_category}")
                # TODO: カテゴリフィルタリング機能を実装

            if lookback_hours != 24:
                logger.info(f"Custom lookback hours: {lookback_hours}")
                os.environ["LOOKBACK_HOURS"] = str(lookback_hours)

    async def process_daily_topic(self) -> DailyTopicReport:
        """日次処理のメインフロー"""
        try:
            logger.info("Starting Daily Topic processing")

            # 1. RSS取得
            urls = await self._step_fetch_rss_urls()

            # 2. コンテンツ処理
            articles = await self._step_process_content(urls)

            # 3. カテゴリ分類
            categorized_articles, other_articles = await self._step_categorize_articles(
                articles
            )

            # 4. 要約生成
            summaries = await self._step_generate_summaries(categorized_articles)

            # 5. レポート作成
            report = await self._step_create_report(summaries, other_articles)

            # 6. Slack投稿
            await self._step_post_to_slack(report)

            # 7. 統計保存
            await self._step_save_statistics()

            logger.info(
                "Daily Topic processing completed in %.1fs",
                time.time() - self.start_time,
            )
            return report

        except Exception as e:
            logger.error("Daily Topic processing failed: %s", e)
            await self._handle_processing_error(e)
            raise

    async def _step_fetch_rss_urls(self) -> list[str]:
        """Step 1: RSS URL取得"""
        logger.info("Step 1: Fetching RSS URLs")

        try:
            urls = self.rss_fetcher.fetch_rss_urls()

            if not urls:
                raise DailyTopicError("No URLs found in RSS feed", step="rss_fetch")

            logger.info("Fetched %d URLs from RSS feed", len(urls))
            return urls

        except Exception as e:
            logger.error("RSS URL fetch failed: %s", e)
            raise DailyTopicError(f"RSS URL fetch failed: {e}", step="rss_fetch") from e

    async def _step_process_content(self, urls: list[str]) -> list[ArticleMetadata]:
        """Step 2: コンテンツ処理"""
        logger.info("Step 2: Processing content from %d URLs", len(urls))

        try:
            # 将来的に並列処理に拡張可能な構造
            # 現在は同期実行だが、asyncio対応済み
            url_content_map = await asyncio.to_thread(
                self.content_fetcher.fetch_multiple_contents, urls
            )

            if not url_content_map:
                raise DailyTopicError(
                    "No content could be fetched", step="content_fetch"
                )

            logger.info(
                "Successfully fetched content from %d URLs",
                len(url_content_map),
            )

            # コンテンツ解析
            articles = await asyncio.to_thread(
                self.content_parser.parse_articles, url_content_map
            )

            if not articles:
                raise DailyTopicError(
                    "No articles could be parsed", step="content_parse"
                )

            logger.info("Successfully parsed %d articles", len(articles))
            return articles

        except Exception as e:
            logger.error("Content processing failed: %s", e)
            raise DailyTopicError(
                f"Content processing failed: {e}", step="content_processing"
            ) from e

    async def _step_categorize_articles(
        self, articles: list[ArticleMetadata]
    ) -> tuple[dict, list[ArticleMetadata]]:
        """Step 3: カテゴリ分類"""
        logger.info("Step 3: Categorizing %d articles", len(articles))

        try:
            # カテゴリ分類
            categorized_articles = await asyncio.to_thread(
                self.categorizer.classify_articles, articles
            )

            # Otherカテゴリの記事を保存
            other_articles = categorized_articles.get("C6", [])

            # "Other"カテゴリを除外
            filtered_articles = self.categorizer.filter_non_other_categories(
                categorized_articles
            )

            # 記事数制限
            limited_articles = self.categorizer.limit_articles_per_category(
                filtered_articles
            )

            if not limited_articles:
                raise DailyTopicError(
                    "No articles remaining after categorization",
                    step="categorization",
                )

            total_articles = sum(
                len(articles) for articles in limited_articles.values()
            )
            logger.info(
                "Successfully categorized %d articles into %d categories",
                total_articles,
                len(limited_articles),
            )

            return limited_articles, other_articles

        except Exception as e:
            logger.error("Article categorization failed: %s", e)
            raise DailyTopicError(
                f"Article categorization failed: {e}", step="categorization"
            ) from e

    async def _step_generate_summaries(self, categorized_articles: dict) -> list:
        """Step 4: 要約生成"""
        logger.info(
            "Step 4: Generating summaries for %d categories",
            len(categorized_articles),
        )

        try:
            summaries = await asyncio.to_thread(
                self.summary_generator.generate_multiple_summaries, categorized_articles
            )

            if not summaries:
                raise DailyTopicError(
                    "No summaries could be generated", step="summary_generation"
                )

            logger.info("Successfully generated %d summaries", len(summaries))
            return summaries

        except Exception as e:
            logger.error("Summary generation failed: %s", e)
            raise DailyTopicError(
                f"Summary generation failed: {e}", step="summary_generation"
            ) from e

    async def _step_create_report(
        self, summaries: list, other_articles: list = None
    ) -> DailyTopicReport:
        """Step 5: レポート作成"""
        logger.info("Step 5: Creating daily report")

        try:
            report = DailyTopicReport(
                date=now_jst(), processing_time_seconds=time.time() - self.start_time
            )

            for summary in summaries:
                report.add_summary(summary)

            # Otherカテゴリの記事を追加
            if other_articles:
                report.add_other_articles(other_articles)

            logger.info(
                "Report created: %d articles, %d tokens, $%.4f",
                report.total_articles,
                report.total_tokens,
                report.total_cost_usd,
            )

            return report

        except Exception as e:
            logger.error("Report creation failed: %s", e)
            raise DailyTopicError(
                f"Report creation failed: {e}", step="report_creation"
            ) from e

    async def _step_post_to_slack(self, report: DailyTopicReport) -> None:
        """Step 6: Slack投稿"""
        logger.info("Step 6: Posting to Slack")

        try:
            await asyncio.to_thread(self.message_poster.post_daily_report, report)

            logger.info("Successfully posted to Slack")

        except Exception as e:
            logger.error("Slack posting failed: %s", e)
            raise DailyTopicError(
                f"Slack posting failed: {e}", step="slack_posting"
            ) from e

    async def _step_save_statistics(self) -> None:
        """Step 7: 統計保存"""
        logger.info("Step 7: Saving statistics")

        try:
            # CSV保存
            csv_file = await asyncio.to_thread(self.summary_generator.save_stats_to_csv)

            # JSON保存
            json_file = await asyncio.to_thread(
                self.summary_generator.save_stats_to_json
            )

            logger.info("Statistics saved to %s and %s", csv_file, json_file)

        except Exception as e:
            logger.error("Statistics saving failed: %s", e)
            # 統計保存の失敗は処理全体を止めない
            logger.warning("Continuing despite statistics saving failure")

    async def _handle_processing_error(self, error: Exception) -> None:
        """処理エラーのハンドリング"""
        try:
            processing_error = handle_exception(error, log_error=False)

            # Slackにエラーメッセージを投稿
            await asyncio.to_thread(
                self.message_poster.post_error_message,
                processing_error.message,
                processing_error.job_id,
                processing_error.step,
                processing_error.stack_trace,
            )

        except Exception as e:
            logger.error("Error handling failed: %s", e)
            # エラーハンドリングの失敗は最後の手段

    def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        try:
            self.content_fetcher.close()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error("Cleanup failed: %s", e)


async def main() -> int:
    """メイン関数"""
    processor = None

    try:
        # 設定の確認
        config = get_config()
        logger.info("Starting Daily Topic system in %s mode", config.environment)

        # プロセッサー初期化
        processor = DailyTopicProcessor()

        # 日次処理実行
        report = await processor.process_daily_topic()

        # 成功時のログ
        logger.info(
            "Daily Topic processing completed successfully. "
            "Report: %d articles, %d summaries, %.1fs",
            report.total_articles,
            len(report.summaries),
            report.processing_time_seconds,
        )

        return 0

    except DailyTopicError as e:
        logger.error("Daily Topic error: %s", e)
        return 1

    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return 1

    finally:
        if processor:
            processor.cleanup()


def cli_main() -> None:
    """CLI エントリーポイント"""
    parser = argparse.ArgumentParser(description="Daily Topic システム")
    parser.add_argument("--serve", action="store_true", help="サーバーモードで実行（将来的な拡張用）")

    args = parser.parse_args()

    if args.serve:
        logger.info("Server mode is not yet implemented")
        sys.exit(1)

    # 非同期実行
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    cli_main()

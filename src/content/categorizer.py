"""カテゴリ分類機能"""
import re

from src.config import get_config
from src.models import CATEGORY_INFO, ArticleMetadata, Category
from src.utils.error_handler import CategoryClassificationError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CategoryClassifier:
    """カテゴリ分類クラス"""

    def __init__(self):
        self.config = get_config()
        self.category_info = CATEGORY_INFO

        # カテゴリ優先順位（C1 > C2 > ... > C6）
        self.category_priority = ["C1", "C2", "C3", "C4", "C5", "C6"]

        logger.info("Category classifier initialized")

    def _calculate_keyword_score(self, text: str, keywords: list[str]) -> float:
        """キーワードマッチングスコアを計算"""
        text_lower = text.lower()
        score = 0.0
        total_keywords = len(keywords)

        if total_keywords == 0:
            return 0.0

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 完全一致
            if keyword_lower in text_lower:
                # 長いキーワードほど高スコア
                keyword_score = len(keyword) / 10.0

                # 出現回数を考慮
                occurrence_count = text_lower.count(keyword_lower)
                score += keyword_score * occurrence_count

        # 正規化（0.0-1.0の範囲）
        normalized_score = min(score / total_keywords, 1.0)

        return normalized_score

    def _extract_text_for_classification(self, article: ArticleMetadata) -> str:
        """分類用のテキストを抽出"""
        # タイトルとコンテンツを結合（タイトルを重視）
        title_weight = 3  # タイトルを3倍重視
        text_parts = []

        # タイトルを重複して追加
        for _ in range(title_weight):
            text_parts.append(article.title)

        # コンテンツから本文を抽出
        content = article.content

        # Markdownリンクからテキストのみ抽出
        content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)

        # 見出しマークを除去
        content = re.sub(r"^#+\s*", "", content, flags=re.MULTILINE)

        # 強調記号を除去
        content = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", content)

        # 最初の500文字のみ使用（パフォーマンス向上のため）
        content = content[:500]

        text_parts.append(content)

        return " ".join(text_parts)

    def classify_article(self, article: ArticleMetadata) -> tuple[Category, float]:
        """記事を分類

        Returns:
            tuple: (category, confidence_score)
        """
        try:
            text = self._extract_text_for_classification(article)

            category_scores = {}

            # 各カテゴリのスコアを計算
            for category_id in self.category_priority:
                if category_id == "C6":  # Other は最後に処理
                    continue

                category_data = self.category_info[category_id]
                keywords = category_data["keywords"]

                score = self._calculate_keyword_score(text, keywords)
                category_scores[category_id] = score

                logger.debug(
                    f"Article {str(article.article_url)[:50]}... - "
                    f"Category {category_id}: {score:.3f}"
                )

            # 最高スコアのカテゴリを選択
            if category_scores:
                best_category = max(category_scores, key=category_scores.get)
                best_score = category_scores[best_category]

                # 閾値チェック（0.1以上でないとOtherに分類）
                if best_score >= 0.1:
                    logger.info(
                        f"Article classified as {best_category} "
                        f"(score: {best_score:.3f}): {article.title}"
                    )
                    return best_category, best_score

            # 閾値未満またはスコアがない場合はOtherに分類
            logger.info(f"Article classified as C6 (Other): {article.title}")
            return "C6", 0.0

        except Exception as e:
            logger.error(f"Error classifying article {str(article.article_url)}: {e}")
            raise CategoryClassificationError(f"Failed to classify article: {e}")

    def classify_articles(
        self, articles: list[ArticleMetadata]
    ) -> dict[Category, list[ArticleMetadata]]:
        """複数の記事を分類

        Returns:
            dict: {category: [articles]}
        """
        categorized_articles = {}

        logger.info(f"Classifying {len(articles)} articles")

        for article in articles:
            try:
                category, confidence = self.classify_article(article)

                # 分類結果を記事に保存
                article.category = category
                article.category_confidence = confidence

                # カテゴリ別に分類
                if category not in categorized_articles:
                    categorized_articles[category] = []
                categorized_articles[category].append(article)

            except CategoryClassificationError as e:
                logger.warning(
                    f"Failed to classify article {str(article.article_url)}: {e}"
                )
                # 分類失敗の場合はOtherに分類
                article.category = "C6"
                article.category_confidence = 0.0

                if "C6" not in categorized_articles:
                    categorized_articles["C6"] = []
                categorized_articles["C6"].append(article)

        # 統計情報をログ出力
        for category, articles_list in categorized_articles.items():
            category_label = self.category_info[category]["label"]
            logger.info(
                f"Category {category} ({category_label}): {len(articles_list)} articles"
            )

        return categorized_articles

    def filter_non_other_categories(
        self, categorized_articles: dict[Category, list[ArticleMetadata]]
    ) -> dict[Category, list[ArticleMetadata]]:
        """Otherカテゴリ以外をフィルタ（要件: category != "other"）"""
        filtered = {}

        for category, articles_list in categorized_articles.items():
            if category != "C6":  # C6 = Other
                filtered[category] = articles_list

        total_articles = sum(len(articles) for articles in filtered.values())
        logger.info(
            f"Filtered out 'Other' category: {total_articles} articles remaining"
        )

        return filtered

    def limit_articles_per_category(
        self,
        categorized_articles: dict[Category, list[ArticleMetadata]],
        max_per_category: int | None = None,
    ) -> dict[Category, list[ArticleMetadata]]:
        """カテゴリあたりの記事数を制限"""
        if max_per_category is None:
            max_per_category = self.config.system.max_articles_per_category

        limited_articles = {}

        for category, articles_list in categorized_articles.items():
            if len(articles_list) <= max_per_category:
                limited_articles[category] = articles_list
            else:
                # 信頼度の高い順でソート
                sorted_articles = sorted(
                    articles_list,
                    key=lambda a: a.category_confidence or 0.0,
                    reverse=True,
                )
                limited_articles[category] = sorted_articles[:max_per_category]

                logger.info(
                    f"Limited category {category} from {len(articles_list)} "
                    f"to {max_per_category} articles"
                )

        return limited_articles

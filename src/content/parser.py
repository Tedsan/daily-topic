"""コンテンツ解析機能"""
import re

from bs4 import BeautifulSoup
from markdownify import markdownify
from readability import Document

from src.config import get_config
from src.models import ArticleMetadata
from src.utils.error_handler import ContentParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContentParser:
    """コンテンツ解析クラス"""

    def __init__(self):
        self.config = get_config()
        self.min_content_length = self.config.system.min_content_length

        # markdownify設定
        self.markdown_options = {
            "heading_style": "ATX",  # # スタイル
            "bullets": "-",  # リスト記号
            "emphasis_mark": "*",  # 強調記号
            "strong_mark": "**",  # 太字記号
            "strip": [
                "script",
                "style",
                "nav",
                "header",
                "footer",
                "aside",
            ],  # 除去するタグのみ指定
        }

        logger.info("Content parser initialized")

    def extract_readable_content(self, html: str, url: str) -> tuple[str, str, str]:
        """readability-lxmlで読みやすいコンテンツを抽出

        Returns:
            tuple: (title, summary, readable_html)
        """
        try:
            # readability-lxmlで主要コンテンツを抽出
            doc = Document(html)

            title = doc.title() or "タイトル不明"
            summary = doc.summary()

            # titleの清浄化
            title = re.sub(r"\s+", " ", title).strip()
            title = title[:200]  # 長すぎる場合は切り詰め

            logger.debug(f"Extracted title: {title}")
            logger.debug(f"Extracted content length: {len(summary)}")

            return title, summary, summary

        except Exception as e:
            logger.error(f"Error extracting readable content from {url}: {e}")
            raise ContentParsingError(f"Failed to extract readable content: {e}", url)

    def html_to_markdown(self, html: str) -> str:
        """HTMLをMarkdownに変換"""
        try:
            # BeautifulSoupで前処理
            soup = BeautifulSoup(html, "html.parser")

            # 不要なタグを除去
            for tag in soup.find_all(
                ["script", "style", "nav", "header", "footer", "aside"]
            ):
                tag.decompose()

            # 空のタグを除去
            for tag in soup.find_all():
                if not tag.get_text(strip=True) and not tag.find(["img", "br", "hr"]):
                    tag.decompose()

            # markdownifyで変換
            markdown = markdownify(str(soup), **self.markdown_options)

            # 後処理
            markdown = self._clean_markdown(markdown)

            return markdown

        except Exception as e:
            logger.error(f"Error converting HTML to Markdown: {e}")
            raise ContentParsingError(f"Failed to convert HTML to Markdown: {e}")

    def _clean_markdown(self, markdown: str) -> str:
        """Markdownを清浄化"""
        # 連続する空行を1つに
        markdown = re.sub(r"\n\s*\n\s*\n", "\n\n", markdown)

        # 先頭と末尾の空白を除去
        markdown = markdown.strip()

        # 連続するスペースを1つに
        markdown = re.sub(r" +", " ", markdown)

        # 不要な文字列を除去
        unwanted_patterns = [
            r"Cookie使用に関する通知.*",
            r"プライバシーポリシー.*",
            r"利用規約.*",
            r"広告.*",
            r"スポンサー.*",
            r"関連記事.*",
            r"おすすめ記事.*",
            r"人気記事.*",
            r"最新記事.*",
            r"もっと見る.*",
            r"続きを読む.*",
            r"※.*",
        ]

        for pattern in unwanted_patterns:
            markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE)

        return markdown.strip()

    def extract_body_text(self, markdown: str) -> str:
        """Markdownから本文のみを抽出（見出し、リンクURLなどを除外）"""
        lines = markdown.split("\n")
        body_lines = []

        for line in lines:
            line = line.strip()

            # 空行をスキップ
            if not line:
                continue

            # 見出しをスキップ
            if line.startswith("#"):
                continue

            # リンクのURLのみをスキップ
            if line.startswith("http"):
                continue

            # 画像をスキップ
            if line.startswith("!["):
                continue

            # コードブロックをスキップ
            if line.startswith("```"):
                continue

            body_lines.append(line)

        body_text = " ".join(body_lines)

        # Markdownリンクからテキストのみ抽出
        body_text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body_text)

        # 強調記号を除去
        body_text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", body_text)

        # 余分な空白を除去
        body_text = re.sub(r"\s+", " ", body_text).strip()

        return body_text

    def parse_article(
        self, url: str, html: str, final_url: str | None = None
    ) -> ArticleMetadata:
        """記事を解析してArticleMetadataを作成"""
        try:
            logger.info(f"Parsing article: {url}")

            # readability-lxmlで読みやすいコンテンツを抽出
            title, summary, readable_html = self.extract_readable_content(html, url)

            # HTMLをMarkdownに変換
            markdown = self.html_to_markdown(readable_html)

            # 本文のみを抽出
            body_text = self.extract_body_text(markdown)

            # 200字チェック（本文のみ）
            if len(body_text) < self.min_content_length:
                raise ContentParsingError(
                    f"Content too short: {len(body_text)} characters (minimum: {self.min_content_length})",
                    url,
                )

            # ArticleMetadataを作成
            article = ArticleMetadata(
                article_url=final_url or url,
                title=title,
                content=markdown,  # 全体のMarkdown
                raw_html=html,
            )

            logger.info(
                f"Article parsed successfully: {url} "
                f"(title: {len(title)} chars, content: {len(markdown)} chars, "
                f"body: {len(body_text)} chars)"
            )

            return article

        except ContentParsingError:
            raise
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            raise ContentParsingError(f"Failed to parse article: {e}", url)

    def parse_articles(
        self, url_content_map: dict[str, tuple[str, str]]
    ) -> list[ArticleMetadata]:
        """複数の記事を解析

        Args:
            url_content_map: {original_url: (html, final_url)}
        """
        articles = []

        logger.info(f"Parsing {len(url_content_map)} articles")

        for original_url, (html, final_url) in url_content_map.items():
            try:
                article = self.parse_article(original_url, html, final_url)
                articles.append(article)

            except ContentParsingError as e:
                logger.warning(f"Failed to parse article {original_url}: {e}")
                # 個別の失敗は無視して続行
                continue
            except Exception as e:
                logger.error(f"Unexpected error parsing article {original_url}: {e}")
                continue

        logger.info(
            f"Successfully parsed {len(articles)}/{len(url_content_map)} articles"
        )
        return articles

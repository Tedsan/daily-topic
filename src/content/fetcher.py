"""コンテンツ取得機能"""
import html
import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import get_config
from src.utils.error_handler import ContentFetchError, retry_with_backoff
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContentFetcher:
    """コンテンツ取得クラス"""

    def __init__(self):
        self.config = get_config()
        self.session = self._create_session()

        # User-Agent（適切なボットであることを示す）
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; DailyTopicBot/1.0; "
                "+https://github.com/your-org/daily-topic)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        logger.info("Content fetcher initialized")

    def normalize_url(self, url: str) -> str:
        """URLを正規化（Googleリダイレクトなどから実URLを抽出）"""
        try:
            # URLデコード（パイプ文字やその他のエンコードされた文字を処理）
            if "|" in url:
                url = url.split("|")[0]  # パイプ文字以降を除去

            # HTMLエンティティをデコード（&amp; -> &）
            html_decoded = html.unescape(url)

            # URLデコード
            decoded_url = unquote(html_decoded)

            # Googleリダイレクト形式のチェック
            if "google.com/url" in decoded_url:
                parsed = urlparse(decoded_url)
                query_params = parse_qs(parsed.query)

                # urlパラメータから実URLを抽出
                if "url" in query_params:
                    real_url = query_params["url"][0]
                    logger.info(f"Extracted real URL from Google redirect: {real_url}")
                    return real_url

            # その他のリダイレクト形式
            # bit.ly, tinyurl等への対応も可能

            if decoded_url != url:
                logger.debug(f"URL normalized: {url} -> {decoded_url}")
                return decoded_url

            return url

        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url

    def _create_session(self) -> requests.Session:
        """HTTPセッションを作成"""
        session = requests.Session()

        # リトライ戦略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def fetch_content(self, url: str, timeout: int = 10) -> tuple[str, str]:
        """URLからコンテンツを取得

        Returns:
            tuple: (raw_html, final_url)
        """
        try:
            # URL正規化
            normalized_url = self.normalize_url(url)
            if normalized_url != url:
                logger.info(f"Normalized URL: {url} -> {normalized_url}")

            logger.info(f"Fetching content from: {normalized_url}")

            def fetch():
                response = self.session.get(
                    normalized_url,
                    headers=self.headers,
                    timeout=timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response

            response = retry_with_backoff(
                fetch,
                max_retries=3,
                exceptions=(requests.RequestException,),
                step="content_fetch",
            )

            # エンコーディングの確認・修正
            if response.encoding is None:
                response.encoding = "utf-8"

            # コンテンツサイズチェック
            content_length = len(response.content)
            if content_length > 10 * 1024 * 1024:  # 10MB制限
                raise ContentFetchError(
                    f"Content too large: {content_length} bytes", url
                )

            logger.info(
                f"Content fetched successfully: {content_length} bytes, "
                f"final URL: {response.url}"
            )

            return response.text, str(response.url)

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout for URL: {normalized_url}"
            logger.error(error_msg)
            raise ContentFetchError(error_msg, normalized_url)

        except requests.exceptions.TooManyRedirects:
            error_msg = f"Too many redirects for URL: {normalized_url}"
            logger.error(error_msg)
            raise ContentFetchError(error_msg, normalized_url)

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed for URL {normalized_url}: {e}"
            logger.error(error_msg)
            raise ContentFetchError(error_msg, normalized_url)

        except Exception as e:
            error_msg = f"Unexpected error fetching {normalized_url}: {e}"
            logger.error(error_msg)
            raise ContentFetchError(error_msg, normalized_url)

    def fetch_multiple_contents(
        self, urls: list[str], delay: float = 1.0, timeout: int = 10
    ) -> dict[str, tuple[str, str]]:
        """複数URLからコンテンツを取得

        Returns:
            dict: {url: (raw_html, final_url)}
        """
        results = {}

        logger.info(f"Fetching content from {len(urls)} URLs")

        for i, url in enumerate(urls):
            try:
                raw_html, final_url = self.fetch_content(url, timeout)
                results[url] = (raw_html, final_url)

                # Rate limiting
                if i < len(urls) - 1:  # 最後のURL以外で待機
                    time.sleep(delay)

            except ContentFetchError as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                # 個別の失敗は無視して続行
                continue
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                continue

        logger.info(f"Successfully fetched {len(results)}/{len(urls)} URLs")
        return results

    def is_fetchable_url(self, url: str) -> bool:
        """URLが取得可能かヘッダーで確認"""
        try:
            response = self.session.head(
                url, headers=self.headers, timeout=5, allow_redirects=True
            )

            # 成功ステータスコードの確認
            if not response.ok:
                return False

            # Content-Typeの確認
            content_type = response.headers.get("content-type", "").lower()
            if not any(
                ct in content_type
                for ct in ["text/html", "text/plain", "application/xhtml"]
            ):
                logger.debug(f"Skipping non-HTML content: {content_type}")
                return False

            return True

        except Exception as e:
            logger.debug(f"URL not fetchable: {url} - {e}")
            return False

    def close(self):
        """セッションを閉じる"""
        if self.session:
            self.session.close()
            logger.info("Content fetcher session closed")

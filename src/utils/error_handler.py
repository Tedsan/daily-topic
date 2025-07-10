"""エラーハンドリング"""
import traceback
from typing import Any, Optional
from uuid import uuid4

from src.models import ProcessingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DailyTopicError(Exception):
    """Daily Topic システム基底例外"""

    def __init__(
        self, message: str, step: str = "unknown", job_id: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.step = step
        self.job_id = job_id or str(uuid4())


class SlackAPIError(DailyTopicError):
    """Slack API関連エラー"""

    def __init__(self, message: str, response: Optional[dict] = None):
        super().__init__(message, step="slack_api")
        self.response = response


class ClaudeAPIError(DailyTopicError):
    """Claude API関連エラー"""

    def __init__(self, message: str, response: Optional[dict] = None):
        super().__init__(message, step="claude_api")
        self.response = response


class ContentFetchError(DailyTopicError):
    """コンテンツ取得エラー"""

    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(message, step="content_fetch")
        self.url = url


class ContentParsingError(DailyTopicError):
    """コンテンツ解析エラー"""

    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(message, step="content_parsing")
        self.url = url


class CategoryClassificationError(DailyTopicError):
    """カテゴリ分類エラー"""

    def __init__(self, message: str, content: Optional[str] = None):
        super().__init__(message, step="category_classification")
        self.content = content


def create_processing_error(
    exception: Exception, step: str = "unknown", job_id: Optional[str] = None
) -> ProcessingError:
    """例外からProcessingErrorを作成"""
    error_type = type(exception).__name__
    message = str(exception)
    stack_trace = traceback.format_exc()

    if isinstance(exception, DailyTopicError):
        step = exception.step
        job_id = exception.job_id

    return ProcessingError(
        step=step,
        error_type=error_type,
        message=message,
        job_id=job_id,
        stack_trace=stack_trace,
    )


def handle_exception(
    exception: Exception,
    step: str = "unknown",
    job_id: Optional[str] = None,
    log_error: bool = True,
) -> ProcessingError:
    """例外を処理してProcessingErrorを返す"""
    processing_error = create_processing_error(exception, step, job_id)

    if log_error:
        logger.error(
            f"Error in step '{step}': {processing_error.error_type} - {processing_error.message}",
            extra={
                "job_id": processing_error.job_id,
                "step": step,
                "error_type": processing_error.error_type,
            },
        )
        logger.debug(f"Stack trace: {processing_error.stack_trace}")

    return processing_error


def retry_with_backoff(
    func: callable,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (Exception,),
    step: str = "unknown",
) -> Any:
    """指数バックオフでリトライ"""
    import time

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                # 最後の試行でも失敗
                logger.error(
                    f"Function failed after {max_retries} retries in step '{step}': {e}"
                )
                break

            # バックオフ待機
            wait_time = backoff_factor * (2**attempt)
            logger.warning(
                f"Attempt {attempt + 1} failed in step '{step}': {e}. "
                f"Retrying in {wait_time:.1f} seconds..."
            )
            time.sleep(wait_time)

    # すべてのリトライが失敗
    if last_exception:
        raise last_exception

    raise DailyTopicError(f"Function failed after {max_retries} retries", step=step)


async def async_retry_with_backoff(
    func: callable,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (Exception,),
    step: str = "unknown",
) -> Any:
    """非同期版: 指数バックオフでリトライ"""
    import asyncio

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                # 最後の試行でも失敗
                logger.error(
                    f"Function failed after {max_retries} retries in step '{step}': {e}"
                )
                break

            # バックオフ待機
            wait_time = backoff_factor * (2**attempt)
            logger.warning(
                f"Attempt {attempt + 1} failed in step '{step}': {e}. "
                f"Retrying in {wait_time:.1f} seconds..."
            )
            await asyncio.sleep(wait_time)

    # すべてのリトライが失敗
    if last_exception:
        raise last_exception

    raise DailyTopicError(f"Function failed after {max_retries} retries", step=step)

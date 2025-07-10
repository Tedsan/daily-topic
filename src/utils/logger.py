"""ログ管理"""
import logging
import sys
from typing import Optional

from src.config import get_config


class ColoredFormatter(logging.Formatter):
    """カラー付きログフォーマッター"""

    # ANSI カラーコード
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    COLORS = {
        logging.DEBUG: grey,
        logging.INFO: blue,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelno, self.grey)
        formatter = logging.Formatter(
            f"{log_color}%(asctime)s - %(name)s - %(levelname)s - %(message)s{self.reset}"
        )
        return formatter.format(record)


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """ロガーをセットアップ"""
    config = get_config()
    log_level = level or config.log_level

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 既存のハンドラーをクリア
    logger.handlers = []

    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if config.is_development():
        # 開発環境ではカラー付きフォーマッター
        console_handler.setFormatter(ColoredFormatter())
    else:
        # 本番環境では標準フォーマッター
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # 重複ログ防止
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """ロガーを取得"""
    return setup_logger(name)

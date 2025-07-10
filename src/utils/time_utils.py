"""時刻関連ユーティリティ"""
from datetime import UTC, datetime, timedelta, timezone

import pytz

from src.config import get_config


def get_jst_timezone() -> timezone:
    """JST タイムゾーンを取得"""
    return pytz.timezone("Asia/Tokyo")


def now_jst() -> datetime:
    """現在のJST時刻を取得"""
    jst = get_jst_timezone()
    return datetime.now(jst)


def utc_to_jst(utc_dt: datetime) -> datetime:
    """UTC時刻をJSTに変換"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=UTC)
    jst = get_jst_timezone()
    return utc_dt.astimezone(jst)


def jst_to_utc(jst_dt: datetime) -> datetime:
    """JST時刻をUTCに変換"""
    jst = get_jst_timezone()
    if jst_dt.tzinfo is None:
        jst_dt = jst.localize(jst_dt)
    return jst_dt.astimezone(UTC)


def get_24_hours_ago_jst() -> datetime:
    """24時間前のJST時刻を取得"""
    return now_jst() - timedelta(hours=24)


def get_lookback_time() -> datetime:
    """設定に基づいた過去時刻を取得"""
    config = get_config()
    return now_jst() - timedelta(hours=config.system.lookback_hours)


def slack_timestamp_to_datetime(ts: str) -> datetime:
    """SlackタイムスタンプをJST datetimeに変換"""
    # Slackタイムスタンプは秒単位のUNIX時刻（文字列）
    timestamp = float(ts)
    utc_dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return utc_to_jst(utc_dt)


def datetime_to_slack_timestamp(dt: datetime) -> str:
    """datetimeをSlackタイムスタンプに変換"""
    if dt.tzinfo is None:
        # タイムゾーン未指定の場合はJSTとして扱う
        jst = get_jst_timezone()
        dt = jst.localize(dt)

    utc_dt = dt.astimezone(UTC)
    return str(int(utc_dt.timestamp()))


def is_within_lookback_period(message_ts: str) -> bool:
    """メッセージが過去の指定時間内かどうか判定"""
    message_time = slack_timestamp_to_datetime(message_ts)
    lookback_time = get_lookback_time()
    return message_time >= lookback_time


def format_jst_datetime(dt: datetime, format_str: str = "%Y年%m月%d日 %H:%M") -> str:
    """JST時刻を日本語形式でフォーマット"""
    if dt.tzinfo is None:
        jst = get_jst_timezone()
        dt = jst.localize(dt)
    elif dt.tzinfo != get_jst_timezone():
        dt = dt.astimezone(get_jst_timezone())

    return dt.strftime(format_str)


def get_daily_stats_filename(date: datetime = None) -> str:
    """日次統計ファイル名を生成"""
    if date is None:
        date = now_jst()

    if date.tzinfo is None:
        jst = get_jst_timezone()
        date = jst.localize(date)
    elif date.tzinfo != get_jst_timezone():
        date = date.astimezone(get_jst_timezone())

    return f"stats/{date.strftime('%Y-%m')}.csv"


def get_monthly_stats_filename(date: datetime = None) -> str:
    """月次統計ファイル名を生成"""
    if date is None:
        date = now_jst()

    if date.tzinfo is None:
        jst = get_jst_timezone()
        date = jst.localize(date)
    elif date.tzinfo != get_jst_timezone():
        date = date.astimezone(get_jst_timezone())

    return f"stats/{date.strftime('%Y-%m')}.csv"


def is_scheduled_execution_time() -> bool:
    """スケジュール実行時刻（08:00 JST）かどうか判定"""
    current_time = now_jst()
    target_hour = 8
    target_minute = 0

    # 8:00-8:10の間をスケジュール実行時刻とする（GitHub Actionsの遅延考慮）
    return (
        current_time.hour == target_hour
        and target_minute <= current_time.minute <= target_minute + 10
    )

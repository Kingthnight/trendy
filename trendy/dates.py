from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Calcutta")
RECENT_DAYS = 7


def as_calcutta(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=TZ)
    return moment.astimezone(TZ)


def today(now: datetime | None = None) -> date:
    moment = as_calcutta(now or datetime.now(TZ))
    return moment.date()


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD") from exc


def week_bounds(day: date) -> tuple[date, date]:
    """Monday–Sunday calendar week that contains `day`."""
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=TZ)
    return start, start + timedelta(days=1)


def fetch_window(as_of: date, now: datetime) -> tuple[datetime, datetime] | None:
    """Half-open [start, end) covering the recent days and the as-of week.

    The end is capped at `now`, so a week that is still in progress includes
    only papers submitted so far. Returns None when the whole window is in
    the future.
    """
    now = as_calcutta(now)
    recent_start = as_of - timedelta(days=RECENT_DAYS)
    week_start, week_end = week_bounds(as_of)
    start_day = min(recent_start, week_start)
    end_day = max(as_of, week_end)
    start = datetime.combine(start_day, time.min, tzinfo=TZ)
    end_exclusive = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=TZ)
    end_exclusive = min(end_exclusive, now)
    if end_exclusive <= start:
        return None
    return start, end_exclusive


def arxiv_bounds(start: datetime, end_exclusive: datetime) -> tuple[str, str]:
    """Inclusive UTC minute stamps for an arXiv submittedDate query."""
    start_utc = start.astimezone(timezone.utc).replace(second=0, microsecond=0)
    last = (end_exclusive - timedelta(microseconds=1)).astimezone(timezone.utc)
    last_utc = last.replace(second=0, microsecond=0)
    if last_utc < start_utc:
        raise ValueError("empty arXiv range")
    return start_utc.strftime("%Y%m%d%H%M"), last_utc.strftime("%Y%m%d%H%M")

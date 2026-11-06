from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from trendy.dates import RECENT_DAYS, TZ, as_calcutta, day_bounds, week_bounds
from trendy.models import PaperSignals

MIN_DAY_PAPERS = 25
MIN_RECENT_PAPERS = 25
MOVE_PP = 4.0
MIN_TODAY_FOR_ROSE = 4
MIN_RECENT_FOR_FADE = 8
MIN_NEW_COUNT = 3
MIN_NEW_SHARE = 0.05
MAX_MOVES = 5
WEEK_MIN_SHARE = 0.04
WEEK_MIN_COUNT = 5
WEEK_MAX = 8
SNAPSHOT_MAX = 6


@dataclass(frozen=True)
class TopicStats:
    name: str
    count: int
    share: float


@dataclass(frozen=True)
class Move:
    name: str
    today_count: int
    today_share: float
    recent_count: int
    recent_share: float
    delta_pp: float


@dataclass(frozen=True)
class TrendReport:
    as_of: date
    generated_at: datetime
    week_start: date
    week_end: date
    day_in_progress: bool
    day_is_future: bool
    week_in_progress: bool
    today_count: int
    recent_start: date
    recent_end: date
    recent_count: int
    recent_daily: tuple[tuple[date, int], ...]
    compare_enabled: bool
    new_enabled: bool
    rose: tuple[Move, ...]
    faded: tuple[Move, ...]
    new: tuple[Move, ...]
    today_snapshot: tuple[TopicStats, ...]
    week_count: int
    week_top: tuple[TopicStats, ...]
    week_unclassified: int
    newest_submission: datetime | None


def _aware_submitted(paper: PaperSignals) -> datetime:
    submitted = paper.submitted
    if submitted.tzinfo is None:
        from datetime import timezone

        return submitted.replace(tzinfo=timezone.utc)
    return submitted


def _between(signals: list[PaperSignals], start: datetime, end: datetime) -> list[PaperSignals]:
    chosen: list[PaperSignals] = []
    for paper in signals:
        submitted = _aware_submitted(paper)
        if start <= submitted < end:
            chosen.append(paper)
    return chosen


def _tally(signals: list[PaperSignals]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paper in signals:
        for name in paper.topics:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _stats(signals: list[PaperSignals], *, minimum_share: float, minimum_count: int, limit: int) -> tuple[TopicStats, ...]:
    total = len(signals)
    if total == 0:
        return ()
    ranked = [
        TopicStats(name, count, count / total)
        for name, count in _tally(signals).items()
    ]
    ranked.sort(key=lambda item: (-item.count, item.name))
    chosen = [item for item in ranked if item.share >= minimum_share and item.count >= minimum_count]
    if not chosen and ranked and ranked[0].count > 0:
        chosen = [ranked[0]]
    return tuple(chosen[:limit])


def _snapshot(signals: list[PaperSignals]) -> tuple[TopicStats, ...]:
    total = len(signals)
    if total == 0:
        return ()
    ranked = [
        TopicStats(name, count, count / total)
        for name, count in _tally(signals).items()
    ]
    ranked.sort(key=lambda item: (-item.count, item.name))
    return tuple(ranked[:SNAPSHOT_MAX])


def _move(name: str, today_count: int, today_total: int, recent_count: int, recent_total: int) -> Move:
    today_share = today_count / today_total if today_total else 0.0
    recent_share = recent_count / recent_total if recent_total else 0.0
    return Move(
        name=name,
        today_count=today_count,
        today_share=today_share,
        recent_count=recent_count,
        recent_share=recent_share,
        delta_pp=(today_share - recent_share) * 100,
    )


def compute(as_of: date, now: datetime, signals: list[PaperSignals]) -> TrendReport:
    now = as_calcutta(now)
    week_start, week_end = week_bounds(as_of)
    recent_start = as_of - timedelta(days=RECENT_DAYS)
    recent_end = as_of - timedelta(days=1)
    day_start, day_end = day_bounds(as_of)
    week_start_dt, week_end_dt = day_bounds(week_start)[0], day_bounds(week_end)[1]
    recent_start_dt, _recent_next = day_bounds(recent_start)

    today = _between(signals, day_start, min(now, day_end))
    recent = _between(signals, recent_start_dt, day_start)
    week = _between(signals, week_start_dt, min(now, week_end_dt))

    daily: list[tuple[date, int]] = []
    for offset in range(RECENT_DAYS):
        day = recent_start + timedelta(days=offset)
        start, end = day_bounds(day)
        daily.append((day, len(_between(signals, start, min(end, now)))))

    today_counts = _tally(today)
    recent_counts = _tally(recent)
    names = set(today_counts) | set(recent_counts)
    moves = [
        _move(name, today_counts.get(name, 0), len(today), recent_counts.get(name, 0), len(recent))
        for name in names
    ]

    compare_enabled = len(today) >= MIN_DAY_PAPERS and len(recent) >= MIN_RECENT_PAPERS
    new_enabled = len(today) >= MIN_DAY_PAPERS
    rose: list[Move] = []
    faded: list[Move] = []
    fresh: list[Move] = []
    if compare_enabled:
        rose = [
            item
            for item in moves
            if item.recent_count > 0
            and item.today_count >= MIN_TODAY_FOR_ROSE
            and item.delta_pp >= MOVE_PP
        ]
        rose.sort(key=lambda item: (-item.delta_pp, -item.today_count, item.name))
        faded = [
            item
            for item in moves
            if item.recent_count >= MIN_RECENT_FOR_FADE and item.delta_pp <= -MOVE_PP
        ]
        faded.sort(key=lambda item: (item.delta_pp, -item.recent_count, item.name))
    if new_enabled:
        fresh = [
            item
            for item in moves
            if item.recent_count == 0
            and item.today_count >= MIN_NEW_COUNT
            and item.today_share >= MIN_NEW_SHARE
        ]
        fresh.sort(key=lambda item: (-item.today_count, item.name))

    unclassified = sum(1 for paper in week if not paper.topics)
    submitted_times = [_aware_submitted(paper) for paper in signals if _aware_submitted(paper) < now]
    newest = max(submitted_times) if submitted_times else None
    return TrendReport(
        as_of=as_of,
        generated_at=now,
        week_start=week_start,
        week_end=week_end,
        day_in_progress=day_start <= now < day_end,
        day_is_future=now < day_start,
        week_in_progress=now < week_end_dt,
        today_count=len(today),
        recent_start=recent_start,
        recent_end=recent_end,
        recent_count=len(recent),
        recent_daily=tuple(daily),
        compare_enabled=compare_enabled,
        new_enabled=new_enabled,
        rose=tuple(rose[:MAX_MOVES]),
        faded=tuple(faded[:MAX_MOVES]),
        new=tuple(fresh[:MAX_MOVES]),
        today_snapshot=_snapshot(today) if len(today) < MIN_DAY_PAPERS else (),
        week_count=len(week),
        week_top=_stats(week, minimum_share=WEEK_MIN_SHARE, minimum_count=WEEK_MIN_COUNT, limit=WEEK_MAX),
        week_unclassified=unclassified,
        newest_submission=newest,
    )

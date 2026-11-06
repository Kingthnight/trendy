from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from trendy.dates import RECENT_DAYS, TZ, week_bounds
from trendy.trends import (
    MIN_DAY_PAPERS,
    MIN_NEW_COUNT,
    MIN_NEW_SHARE,
    MOVE_PP,
    WEEK_MIN_SHARE,
    Move,
    TopicStats,
    TrendReport,
)

ROOT = Path(__file__).resolve().parents[1]
_PAPER_LINK = re.compile(r"arxiv\.org/(?:abs|pdf|html)/", re.IGNORECASE)
_PAPER_ID = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")


def report_path(as_of: date) -> Path:
    monday, sunday = week_bounds(as_of)
    name = f"{as_of.isoformat()}_week-{monday.isoformat()}_to_{sunday.isoformat()}.md"
    directory = (ROOT / "reports").resolve()
    path = (directory / name).resolve()
    if path.parent != directory:
        raise RuntimeError("Refusing to write outside reports/")
    return path


def ensure_aggregate(text: str) -> None:
    if _PAPER_LINK.search(text) or _PAPER_ID.search(text):
        raise RuntimeError("Refusing to write a report that contains paper records")


def _long_date(day: date) -> str:
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"


def _month_date(day: date) -> str:
    return f"{day.day} {day.strftime('%B %Y')}"


def _stamp(moment) -> str:
    local = moment.astimezone(TZ)
    return f"{local.strftime('%A')} {local.day} {local.strftime('%B %Y')} {local.strftime('%H:%M')} IST"


def _pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def _num(value: int) -> str:
    return f"{value:,}"


def _daily(report: TrendReport) -> str:
    parts = [f"{day.day} {day.strftime('%b')} {count}" for day, count in report.recent_daily]
    return ", ".join(parts)


def _snapshot_line(report: TrendReport) -> str:
    if not report.today_snapshot:
        return "None of the tracked themes matched those papers."
    bits = [f"{item.name} ({item.count})" for item in report.today_snapshot]
    if report.day_in_progress:
        return "Topics among the papers so far: " + ", ".join(bits) + "."
    return "Topics among the day's papers: " + ", ".join(bits) + "."


def _move_line(item: Move, *, fresh: bool) -> str:
    if fresh:
        return (
            f"- **{item.name}** — {_pct(item.today_share)} of today's papers "
            f"({_num(item.today_count)}), with none in the previous {RECENT_DAYS} days."
        )
    return (
        f"- **{item.name}** — {_pct(item.today_share)} today ({_num(item.today_count)}), "
        f"against {_pct(item.recent_share)} over the recent days ({item.delta_pp:+.1f} points)."
    )


def _list_section(title: str, items: tuple[Move, ...], empty: str, *, fresh: bool) -> list[str]:
    lines = [f"### {title}", ""]
    if not items:
        lines.append(empty)
    else:
        lines.extend(_move_line(item, fresh=fresh) for item in items)
    lines.append("")
    return lines


def _week_prose(top: tuple[TopicStats, ...]) -> str:
    shown = list(top[:3])
    if not shown:
        return f"No tracked theme covered at least {WEEK_MIN_SHARE * 100:.0f}% of the week."
    bits = [f"{item.name} ({_pct(item.share)})" for item in shown]
    if len(bits) == 1:
        lead = bits[0]
    elif len(bits) == 2:
        lead = f"{bits[0]} and {bits[1]}"
    else:
        lead = ", ".join(bits[:-1]) + f", and {bits[-1]}"
    return f"The popular themes are {lead}."


def _week_table(top: tuple[TopicStats, ...]) -> list[str]:
    if not top:
        return []
    lines = ["| Theme | Papers | Share |", "| --- | ---: | ---: |"]
    for item in top:
        lines.append(f"| {item.name} | {_num(item.count)} | {_pct(item.share)} |")
    return lines


def render(report: TrendReport) -> str:
    rule = (
        f"Rises and fades are shifts of at least {MOVE_PP:.0f} percentage points versus "
        f"the previous {RECENT_DAYS} days, reported only when today has at least {MIN_DAY_PAPERS} papers "
        f"and those days have at least {MIN_DAY_PAPERS} too. A new topic has none in that window, "
        f"at least {MIN_NEW_COUNT} papers today, and at least {MIN_NEW_SHARE:.0%} of today."
    )
    today_phrase = (
        f"{_num(report.today_count)} papers so far"
        if report.day_in_progress
        else f"{_num(report.today_count)} papers"
    )
    average = report.recent_count / RECENT_DAYS
    lines = [
        "# TrendY",
        "",
        "cs.LG topic trends from the live arXiv API. Aggregates only: no paper titles, abstracts, or ids.",
        "",
        f"- Run date: {_long_date(report.as_of)} (Asia/Calcutta)",
        f"- Generated: {_stamp(report.generated_at)}",
        f"- Week: Monday {_month_date(report.week_start)} – Sunday {_month_date(report.week_end)}",
        "",
        "A paper can match more than one theme, so shares overlap and do not sum to 100%. "
        f"The day baseline is the pooled share across the previous {RECENT_DAYS} calendar days.",
        "",
        "## Day trend",
        "",
        (
            f"{_long_date(report.as_of)} against the previous {RECENT_DAYS} days "
            f"({_month_date(report.recent_start)} – {_month_date(report.recent_end)})."
        ),
        "",
    ]

    if report.day_is_future:
        lines.append(
            "This date is still in the future in Asia/Calcutta, so there are no submissions to compare. "
            "Nothing rose, nothing faded, and nothing is new."
        )
        lines.append("")
    else:
        lines.extend(
            [
                f"- Today: {today_phrase}.",
                f"- Recent run: {_num(report.recent_count)} papers (about {average:.0f} a day).",
                f"- Recent daily counts: {_daily(report)}.",
                "",
                rule,
                "",
            ]
        )
        if report.today_count < MIN_DAY_PAPERS:
            if report.today_count == 0:
                newest = report.newest_submission
                if newest is not None and newest.astimezone(TZ).date() < report.as_of:
                    lines.append(
                        "No cs.LG submissions on this date are in the API. "
                        f"The newest one returned is {_stamp(newest)}, which is before this day, "
                        "so nothing rose, faded, or is new."
                    )
                else:
                    lines.append("No cs.LG papers on this date, so nothing rose, faded, or is new.")
            else:
                lines.append(
                    f"Not called. Today has {_num(report.today_count)} "
                    f"{'papers so far' if report.day_in_progress else 'papers'}, "
                    f"and these calls need at least {MIN_DAY_PAPERS}."
                )
                lines.append("")
                lines.append(_snapshot_line(report))
            lines.append("")
        else:
            if report.compare_enabled:
                lines.extend(
                    _list_section(
                        "Rose",
                        report.rose,
                        f"No topic rose by {MOVE_PP:.0f} points or more.",
                        fresh=False,
                    )
                )
                lines.extend(
                    _list_section(
                        "Faded",
                        report.faded,
                        f"No topic faded by {MOVE_PP:.0f} points or more.",
                        fresh=False,
                    )
                )
            else:
                lines.extend(
                    [
                        "### Rose",
                        "",
                        f"Not called. The previous {RECENT_DAYS} days have only {_num(report.recent_count)} papers.",
                        "",
                        "### Faded",
                        "",
                        f"Not called. The previous {RECENT_DAYS} days have only {_num(report.recent_count)} papers.",
                        "",
                    ]
                )
            if report.new_enabled:
                lines.extend(
                    _list_section(
                        "New",
                        report.new,
                        f"No topic was new relative to the previous {RECENT_DAYS} days.",
                        fresh=True,
                    )
                )

    lines.extend(["## Week trend", ""])
    if report.week_in_progress:
        if report.newest_submission is None:
            lines.append(
                f"Requested through {_stamp(report.generated_at)}. The week is still in progress."
            )
        else:
            lines.append(
                f"Requested through {_stamp(report.generated_at)}. "
                f"The newest cs.LG submission the API returned is {_stamp(report.newest_submission)}. "
                "The week is still in progress."
            )
    else:
        lines.append(
            f"Monday {_month_date(report.week_start)} – Sunday {_month_date(report.week_end)} is complete."
        )
    if report.week_count == 0:
        lines.append("")
        lines.append("No cs.LG papers in this week window.")
        lines.append("")
    else:
        lines.append(f"{_num(report.week_count)} papers.")
        lines.append("")
        lines.append(_week_prose(report.week_top))
        table = _week_table(report.week_top)
        if table:
            lines.append("")
            lines.extend(table)
        share = report.week_unclassified / report.week_count
        lines.append("")
        lines.append(
            f"{_pct(share)} of this week's papers matched none of the tracked themes."
        )
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    ensure_aggregate(text)
    return text

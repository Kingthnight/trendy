from __future__ import annotations

import argparse
import sys
from datetime import datetime

from trendy.arxiv_client import ArxivError, fetch_signals
from trendy.dates import TZ, fetch_window, parse_date, today
from trendy.report import render, report_path
from trendy.trends import compute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trendy",
        description="Report how cs.LG topics are moving, using the arXiv API as a live source.",
    )
    parser.add_argument(
        "--date",
        help="As-of date in Asia/Calcutta, YYYY-MM-DD. Default: today.",
    )
    args = parser.parse_args(argv)

    now = datetime.now(TZ)
    try:
        as_of = parse_date(args.date) if args.date else today(now)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    window = fetch_window(as_of, now)
    try:
        signals = [] if window is None else fetch_signals(*window)
        text = render(compute(as_of, now, signals))
    except ArxivError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    path = report_path(as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    print(f"Saved {path}", file=sys.stderr)
    return 0

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from trendy.arxiv_client import ArxivError, fetch_signals as fetch_arxiv_signals
from trendy.dates import TZ, daily_source_dates, fetch_window, parse_date, today
from trendy.hf_client import HfError, fetch_signals as fetch_hf_signals
from trendy.report import render_document, report_path
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
        hf_signals = fetch_hf_signals(daily_source_dates(as_of, now))
        arxiv_signals = [] if window is None else fetch_arxiv_signals(*window)
        text = render_document(
            [
                ("arXiv cs.LG", "cs.LG submission", compute(as_of, now, arxiv_signals)),
                (
                    "Hugging Face Daily Papers",
                    "Hugging Face daily paper",
                    compute(as_of, now, hf_signals),
                ),
            ]
        )
    except (ArxivError, HfError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    path = report_path(as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    print(f"Saved {path}", file=sys.stderr)
    return 0

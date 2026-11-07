from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
import re
import sys
import time as time_module
import urllib.error
import urllib.parse
import urllib.request

from trendy.dates import TZ
from trendy.models import PaperSignals
from trendy.topics import match_topics

API_URL = "https://huggingface.co/api/daily_papers"
USER_AGENT = "TrendY/1.0 (local trend report; huggingface daily papers)"
MAX_PAGES = 5
_NEXT = re.compile(r"<([^>]+)>\s*;\s*rel=\"?next\"?", re.IGNORECASE)


class HfError(RuntimeError):
    pass


def next_page_url(link_header: str | None) -> str | None:
    """Return the next daily_papers page, only if it stays on this API."""
    if not link_header:
        return None
    match = _NEXT.search(link_header)
    if match is None:
        return None
    parsed = urllib.parse.urlparse(match.group(1))
    if parsed.scheme != "https" or parsed.netloc != "huggingface.co":
        return None
    if parsed.path.rstrip("/") != "/api/daily_papers":
        return None
    return match.group(1)


def _parse_time(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _feature_time(raw: object, day: date) -> datetime:
    parsed = _parse_time(raw) if isinstance(raw, str) else None
    if parsed is not None and parsed.astimezone(TZ).date() == day:
        return parsed
    return datetime.combine(day, time.min, tzinfo=TZ)


def _rows_from_payload(payload: bytes, day: date) -> list[tuple[str, PaperSignals]]:
    """Parse one page. The id is only for de-duplication and is not kept on the signal."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HfError("Hugging Face returned data that could not be parsed") from exc
    if data is None:
        return []
    if not isinstance(data, list):
        raise HfError("Hugging Face daily papers response was not a list")

    rows: list[tuple[str, PaperSignals]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
        paper_id = str(paper.get("id") or f"row-{index}")
        title = str(paper.get("title") or item.get("title") or "")
        summary = str(paper.get("summary") or item.get("summary") or "")
        submitted = _feature_time(paper.get("submittedOnDailyAt"), day)
        topics = match_topics(title, summary)
        del title, summary
        rows.append((paper_id, PaperSignals(submitted=submitted, topics=topics)))
    return rows


def signals_from_payload(payload: bytes, day: date) -> list[PaperSignals]:
    """Turn one JSON page into topic signals. Titles, abstracts, and ids are dropped."""
    seen: set[str] = set()
    signals: list[PaperSignals] = []
    for paper_id, signal in _rows_from_payload(payload, day):
        if paper_id in seen:
            continue
        seen.add(paper_id)
        signals.append(signal)
    return signals


def _get(url: str) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
                return payload, next_page_url(response.headers.get("Link"))
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 404:
                return b"[]", None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise HfError(f"Hugging Face daily papers returned HTTP {exc.code}") from exc
            time_module.sleep(5 * (attempt + 1))
        except urllib.error.URLError as exc:
            if attempt == 2:
                raise HfError("Hugging Face daily papers request failed") from exc
            time_module.sleep(5 * (attempt + 1))
    raise HfError("Hugging Face daily papers request failed")


def fetch_signals(days: list[date]) -> list[PaperSignals]:
    """One daily_papers request per calendar day, plus further pages when the API links them."""
    signals: list[PaperSignals] = []
    for day in days:
        url: str | None = f"{API_URL}?date={day.isoformat()}"
        seen: set[str] = set()
        day_count = 0
        finished = False
        for _page in range(MAX_PAGES):
            if url is None:
                finished = True
                break
            payload, next_url = _get(url)
            rows = _rows_from_payload(payload, day)
            if not rows:
                finished = True
                break
            for paper_id, signal in rows:
                if paper_id in seen:
                    continue
                seen.add(paper_id)
                signals.append(signal)
                day_count += 1
            if not next_url:
                finished = True
                break
            url = next_url
        if not finished:
            raise HfError("Hugging Face daily papers paging did not finish.")
        print(f"Hugging Face {day.isoformat()}: {day_count} papers.", file=sys.stderr)
    return signals

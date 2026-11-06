from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from trendy.dates import arxiv_bounds
from trendy.models import PaperSignals
from trendy.topics import match_topics

API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "TrendY/1.0 (https://github.com/KoushikLr/trendy; topic trends only)"
ATOM = "http://www.w3.org/2005/Atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"
PAGE_SIZE = 100
MAX_PAGES = 40
PAUSE_SECONDS = 3.0


class ArxivError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Row:
    paper_id: str
    signal: PaperSignals | None


def _text(parent: ET.Element, tag: str) -> str:
    node = parent.find(f"{{{ATOM}}}{tag}")
    if node is None or node.text is None:
        return ""
    return node.text


def _canonical_id(raw: str) -> str:
    token = raw.strip().rstrip("/").rsplit("/", 1)[-1]
    head, sep, tail = token.rpartition("v")
    if sep and head and tail.isdigit():
        return head
    return token


def _parse_time(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def signals_from_feed(
    xml_bytes: bytes,
    start: datetime,
    end_exclusive: datetime,
) -> tuple[int | None, list[_Row]]:
    """Parse one Atom page into topic signals. Titles and abstracts are dropped."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ArxivError("arXiv returned XML that could not be parsed") from exc

    total_node = root.find(f"{{{OPENSEARCH}}}totalResults")
    total: int | None
    if total_node is None or total_node.text is None:
        total = None
    else:
        total = int(total_node.text)

    rows: list[_Row] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        paper_id = _canonical_id(_text(entry, "id"))
        if not paper_id:
            continue
        published = _parse_time(_text(entry, "published"))
        categories = [
            node.attrib.get("term", "")
            for node in entry.findall(f"{{{ATOM}}}category")
        ]
        title = _text(entry, "title")
        summary = _text(entry, "summary")
        in_window = (
            published is not None
            and "cs.LG" in categories
            and start <= published < end_exclusive
        )
        signal = (
            PaperSignals(submitted=published, topics=match_topics(title, summary))
            if in_window and published is not None
            else None
        )
        del title, summary
        rows.append(_Row(paper_id, signal))
    return total, rows


def _query_url(search_query: str, start_index: int) -> str:
    params = urllib.parse.urlencode(
        {
            "search_query": search_query,
            "start": start_index,
            "max_results": PAGE_SIZE,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
    )
    return f"{API_URL}?{params}"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ArxivError(f"arXiv API returned HTTP {exc.code}") from exc
            time.sleep(10 * (attempt + 1))
        except urllib.error.URLError as exc:
            if attempt == 2:
                raise ArxivError("arXiv API request failed") from exc
            time.sleep(5 * (attempt + 1))
    raise ArxivError("arXiv API request failed")


def fetch_signals(start: datetime, end_exclusive: datetime) -> list[PaperSignals]:
    """Pull cs.LG submissions in [start, end) and keep topic hits only."""
    start_minute, end_minute = arxiv_bounds(start, end_exclusive)
    search_query = f"cat:cs.LG AND submittedDate:[{start_minute} TO {end_minute}]"
    print("Fetching cs.LG submissions from the arXiv API...", file=sys.stderr)

    seen: set[str] = set()
    signals: list[PaperSignals] = []
    start_index = 0
    total: int | None = None
    finished = False

    for page in range(MAX_PAGES):
        if page:
            time.sleep(PAUSE_SECONDS)
        page_total, rows = signals_from_feed(
            _get(_query_url(search_query, start_index)),
            start,
            end_exclusive,
        )
        if total is None:
            total = page_total
        fresh = 0
        for row in rows:
            if row.paper_id in seen:
                continue
            seen.add(row.paper_id)
            fresh += 1
            if row.signal is not None:
                signals.append(row.signal)
        start_index += len(rows)
        print(
            f"Page {page + 1}: {len(signals)} papers in range so far.",
            file=sys.stderr,
        )
        if not rows or fresh == 0 or len(rows) < PAGE_SIZE:
            if fresh == 0 and rows and total is not None and start_index < total:
                raise ArxivError("arXiv repeated a page before the result set was finished.")
            finished = True
            break
        if total is not None and start_index >= total:
            finished = True
            break

    if not finished:
        raise ArxivError("The arXiv result set exceeded the page cap, so no report was written.")
    return signals

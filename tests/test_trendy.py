from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest

from trendy.arxiv_client import signals_from_feed
from trendy.dates import TZ, arxiv_bounds, daily_source_dates, fetch_window, week_bounds
from trendy.hf_client import next_page_url, signals_from_payload
from trendy.models import PaperSignals
from trendy.report import ensure_aggregate, render, render_document, report_path
from trendy.topics import match_topics
from trendy.trends import compute


def paper(day: date, hour: int, topics: set[str]) -> PaperSignals:
    submitted = datetime(day.year, day.month, day.day, hour, 0, tzinfo=TZ)
    return PaperSignals(submitted, frozenset(topics))


class DateTests(unittest.TestCase):
    def test_week_containing_saturday(self) -> None:
        monday, sunday = week_bounds(date(2026, 11, 7))
        self.assertEqual(monday, date(2026, 11, 2))
        self.assertEqual(sunday, date(2026, 11, 8))
        self.assertEqual(monday.weekday(), 0)
        self.assertEqual(sunday.weekday(), 6)

    def test_early_saturday_window_stops_at_now(self) -> None:
        now = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        window = fetch_window(date(2026, 11, 7), now)
        self.assertIsNotNone(window)
        assert window is not None
        start, end = window
        self.assertEqual(start, datetime(2026, 10, 31, 0, 0, tzinfo=TZ))
        self.assertEqual(end, now)

    def test_future_window_is_empty(self) -> None:
        now = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        self.assertIsNone(fetch_window(date(2026, 11, 20), now))

    def test_past_week_is_complete(self) -> None:
        now = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        window = fetch_window(date(2026, 10, 15), now)
        self.assertIsNotNone(window)
        assert window is not None
        start, end = window
        self.assertEqual(start, datetime(2026, 10, 8, 0, 0, tzinfo=TZ))
        self.assertEqual(end, datetime(2026, 10, 19, 0, 0, tzinfo=TZ))

    def test_daily_source_stops_at_today(self) -> None:
        now = datetime(2026, 11, 7, 8, 49, tzinfo=TZ)
        days = daily_source_dates(date(2026, 11, 7), now)
        self.assertEqual(days[0], date(2026, 10, 31))
        self.assertEqual(days[-1], date(2026, 11, 7))
        self.assertNotIn(date(2026, 11, 8), days)

    def test_future_daily_source_has_no_days(self) -> None:
        now = datetime(2026, 11, 7, 8, 49, tzinfo=TZ)
        self.assertEqual(daily_source_dates(date(2026, 11, 20), now), [])

    def test_arxiv_minutes_use_utc(self) -> None:
        start = datetime(2026, 11, 2, 0, 0, tzinfo=TZ)
        end = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        self.assertEqual(arxiv_bounds(start, end), ("202611011830", "202611061909"))


class HuggingFaceTests(unittest.TestCase):
    def test_page_drops_text_and_duplicate_ids(self) -> None:
        payload = """
        [
          {
            "title": "Graph neural networks for weather",
            "summary": "This note proposes a graph neural network.",
            "paper": {
              "id": "9999.00001",
              "title": "Graph neural networks for weather",
              "summary": "This note proposes a graph neural network.",
              "submittedOnDailyAt": "2026-11-06T04:00:00Z"
            }
          },
          {
            "title": "Graph neural networks for weather again",
            "paper": {
              "id": "9999.00001",
              "title": "duplicate listing",
              "summary": "duplicate graph neural network",
              "submittedOnDailyAt": "2026-11-06T05:00:00Z"
            }
          }
        ]
        """.encode()
        signals = signals_from_payload(payload, date(2026, 11, 6))
        self.assertEqual(len(signals), 1)
        self.assertIn("Graph learning", signals[0].topics)
        self.assertEqual(signals[0].submitted.astimezone(TZ).date(), date(2026, 11, 6))
        blob = repr(signals[0])
        self.assertNotIn("weather", blob.lower())
        self.assertNotIn("proposes", blob.lower())
        self.assertNotIn("9999.00001", blob)

    def test_next_page_stays_on_the_api(self) -> None:
        header = '<https://huggingface.co/api/daily_papers?date=2026-11-06&p=1>; rel="next"'
        self.assertEqual(
            next_page_url(header),
            "https://huggingface.co/api/daily_papers?date=2026-11-06&p=1",
        )
        self.assertIsNone(
            next_page_url('<https://example.com/api/daily_papers?p=1>; rel="next"')
        )


class TopicTests(unittest.TestCase):
    def test_llm_and_hyphenated_reasoning(self) -> None:
        self.assertIn("Large language models", match_topics("A survey", "large language models"))
        self.assertIn("Reasoning", match_topics("Chain-of-thought for math", ""))

    def test_rl_agent_is_not_labeled_as_an_agent_paper(self) -> None:
        topics = match_topics(
            "Policy gradient methods for continuous control",
            "The agent learns a policy by reinforcement learning.",
        )
        self.assertIn("Reinforcement learning", topics)
        self.assertNotIn("Agents", topics)

    def test_benchmark_is_title_only(self) -> None:
        self.assertNotIn(
            "Evaluation",
            match_topics("A new optimizer", "We benchmark the method on three suites."),
        )
        self.assertIn("Evaluation", match_topics("A benchmark for planners", "Details."))

    def test_graph_phrase(self) -> None:
        self.assertIn(
            "Graph learning",
            match_topics("Graph neural networks for weather", "A short note."),
        )

    def test_matcher_returns_names_only(self) -> None:
        found = match_topics("Secret Title XYZ", "secret abstract xyz")
        self.assertEqual(found, frozenset())


class FeedTests(unittest.TestCase):
    def test_feed_keeps_topics_and_drops_text(self) -> None:
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>3</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/9999.00001v1</id>
    <published>2026-11-02T04:00:00Z</published>
    <title>Graph neural networks for weather</title>
    <summary>This note proposes a graph neural network.</summary>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/9999.00002v2</id>
    <published>2026-11-02T05:00:00Z</published>
    <title>Only another archive</title>
    <summary>Not machine learning.</summary>
    <category term="cs.CL"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/9999.00003v1</id>
    <published>2026-11-03T00:00:00Z</published>
    <title>Graph neural networks tomorrow</title>
    <summary>Outside the window.</summary>
    <category term="cs.LG"/>
  </entry>
</feed>
"""
        start = datetime(2026, 11, 2, 0, 0, tzinfo=TZ)
        end = datetime(2026, 11, 3, 0, 0, tzinfo=TZ)
        total, rows = signals_from_feed(xml, start, end)
        self.assertEqual(total, 3)
        kept = [row for row in rows if row.signal is not None]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].paper_id, "9999.00001")
        self.assertIsNotNone(kept[0].signal)
        assert kept[0].signal is not None
        self.assertIn("Graph learning", kept[0].signal.topics)
        blob = repr(kept[0].signal)
        self.assertNotIn("weather", blob.lower())
        self.assertNotIn("proposes", blob.lower())


class TrendTests(unittest.TestCase):
    def test_calcutta_date_not_utc_date(self) -> None:
        # 19:00 UTC on 6 Nov is 00:30 IST on 7 Nov.
        late = PaperSignals(
            datetime(2026, 11, 6, 19, 0, tzinfo=timezone.utc),
            frozenset({"Agents"}),
        )
        now = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        report = compute(date(2026, 11, 7), now, [late])
        self.assertEqual(report.today_count, 1)
        self.assertEqual(report.recent_count, 0)
        self.assertEqual(report.week_count, 1)

        friday = PaperSignals(
            datetime(2026, 11, 6, 18, 0, tzinfo=timezone.utc),
            frozenset({"Agents"}),
        )
        report = compute(date(2026, 11, 7), now, [friday])
        self.assertEqual(report.today_count, 0)
        self.assertEqual(report.recent_count, 1)
        self.assertEqual(report.week_count, 1)

    def test_rose_faded_and_new(self) -> None:
        signals: list[PaperSignals] = []
        recent_start = date(2026, 10, 31)
        for offset in range(7):
            day = recent_start + timedelta(days=offset)
            for _ in range(10):
                signals.append(
                    paper(day, 12, {"Large language models", "Diffusion and generative models"})
                )
        for _ in range(30):
            signals.append(paper(date(2026, 11, 7), 15, {"Agents"}))
        for _ in range(10):
            signals.append(paper(date(2026, 11, 7), 16, {"Large language models"}))

        now = datetime(2026, 11, 7, 18, 0, tzinfo=TZ)
        report = compute(date(2026, 11, 7), now, signals)
        self.assertTrue(report.compare_enabled)
        self.assertEqual(report.rose, ())
        self.assertIn("Agents", [item.name for item in report.new])
        faded = {item.name for item in report.faded}
        self.assertIn("Diffusion and generative models", faded)
        self.assertIn("Large language models", faded)
        self.assertEqual(report.week_count, 90)
        self.assertEqual(report.week_top[0].name, "Large language models")

        text = render(report)
        self.assertIn("### Rose", text)
        self.assertIn("### Faded", text)
        self.assertIn("### New", text)
        self.assertIn("Diffusion and generative models", text)
        ensure_aggregate(text)
        self.assertNotIn("arxiv.org", text.lower())

    def test_empty_day_reports_newest_indexed_submission(self) -> None:
        # 18:59 UTC on 5 Nov is 00:29 IST on 6 Nov, before Saturday.
        old = PaperSignals(
            datetime(2026, 11, 5, 18, 59, tzinfo=timezone.utc),
            frozenset({"Large language models"}),
        )
        now = datetime(2026, 11, 7, 0, 44, tzinfo=TZ)
        text = render(compute(date(2026, 11, 7), now, [old]))
        self.assertIn("Friday 6 November 2026 00:29 IST", text)
        self.assertIn("nothing rose, faded, or is new", text)
        self.assertNotIn("### Rose", text)
        ensure_aggregate(text)

    def test_early_day_does_not_call_moves(self) -> None:
        signals = [paper(date(2026, 11, 7), 0, {"Healthcare and life sciences"})]
        now = datetime(2026, 11, 7, 0, 40, tzinfo=TZ)
        report = compute(date(2026, 11, 7), now, signals)
        text = render(report)
        self.assertIn("Not called", text)
        self.assertNotIn("### Rose", text)
        self.assertIn("Healthcare and life sciences (1)", text)
        self.assertNotIn("arxiv.org", text.lower())
        ensure_aggregate(text)

    def test_document_has_both_sources(self) -> None:
        now = datetime(2026, 11, 7, 8, 49, tzinfo=TZ)
        arxiv = compute(
            date(2026, 11, 7),
            now,
            [paper(date(2026, 11, 6), 12, {"Large language models"})],
        )
        hf = compute(
            date(2026, 11, 7),
            now,
            [paper(date(2026, 11, 5), 12, {"Agents"})],
        )
        text = render_document(
            [
                ("arXiv cs.LG", "cs.LG submission", arxiv),
                ("Hugging Face Daily Papers", "Hugging Face daily paper", hf),
            ]
        )
        self.assertIn("## arXiv cs.LG", text)
        self.assertIn("## Hugging Face Daily Papers", text)
        self.assertEqual(text.count("### Day trend"), 2)
        self.assertEqual(text.count("### Week trend"), 2)
        self.assertIn("Agents", text)
        ensure_aggregate(text)
        self.assertNotIn("huggingface.co/papers", text.lower())

    def test_report_path_names_the_date_and_week(self) -> None:
        path = report_path(date(2026, 11, 7))
        self.assertEqual(path.name, "2026-11-07_week-2026-11-02_to_2026-11-08.md")
        self.assertEqual(path.parent.name, "reports")

    def test_rejects_paper_ids(self) -> None:
        with self.assertRaises(RuntimeError):
            ensure_aggregate("see 2611.02112 for the paper\n")


if __name__ == "__main__":
    unittest.main()

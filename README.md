# TrendY

Short trend reports for two public sources:

- arXiv's Machine Learning section (`cs.LG`), from the [arXiv API](https://export.arxiv.org/api/help)
- [Hugging Face Daily Papers](https://huggingface.co/papers), from `GET https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`

Each run scores a fixed list of AI/ML themes in memory and writes one short report. For each source the report has:

- **Day trend** for the chosen date (default: today in Asia/Calcutta). It compares that day's papers with the previous 7 calendar days and says what rose, what faded, and what is new.
- **Week trend** for the Monday–Sunday week that contains that date: the popular themes.

The report is the only file written. Titles, abstracts, author names, and paper ids are not saved.

## Run

Python 3.9 or newer. No third-party packages. Run it from this directory:

```bash
python3 -m trendy
python3 -m trendy --date 2026-11-07
```

The command prints the report and saves it to:

```text
reports/<YYYY-MM-DD>_week-<monday>_to_<sunday>.md
```

Running the same date again overwrites that file. A run takes a few minutes, because TrendY pages `export.arxiv.org` and waits 3 seconds between those requests.

Hugging Face is one request per Asia/Calcutta calendar day, for the previous 7 days and for the Monday–Sunday week, stopping at today when the week is still in progress. If that API links a next page, TrendY follows it. No API key is used.

## Dates

Dates use Asia/Calcutta, including when the machine's clock is set somewhere else.

The week is Monday through Sunday. If that week is still in progress, the week trend includes papers submitted so far and stops at the current time. The day trend uses that calendar day only. Papers that have not been submitted yet are not in the report.

Rises and fades are shifts of at least 4 percentage points against the pooled share of the previous 7 days. They are reported only when the day has at least 25 papers, so a day that has barely started is not compared with full recent days. A topic is new when it has no matches in those 7 days, at least 3 papers on the day, and at least 5% of that day.

Themes are multi-label. A paper can count toward more than one theme, so the shares overlap.

The arXiv API sometimes lags the clock. The report names the newest submission the API actually returned, so an empty day is not mistaken for a shift in topics.

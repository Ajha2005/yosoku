# Decisions

These six choices shape the dataset and every result built on it. They are fixed before any data is
used, so later work cannot quietly bend them to fit the results. To change one, add a row to the
change log at the bottom, say why, and rerun everything that depends on it.

## 1. Title universe

- **Collected:** Japanese anime (AniList country of origin JP) in TV, TV short, ONA and movie formats,
  no adult titles. The 50 most popular of each season, 2019–2025: about 1,400 titles. These are the
  defaults of `collect_titles.py`.
- **Slow sources:** YouTube and Google Trends cover the 200 most popular of those (`--limit 200`).
- **Upcoming titles** for live forecasts go in `data/upcoming/` (`--data-dir data/upcoming`), never in `data/`.
- **Known bias:** choosing by popularity favours hits. Every result is also reported by segment:
  new show vs sequel, genre, source material.

## 2. Target: the India Demand Index

- Measured over days 0–27 after the Japanese start date (the deck's "week 4").
- Four parts, each turned into a percentile rank after a log transform:

  | Part | Weight | Column(s) in `dataset.csv` |
  | --- | --- | --- |
  | Search | 40% | `trends_month1_vs_anchor` |
  | YouTube in Indian languages | 30% | `yt_comments_month1` × share of comments in Indian scripts |
  | Streaming | 20% | `netflix_top10_weeks_90d` |
  | Wikipedia | 10% | `wiki_hi_month1` + `wiki_ta_month1` + `wiki_te_month1` + `wiki_en_month1` |

- A part with no data is left out and the other weights are rescaled. A title needs at least two
  parts to get a label.
- It measures attention in India, not revenue. India box office for anime films is the money check.
- The exact formula and the agreement, stability and box-office checks go in `docs/label.md` when
  the label is frozen.

## 3. Forecast moments

| Moment | Uses data from | Main model |
| --- | --- | --- |
| Cold | Metadata and Japan-side signals only; any time before launch | Lookalike |
| T−28 | Before day −28 (days counted from the Japanese start date) | Blend |
| T+7 | Up to day +6 | Blend |

- An input dated on or after its moment is leakage, and the leakage test fails on it.
- Today's AniList popularity and score, and YouTube view counts, are never model inputs: they are
  values on the day of collection, not at the forecast moment.

## 4. Split

- By Japanese start date: train 2019–2023, validate 2024, test 2025.
- Rolling check: for each season from Winter 2020 to Fall 2024, train on all earlier seasons and
  forecast that season.
- The 2025 test titles are scored once, with `--final`, after everything else is settled.
- Netflix's country charts start in June 2021, so the Streaming part is blank before then. That is
  expected, not missing data to fill in.

## 5. Google Trends anchor

- **"Naruto"**, resolved to its Trends topic on the first run and cached in
  `data/raw/trends/_anchor.json`. Every India request includes it, so all titles share one scale.
- Chosen because it is long-running and widely known in India, so its search level should be steady.
  Check that in the first data: its daily line in `trends_india_daily.csv` should be roughly flat.
  If it is not, change the anchor before collecting at scale.
- Never change it during a collection. The script refuses a different `--anchor` once data exists.

## 6. Working style

- One branch per task, merged into `main` through a pull request that one teammate reviews.
- Logic lives in `.py` files. `notebooks/` is for exploration, and no code imports from it.
- Never commit `.env`, `data/raw/` or comment text (`youtube_comments.csv`); all three are
  git-ignored. The repo is public.
- Files in `reports/` are generated: fix the code that writes them, not the report.

## Change log

| Date | Decision | Change | Why |
| --- | --- | --- | --- |
| 2026-10-24 | All | Adopted the defaults above | Phase 0 |
| 2026-10-24 | 2, 5 | No Google Trends this round. The Search part is left out, so the index uses YouTube 50%, Streaming 33%, Wikipedia 17% (the same rescaling as for any missing part). Decision 5 is not in use. | One day left; Trends takes nights to collect |
| 2026-10-24 | 1 | YouTube collected with `--no-hindi` (trailer search only) | Fits 200 titles into one day of quota on three keys; Indian-script comments still come from the trailers |
| 2026-10-24 | 2 | Regional view comes from the scripts of trailer comments (Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam hubs), not from Trends states | Trends state data is not collected; English-speaking fans are not placed on any hub, and the dashboard says so |

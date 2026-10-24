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
| Cold | Metadata and Japan-side signals only; any time before launch | Blend (metadata, lookalike, prequel) |
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
| 2026-10-24 | 2 | The YouTube part counts trailer comments by people in India in days 0–27 (`yt_india_month1`): Indian scripts, Hinglish typed in Latin letters, or naming India, an Indian language or city (`collectors/india_signals.py`). Language hubs also count Hinglish (Hindi) and language names. Replaces comments × Indian-script share. | Fewer than 1 in 2,000 comments use an Indian script (41 of 200 titles had any); with Hinglish and mentions about 1 in 100 do, on 107 titles |
| 2026-10-24 | 2 | Hinglish also counts a Latin-letter comment that IndicLID (romanized fastText model) reads as any Indian language with probability ≥ 0.5, if it has three or more words and two Hindi words (`collectors/detect_languages.py`, `india_signals.py`). | The word rules missed short Hinglish; IndicLID alone flags Spanish, Indonesian and emoji, so it only confirms. 2024 T+7 check, before the next row: rank correlation 0.46 → 0.49 |
| 2026-10-24 | 2 | A matched Wikipedia article with no pageviews in the 240 days around launch, and a YouTube title whose videos have comments but none were collected, are blank instead of 0, in `dataset.csv` and in the model inputs (Wikipedia inputs: no views by the cutoff). | They were counted as zero attention, which put Demon Slayer, Jujutsu Kaisen, Frieren and Solo Leveling near the bottom. Labelled titles drop from 336 to 234 |
| 2026-10-24 | 3 | Gate G4 fallback is applied automatically: at a moment where the main model does not beat the best baseline (rank correlation, top-20% hits and new shows), `evaluate.py` marks that baseline as **used**, and `decision.py` takes its forecasts, 80% range and verdicts from it. Lookalikes and the regional view still come from the model. Today this is T−28 (Sequel carry-over); cold uses the lookalike and T+7 the blend. | G4 failed at T−28; the plan says to ship the best baseline there and report it, rather than a model that loses to a simple rule |
| 2026-10-24 | 2 | `collect_wikipedia.py` swaps an English article with no views in the 240-day window for the name readers used at launch: the main article or "List of … episodes", if that page links to the original and had at least 1,000 views in the window; the one with most views wins. Swaps are marked `fallback` and listed in `wiki_articles_fixes.csv`. | 223 matched articles (Demon Slayer, Jujutsu Kaisen, Frieren…) were split off after launch, so the biggest shows had no Wikipedia part; the link check stops "Lazarus (Japanese TV series)" becoming the Bible's Lazarus |
| 2026-10-24 | 2 | Money check runs on 6 films with an India release (`data/india_box_office.csv`). Figures mix net and gross and some runs were still going; each row says which and links its source. Only the ranking is used. | Gate G2's box-office sanity check had no data; the six are far enough apart that net vs gross does not change their order |
| 2026-10-24 | 2 | Two described (not modelled) extras on each title: **dub demand**, the similarity-weighted share of Indian trailer comments on the closest past titles that ask for or about an Indian-language dub (`dub_ask` in `india_signals.py`, `yt_dub_share` in `dataset.csv`; comments with links left out), and a **release-window what-if**, the average index of labelled past titles by window (festive, board exams, IPL, other; shown only with 10+ titles). Neither changes the forecast or verdict. | Both answer launch questions a distributor asks. On 2019–2024 titles the windows differ by under 2 points (exams has only 6 titles), so the site says the window makes no clear difference rather than implying one |
| 2026-10-24 | 3 | Three additions that change no forecast: **what each signal is worth** (`yosoku/ablation.py`: the Blend refitted without one input group at a time, scored on 2024 and the rolling seasons); a **launch plan** on every title (decision, re-decide rule at T+7, dub order, release window), built only from evidence already on the sheet; and **sealed forecasts** (`yosoku/seal.py`: upcoming forecasts frozen in a file whose SHA-256 is recorded in `predictions/sealed/LEDGER.md`; never rewritten). | Shows how reliably each source predicts, turns a score into an action, and makes the forecasts for unreleased titles checkable when they air. Ablation: at T−28 English and Japanese Wikipedia carries the forecast (−0.10 rolling); at T+7 global Wikipedia (−0.23) and YouTube (−0.19); Indian-language Wikipedia, the prequel's index and metadata add nothing |
| 2026-10-24 | 3 | Two inputs removed as hindsight. `has_youtube` marked the titles searched on YouTube, which were the top 200 by today's AniList popularity; `has_india_article` counted a Hindi, Tamil or Telugu article with views on any day up to +120, and now counts only views by the cutoff. The leakage test now also removes every row after the cutoff, not only changes them, and covers in-between days. | Both carried information from after the forecast moment, and `has_youtube` would have been 1 for every upcoming title once its YouTube data is collected. On 2024: T−28 0.27 → 0.25, T+7 0.69 → 0.66 (rolling 0.34 → 0.33 and 0.63 → 0.62); the T−28 lines re-tune to 45/40, giving 5 Launch instead of 1 |
| 2026-10-24 | 3 | The Blend is the main model at every stage, cold included: metadata, the lookalike forecast and the prequel's index. The lookalike alone stays a reported method. Gate G4 is unchanged, so the genre average still makes the cold forecasts. | The lookalike alone ranked 2024 titles at −0.01. Over 20 rolling seasons the cold Blend ranks at 0.21 against the genre average's 0.08, but on 2024 alone it loses (0.06 against 0.12) and the pre-registered rule picks on 2024. Every 95% interval at cold spans about −0.3 to 0.4, so 2024 alone cannot separate them; `docs/roadmap.md` proposes picking on the rolling seasons from the next sealed round |
| 2026-10-24 | 2 | The ranking pool is frozen: `labels/reference_v1.csv` lists the 1,400 titles released by now, and any later title is placed among them without joining them. Titles in `--upcoming-dir` are labelled the same way once their 28 days are over, so `seal --score` can grade them. Today's labels are unchanged byte for byte. | With a pool of all titles, collecting the 2025 titles alone moved the 2019–2024 labels by 0.9 points on average (up to 2.8): every new collection re-scored history, and sealed forecasts would have been graded on a different scale from the one they were made on |
| 2026-10-24 | 3 | Titles not released yet take their 80% range from every rolling season known, 2024 included: cold ± 15.6, T−28 ± 13.9, T+7 ± 10.8. The 2024 backtest keeps the range set before 2024. | Set season by season from earlier seasons only, the ranges held 78–82% of titles up to 2023, but 58–67% in 2024, whose titles scored about 5 points above their cold and T−28 forecasts. A forward forecast should carry the misses already seen |
| 2026-10-24 | 3 | The decision clock (`yosoku/clock.py`): the Blend refitted for each day from −49 to +14 with only the data dated before it, scored like the stages, plus each 2024 title's forecast day by day. It changes no forecast or verdict. | Shows how much a forecast made on a given day can be trusted. Over 20 seasons it is flat before launch (0.30 on day −49, 0.36 on day −7) and jumps between the premiere (0.39) and day +3 (0.54) |
| 2026-10-24 | 1, 6 | Titles in play are collected every day (`yosoku/daily.py`): YouTube with `--refresh` (only comments newer than the cached ones, a new search each week, view counts kept 30 days), the title list with `--keep`, and Netflix for upcoming titles once they air. Comments are also kept as per-day counts without text (`data/youtube_comment_daily.csv`), and the pipeline runs from those when the text is absent. | Collected once, an upcoming title never got its launch-week comments or later trailers, and comments were capped at the newest 1,000 per video. The counts let the comment text leave the public repo, as decision 6 requires. YouTube's API policies let a client keep statistics 30 days without the channel owner's authorisation |

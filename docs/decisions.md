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
| 2026-10-24 | 2 | IndicLID labels for every comment in Latin letters (167,323), not only the 74,542 labelled before the full YouTube rerun; the daily job now labels new comments as they come. | The India comment counts mixed two methods: 92 of 197 titles had comments read by the word list alone. 37 more India comments in the first 28 days (661 → 698); labels keep a rank correlation of 0.99 with the old ones, except where a title gets its first India comment: Kaguya-sama Season 3 50 → 82, The Summer Hikaru Died 51 → 73. 2024: T−28 0.25 → 0.23, T+7 0.66 unchanged; T−28 gives 4 Launch instead of 5 |
| 2026-10-24 | 3 | Titles not released yet take their 80% range from the misses of the titles whose index includes YouTube only, in every rolling season: cold ± 21.9, T−28 ± 18.7, T+7 ± 12.7, and likewise for each day of the decision clock, which the daily job uses. The 2024 check reports the two groups apart; the 2024 backtest keeps the range set before 2024. | The 2024 misses are the 19 titles whose index includes YouTube: 37–47% of them landed inside the range, against 79–85% of the other 33. YouTube was collected for the 200 titles most popular on AniList today, and a 2024 title had to be a hit to be among them. Every upcoming title gets YouTube data, so its index will include it. Collecting YouTube for every title (label v2) removes the cause |
| 2026-10-24 | 3 | A stage already sealed shows the sealed numbers, verdict and lines on the site, with today's forecast for it beside them; the daily alerts judge a sealed verdict on its own range and lines. A sealed file that no longer matches the ledger is skipped. | The site showed today's forecasts beside the line "Sealed 24 Oct 2026", and all 50 differed from the file anyone could download and check |
| 2026-10-24 | 1 | Indian comments asking for a title are counted per day in `data/youtube_ask_daily.csv`: a dub, by language (`dub_<hub>`), and when or where to watch it (`watch_ask`, Indian comments only). The Demand guide lists the titles India asks for. Not a model input. | 1,197 comments on 68 titles ask: 1,090 for a dub (Hindi 1,016, Tamil 50, Telugu 23) and 160 for when or where to watch, about 9 in 10 of them real asks in a sample of 20. It is the demand half of a list of titles India asks for and cannot get; where each title is available in India is not joined yet |
| 2026-10-24 | 3 | Each forecast sheet also prints as a one-page Japanese 稟議書 (`web/js/ringi.js`): conclusion, grounds, the three closest past titles with what they share (series, genres, studio, source, format, audience, tags) and how they did in India, risks, the next decision dates, and boxes for the approvers' seals. The Japanese reason line names a simple rule in Japanese. No forecast changes. | Japanese companies approve through ringi and argue by precedent, and an English dashboard is not passed around inside them. The Japanese is templated by machine, and the page says so |
| 2026-10-24 | 3 | A **chance of a top-third result** (an index at or above the top third of past titles, 54 today): a logistic curve on the forecast, fitted on the rolling seasons' out-of-sample forecasts, shown only where it beats the base rate by 0.10 in Brier skill, a bar set before looking. That is T+7 (0.19) and the decision clock from day +3 (0.15, then 0.19 and 0.22), not cold (0.02) or T−28 (0.07). The daily job logs it for titles in play. | Buyers ask how likely a hit is, not where an index lands. At T+7, 94% of the calls of 70% or more came true (17 calls); before the premiere the curve has too little skill to show a number |
| 2026-10-24 | 3 | **Forecasts in money** (`yosoku/money.py`): with a partner's India revenue or viewing hours for 30 or more labelled titles (`data/partner/revenue.csv`), log(amount) is fitted to the index and checked leaving each title out, and every forecast gets a range: its index range through the line, widened by the 10% and 90% left-out misses. Partner files are never committed (`.gitignore`); the site shows amounts only when exported with `--with-money`. | The index measures attention, but buyers price in yen. Without partner figures the sheet says what it would take, rather than inventing a number |
| 2026-10-24 | 1 | The Netflix collector also keeps every country's Top 10 weeks within 180 days of a title's Japanese start (`data/netflix_countries.csv`), matched more strictly than India's: a film row only to an anime film by its exact name, a TV row only to a series. `yosoku/markets.py` lists for every forecast where its 10 most similar earlier titles charted beyond Japan, beside how often anime in general did; the Demand guide shows the world view. India's own matching is unchanged. | 160 titles reached a Top 10 in 88 countries; India comes joint 36th, with 13. Checked on past titles only, similar titles rank the titles that charted in a country at AUC 0.70 on average over 44 countries, against 0.55 for titles of the same genre. Ranking countries by how often anime charts there picked a title's top 5 as well (85% against 83%), so each country's typical rate is shown beside it. Loose name matching had matched live-action remakes and unrelated films abroad (City Hunter, Golden Kamuy, Liar Liar, The Stranger) |
| 2026-10-24 | 6 | The collectors write CSVs with Unix line endings, as the committed files have them. | The csv module's default (\r\n) made every collector run rewrite unchanged files in full |

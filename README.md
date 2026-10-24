# Yosoku 予測

Predicting how Japanese anime will perform in India before the launch decision is made.
Thapar Japan Hackathon, GEEK-PS-01, Team shecodes.

The repo has three parts, in the order the data flows:

1. **Collectors** (`collectors/`): small Python scripts that download public data from official APIs and save it
   as CSV files in `data/`, ending in `data/dataset.csv` (one row per title).
2. **Model pipeline** (`yosoku/`): turns that data into the India Demand Index (the label), forecasts it at three
   moments around launch, tests the forecasts against simple rules, and gives every title a verdict:
   Launch, Test-market or Hold.
3. **Website** (`web/`): a static dashboard for Vercel with the forecasts, the track record, the method and a guide
   to what India is actually watching.

## Where things stand

As of 24 October 2026. The files in `reports/` are generated and are the source of truth if these lines drift.

- **Data:** 1,400 titles, the 50 most popular Japanese anime of every season from 2019 to 2025. The 200 most popular
  also have YouTube trailer comments (trailer search only, `--no-hindi`). The collected CSVs are committed in `data/`
  (the Reddit files are not), so the model and the site run without any API key (see "Run the model and the site").
  The comments are also kept as per-day counts without text (`data/youtube_comment_daily.csv`, and the comments asking
  for a dub or for where to watch in `data/youtube_ask_daily.csv`), and the pipeline runs from those alone: see
  "Responsible data use" for taking the text out of the public repo.
- **No Google Trends this round**, so the India Demand Index is YouTube 50%, Streaming 33%, Wikipedia 17%.
  319 titles have at least two parts and get a label. The ranking pool is frozen (`labels/reference_v1.csv`), so
  collecting new titles never moves an existing label. `docs/decisions.md` has the change log.
- **Label checks (gate G2): fail, narrowly.** All three pairs of parts now agree positively (YouTube and Netflix 0.50,
  the Wikipedia pairs about 0.14), but lowering the Wikipedia weight by 0.10 still moves the ranking (Kendall's tau 0.70,
  target 0.9). The box-office check covers only 6 films (rank correlation 0.43, interval −0.60 to 1.00).
- **Forecast checks (gate G4): fail at Cold only.** On the 52 labelled 2024 titles the Blend beats every simple rule at
  T−28 (rank correlation 0.23) and T+7 (0.66, interval 0.47 to 0.80). At Cold it ranks the 20 rolling seasons at 0.18
  against the genre average's 0.09, but loses on 2024 alone (0.05 against 0.12), and the rule picks on 2024, so the
  genre average makes the cold forecasts. T+7 is a nowcast: its inputs sit inside the 28 days it measures.
- **The decision clock** (Track record tab, `reports/clock.md`) scores a forecast made on each day: over 20 seasons
  it improves little from day −49 (0.29) to day −7 (0.38), then jumps between the premiere (0.41) and day +3 (0.53).
- **Verdicts:** the cold ranges are too wide to separate titles, so every title is Test-market there. On the 2024
  split, T−28 gives 4 Launch and 48 Test-market; T+7 gives 11 Launch, 40 Test-market, 1 Hold.
- **What the site shows:** 50 upcoming Winter 2027 titles (cold forecasts, dated 24 October 2026; 39 have no announced
  start date yet) and the 2024 backtest, 52 titles. The 2025 test titles are unscored: that happens once, at the very end.
- **Wikipedia articles written after launch** were swapped for the page readers used then (`fallback` rows in
  `data/wiki_articles_fixes.csv`), so the biggest shows now have a Wikipedia part.
- **YouTube for upcoming titles** is not collected yet (the API key was rejected), so they have cold forecasts only.
- **What to build next** is in `docs/roadmap.md`: a review of the model, how the project scales as data arrives
  every day, what would make Japanese rights holders buy it, and the licences to check before selling it.

## Setup (once per laptop)

1. **Install Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** in the installer.
2. **Get the code** (or download the ZIP from GitHub):
   ```
   git clone https://github.com/ajha2005/yosoku.git
   cd yosoku
   ```
3. **Create a virtual environment**, a private folder for this project's libraries:
   - Mac / Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`

   Your prompt now starts with `(.venv)`. Run the activate command again whenever you open a new terminal.
4. **Install the libraries:**
   ```
   pip install -r requirements.txt
   ```
5. **Only if you will collect data:** copy `.env.example` to a new file named `.env` and fill it in.
   `YOUTUBE_API_KEY` is needed for step 4 of the collectors (see below); `YOSOKU_CONTACT` is an optional email or URL
   that Wikipedia can reach you on. `.env` holds your API key, so it is git-ignored. Never commit it or paste it in chat.

## Run the model and the site

The collected CSVs are committed, so this needs no key and no collecting. Run it from the `yosoku` folder with the
virtual environment active:

```
python -m yosoku.run                    # label, evaluation, decision clock and verdicts (about 2 minutes)
python -m yosoku.export_web --no-covers # copies the forecasts to web/data/ and builds the Demand guide
python -m http.server -d web 8000       # the dashboard, at http://localhost:8000
python -m pytest tests                  # about 2 minutes
```

GitHub Actions runs the tests on every push and pull request (`.github/workflows/tests.yml`).
For a presentation, `docs/demo.md` is a 3-minute walk through the site, with answers to the questions judges are likely to ask.

It rewrites `labels/`, `reports/` and `predictions/` with the same content as is committed. A few scipy "constant
input" warnings during the evaluation are normal: some baselines predict the same value for every title.
Leave out `--no-covers` to fetch cover art from AniList.

## Collecting data

| Step | Script | Source | Time | Output in `data/` |
|---|---|---|---|---|
| 1 | `collect_titles.py` | AniList API | ~3 min | `titles.csv` |
| 2 | `collect_wikipedia.py` | Wikidata + Wikipedia pageviews API | ~15–30 min | `wiki_articles.csv`, `wiki_articles_fixes.csv`, `wikipedia_daily.csv` |
| 3 | `collect_netflix.py` | Netflix Top 10 download | ~1 min | `netflix_india_top10.csv`, `netflix_matches.csv` |
| 4 | `collect_youtube.py` | YouTube Data API (needs a key) | a few days (daily quota) | `youtube_videos.csv`, `youtube_comments.csv` |
| 4b | `detect_languages.py` (optional) | IndicLID language ID on the trailer comments (needs `pip install fasttext`) | ~1 min, plus a 230 MB model download | `comment_languages.csv` |
| 5 | `collect_trends.py` | Google Trends via `pytrends-modern` | overnight or longer | `trends_terms.csv`, `trends_india_daily.csv`, `trends_india_states.csv`, `trends_countries.csv` |
| 5b | `collect_reddit.py` (optional) | Reddit posts, read from the Arctic Shift archive | ~15–20 min for 200 titles | `reddit_posts.csv`, `reddit_titles.csv` |
| 6 | `merge.py` | the files above | seconds | `dataset.csv` (one row per title) |

Steps 5 and 5b were **not** collected for the current dataset (no Trends this round, and no Reddit file is committed);
`merge.py` and the models simply run without them. The scripts still work if you want them back.

### Getting a YouTube API key (free, ~5 minutes)

1. Open [console.cloud.google.com](https://console.cloud.google.com/), sign in and create a project (e.g. "yosoku").
2. **APIs & Services → Library**, search **YouTube Data API v3**, click **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Put it in `.env` as `YOUTUBE_API_KEY=...`. In the key's settings, restricting it to the YouTube Data API v3 is a good idea.

Each key gets 10,000 quota units a day, so three teammates with a key each collect three times as fast (see below).

### Running the collectors

Run them from the `yosoku` folder with the virtual environment active:

```
python collectors/collect_titles.py
python collectors/collect_wikipedia.py
python collectors/collect_netflix.py
python collectors/collect_youtube.py
python collectors/detect_languages.py  # optional, after YouTube
python collectors/collect_trends.py    # skipped this round
python collectors/collect_reddit.py    # optional
python collectors/merge.py
```

- **Step 1 comes first**; the others all read `data/titles.csv`. After that, steps 2–5 are independent and can run at the same time in separate terminals.
  If you do use Trends (step 5), **start it early**: it is the slowest.
- Every script explains its options with `--help`, e.g. `python collectors/collect_titles.py --help`.
- **Stopping is safe.** Finished work is cached in `data/raw/` (git-ignored); rerun the same command and it carries on.
- `merge.py` works with whatever has been collected so far, so you can run it any time.

### Choosing titles

`collect_titles.py` keeps the 50 most popular Japanese anime of each season from 2019 to 2025
(about 1,400 titles). Change that with `--start-year`, `--end-year`, `--per-season` and `--seasons`.
YouTube and Trends are slow, so they only take the `--limit` most popular titles (default 200).
Each title comes with its synopsis and its well-fitting, spoiler-free AniList tags, which the
lookalike model uses.

### Upcoming titles (live forecasts)

Unreleased titles get their own folder, so they never mix into the training data. Give every step
the same `--data-dir`:

```
python collectors/collect_titles.py --data-dir data/upcoming --start-year 2027 --end-year 2027 --seasons WINTER
python collectors/collect_wikipedia.py --data-dir data/upcoming
python collectors/collect_youtube.py --data-dir data/upcoming
python collectors/merge.py --data-dir data/upcoming
python -m yosoku.run                   # picks up data/upcoming/ and adds the titles to predictions.json
```

(Add `collect_trends.py --data-dir data/upcoming` before `merge.py` if Trends is back in use.)

**Seal the forecasts** so anyone can check later that they were made before launch:

```
python -m yosoku.seal            # writes predictions/sealed/<date>-<season>.json and its SHA-256 in LEDGER.md
python -m yosoku.export_web      # copies the seal to the site (Forecasts → Upcoming shows it)
git add predictions/sealed web/data && git commit -m "Seal forecasts" && git push
python -m yosoku.seal --verify   # any time: every sealed file still matches its fingerprint
python -m yosoku.seal --score    # after the titles air and are labelled: how the sealed forecasts did
```

A seal is never rewritten; sealing again on another day adds a new file. The 50 Winter 2027 forecasts were sealed
on 24 October 2026.
An upcoming title gets a cold forecast right away, and T−28 / T+7 forecasts once those dates pass and its
Wikipedia and YouTube data are collected. Their windows are still running, so these titles are fetched fresh on
every run; rerun them before the demo for the latest buzz. The cache in `data/raw/` is shared between folders,
which is safe because it is keyed by title. Once a title's 28 days are over, `python -m yosoku.labels` gives it an
India Demand Index on the frozen scale, and `seal --score` can grade it.

### Every day: the titles in play

A title's data stops changing 90 days after its Japanese premiere (its last window, Netflix weeks, closes then), so
only the titles before that point need collecting and forecasting again. One command does it all:

```
python -m yosoku.daily                # collect, label, forecast today, log, alert, publish to web/data
python -m yosoku.daily --no-collect   # the same from the files already collected (no network)
```

- It runs the collectors for `data/upcoming`: `collect_titles.py --keep` (picks up announced start dates and never
  drops a title already forecast), Wikipedia, Netflix (the weekly file fetched again on Wednesdays),
  `collect_youtube.py --refresh`, which fetches only comments newer than the cached ones, searches again weekly for
  new trailers and logs today's view counts (kept 30 days, as YouTube's API policies require), then IndicLID on the
  comments it has not labelled yet, so new comments are read the way the old ones were. IndicLID needs
  `pip install fasttext` on the machine that runs the job; without it, the job says so and uses the word list alone.
- Each title in play is forecast as of today with the decision clock's model; the forecast goes into
  `predictions/history.csv` (one row per title per day), and each upcoming title's sheet on the site draws it.
- `reports/alerts.md` lists titles whose forecast has left the 80% range of their last verdict, or crossed a
  verdict line, once buzz is in; `predictions/alerts.json` carries the same for the site, which shows the day's
  status and alerts on Forecasts → Upcoming and a *Moved* badge on those titles. Verdicts themselves still change
  only at the three stages.
- Run it once a day on a machine whose disk persists: the comment refresh builds on the cache in `data/raw/`. With cron:
  `30 6 * * * cd ~/yosoku && .venv/bin/python -m yosoku.daily`, then commit `data/upcoming`, `predictions/history.csv`,
  `reports/alerts.md` and `web/data`. Rerun `python -m yosoku.run` weekly, or when titles get labels.

### Other markets (countries)

India is the default market. A data folder can be collected for another country instead: its Netflix
Top 10 chart and its own Wikipedia languages replace India's (English and Japanese stay as global buzz).
The markets are listed in `collectors/markets.py` (India, Indonesia, Thailand, Brazil, Mexico); adding one is a line there.

```
python collectors/collect_titles.py --data-dir data/markets/id --market ID
python collectors/collect_wikipedia.py --data-dir data/markets/id
python collectors/collect_netflix.py --data-dir data/markets/id
python collectors/merge.py --data-dir data/markets/id
python -m yosoku.labels --data-dir data/markets/id --out-dir out/id
```

The folder remembers its market (`market.txt`), so only the first step needs `--market`, and a folder never mixes two.
Trailer comments, language detection and Trends are India only (the word list that finds Indian commenters has no
equivalent elsewhere yet), so another market's index has two parts, Netflix and Wikipedia. Report and site wording
still says India: the site is the India product. No other market has been collected yet.

### Sharing the YouTube work between three keys

Each person runs a different slice of the top 200:

```
python collectors/collect_youtube.py --limit 70                # person 1: titles 1–70
python collectors/collect_youtube.py --limit 140 --skip 70     # person 2: titles 71–140
python collectors/collect_youtube.py --limit 200 --skip 140    # person 3: titles 141–200
```

Rerun the same command on the following days until it says it is done. Then copy everyone's
`data/raw/youtube/` folders into one, and run `python collectors/collect_youtube.py` once more on that
laptop: it rebuilds the CSV files from the cache and only spends a few units on view counts.

## From data to forecasts

After `merge.py`, `python -m yosoku.run` runs the label, evaluate, ablation, clock and decide steps below in order.
`yosoku/features.py`, `models.py` and `split.py` hold the model inputs, the models and the train / validate / test
split they share.

| Step | Module | Writes |
|---|---|---|
| Label | `yosoku/labels.py` | `labels/label_v1.csv`, `reports/label.md` (agreement, stability and box-office checks: gate G2); the first run also freezes the ranking pool in `labels/reference_v1.csv` |
| Evaluate | `yosoku/evaluate.py` | `reports/evaluation.md` and `.json` (models against baselines on 2024: gate G4); with `--final`, `reports/final.md` |
| Ablation | `yosoku/ablation.py` | `reports/ablation.md` and `.json` (what each signal is worth) |
| Clock | `yosoku/clock.py` | `reports/clock.md` and `.json` (the decision clock: a forecast made on each day from −49 to +14, scored) |
| Decide | `yosoku/decision.py` | `predictions/predictions.json`, `reports/decision.md` (verdicts: gate G5) |
| Daily | `yosoku/daily.py` | `predictions/history.csv`, `reports/alerts.md` (titles in play, every day; not part of `run`) |
| Guide | `yosoku/guide.py` | `web/data/guide.json` (run by `export_web`) |
| Export | `yosoku/export_web.py` | copies the forecasts to `web/data/` and fetches cover art |

- Forecast moments: **cold** (metadata only, any time before launch), **T−28** and **T+7**, each using only data
  from before its cutoff. Days are counted from the Japanese premiere (day 0): T−28 is made 28 days before it and sees
  days −56 to −29 (a fixed window, not the gap between the trailer and the premiere); T+7 is made 7 days after it and
  adds days −28 to −1 and launch week, days 0 to 6. The Method tab and each forecast sheet draw this timeline.
  The split is by Japanese start date: train 2019–2023, validate 2024, test 2025.
- The Blend is the main model at every stage; at cold its inputs are the metadata, the closest past titles and the
  prequel's index. The decision clock refits it for the days in between (`features.stage` cuts the same windows off
  at any day), and the daily job uses it for titles in play.
- If the model does not beat the best simple rule at a moment, that rule makes the forecasts there and the report says so (gate G4 fallback).
- The 80% ranges come from how far forecasts missed on the rolling seasons: for the 2024 backtest, only seasons
  before 2024; for titles not released yet, every season, the 2024 misses included, and only the titles whose index
  includes YouTube, as theirs will. In 2024 the ranges held for 79–85% of the other titles but 37–47% of those: YouTube
  was collected for the 200 titles most popular today, so the 2024 ones are mostly hits. A stage already sealed shows
  the sealed numbers on the site, with today's forecast beside them.
- Each title also carries two described, not modelled, extras that change neither the forecast nor the verdict:
  **dub demand** (the share of Indian trailer comments on its closest past titles that ask for or about an
  Indian-language dub) and a **release-window what-if** (how labelled past titles did in the festive, board-exam, IPL
  and other windows; a window is shown only with 10 or more titles). `docs/decisions.md` has the reasoning.
- The 2025 test titles are scored once, at the very end: `python -m yosoku.run --final`.
- Tests, including the check that no input uses data from after its forecast moment: `python -m pytest tests`.
- See `docs/decisions.md` for what was fixed in advance and what changed since (the change log at the bottom).

## The website (static, for Vercel)

`web/` is the dashboard, a plain static site (no server, no build step) with six tabs (Overview, Forecasts, Track record, Business, Method, Demand guide):
poster wall, a verdict card for every title (with its dub demand and release-window what-if) that prints as a one-page
brief in English or as a Japanese 稟議書 (the 稟 button: conclusion, grounds, precedents, risks, next decision dates), an India language-hub map,
the backtest, the decision clock ("When will we know?" on Track record), each title's forecast path (day by day for the
2024 titles, from the daily log for upcoming ones), the daily job's status and alerts on Forecasts → Upcoming, and the
method, including how it keeps up as data arrives every day. Vercel can
host it because it is only HTML, CSS, JavaScript and a few JSON files.

**Update it after every pipeline run:**

```
python -m yosoku.run                # writes predictions/predictions.json
python -m yosoku.export_web         # copies it to web/data/ and fetches cover art from AniList
git add web/data predictions && git commit -m "Update website data" && git push
```

- The **Demand guide** tab ("what is India actually watching?") is built by `python -m yosoku.guide`, which `export_web` runs for you.
  It counts only two real signals: which anime reached Netflix India's weekly Top 10 (`data/netflix_matches.csv`) and the
  India-flagged YouTube trailer comments in `data/dataset.csv`, with the ones asking for a dub (by language) or for when
  and where to watch listed title by title ("What India is asking for", `data/youtube_ask_daily.csv`). It does not use
  the forecast model or the India Demand Index.
- The site shows the real forecasts in `predictions/predictions.json`. If that file is missing, it falls back to
  `web/data/mock_predictions.json`, made from **fake** data, with a yellow "Preview data" banner.
  Mock titles get generated Japanese-print posters instead of covers, because their made-up ids collide with real AniList ids.
- `--no-covers` skips the AniList lookup (offline) and keeps `covers.json` as it is. Covers are links to AniList's image servers,
  not copies, and a cover that fails to load falls back to the generated poster.
- Look at it locally: `python -m http.server -d web 8000`, then open <http://localhost:8000>.

**Deploy on Vercel (about 2 minutes):**

1. Push this repo to GitHub, then go to [vercel.com/new](https://vercel.com/new) and import it.
2. Set **Root Directory** to `web`. Leave the framework as **Other** and the build and output settings empty.
3. Click **Deploy**. Every push to the branch redeploys. Or from a terminal: `cd web && npx vercel --prod`.
4. Optional: for link previews on social media, change `og:image` in `web/index.html` to the full address of
   `img/og.png` on your domain (crawlers need an absolute URL).

`web/vercel.json` adds a strict content-security policy. If you add a script or image from another site, allow it there.
`tools/build_india_map.py` rebuilt `web/js/india-map.js` from district boundaries; you never need to rerun it.

## Check these by hand

Automatic matching makes mistakes. Before modelling, look through:

- **`wiki_articles.csv`**: rows with `match_method` = `search` were guessed. Fix the article names by hand and rerun step 2
  (the 62 `fixed` rows are earlier hand fixes, listed in `wiki_articles_fixes.csv`).
  Rows with `match_method` = `fallback` are swapped automatically when the matched English article had no
  views around launch (it was written later); `wiki_articles_fixes.csv` lists the old and new names (action
  `fallback`). **That swap has not been run on the real data yet**, so the file has no `fallback` rows today.
  A sequel swapped to its main article counts attention to the whole show, not only that season, so check them when they appear.
- **`netflix_matches.csv`**: names are matched loosely, and live-action remakes (One Piece, Yu Yu Hakusho) share their anime's name.
  To drop a wrong match, add a line `anilist_id,show_title,reason` to `data/netflix_match_exclusions.csv`
  (first line: `anilist_id,show_title,reason`) and rerun step 3, then step 6. The ones found so far are already listed there.
- **`india_box_office.csv`**: India box office for 6 anime films, typed in by hand, for the money check in `reports/label.md`.
  Each row says whether the figure is net or gross and links its source; some runs were still going. Only the ranking is used.
  Add films as reliable figures turn up, then rerun `python -m yosoku.labels`.
- **`youtube_videos.csv`**: a search can return the wrong video. To fix one, edit the list of video IDs in
  `data/raw/youtube/search/<anilist_id>_trailer.json` (or `_hindi.json`) so the right video comes first, then rerun step 4.
- **`reddit_posts.csv`**: posts are matched by name (`match_name`). Short or common names pull in unrelated posts,
  and a sequel's name also matches posts about earlier seasons. Look through the busiest titles.
- **`trends_terms.csv`**: the Trends topic used for each title. If one is wrong, find the right topic on
  [trends.google.com](https://trends.google.com/): its ID is in the page address after `q=`, e.g. `%2Fg%2F11abc123`
  means `/g/11abc123`. Add a line `anilist_id,term` with that ID (or a plain search phrase) to
  `data/trends_overrides.csv` (first line: `anilist_id,term`), delete `data/raw/trends/<anilist_id>.json` and rerun step 5.

## Know this before modelling

- **Blank is not zero.** A blank cell means "no data": no Hindi Wikipedia article, not on Netflix, or
  started before June 2021 when Netflix's country charts begin. Don't fill blanks with 0 in the India Demand Index.
- **`popularity` and `average_score` are today's values**, so they include how well a title did. Fine for
  choosing titles, but don't use them as model inputs. Choosing titles by popularity also favours hits, and for the
  same reason whether a title was searched on YouTube (the top 200 by today's popularity) is not an input either.
- **YouTube view counts are from the day you collected them**, not from launch. For backtesting, use the
  dated comment counts (`yt_comments_pre`, `yt_comments_month1`).
- **Comments are fetched newest first, up to 1,000 per video**, so a very popular trailer's launch-week comments may be missing.
  Compare with the video's total in the `comments` column. Titles kept up to date with `--refresh` (the daily job) do
  not have this gap: each run fetches only the comments newer than the cached ones.
- **Labels are on a frozen scale.** Each part is a percentile among the titles in `labels/reference_v1.csv`; a title
  collected later is placed among them without moving them. Delete that file only to start a new label version.
- **Reddit is global attention, not India.** It has no country signal, so Reddit is not part of the India Demand
  Index. It is a model input instead: `yosoku/features.py` reads `reddit_posts.csv` and adds `reddit_posts_<window>`
  (log of the post count, same day windows and cutoffs as Wikipedia) to the T−28 and T+7 models, under "Global buzz".
  It only runs when `reddit_posts.csv` exists, and that file is git-ignored and not in the repo today: the committed
  results were made without it. Share it between laptops outside git, or the model silently runs without it.
  Scores and comment counts are archived after the post's date, so only post counts are used.
  The `reddit_*` columns in `dataset.csv` are for looking at the data.
- **Trends values are relative** (0–100 within each request). `trends_month1_vs_anchor` puts titles on one scale by
  dividing by the fixed anchor term; keep the same anchor (`--anchor`, default "Naruto") for the whole collection.
  There is no Trends data in the current dataset, so the Search part of the index is left out.
- **India comments** (`yt_india_*`, `yt_share_<hub>`) come from a word list in `collectors/india_signals.py`:
  Indian scripts, Hinglish typed in Latin letters, or naming India. Only about 1 in 70 comments match, and fewer
  than 1 in 2,000 use an Indian script. When `comment_languages.csv` exists, AI4Bharat's IndicLID also counts short
  Hinglish the word rules miss ("Kab release hogi ye movie"): 858 Hinglish comments instead of 561, and in an earlier
  hand check nearly all of the extra ones were real Hinglish. Every comment in Latin letters has an IndicLID label, and
  the daily job labels new ones as they come.
  IndicLID only knows Indian languages and English, so on its own it calls Spanish, Indonesian and emoji Indian,
  and it often names the wrong Indian language. A comment therefore also needs two Hindi words, and its exact
  language is not used. `comment_languages.csv` is committed, so only one person needs fastText and the model.
  `yt_dub_share` is the share of a title's India comments that ask for or about an Indian-language dub
  ("hindi dub kab aayega", "please dub in tamil"; comments with a link are left out, they are mostly channels announcing a dub).
- **A missing measurement is blank, not 0.** 223 matched English Wikipedia articles have no pageviews around
  launch, because they were written later (often "<show> season 1" pages), and comments were not collected for
  92 of the 200 YouTube titles. `merge.py` and the models treat both as unknown, not as zero attention, and a title
  needs two index parts to get a label: that cut the labelled titles from 336 to 234 (see `docs/decisions.md`).
  Rerunning step 2 will swap the Wikipedia articles itself (see `fallback` above), and with the YouTube comments
  finished, about 100 more titles should be labelled.

## Responsible data use

Public data only: official APIs where they exist (AniList, Wikimedia, YouTube) and Netflix's published file.
No usernames are stored. Google Trends has no open API, so `pytrends-modern` reads the public website;
the script deliberately goes slowly, so please don't lower `--pause` much.

Reddit posts come from the public [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) archive, not from
reddit.com, so nothing is scraped from Reddit's site. Arctic Shift is free and asks users to be considerate, so the
script waits between requests; for large jobs it recommends the monthly dumps instead. Only a post's title, date,
score, comment count and flair are kept, never usernames or post text.

The optional language step runs AI4Bharat's [IndicLID](https://github.com/AI4Bharat/IndicLID) model on your own laptop
(a one-off 230 MB download), so no comment text is sent anywhere. Only its verdict per comment is saved.

**Comment text should not be in a public repo.** `data/youtube_comments.csv` is committed today, although decision 6
in `docs/decisions.md` says it never should be. `merge.py` now keeps `data/youtube_comment_daily.csv`, the same
comments counted per title, video and day with no text, and the whole pipeline runs from it. To take the text out:
every teammate first keeps a private copy (git deletes it from working copies once the removal is pulled), then
`git rm --cached data/youtube_comments.csv` and commit. It stays in git's history until that is rewritten, which is
the repo owner's call.

**Before charging anyone,** check the sources' commercial terms: AniList's API is free only below $150 a month of
revenue and forbids mass collection; YouTube's API policies limit how long API data, statistics included, may be kept
(30 days without the channel owner's authorisation, which is why the daily view-count log keeps 30 days). Section 7 of
`docs/roadmap.md` has the details and what to do about each.

## Layout

```
collectors/   the data collectors (common.py holds shared helpers, india_signals.py the word list for India comments)
yosoku/       the model pipeline: labels, features, models, split, evaluate, ablation, clock, decision, daily, seal, plus guide and export_web for the site
labels/       label_v1.csv: the India Demand Index of every labelled title (written by yosoku.labels); reference_v1.csv: the frozen ranking pool
predictions/  predictions.json: forecasts and verdicts (written by yosoku.decision); history.csv: the daily forecast log (yosoku.daily);
              sealed/: sealed forecasts and their fingerprints
reports/      generated reports: label.md, evaluation.md / .json, ablation.md / .json, clock.md / .json, decision.md, alerts.md,
              and final.md after --final; fix the code, not the report
web/          the dashboard: a static site for Vercel (see "The website"); web/data/ is written by yosoku.export_web, and holds the mock forecasts
tools/        one-off generators (the India map outlines)
tests/        pipeline, collector and website-export tests on fake data (tests/fake_data.py) and a fake YouTube API
docs/         decisions.md: the six choices that shape the dataset, and the change log; read it before changing a default
              demo.md: the 3-minute demo path and prepared answers
              roadmap.md: the review, how it scales with daily data, what Japanese buyers need, licences, the plan
data/         CSV outputs; data/raw/ is the cache and is git-ignored; data/upcoming/ holds unreleased titles
.env          your API key and contact (git-ignored; copy from .env.example)
```

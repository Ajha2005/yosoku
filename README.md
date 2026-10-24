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
- **No Google Trends this round**, so the India Demand Index is YouTube 50%, Streaming 33%, Wikipedia 17%.
  234 titles have at least two parts and get a label. `docs/decisions.md` has the change log.
- **Label checks (gate G2): fail.** The Wikipedia part does not agree with the other two (rank correlation about 0),
  and moving its weight by 0.10 changes the ranking more than the 0.9 target allows. The box-office check covers only 6 films.
- **Forecast checks (gate G4): fail.** On the 2024 validation titles, only the T+7 Blend edges past a simple rule
  (rank correlation 0.42, against 0.40 for global buzz alone; the intervals overlap almost entirely). Before launch,
  nothing gets above 0.09 (interval −0.20 to 0.37), which cannot be told apart from chance. Where the model loses,
  the best simple rule makes the forecasts instead: today that is Sequel carry-over at T−28.
- **Verdicts:** the cold and T−28 ranges are too wide to separate titles, so all 48 validation titles land on
  Test-market there. At T+7 the split is 1 Launch, 42 Test-market, 5 Hold.
- **What the site shows:** the 2024 backtest, 48 titles forecast as if before launch. No upcoming titles have been
  collected yet (`data/upcoming/` does not exist), and the 2025 test titles are unscored: that happens once, at the very end.
- **Written but not run on the real data yet:** the Wikipedia swap for articles that were written after launch
  (see "Check these by hand"). It needs internet access to Wikipedia; until it runs, 223 titles have no Wikipedia part.

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
python -m yosoku.run                    # label, evaluation and verdicts (about 30 seconds)
python -m yosoku.export_web --no-covers # copies the forecasts to web/data/ and builds the Demand guide
python -m http.server -d web 8000       # the dashboard, at http://localhost:8000
python -m pytest tests                  # about 30 seconds
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
An upcoming title gets a cold forecast right away, and T−28 / T+7 forecasts once those dates pass and its
Wikipedia and YouTube data are collected. Their windows are still running, so these titles are fetched fresh on
every run; rerun them before the demo for the latest buzz. The cache in `data/raw/` is shared between folders,
which is safe because it is keyed by title. Netflix is skipped here: an unreleased title cannot be in a chart yet.

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

After `merge.py`, `python -m yosoku.run` runs the first three steps below in order. `yosoku/features.py`, `models.py` and
`split.py` hold the model inputs, the models and the train / validate / test split they share.

| Step | Module | Writes |
|---|---|---|
| Label | `yosoku/labels.py` | `labels/label_v1.csv`, `reports/label.md` (agreement, stability and box-office checks: gate G2) |
| Evaluate | `yosoku/evaluate.py` | `reports/evaluation.md` and `.json` (models against baselines on 2024: gate G4); with `--final`, `reports/final.md` |
| Decide | `yosoku/decision.py` | `predictions/predictions.json`, `reports/decision.md` (verdicts: gate G5) |
| Guide | `yosoku/guide.py` | `web/data/guide.json` (run by `export_web`) |
| Export | `yosoku/export_web.py` | copies the forecasts to `web/data/` and fetches cover art |

- Forecast moments: **cold** (metadata only, any time before launch), **T−28** and **T+7**, each using only data
  from before its cutoff. The split is by Japanese start date: train 2019–2023, validate 2024, test 2025.
- If the model does not beat the best simple rule at a moment, that rule makes the forecasts there and the report says so (gate G4 fallback).
- Each title also carries two described, not modelled, extras that change neither the forecast nor the verdict:
  **dub demand** (the share of Indian trailer comments on its closest past titles that ask for or about an
  Indian-language dub) and a **release-window what-if** (how labelled past titles did in the festive, board-exam, IPL
  and other windows; a window is shown only with 10 or more titles). `docs/decisions.md` has the reasoning.
- The 2025 test titles are scored once, at the very end: `python -m yosoku.run --final`.
- Tests, including the check that no input uses data from after its forecast moment: `python -m pytest tests`.
- See `docs/decisions.md` for what was fixed in advance and what changed since (the change log at the bottom).

## The website (static, for Vercel)

`web/` is the dashboard, a plain static site (no server, no build step) with five tabs (Overview, Forecasts, Track record, Method, Demand guide):
poster wall, a verdict card for every title (with its dub demand and release-window what-if), an India language-hub map,
the backtest and the method. Vercel can
host it because it is only HTML, CSS, JavaScript and a few JSON files.

**Update it after every pipeline run:**

```
python -m yosoku.run                # writes predictions/predictions.json
python -m yosoku.export_web         # copies it to web/data/ and fetches cover art from AniList
git add web/data predictions && git commit -m "Update website data" && git push
```

- The **Demand guide** tab ("what is India actually watching?") is built by `python -m yosoku.guide`, which `export_web` runs for you.
  It counts only two real signals: which anime reached Netflix India's weekly Top 10 (`data/netflix_matches.csv`) and the
  India-flagged YouTube trailer comments in `data/dataset.csv`. It does not use the forecast model or the India Demand Index.
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
  choosing titles, but don't use them as model inputs. Choosing titles by popularity also favours hits.
- **YouTube view counts are from the day you collected them**, not from launch. For backtesting, use the
  dated comment counts (`yt_comments_pre`, `yt_comments_month1`).
- **Comments are fetched newest first, up to 1,000 per video**, so a very popular trailer's launch-week comments may be missing.
  Compare with the video's total in the `comments` column.
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
  Indian scripts, Hinglish typed in Latin letters, or naming India. Only about 1 in 100 comments match, and fewer
  than 1 in 2,000 use an Indian script. When `comment_languages.csv` exists, AI4Bharat's IndicLID also counts short
  Hinglish the word rules miss ("Kab release hogi ye movie"): 550 Hinglish comments instead of 373, and nearly all
  of the extra ones checked by hand were real Hinglish.
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

## Layout

```
collectors/   the data collectors (common.py holds shared helpers, india_signals.py the word list for India comments)
yosoku/       the model pipeline: labels, features, models, split, evaluate, decision, plus guide and export_web for the site
labels/       label_v1.csv: the India Demand Index of every labelled title (written by yosoku.labels)
predictions/  predictions.json: forecasts and verdicts (written by yosoku.decision)
reports/      generated reports: label.md, evaluation.md / .json, decision.md, and final.md after --final; fix the code, not the report
web/          the dashboard: a static site for Vercel (see "The website"); web/data/ is written by yosoku.export_web, and holds the mock forecasts
tools/        one-off generators (the India map outlines)
tests/        pipeline and website-export tests on fake data (tests/fake_data.py)
docs/         decisions.md: the six choices that shape the dataset, and the change log; read it before changing a default
              demo.md: the 3-minute demo path and prepared answers
data/         CSV outputs; data/raw/ is the cache and is git-ignored; data/upcoming/ would hold unreleased titles
.env          your API key and contact (git-ignored; copy from .env.example)
```

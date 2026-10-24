# Yosoku 予測

Predicting how Japanese anime will perform in India before the launch decision is made.
Thapar Japan Hackathon, GEEK-PS-01, Team shecodes.

This repo currently holds the **data collectors**: small Python scripts that download public data
from official APIs and save it as CSV files in `data/`. Together they build the training dataset
for the India Demand Index described in the idea deck.

| Step | Script | Source | Time | Output in `data/` |
|---|---|---|---|---|
| 1 | `collect_titles.py` | AniList API | ~3 min | `titles.csv` |
| 2 | `collect_wikipedia.py` | Wikidata + Wikipedia pageviews API | ~15–30 min | `wiki_articles.csv`, `wikipedia_daily.csv` |
| 3 | `collect_netflix.py` | Netflix Top 10 download | ~1 min | `netflix_india_top10.csv`, `netflix_matches.csv` |
| 4 | `collect_youtube.py` | YouTube Data API (needs a key) | a few days (daily quota) | `youtube_videos.csv`, `youtube_comments.csv` |
| 5 | `collect_trends.py` | Google Trends via `pytrends-modern` | overnight or longer | `trends_terms.csv`, `trends_india_daily.csv`, `trends_india_states.csv`, `trends_countries.csv` |
| 5b | `collect_reddit.py` (optional) | Reddit posts, read from the Arctic Shift archive | ~15–20 min for 200 titles | `reddit_posts.csv`, `reddit_titles.csv` |
| 6 | `merge.py` | the files above | seconds | `dataset.csv` (one row per title) |

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
5. **Add your settings:** copy `.env.example` to a new file named `.env` and fill it in.
   `.env` holds your API key, so it is git-ignored. Never commit it or paste it in chat.

### Getting a YouTube API key (free, ~5 minutes)

1. Open [console.cloud.google.com](https://console.cloud.google.com/), sign in and create a project (e.g. "yosoku").
2. **APIs & Services → Library**, search **YouTube Data API v3**, click **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Put it in `.env` as `YOUTUBE_API_KEY=...`. In the key's settings, restricting it to the YouTube Data API v3 is a good idea.

Each key gets 10,000 quota units a day, so three teammates with a key each collect three times as fast (see below).

## Running the collectors

Run them from the `yosoku` folder with the virtual environment active:

```
python collectors/collect_titles.py
python collectors/collect_wikipedia.py
python collectors/collect_netflix.py
python collectors/collect_youtube.py
python collectors/collect_trends.py
python collectors/collect_reddit.py    # optional
python collectors/merge.py
```

- **Step 1 comes first**; the others all read `data/titles.csv`. After that, steps 2–5 are independent and can run at the same time in separate terminals.
  **Start Trends (step 5) early**: it is the slowest.
- Every script explains its options with `--help`, e.g. `python collectors/collect_titles.py --help`.
- **Stopping is safe.** Finished work is cached in `data/raw/`; rerun the same command and it carries on.
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
python collectors/collect_trends.py --data-dir data/upcoming
python collectors/merge.py --data-dir data/upcoming
```

Their windows are still running, so these titles are fetched fresh on every run; rerun them before the demo
for the latest buzz. The cache in `data/raw/` is shared between folders, which is safe because it is keyed by
title. Netflix is skipped here: an unreleased title cannot be in a chart yet.

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

After the collectors, run the model pipeline and the dashboard (same folder, virtual environment active):

```
python collectors/merge.py
python -m yosoku.run               # label, evaluation and verdicts
streamlit run app/dashboard.py     # opens the dashboard in your browser
```

| Step | Module | Writes |
|---|---|---|
| Label | `yosoku/labels.py` | `labels/label_v1.csv`, `reports/label.md` (agreement and stability checks, gate G2) |
| Evaluate | `yosoku/evaluate.py` | `reports/evaluation.md` (models against baselines on 2024, gate G4) |
| Decide | `yosoku/decision.py` | `predictions/predictions.json`, `reports/decision.md` (verdicts, gate G5) |

- Until `predictions/predictions.json` exists, the dashboard shows `app/mock_predictions.json`, made from **fake** data, with a banner.
- Unreleased titles: collect them into their own folder, e.g.
  `python collectors/collect_titles.py --start-year 2027 --end-year 2027 --seasons WINTER --data-dir data/upcoming`,
  then rerun `python -m yosoku.run`. They get a cold forecast now, and T−28 / T+7 forecasts once those dates pass
  and their Wikipedia and YouTube data are collected.
- The 2025 test titles are scored once, at the very end: `python -m yosoku.run --final`.
- Tests, including the check that no input uses data from after its forecast moment: `python -m pytest tests`.
- See `docs/decisions.md` for what was fixed in advance and what changed (no Google Trends this round).

## The website (static, for Vercel)

`web/` is the same dashboard as `app/dashboard.py`, rebuilt as a plain static site (no server, no build step):
poster wall, a verdict card for every title, an India language-hub map, the backtest and the method. Vercel can
host it because it is only HTML, CSS, JavaScript and two JSON files.

**Update it after every pipeline run:**

```
python -m yosoku.run                # writes predictions/predictions.json
python -m yosoku.export_web         # copies it to web/data/ and fetches cover art from AniList
git add web/data predictions && git commit -m "Update website data" && git push
```

- Without `predictions/predictions.json` the site shows the mock forecasts with a yellow "Preview data" banner.
  Mock titles get generated Japanese-print posters instead of covers, because their made-up ids collide with real AniList ids.
- `--no-covers` skips the AniList lookup (offline). Covers are links to AniList's image servers, not copies,
  and a cover that fails to load falls back to the generated poster.
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

- **`wiki_articles.csv`**: rows with `match_method` = `search` were guessed. Fix the article names by hand and rerun step 2.
- **`netflix_matches.csv`**: names are matched loosely, and live-action remakes (One Piece, Yu Yu Hakusho) share their anime's name.
  To drop a wrong match, add a line `anilist_id,show_title,reason` to `data/netflix_match_exclusions.csv`
  (first line: `anilist_id,show_title,reason`) and rerun step 3, then step 6. The ones found so far are already listed there.
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
  It only runs when `reddit_posts.csv` exists, and that file is git-ignored: share it between laptops outside git,
  or the model silently runs without it. Scores and comment counts are archived after the post's date, so only
  post counts are used. The `reddit_*` columns in `dataset.csv` are for looking at the data.
- **Trends values are relative** (0–100 within each request). `trends_month1_vs_anchor` puts titles on one scale by
  dividing by the fixed anchor term; keep the same anchor (`--anchor`, default "Naruto") for the whole collection.
- **India comments** (`yt_india_*`, `yt_share_<hub>`) come from a word list in `collectors/india_signals.py`:
  Indian scripts, Hinglish typed in Latin letters, or naming India. Only about 1 in 100 comments match, and fewer
  than 1 in 2,000 use an Indian script. It misses some Indian English; a language-ID model such as AI4Bharat's
  IndicLID is the next step.

## Responsible data use

Public data only: official APIs where they exist (AniList, Wikimedia, YouTube) and Netflix's published file.
No usernames are stored. Google Trends has no open API, so `pytrends-modern` reads the public website;
the script deliberately goes slowly, so please don't lower `--pause` much.

Reddit posts come from the public [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) archive, not from
reddit.com, so nothing is scraped from Reddit's site. Arctic Shift is free and asks users to be considerate, so the
script waits between requests; for large jobs it recommends the monthly dumps instead. Only a post's title, date,
score, comment count and flair are kept, never usernames or post text.

## Layout

```
collectors/   the data collectors (common.py holds shared helpers)
yosoku/       label, features, models, evaluation and verdicts
app/          the Streamlit dashboard, and its mock data
web/          the same dashboard as a static site for Vercel (see "The website"); web/data/ is written by yosoku.export_web
tools/        one-off generators (the India map outlines)
tests/        pipeline tests on fake data (tests/fake_data.py)
docs/         decisions.md: the six choices that shape the dataset; read it before changing a default
data/         CSV outputs; data/raw/ is the cache and is git-ignored
.env          your API key and contact (git-ignored; copy from .env.example)
```

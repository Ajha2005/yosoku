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
python collectors/merge.py
```

- **Step 1 comes first**; the others all read `data/titles.csv`. After that, steps 2–5 are independent and can run at the same time in separate terminals.
  **Start Trends (step 5) early**: it is the slowest.
- Every script explains its options with `--help`, e.g. `python collectors/collect_titles.py --help`.
- **Stopping is safe.** Finished work is cached in `data/raw/`; rerun the same command and it carries on.
- `merge.py` works with whatever has been collected so far, so you can run it any time.

### Choosing titles

`collect_titles.py` keeps the 50 most popular Japanese anime of each season from 2019 to 2025
(about 1,400 titles). Change that with `--start-year`, `--end-year` and `--per-season`.
YouTube and Trends are slow, so they only take the `--limit` most popular titles (default 200).

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

## Check these by hand

Automatic matching makes mistakes. Before modelling, look through:

- **`wiki_articles.csv`**: rows with `match_method` = `search` were guessed. Fix the article names by hand and rerun step 2.
- **`netflix_matches.csv`**: names are matched loosely, and live-action remakes (One Piece, Yu Yu Hakusho) share their anime's name.
- **`youtube_videos.csv`**: a search can return the wrong video. To fix one, edit the list of video IDs in
  `data/raw/youtube/search/<anilist_id>_trailer.json` (or `_hindi.json`) so the right video comes first, then rerun step 4.
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
- **Trends values are relative** (0–100 within each request). `trends_month1_vs_anchor` puts titles on one scale by
  dividing by the fixed anchor term; keep the same anchor (`--anchor`, default "Naruto") for the whole collection.
- **Indian-script detection** (`yt_share_devanagari` etc.) misses Hinglish typed in Latin letters.
  A language-ID model such as AI4Bharat's IndicLID is the next step for that.

## Responsible data use

Public data only: official APIs where they exist (AniList, Wikimedia, YouTube) and Netflix's published file.
No usernames are stored. Google Trends has no open API, so `pytrends-modern` reads the public website;
the script deliberately goes slowly, so please don't lower `--pause` much.

## Layout

```
collectors/   the scripts (common.py holds shared helpers)
data/         CSV outputs; data/raw/ is the cache and is git-ignored
.env          your API key and contact (git-ignored; copy from .env.example)
```

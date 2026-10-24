"""Write a small fake data folder shaped like the collectors' output, for tests and the dashboard mock.

Every number is made up from a hidden "demand" per title, so the pipeline has something to find.
Never mix this folder with real data.

    python tests/fake_data.py /tmp/yosoku-fake      # then: python collectors/merge.py --data-dir /tmp/yosoku-fake
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

GENRES = ["Action", "Adventure", "Comedy", "Drama", "Fantasy", "Romance", "Sci-Fi", "Slice of Life", "Sports", "Mystery"]
TAGS = ["Isekai", "Shounen", "Seinen", "Shoujo", "School", "Super Power", "Magic", "Martial Arts", "Mecha", "Idol"]
SEASONS = {"WINTER": 1, "SPRING": 4, "SUMMER": 7, "FALL": 10}
SCRIPTS = {"devanagari": "नमस्ते बहुत अच्छा", "tamil": "மிகவும் நல்லது", "telugu": "చాలా బాగుంది", "bengali": "খুব ভালো"}


def titles(rng, years, per_season, first_id=1):
    rows, anilist_id = [], first_id
    for year in years:
        for season, month in SEASONS.items():
            for _ in range(per_season):
                genres = list(rng.choice(GENRES, size=rng.integers(1, 4), replace=False))
                tags = list(rng.choice(TAGS, size=rng.integers(1, 4), replace=False))
                start = date(year, month, int(rng.integers(1, 28)))
                rows.append({
                    "anilist_id": anilist_id, "mal_id": anilist_id + 50000,
                    "title_english": f"Fake Anime {anilist_id}", "title_romaji": f"Fake Anime {anilist_id}",
                    "title_japanese": f"偽アニメ{anilist_id}", "synonyms": "", "season": season, "year": year,
                    "start_date": start.isoformat(), "format": rng.choice(["TV", "TV", "TV", "ONA", "MOVIE"]),
                    "episodes": 12, "source": rng.choice(["MANGA", "LIGHT_NOVEL", "ORIGINAL", "WEB_NOVEL"]),
                    "genres": "|".join(genres), "tags": "|".join(tags), "studio": rng.choice(["Studio A", "Studio B", "Studio C"]),
                    "streaming_sites": "Crunchyroll|Netflix" if rng.random() < 0.4 else "Crunchyroll",
                    "is_sequel": 0, "prequel_anilist_id": np.nan, "popularity": 0, "average_score": 70,
                    "synopsis": f"A story about {' and '.join(g.lower() for g in genres)} with {' '.join(t.lower() for t in tags)}.",
                })
                anilist_id += 1
    frame = pd.DataFrame(rows)
    # Demand comes from genres and tags plus noise, so lookalikes carry real signal.
    effect = {"Action": 0.8, "Fantasy": 0.5, "Sports": 0.4, "Romance": -0.3, "Slice of Life": -0.5, "Isekai": 0.6, "Shounen": 0.7}
    frame["demand"] = [sum(effect.get(x, 0) for x in g.split("|") + t.split("|")) + rng.normal(0, 0.8)
                       for g, t in zip(frame["genres"], frame["tags"])]
    for i in range(len(frame)):  # some sequels inherit their prequel's demand
        earlier = frame.index[(frame["year"] < frame.loc[i, "year"])]
        if len(earlier) and rng.random() < 0.2:
            prequel = int(rng.choice(earlier))
            frame.loc[i, ["is_sequel", "prequel_anilist_id", "genres", "tags"]] = \
                [1, float(frame.loc[prequel, "anilist_id"]), frame.loc[prequel, "genres"], frame.loc[prequel, "tags"]]
            frame.loc[i, "demand"] = frame.loc[prequel, "demand"] + rng.normal(0, 0.4)
    frame["popularity"] = (np.exp(frame["demand"] + 8) + rng.normal(0, 100, len(frame))).clip(10).astype(int)
    return frame


def activity(rng, frame, folder, youtube_top=200):
    wiki_rows, articles = [], []
    for row in frame.itertuples():
        start = date.fromisoformat(row.start_date)
        langs = {"en": 1.0, "ja": 1.5} | {lang: 0.05 for lang in ("hi", "ta", "te") if rng.random() < 0.3 + 0.1 * row.demand}
        articles.append({"anilist_id": row.anilist_id, "title": row.title_english, "match_method": "wikidata",
                         **{lang: (row.title_english if lang in langs else "") for lang in ("en", "ja", "hi", "ta", "te")}})
        for lang, scale in langs.items():
            for day in range(-60, 31):
                level = np.exp(row.demand + 5) * scale * (1.6 if day >= 0 else 0.6 + 0.01 * (day + 60))
                wiki_rows.append({"anilist_id": row.anilist_id, "lang": lang, "article": row.title_english,
                                  "date": (start + timedelta(days=day)).isoformat(), "days_from_start": day,
                                  "views": int(rng.poisson(level))})
    pd.DataFrame(articles).to_csv(folder / "wiki_articles.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(wiki_rows).to_csv(folder / "wikipedia_daily.csv", index=False, encoding="utf-8-sig")

    matches = []
    for row in frame[frame["streaming_sites"].str.contains("Netflix")].itertuples():
        weeks = int(np.clip(rng.poisson(np.exp(row.demand)), 0, 10)) if row.start_date >= "2021-06-28" else 0
        for w in range(weeks):
            day = 7 * w + 3
            week = (date.fromisoformat(row.start_date) + timedelta(days=day)).isoformat()
            matches.append({"anilist_id": row.anilist_id, "title_english": row.title_english, "title_romaji": row.title_romaji,
                            "days_from_start": day, "week": week, "category": "TV (English)", "weekly_rank": int(rng.integers(1, 11)),
                            "show_title": row.title_english, "season_title": "", "cumulative_weeks_in_top_10": w + 1})
    pd.DataFrame(matches, columns=["anilist_id", "title_english", "title_romaji", "days_from_start", "week", "category",
                                   "weekly_rank", "show_title", "season_title", "cumulative_weeks_in_top_10"]
                 ).to_csv(folder / "netflix_matches.csv", index=False, encoding="utf-8-sig")

    videos, comments = [], []
    for row in frame.nlargest(youtube_top, "popularity").itertuples():
        start = date.fromisoformat(row.start_date)
        videos.append({"anilist_id": row.anilist_id, "query": f"{row.title_english} official trailer", "search_rank": 1,
                       "video_id": f"v{row.anilist_id}", "video_title": "Trailer", "channel": "Official", "published_at":
                       (start - timedelta(days=70)).isoformat() + "T00:00:00Z", "views": int(row.popularity * 10),
                       "likes": 0, "comments": 0, "audio_language": "ja", "collected_on": "2026-10-24"})
        hub = rng.choice(list(SCRIPTS))
        for c in range(int(np.clip(rng.poisson(np.exp(row.demand + 2.5)), 0, 300))):
            day = int(rng.integers(-70, 60))
            indic = rng.random() < 0.15 + 0.05 * row.demand
            text = SCRIPTS[hub if rng.random() < 0.7 else rng.choice(list(SCRIPTS))] if indic else "great trailer"
            comments.append({"anilist_id": row.anilist_id, "video_id": f"v{row.anilist_id}", "comment_id": f"c{row.anilist_id}_{c}",
                             "published_at": (start + timedelta(days=day)).isoformat() + "T12:00:00Z", "likes": 0,
                             "replies": 0, "text": text})
    pd.DataFrame(videos).to_csv(folder / "youtube_videos.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(comments).to_csv(folder / "youtube_comments.csv", index=False, encoding="utf-8-sig")


def main(folder, seed=0, per_season=25):
    folder = Path(folder)
    rng = np.random.default_rng(seed)
    (folder / "upcoming").mkdir(parents=True, exist_ok=True)
    frame = titles(rng, range(2019, 2026), per_season)
    frame.drop(columns="demand").to_csv(folder / "titles.csv", index=False, encoding="utf-8-sig")
    activity(rng, frame, folder)
    upcoming = titles(rng, [2027], 8, first_id=90001)
    upcoming = upcoming[upcoming["season"] == "WINTER"]
    upcoming.drop(columns="demand").to_csv(folder / "upcoming" / "titles.csv", index=False, encoding="utf-8-sig")
    print(f"Fake data in {folder}: {len(frame)} titles, {len(upcoming)} upcoming")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/yosoku-fake")

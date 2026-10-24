"""Paths and loaders shared by the yosoku modules.

Every command reads the collectors' files from a data folder (default data/) and writes its own
outputs under an output folder (default: the repo root, so labels/, reports/ and predictions/).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "collectors"))
from india_signals import classify, indic_flags  # noqa: E402  (shared with collectors/merge.py)

# Language hubs for the regional view: the keys match india_signals.HUBS and yt_share_<hub>.
HUBS = {
    "hindi": ("Hindi", "Hindi belt: UP, Bihar, MP, Rajasthan, Delhi, Haryana and neighbours (also Marathi)"),
    "bengali": ("Bengali", "West Bengal, Tripura"),
    "tamil": ("Tamil", "Tamil Nadu"),
    "telugu": ("Telugu", "Andhra Pradesh, Telangana"),
    "kannada": ("Kannada", "Karnataka"),
    "malayalam": ("Malayalam", "Kerala"),
}

# AniList tags that name the intended audience; the nearest thing to an age group in public data.
DEMOGRAPHICS = {"Kids": "Kids", "Shounen": "Teens (boys)", "Shoujo": "Teens (girls)",
                "Seinen": "Adults (men)", "Josei": "Adults (women)"}


def add_folder_arguments(parser):
    parser.add_argument("--data-dir", default="data", help="folder with titles.csv and dataset.csv (default: data)")
    parser.add_argument("--out-dir", default=".", help="where labels/, reports/ and predictions/ go (default: repo root)")


def folder(path):
    return ROOT / path


def read(path, required=True):
    if not path.exists():
        if required:
            raise SystemExit(f"{path} not found. Run the collectors and `python collectors/merge.py` first.")
        return None
    return pd.read_csv(path, encoding="utf-8-sig")


def split_list(text):
    return [part for part in str(text).split("|") if part and part != "nan"]


def load_titles(data_dir):
    """dataset.csv (or titles.csv if nothing is merged yet), indexed by anilist_id, with metadata helpers."""
    path = data_dir / "dataset.csv"
    titles = read(path if path.exists() else data_dir / "titles.csv").set_index("anilist_id")
    titles["start"] = pd.to_datetime(titles["start_date"], errors="coerce")
    titles["name"] = titles["title_english"].fillna(titles["title_romaji"])
    titles["genre_list"] = titles["genres"].map(split_list)
    titles["tag_list"] = titles["tags"].map(split_list) if "tags" in titles else [[] for _ in range(len(titles))]
    titles["main_genre"] = titles["genre_list"].map(lambda genres: genres[0] if genres else "Unknown")
    titles["demographic"] = titles["tag_list"].map(
        lambda tags: next((DEMOGRAPHICS[tag] for tag in tags if tag in DEMOGRAPHICS), "Not tagged"))
    titles["is_sequel"] = titles["is_sequel"].fillna(0).astype(int)
    return titles


def load_daily(data_dir, titles):
    """(wikipedia_daily, youtube_comments) with days_from_start; either is None if not collected.

    The comments are one row per comment when their text is here, or else one row per title, video and day from
    youtube_comment_daily.csv (written by merge.py). Either way `n` counts the comments in a row and `india` the
    Indian ones among them.
    """
    wiki = read(data_dir / "wikipedia_daily.csv", required=False)
    comments = read(data_dir / "youtube_comments.csv", required=False)
    if comments is not None:
        published = pd.to_datetime(comments["published_at"], utc=True).dt.tz_localize(None).dt.normalize()
        comments["days_from_start"] = (published - comments["anilist_id"].map(titles["start"])).dt.days
        languages = read(data_dir / "comment_languages.csv", required=False)  # IndicLID, optional
        comments["india"] = classify(comments["text"], indic_flags(comments, languages))["india"].astype(int)
        comments["n"] = 1
    elif (counts := read(data_dir / "youtube_comment_daily.csv", required=False)) is not None:
        comments = counts.assign(days_from_start=(pd.to_datetime(counts["date"]) - counts["anilist_id"].map(titles["start"])).dt.days)
    return wiki, comments


def load_reddit(data_dir):
    """reddit_posts.csv (one row per post, with days_from_start), or None if Reddit was not collected."""
    return read(data_dir / "reddit_posts.csv", required=False)

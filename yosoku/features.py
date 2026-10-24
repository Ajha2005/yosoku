"""Phase 3: each title's model inputs at each forecast moment, from the daily files.

Days are counted from the Japanese start date (day 0). A moment may only use days up to its cutoff:

  cold   metadata only (genres, tags, source, format, audience, sequel), usable any time before launch
  t-28   plus Wikipedia, YouTube and Reddit activity in days -56 to -29
  t+7    plus days -28 to -1 and the launch week, days 0 to 6

Those are the three stages verdicts are made at. A moment can also be a plain day number, the last day it may
use (-15 is a forecast made 14 days before the premiere): the decision clock (yosoku/clock.py) and the daily
job (yosoku/daily.py) forecast between the stages with the same windows, cut off at that day.

Today's AniList popularity and score and YouTube view counts are never inputs: they are measured on
the day of collection, not at the forecast moment. Nor is whether a title was searched on YouTube: only
the most popular titles were, by today's popularity. tests/test_pipeline.py checks the cutoffs.
"""

import numpy as np
import pandas as pd

from yosoku.data import DEMOGRAPHICS

MOMENTS = ["cold", "t-28", "t+7"]
CUTOFF = {"cold": None, "t-28": -29, "t+7": 6}  # last day a moment may use
SPANS = [("early", -56, -29), ("pre", -28, -1), ("launch", 0, 6), ("week2", 7, 13), ("week3", 14, 20), ("week4", 21, 27)]


def spans_until(cutoff):
    """{window: (first day, last day)} of the spans that start by `cutoff`, the last one cut short at it."""
    return {name: (lo, min(hi, cutoff)) for name, lo, hi in SPANS if lo <= cutoff}


WINDOWS = {"cold": {}, "t-28": spans_until(CUTOFF["t-28"]), "t+7": spans_until(CUTOFF["t+7"])}
WINDOW_NAMES = {"early": "days -56 to -29", "pre": "last 28 days", "launch": "launch week",
                "week2": "week 2", "week3": "week 3", "week4": "week 4"}


def stage(moment):
    """(cutoff, windows) of a moment: one of MOMENTS, or the last day it may use as an int."""
    if moment in CUTOFF:
        return CUTOFF[moment], WINDOWS[moment]
    return int(moment), spans_until(int(moment))
WIKI_GROUPS = {"en": ["en"], "ja": ["ja"], "india": ["hi", "ta", "te"]}
FORMATS = ["TV", "TV_SHORT", "ONA", "MOVIE"]
SOURCES = ["MANGA", "LIGHT_NOVEL", "ORIGINAL", "VIDEO_GAME", "WEB_NOVEL", "NOVEL"]

# Drivers are reported per business signal: features that move together are summed, so their
# separate coefficients can't offset each other on screen.
SIGNALS = {
    "wiki_en": "Global buzz", "wiki_ja": "Global buzz", "yt_comments": "Global buzz", "reddit_posts": "Global buzz",
    "wiki_india": "India buzz", "has_india_article": "India buzz", "yt_india": "India buzz",
    "is_sequel": "Franchise history", "prequel_label": "Franchise history", "has_prequel_label": "Franchise history",
    "lookalike": "Similar past titles",
}
SIGNAL_NOTES = {
    "Global buzz": "English and Japanese Wikipedia views, trailer comments and Reddit posts worldwide",
    "India buzz": "Hindi, Tamil and Telugu Wikipedia views and trailer comments by people in India",
    "Franchise history": "whether it is a sequel, and how its prequel did in India",
    "Similar past titles": "the India index of the 10 most similar past titles",
}


def signal(feature):
    """The business signal a feature belongs to, e.g. wiki_india_early -> India buzz, genre_Action -> Genre: Action."""
    base, _, window = feature.rpartition("_")
    if window in WINDOW_NAMES:
        feature = base
    for prefix, kind in (("genre_", "Genre"), ("format_", "Format"), ("source_", "Source"), ("audience_", "Audience")):
        if feature.startswith(prefix):
            return f"{kind}: {feature[len(prefix):].replace('_', ' ').title()}"
    return SIGNALS.get(feature, feature)


def window_total(rows, value, lo, hi, cutoff, ids):
    """Sum of rows[value] per title over days lo..hi, which must end by the moment's cutoff."""
    if cutoff is None or hi > cutoff:
        raise ValueError(f"window {lo}..{hi} ends after the cutoff day {cutoff}: that would be leakage")
    inside = rows[rows["days_from_start"].between(lo, hi)]
    return inside.groupby("anilist_id")[value].sum().reindex(ids)


def metadata(titles, genres):
    out = pd.DataFrame(index=titles.index)
    out["is_sequel"] = titles["is_sequel"]
    for genre in genres:
        out[f"genre_{genre}"] = titles["genre_list"].map(lambda g, genre=genre: int(genre in g))
    for fmt in FORMATS:
        out[f"format_{fmt}"] = (titles["format"] == fmt).astype(int)
    for source in SOURCES:
        out[f"source_{source}"] = (titles["source"] == source).astype(int)
    for audience in DEMOGRAPHICS.values():
        out[f"audience_{audience}"] = (titles["demographic"] == audience).astype(int)
    return out


def activity(titles, wiki, comments, moment, reddit=None):
    """Wikipedia views, trailer comments and Reddit posts in each of the moment's windows, log1p; unknown is blank, not 0."""
    out = pd.DataFrame(index=titles.index)
    cutoff, windows = stage(moment)
    posts = None if reddit is None else reddit.assign(one=1)
    for window, (lo, hi) in windows.items():
        if wiki is not None:
            for group, langs in WIKI_GROUPS.items():
                rows = wiki[wiki["lang"].isin(langs)]
                views = np.log1p(window_total(rows, "views", lo, hi, cutoff, titles.index).fillna(0))
                if group != "india":  # India has has_india_article instead: few titles have such an article
                    # No rows by the cutoff: the matched article did not exist yet, so the views are unknown.
                    views = views.where(titles.index.isin(rows.loc[rows["days_from_start"] <= cutoff, "anilist_id"]))
                out[f"wiki_{group}_{window}"] = views
        if comments is not None:
            for name, column in (("yt_comments", "n"), ("yt_india", "india")):
                count = window_total(comments, column, lo, hi, cutoff, titles.index)
                # Only the most popular titles were searched on YouTube: the rest are blank, not zero.
                out[f"{name}_{window}"] = np.log1p(count.fillna(0)).where(searched(titles, comments))
        if posts is not None:
            # Post counts only: scores and comment counts are archived after the post, so they would leak.
            count = window_total(posts, "one", lo, hi, cutoff, titles.index)
            out[f"reddit_posts_{window}"] = np.log1p(count.fillna(0)).where(searched_reddit(titles, posts))
    if windows and wiki is not None:
        # An Indian-language article counts once it has views by the cutoff: one written later was not known yet.
        india = wiki[wiki["lang"].isin(WIKI_GROUPS["india"]) & (wiki["days_from_start"] <= cutoff)]
        out["has_india_article"] = titles.index.isin(india["anilist_id"]).astype(int)
    # No "was searched on YouTube" input: the titles searched were the most popular by today's count, after the outcome.
    return out


def searched(titles, comments):
    if "yt_comments_month1" in titles:
        return titles["yt_comments_month1"].notna()
    return pd.Series(titles.index.isin(comments["anilist_id"]), index=titles.index)


def searched_reddit(titles, posts):
    """Titles whose Reddit posts were collected: the rest are blank, not zero."""
    if "reddit_posts_month1" in titles:
        return titles["reddit_posts_month1"].notna()
    return pd.Series(titles.index.isin(posts["anilist_id"]), index=titles.index)


def build(titles, wiki, comments, moment, genres, reddit=None):
    """Feature table for one moment; the lookalike and prequel inputs are added by the models."""
    return pd.concat([metadata(titles, genres), activity(titles, wiki, comments, moment, reddit)], axis=1)


def prequel_label(titles, labels):
    """Each title's prequel's India index (labels: Series by anilist_id), if the prequel's label window
    ended 28+ days before this title starts."""
    prequel = pd.to_numeric(titles["prequel_anilist_id"], errors="coerce")
    known = prequel.map(labels)
    prequel_end = prequel.map(titles["start"]) + pd.Timedelta(days=27)
    in_time = prequel_end < titles["start"] - pd.Timedelta(days=28)
    return known.where(in_time)

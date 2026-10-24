"""Step 6: join every collector's output into data/dataset.csv, one row per title.

Works with whichever outputs exist so far; sources not collected yet are skipped.
Daily values are summed or averaged over windows counted in days from the
Japanese start date:

  pre     the 28 days before start (all you know before launch)
  week1   start day and the 6 days after
  month1  start day and the 27 days after (the deck's "week 4" horizon)
  early   Reddit only: days -90 to -29, before the T-28 forecast moment

yt_india_* counts comments written by people in India (Indian scripts, Hinglish typed in Latin
letters, or naming India); yt_share_<hub> is the share pointing to each language hub, and
yt_dub_share the share of the Indian ones asking for or about an Indian-language dub. If
comment_languages.csv exists (collectors/detect_languages.py), IndicLID helps find Hinglish.

All of those come from youtube_comment_daily.csv: comments counted per title, video and day, with
no text. It is rebuilt from youtube_comments.csv whenever the comment text is here, and read as it
is when it is not, so the text never has to be shared or kept for the pipeline to run. Beside it,
youtube_ask_daily.csv counts the comments asking for a dub (by language) or for where to watch, for
the Demand guide; it is not a model input.

A blank cell means "no data", which is different from zero: a title with no
Hindi Wikipedia article, a title not on Netflix, or one that started before
Netflix published India charts. Keep the two apart in the India Demand Index.

A folder for another market (collectors/markets.py) gets that country's Netflix chart and
Wikipedia languages instead of India's; trailer comments and Trends are India only.

    python collectors/merge.py
"""

import argparse

import pandas as pd

from common import add_data_dir_argument, current_market, data_file, read_titles, use_data_dir
from india_signals import COUNTS, HUBS, classify, daily_asks, daily_counts, indic_flags

WINDOWS = {"pre": (-28, -1), "week1": (0, 6), "month1": (0, 27)}
# Reddit also gets "early", the days before the T-28 forecast moment (see docs/decisions.md).
REDDIT_WINDOWS = {"early": (-90, -29), **WINDOWS}
GLOBAL_WIKI_LANGS = ["en", "ja"]  # then the market's languages (India: hi, ta, te; see markets.py)
NETFLIX_CHARTS_START = "2021-06-28"  # first week of Netflix's per-country lists
NETFLIX_DAYS = 90
OUT_CSV = "dataset.csv"
COUNTS_CSV = "youtube_comment_daily.csv"
ASKS_CSV = "youtube_ask_daily.csv"  # what Indian fans ask for, by day (the Demand guide; not a model input)


def load(name):
    path = data_file(name)
    if not path.exists():
        print(f"  {name} not found; skipping it")
        return None
    return pd.read_csv(path, encoding="utf-8-sig")


def window_totals(rows, value, how, index, windows=WINDOWS):
    """{window: Series indexed by anilist_id} of rows[value] summed or averaged within each window."""
    totals = {}
    for window, (lo, hi) in windows.items():
        inside = rows[rows["days_from_start"].between(lo, hi)]
        totals[window] = inside.groupby("anilist_id")[value].agg(how).reindex(index)
    return totals


def wikipedia(titles):
    daily, articles = load("wikipedia_daily.csv"), load("wiki_articles.csv")
    if daily is None or articles is None:
        return None
    articles = articles.set_index("anilist_id").reindex(titles.index)
    out = pd.DataFrame(index=titles.index)
    for lang in GLOBAL_WIKI_LANGS + current_market()["wiki"]:
        # Days with no views are absent from the API's answer, but an article with no rows at all in the
        # 240-day window did not exist yet (often a "season 1" page written later), so its views are unknown.
        has_rows = titles.index.isin(daily.loc[daily["lang"] == lang, "anilist_id"])
        has_article = articles[lang].notna() & titles["start_date"].notna() & has_rows
        for window, views in window_totals(daily[daily["lang"] == lang], "views", "sum", titles.index).items():
            out[f"wiki_{lang}_{window}"] = views.fillna(0).where(has_article)
    return out


def netflix(titles):
    matches = load("netflix_matches.csv")
    if matches is None:
        return None
    inside = matches[matches["days_from_start"].between(0, NETFLIX_DAYS)]
    weeks = inside.groupby("anilist_id")["week"].nunique().reindex(titles.index).fillna(0)
    charts_cover_it = titles["start_date"].fillna("") >= NETFLIX_CHARTS_START
    on_netflix = titles["streaming_sites"].fillna("").str.contains("Netflix") | (weeks > 0)
    return pd.DataFrame({
        f"netflix_top10_weeks_{NETFLIX_DAYS}d": weeks.where(charts_cover_it & on_netflix),
        f"netflix_best_rank_{NETFLIX_DAYS}d": inside.groupby("anilist_id")["weekly_rank"].min().reindex(titles.index),
    })


def comment_counts():
    """Daily comment counts (india_signals.daily_counts): rebuilt and saved from the comment text if it is here,
    with the daily asks beside them (india_signals.daily_asks)."""
    if not data_file("youtube_comments.csv").exists():
        return load(COUNTS_CSV)
    comments = load("youtube_comments.csv")
    found = classify(comments["text"], indic_flags(comments, load("comment_languages.csv")))
    counts = daily_counts(comments, found=found)
    counts.to_csv(data_file(COUNTS_CSV), index=False, encoding="utf-8-sig")
    daily_asks(comments, found=found).to_csv(data_file(ASKS_CSV), index=False, encoding="utf-8-sig")
    return counts


def youtube(titles):
    videos = load("youtube_videos.csv")
    if videos is None:
        return None
    out = pd.DataFrame(index=titles.index)
    searched = titles.index.isin(videos["anilist_id"])
    top = videos[videos["search_rank"] == 1]
    for kind, suffix in (("trailer", "official trailer"), ("hindi", "hindi dub")):
        first = top[top["query"].str.endswith(suffix)].drop_duplicates("anilist_id").set_index("anilist_id")
        out[f"yt_{kind}_views"] = first["views"].reindex(titles.index)

    counts = comment_counts()
    if counts is None:
        return out
    # A title whose videos have comments but none in the file was not collected (quota ran out): unknown, not 0.
    has_comments = videos.groupby("anilist_id")["comments"].sum().reindex(titles.index).fillna(0) > 0
    searched = searched & (titles.index.isin(counts["anilist_id"]) | ~has_comments.to_numpy())
    start = pd.to_datetime(titles["start_date"])
    counts["days_from_start"] = (pd.to_datetime(counts["date"]) - counts["anilist_id"].map(start)).dt.days
    for window, count in window_totals(counts, "n", "sum", titles.index).items():
        out[f"yt_comments_{window}"] = count.fillna(0).where(searched)
    # Comments by people in India: Indian scripts, Hinglish or naming India (see india_signals.py).
    for window, count in window_totals(counts, "india", "sum", titles.index).items():
        out[f"yt_india_{window}"] = count.fillna(0).where(searched)
    by_title = counts.groupby("anilist_id")[COUNTS].sum()
    out["yt_share_india"] = (by_title["india"] / by_title["n"]).reindex(titles.index)
    # Of the Indian comments, the share asking for or about a Hindi, Tamil or other Indian-language dub.
    out["yt_dub_share"] = (by_title["dub_ask"] / by_title["india"].where(by_title["india"] > 0)).reindex(titles.index)
    for hub in HUBS:
        out[f"yt_share_{hub}"] = (by_title[hub] / by_title["n"]).reindex(titles.index)
    # How many comments the regional view rests on: those pointing to at least one language hub.
    out["yt_hub_comments"] = by_title["any_hub"].reindex(titles.index)
    return out


def trends(titles):
    terms, daily = load("trends_terms.csv"), load("trends_india_daily.csv")
    if terms is None or daily is None:
        return None
    out = pd.DataFrame(index=titles.index)
    collected = titles.index.isin(terms["anilist_id"])
    for window, mean in window_totals(daily, "title_interest", "mean", titles.index).items():
        # A collected title with no rows had too few searches for Trends to report: treat as 0.
        out[f"trends_{window}"] = mean.fillna(0).where(collected)
    anchor = daily.groupby("anilist_id")["anchor_interest"].mean().reindex(titles.index)
    out["trends_month1_vs_anchor"] = out["trends_month1"] / anchor.where(anchor > 0)

    countries = load("trends_countries.csv")
    if countries is not None:
        countries["rank"] = countries.groupby("anilist_id")["interest"].rank(ascending=False, method="min")
        india = countries[countries["country_code"] == "IN"].set_index("anilist_id")
        out["trends_india_country_interest"] = india["interest"].reindex(titles.index)
        out["trends_india_country_rank"] = india["rank"].reindex(titles.index)

    states = load("trends_india_states.csv")
    if states is not None:
        positive = states[states["interest"] > 0]
        out["trends_states_with_interest"] = positive.groupby("anilist_id").size().reindex(titles.index).fillna(0).where(collected)
        top = states.sort_values("interest", ascending=False).drop_duplicates("anilist_id").set_index("anilist_id")
        out["trends_top_state"] = top["state"].where(top["interest"] > 0).reindex(titles.index)
    return out


def reddit(titles):
    posts, finished = load("reddit_posts.csv"), load("reddit_titles.csv")
    if posts is None or finished is None:
        return None
    out = pd.DataFrame(index=titles.index)
    collected = titles.index.isin(finished["anilist_id"])
    posts["posts"] = 1
    for value, name in (("posts", "posts"), ("score", "score"), ("num_comments", "comments")):
        for window, total in window_totals(posts, value, "sum", titles.index, REDDIT_WINDOWS).items():
            # A finished title with no matching posts had none: 0, not blank.
            out[f"reddit_{name}_{window}"] = total.fillna(0).where(collected)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir, args.market)

    read_titles()  # exits with a hint if titles.csv is missing
    titles = pd.read_csv(data_file("titles.csv"), encoding="utf-8-sig").set_index("anilist_id")
    parts = [titles]
    for source in (wikipedia, netflix, youtube, trends, reddit):
        part = source(titles)
        if part is not None:
            covered = part.notna().any(axis=1).sum()
            print(f"{source.__name__}: data for {covered} of {len(titles)} titles")
            parts.append(part)

    dataset = pd.concat(parts, axis=1)
    dataset.to_csv(data_file(OUT_CSV), encoding="utf-8-sig")
    print(f"Saved {len(dataset)} titles x {dataset.shape[1]} columns to {data_file(OUT_CSV)}")


if __name__ == "__main__":
    main()

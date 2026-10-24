"""Step 4: YouTube trailers for each title, with their view counts and comments.

Needs a free YouTube Data API key in .env (see README). Google gives each key
10,000 quota units a day: a search costs 100 units, a page of 100 comments 1
unit. With two searches per title that is roughly 35 titles a day, so the
script stops when it reaches --budget and carries on where it stopped when you
run it again the next day (finished work is cached in data/raw/youtube/).

For each title it searches "<name> official trailer" and "<name> hindi dub",
published from a year before to 60 days after the Japanese start date, and
keeps the top results.

  data/youtube_videos.csv    candidate videos per title, with views/likes/comments as of the day collected
  data/youtube_comments.csv  comment text, date and likes (no usernames)

Check youtube_videos.csv: a search can return the wrong video.

With --refresh, a title still in play (start date unknown, to come, or at most 90 days ago: common.is_active) is
kept up to date instead of being collected once: its comments are fetched newest first until the newest one
already cached, so a daily run catches every comment as it comes (a single fetch keeps only the newest
--comment-pages pages, and a busy trailer loses its launch week); it is searched again every --search-every days,
so trailers posted later are found; and its videos' views, likes and comment counts are logged each day to

  data/youtube_video_stats.csv  one row per video per day collected, for the last 30 days only: YouTube keeps no
                                history of these counts, and its API policies let a client keep statistics it is
                                not authorised by the channel to keep for 30 days at most

    python collectors/collect_youtube.py
    python collectors/collect_youtube.py --limit 100 --budget 9000 --no-hindi
    python collectors/collect_youtube.py --data-dir data/upcoming --refresh   # daily, for titles still in play
"""

import argparse
import os
import sys
from datetime import date, timedelta

import requests

from common import (RAW_DIR, add_data_dir_argument, cached, data_file, india_only, is_active, load_json, parse_date,
                    read_csv, read_titles, request_json, save_json, use_data_dir, write_csv)

API_URL = "https://www.googleapis.com/youtube/v3/"
CACHE = RAW_DIR / "youtube"
VIDEOS_CSV = "youtube_videos.csv"
COMMENTS_CSV = "youtube_comments.csv"
STATS_CSV = "youtube_video_stats.csv"
MAX_UNITS_PER_TITLE = 300  # two searches plus comment pages; stops a run before it overshoots the budget

VIDEO_FIELDS = [
    "anilist_id", "query", "search_rank", "video_id", "video_title", "channel", "published_at",
    "views", "likes", "comments", "audio_language", "collected_on",
]
COMMENT_FIELDS = ["anilist_id", "video_id", "comment_id", "published_at", "likes", "replies", "text"]
STATS_FIELDS = ["video_id", "collected_on", "views", "likes", "comments"]
STATS_DAYS = 30  # YouTube API policies: statistics kept without the channel owner's authorisation, 30 days at most


class QuotaExceeded(Exception):
    pass


class YouTube:
    def __init__(self, key):
        self.key = key
        self.units_used = 0

    def get(self, endpoint, cost, **params):
        self.units_used += cost
        try:
            return request_json("GET", API_URL + endpoint, params={**params, "key": self.key})
        except requests.HTTPError as error:
            if error_reason(error) in ("quotaExceeded", "dailyLimitExceeded"):
                raise QuotaExceeded() from None
            raise


def error_reason(error):
    try:
        return error.response.json()["error"]["errors"][0]["reason"]
    except (ValueError, KeyError, IndexError):
        return ""


def queries_for(title, hindi):
    """[(kind, search text)] for a title."""
    name = title["title_english"] or title["title_romaji"]
    queries = [("trailer", f"{name} official trailer")]
    if hindi:
        queries.append(("hindi", f"{name} hindi dub"))
    return queries


def search_path(title, kind):
    return CACHE / "search" / f"{title['anilist_id']}_{kind}.json"


def comments_path(video_id):
    return CACHE / "comments" / f"{video_id}.json"


def stats_path(video_id):
    return CACHE / "stats" / f"{video_id}.json"


def rfc3339(day):
    return f"{day.isoformat()}T00:00:00Z"


def search(youtube, query, start_date, max_results):
    params = {"part": "snippet", "q": query, "type": "video", "maxResults": max_results, "regionCode": "IN"}
    if start_date:
        params["publishedAfter"] = rfc3339(start_date - timedelta(days=365))
        params["publishedBefore"] = rfc3339(start_date + timedelta(days=60))
    data = youtube.get("search", 100, **params)
    return [item["id"]["videoId"] for item in data["items"]]


def fetch_comments(youtube, video_id, max_pages, known=frozenset()):
    """Newest comments first, up to max_pages pages of 100; stops after a page whose oldest comment is in `known`.

    (Its oldest, not any: one older comment out of order at the top, such as a pinned one, must not end the scan.)"""
    comments, token = [], None
    for _ in range(max_pages):
        params = {"part": "snippet", "videoId": video_id, "maxResults": 100, "order": "time", "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        try:
            data = youtube.get("commentThreads", 1, **params)
        except requests.HTTPError as error:
            if error_reason(error) in ("commentsDisabled", "videoNotFound", "forbidden"):
                break
            raise
        page = []
        for item in data["items"]:
            top = item["snippet"]["topLevelComment"]["snippet"]
            page.append({
                "comment_id": item["id"],
                "published_at": top["publishedAt"],
                "likes": top.get("likeCount", 0),
                "replies": item["snippet"].get("totalReplyCount", 0),
                "text": top.get("textDisplay", ""),
            })
        comments += [c for c in page if c["comment_id"] not in known]
        token = data.get("nextPageToken")
        if not token or (page and page[-1]["comment_id"] in known):
            break
    return comments


def refresh_comments(youtube, video_id, max_pages):
    """Put the comments posted since the cached ones on top of them; returns how many were new."""
    path = comments_path(video_id)
    old = load_json(path) if path.exists() else []
    new = fetch_comments(youtube, video_id, max_pages, {c["comment_id"] for c in old})
    save_json(path, new + old)
    return len(new)


def refresh_search(youtube, title, kind, query, start_date, args, today):
    """A title's video ids, searched again once the last search is --search-every days old; new ones go after the old."""
    path = search_path(title, kind)
    if path.exists() and (today - date.fromtimestamp(path.stat().st_mtime)).days < args.search_every:
        return load_json(path)
    old = load_json(path) if path.exists() else []
    ids = old + [v for v in search(youtube, query, start_date, args.videos_per_query) if v not in old]
    save_json(path, ids)
    return ids


def fetch_stats(youtube, video_ids):
    """Cache today's title, channel and counts for videos that have none cached yet."""
    missing = [v for v in video_ids if not stats_path(v).exists()]
    for start in range(0, len(missing), 50):
        batch = missing[start:start + 50]
        data = youtube.get("videos", 1, part="snippet,statistics", id=",".join(batch))
        found = {item["id"]: item for item in data["items"]}
        for video_id in batch:  # deleted videos get an empty entry, so they are not asked for again
            save_json(stats_path(video_id), {"collected_on": date.today().isoformat(), **found.get(video_id, {})})


def log_stats(youtube, video_ids, today):
    """Today's counts for these videos: refreshed in the stats cache and returned as rows for youtube_video_stats.csv."""
    rows = []
    for start in range(0, len(video_ids), 50):
        data = youtube.get("videos", 1, part="snippet,statistics", id=",".join(video_ids[start:start + 50]))
        for item in data["items"]:
            save_json(stats_path(item["id"]), {"collected_on": today.isoformat(), **item})
            counts = item.get("statistics", {})
            rows.append({"video_id": item["id"], "collected_on": today.isoformat(), "views": counts.get("viewCount", ""),
                         "likes": counts.get("likeCount", ""), "comments": counts.get("commentCount", "")})
    return rows


def append_stats(rows, today):
    """Add rows to youtube_video_stats.csv and drop those older than STATS_DAYS; a video collected twice on one day
    keeps the later counts."""
    path = data_file(STATS_CSV)
    oldest = (today - timedelta(days=STATS_DAYS)).isoformat()
    kept = {(r["video_id"], r["collected_on"]): r for r in (read_csv(path) if path.exists() else []) + rows
            if r["collected_on"] > oldest}
    write_csv(path, list(kept.values()), STATS_FIELDS)


def video_row(title, query, rank, video_id):
    stats = load_json(stats_path(video_id)) if stats_path(video_id).exists() else {}
    snippet, statistics = stats.get("snippet", {}), stats.get("statistics", {})
    return {
        "anilist_id": title["anilist_id"],
        "query": query,
        "search_rank": rank,
        "video_id": video_id,
        "video_title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "views": statistics.get("viewCount", ""),
        "likes": statistics.get("likeCount", ""),
        "comments": statistics.get("commentCount", ""),
        "audio_language": snippet.get("defaultAudioLanguage", ""),
        "collected_on": stats.get("collected_on", ""),
    }


def collect(youtube, titles, args, today):
    """Search and fetch comments title by title (with --refresh, bring titles in play up to date); False if the budget
    ran out first."""
    for i, title in enumerate(titles, 1):
        if youtube.units_used + MAX_UNITS_PER_TITLE > args.budget:
            print(f"Reached the budget of {args.budget} units; run again tomorrow to continue.")
            return False
        start_date = parse_date(title["start_date"])
        live = args.refresh and is_active(start_date, today)
        for kind, query in queries_for(title, args.hindi):
            if live:
                video_ids = refresh_search(youtube, title, kind, query, start_date, args, today)
            else:
                video_ids = cached(search_path(title, kind),
                                   lambda: search(youtube, query, start_date, args.videos_per_query))
            for video_id in video_ids:
                if live:
                    refresh_comments(youtube, video_id, args.comment_pages)
                else:
                    cached(comments_path(video_id), lambda: fetch_comments(youtube, video_id, args.comment_pages))
        if i % 10 == 0:
            print(f"{i}/{len(titles)} titles, {youtube.units_used} units used")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=200, help="the N most popular titles")
    parser.add_argument("--skip", type=int, default=0, help="skip the first N of those (to split work between keys)")
    parser.add_argument("--budget", type=int, default=9000, help="quota units to spend in this run")
    parser.add_argument("--videos-per-query", type=int, default=3)
    parser.add_argument("--comment-pages", type=int, default=10, help="pages of 100 comments per video")
    parser.add_argument("--no-hindi", dest="hindi", action="store_false", help="skip the Hindi-dub search (halves the cost)")
    parser.add_argument("--refresh", action="store_true",
                        help="bring titles still in play up to date: new comments, new searches, today's view counts")
    parser.add_argument("--search-every", type=int, default=7, help="with --refresh, days between searches of a title")
    parser.add_argument("--today", default=date.today().isoformat(), help="the collection date (for tests)")
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir, args.market)
    india_only("Trailer comments")
    today = date.fromisoformat(args.today)

    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY is missing. Copy .env.example to .env and add your key (see README).")
    youtube = YouTube(key)
    titles = read_titles(args.limit)[args.skip:]

    try:
        if collect(youtube, titles, args, today):
            print("Searches and comments done for every title in range.")
    except QuotaExceeded:
        print("YouTube says this key's daily quota is used up; run again tomorrow to continue.")

    # Build the output files from everything cached so far, including earlier runs.
    found = []
    for title in titles:
        for kind, query in queries_for(title, args.hindi):
            if search_path(title, kind).exists():
                found += [(title, query, rank, v) for rank, v in enumerate(load_json(search_path(title, kind)), 1)]
    try:
        fetch_stats(youtube, list(dict.fromkeys(video_id for *_, video_id in found)))
        if args.refresh:  # titles in play: today's counts, logged because YouTube keeps no history of them
            live = [v for title, _, _, v in found if is_active(parse_date(title["start_date"]), today)]
            append_stats(log_stats(youtube, list(dict.fromkeys(live)), today), today)
    except QuotaExceeded:
        print("No quota left for view counts; they will be filled in on the next run.")

    video_rows = [video_row(*item) for item in found]
    comment_rows, done = [], set()
    for title, _, _, video_id in found:
        if (title["anilist_id"], video_id) in done or not comments_path(video_id).exists():
            continue
        done.add((title["anilist_id"], video_id))
        comment_rows += [{"anilist_id": title["anilist_id"], "video_id": video_id, **c}
                         for c in load_json(comments_path(video_id))]

    write_csv(data_file(VIDEOS_CSV), video_rows, VIDEO_FIELDS)
    write_csv(data_file(COMMENTS_CSV), comment_rows, COMMENT_FIELDS)
    print(f"Saved {len(video_rows)} videos to {data_file(VIDEOS_CSV)} and {len(comment_rows)} comments to {data_file(COMMENTS_CSV)}")
    print(f"Quota units used this run: {youtube.units_used}")


if __name__ == "__main__":
    main()

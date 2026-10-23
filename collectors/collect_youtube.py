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

    python collectors/collect_youtube.py
    python collectors/collect_youtube.py --limit 100 --budget 9000 --no-hindi
"""

import argparse
import os
import sys
from datetime import date, timedelta

import requests

from common import DATA_DIR, RAW_DIR, cached, load_json, parse_date, read_titles, request_json, save_json, write_csv

API_URL = "https://www.googleapis.com/youtube/v3/"
CACHE = RAW_DIR / "youtube"
VIDEOS_CSV = DATA_DIR / "youtube_videos.csv"
COMMENTS_CSV = DATA_DIR / "youtube_comments.csv"
MAX_UNITS_PER_TITLE = 300  # two searches plus comment pages; stops a run before it overshoots the budget

VIDEO_FIELDS = [
    "anilist_id", "query", "search_rank", "video_id", "video_title", "channel", "published_at",
    "views", "likes", "comments", "audio_language", "collected_on",
]
COMMENT_FIELDS = ["anilist_id", "video_id", "comment_id", "published_at", "likes", "replies", "text"]


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


def fetch_comments(youtube, video_id, max_pages):
    """Newest comments first, up to max_pages pages of 100."""
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
        for item in data["items"]:
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id": item["id"],
                "published_at": top["publishedAt"],
                "likes": top.get("likeCount", 0),
                "replies": item["snippet"].get("totalReplyCount", 0),
                "text": top.get("textDisplay", ""),
            })
        token = data.get("nextPageToken")
        if not token:
            break
    return comments


def fetch_stats(youtube, video_ids):
    """Cache today's title, channel and counts for videos that have none cached yet."""
    missing = [v for v in video_ids if not stats_path(v).exists()]
    for start in range(0, len(missing), 50):
        batch = missing[start:start + 50]
        data = youtube.get("videos", 1, part="snippet,statistics", id=",".join(batch))
        found = {item["id"]: item for item in data["items"]}
        for video_id in batch:  # deleted videos get an empty entry, so they are not asked for again
            save_json(stats_path(video_id), {"collected_on": date.today().isoformat(), **found.get(video_id, {})})


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


def collect(youtube, titles, args):
    """Search and fetch comments title by title; False if the budget ran out first."""
    for i, title in enumerate(titles, 1):
        if youtube.units_used + MAX_UNITS_PER_TITLE > args.budget:
            print(f"Reached the budget of {args.budget} units; run again tomorrow to continue.")
            return False
        start_date = parse_date(title["start_date"])
        for kind, query in queries_for(title, args.hindi):
            video_ids = cached(search_path(title, kind),
                               lambda: search(youtube, query, start_date, args.videos_per_query))
            for video_id in video_ids:
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
    args = parser.parse_args()

    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY is missing. Copy .env.example to .env and add your key (see README).")
    youtube = YouTube(key)
    titles = read_titles(args.limit)[args.skip:]

    try:
        if collect(youtube, titles, args):
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

    write_csv(VIDEOS_CSV, video_rows, VIDEO_FIELDS)
    write_csv(COMMENTS_CSV, comment_rows, COMMENT_FIELDS)
    print(f"Saved {len(video_rows)} videos to {VIDEOS_CSV} and {len(comment_rows)} comments to {COMMENTS_CSV}")
    print(f"Quota units used this run: {youtube.units_used}")


if __name__ == "__main__":
    main()

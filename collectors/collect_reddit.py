"""Step 5b (optional): Reddit posts about each title around its launch.

Reads the Arctic Shift archive of public Reddit posts, not reddit.com itself: it
needs no key and no login. For each title it searches the subreddits for posts
that mention the title's name, from 90 days before to 27 days after the Japanese
start date, and keeps only the post's title, date, score, comment count and flair.
No usernames and no post text are requested or stored.

  data/reddit_posts.csv   one row per matching post (large, git-ignored)
  data/reddit_titles.csv  one row per finished title: the names searched and how many posts matched

Things to know:
- Reddit has no country signal. This is global attention to a title, a hype input
  for the models, not a measure of demand in India. It is not part of the India Demand Index.
- Posts are matched by name (`match_name` in reddit_posts.csv). Short or common names
  are noisy, and a sequel's name also matches posts about earlier seasons. Look through the file.
- Scores and comment counts are as archived, after the post's date. The number of posts
  is the safest input for a forecast made before launch.
- Arctic Shift promises no uptime. A query that keeps failing is reported at the end, and
  its title is left out of the files until a rerun succeeds. Finished queries are cached
  in data/raw/reddit/, so stopping and rerunning is safe.
- A query stops after 1,000 posts (oldest first) and its title is marked `truncated`.

    python collectors/collect_reddit.py
    python collectors/collect_reddit.py --limit 500 --subreddits anime
"""

import argparse
import hashlib
import time
from datetime import date, datetime, timedelta, timezone

import requests

from common import (RAW_DIR, add_data_dir_argument, cached, data_file, normalize, parse_date, read_titles,
                    request_json, search_names, use_data_dir, write_csv)

API_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
CACHE = RAW_DIR / "reddit"
POSTS_CSV = "reddit_posts.csv"
TITLES_CSV = "reddit_titles.csv"

DAYS_BEFORE = 90
DAYS_AFTER = 27  # the deck's "week 4" horizon, as in merge.py
PAGE_SIZE = 100
MAX_PAGES = 10
MIN_NAME_LENGTH = 4  # shorter names match too many unrelated posts
API_FIELDS = "id,title,created_utc,score,num_comments,link_flair_text"

POST_FIELDS = ["anilist_id", "subreddit", "post_id", "created", "days_from_start", "score", "num_comments",
               "flair", "match_name", "post_title"]
TITLE_FIELDS = ["anilist_id", "title", "subreddits", "names", "posts", "truncated"]


def fetch_posts(subreddit, name, first, last, pause):
    """Posts in `subreddit` mentioning `name`, created from `first` to `last`, oldest first.

    Returns {"posts": [...], "truncated": bool}; truncated means there were more than MAX_PAGES pages.
    Only the fields we keep are copied, so nothing else the API sends can reach the cache or the CSVs.
    """
    posts, seen = [], set()
    after = first.isoformat()
    before = (last + timedelta(days=1)).isoformat()
    for _ in range(MAX_PAGES):
        params = {"subreddit": subreddit, "query": name, "after": after, "before": before,
                  "limit": PAGE_SIZE, "sort": "asc", "fields": API_FIELDS}
        page = request_json("GET", API_URL, params=params)["data"]
        time.sleep(pause)
        new = [post for post in page if post["id"] not in seen]
        for post in new:
            seen.add(post["id"])
            posts.append({
                "id": post["id"],
                "title": post.get("title") or "",
                "created_utc": int(float(post["created_utc"])),
                "score": post.get("score") or 0,
                "num_comments": post.get("num_comments") or 0,
                "flair": post.get("link_flair_text") or "",
            })
        if len(page) < PAGE_SIZE:
            return {"posts": posts, "truncated": False}
        if not new:  # a whole page of posts already seen: the date cursor is stuck
            break
        after = max(post["created_utc"] for post in posts)
    return {"posts": posts, "truncated": True}


def mentions(post_title, name):
    """True if the name appears in the post title as whole words."""
    return f" {normalize(name)} " in f" {normalize(post_title)} "


def collect_title(title, subreddits, first, last, window_complete, pause):
    """(post rows, names searched, truncated) for one title. Raises if a query could not be completed."""
    names = [n for n in search_names(title) if len(normalize(n)) >= MIN_NAME_LENGTH]
    start_date = parse_date(title["start_date"])
    claimed, truncated = {}, False
    for subreddit in subreddits:
        for name in names:
            key = hashlib.md5(f"{subreddit}|{name}".encode()).hexdigest()[:8]
            path = CACHE / f"{title['anilist_id']}_{key}.json"
            # A window that is still running is fetched fresh each time instead of cached.
            result = cached(path, lambda: fetch_posts(subreddit, name, first, last, pause), save=window_complete)
            truncated = truncated or result["truncated"]
            for post in result["posts"]:
                if (subreddit, post["id"]) in claimed or not mentions(post["title"], name):
                    continue
                created = datetime.fromtimestamp(post["created_utc"], timezone.utc).date()
                claimed[(subreddit, post["id"])] = {
                    "anilist_id": title["anilist_id"],
                    "subreddit": subreddit,
                    "post_id": post["id"],
                    "created": created.isoformat(),
                    "days_from_start": (created - start_date).days,
                    "score": post["score"],
                    "num_comments": post["num_comments"],
                    "flair": post["flair"],
                    "match_name": name,
                    "post_title": post["title"],
                }
    return list(claimed.values()), names, truncated


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_dir_argument(parser)
    parser.add_argument("--subreddits", default="anime",
                        help="comma-separated subreddits to search (default: anime)")
    parser.add_argument("--limit", type=int, default=200,
                        help="only the N most popular titles (default 200; 0 = all, about 2 hours for 1,400)")
    parser.add_argument("--pause", type=float, default=1.0,
                        help="seconds to wait between requests (default 1; please don't lower it much)")
    args = parser.parse_args()
    use_data_dir(args.data_dir)
    subreddits = [s.strip() for s in args.subreddits.split(",") if s.strip()]

    titles = read_titles(args.limit or None)
    today = date.today()
    post_rows, title_rows, failed = [], [], []
    for i, title in enumerate(titles, 1):
        start_date = parse_date(title["start_date"])
        if not start_date:
            continue
        first = start_date - timedelta(days=DAYS_BEFORE)
        last = min(start_date + timedelta(days=DAYS_AFTER), today)
        if first > last:  # starts too far in the future for any post to exist yet
            continue
        window_complete = last == start_date + timedelta(days=DAYS_AFTER)
        label = title["title_english"] or title["title_romaji"]
        try:
            posts, names, truncated = collect_title(title, subreddits, first, last, window_complete, args.pause)
        except (requests.HTTPError, RuntimeError) as error:
            print(f"  {label}: {str(error)[:200]}")
            failed.append(label)
            continue
        post_rows += posts
        title_rows.append({
            "anilist_id": title["anilist_id"],
            "title": label,
            "subreddits": ",".join(subreddits),
            "names": " | ".join(names),
            "posts": len(posts),
            "truncated": int(truncated),
        })
        if i % 25 == 0:
            print(f"Reddit: {i}/{len(titles)} titles")

    write_csv(data_file(POSTS_CSV), post_rows, POST_FIELDS)
    write_csv(data_file(TITLES_CSV), title_rows, TITLE_FIELDS)
    print(f"Saved {len(post_rows)} posts for {len(title_rows)} titles to {data_file(POSTS_CSV)}")
    if failed:
        print(f"{len(failed)} titles had a failing query and were left out; rerun to retry them: " + ", ".join(failed[:10]))


if __name__ == "__main__":
    main()

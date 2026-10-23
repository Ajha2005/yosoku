"""Step 5: Google Trends interest around each title's launch. Slow: run it overnight.

Google has no open Trends API, so this uses the community library
pytrends-modern, which reads the same data as trends.google.com. Google blocks
clients that ask too fast, so the script pauses between requests and waits
longer when blocked. Each finished title is saved in data/raw/trends/, so you
can stop it with Ctrl+C and rerun later; it carries on where it stopped.

For each title it searches Trends for a matching topic (e.g. "Jujutsu Kaisen
(Anime)"), which avoids mixing in other meanings of the name, and falls back to
the plain name. Then, from 90 days before to 120 days after the start date:

  data/trends_terms.csv         the topic or name used per title (check these by eye)
  data/trends_india_daily.csv   daily interest in India, beside a fixed anchor term so titles can be compared
  data/trends_india_states.csv  interest by Indian state
  data/trends_countries.csv     interest by country worldwide (for the India affinity ratio)

Trends numbers are relative (0 to 100 within each request), not search counts.

    python collectors/collect_trends.py
    python collectors/collect_trends.py --limit 50 --anchor "Naruto" --pause 20
"""

import argparse
import time
from datetime import date, timedelta

from pytrends_modern import TrendReq
from pytrends_modern.exceptions import TooManyRequestsError

from common import (RAW_DIR, add_data_dir_argument, cached, data_file, load_json, parse_date, read_csv, read_titles,
                    save_json, search_names, use_data_dir, write_csv)

DAYS_BEFORE = 90
DAYS_AFTER = 120  # windows under 270 days come back as daily values
CACHE = RAW_DIR / "trends"
IST_OFFSET_MINUTES = -330  # Trends wants UTC minus local time

OVERRIDES_CSV = "trends_overrides.csv"  # optional, written by hand: anilist_id,term
TERMS_CSV = "trends_terms.csv"
DAILY_CSV = "trends_india_daily.csv"
STATES_CSV = "trends_india_states.csv"
COUNTRIES_CSV = "trends_countries.csv"

# Topic types that mean "this suggestion is the show", e.g. "2020 anime series" or "Manga series".
SHOW_TYPES = ("anime", "manga", "animat", "series", "franchise", "film", "novel")

TERMS_FIELDS = ["anilist_id", "title", "term", "label", "complete"]
DAILY_FIELDS = ["anilist_id", "term", "date", "days_from_start", "title_interest", "anchor_interest", "is_partial"]
STATES_FIELDS = ["anilist_id", "term", "state", "state_code", "interest"]
COUNTRIES_FIELDS = ["anilist_id", "term", "country", "country_code", "interest"]


class RateLimited(Exception):
    pass


class Trends:
    """Wraps pytrends-modern with pauses between requests and long waits when Google rate-limits us."""

    def __init__(self, pause):
        self.pause = pause
        # Separate clients: pytrends-modern keeps the last geo, so one client cannot switch back to worldwide.
        self.india = TrendReq(hl="en-US", tz=IST_OFFSET_MINUTES, retries=0, backoff_factor=0)
        self.world = TrendReq(hl="en-US", tz=IST_OFFSET_MINUTES, retries=0, backoff_factor=0)

    def call(self, fn):
        for attempt in range(6):
            time.sleep(self.pause)
            try:
                return fn()
            except TooManyRequestsError:
                wait = min(120 * 2**attempt, 1800)
                print(f"  Google is rate-limiting us; waiting {wait // 60} min")
                time.sleep(wait)
        raise RateLimited()

    def topic(self, names):
        """(term, label): a Trends topic ID for the first name that has a show-like topic, else the first name."""
        for name in names:
            for suggestion in self.call(lambda: self.india.suggestions(name)):
                if suggestion.get("mid") and any(word in suggestion.get("type", "").lower() for word in SHOW_TYPES):
                    return suggestion["mid"], f"{suggestion['title']} ({suggestion['type']})"
        return names[0], names[0]

    def india_daily(self, term, anchor, timeframe):
        def fetch():
            self.india.build_payload([term] if term == anchor else [term, anchor], timeframe=timeframe, geo="IN")
            return self.india.interest_over_time()
        frame = self.call(fetch)
        if frame.empty:
            return []
        return [{
            "date": day.date().isoformat(),
            "title_interest": int(row[term]),
            "anchor_interest": int(row[anchor]),
            "is_partial": bool(row["isPartial"]),
        } for day, row in frame.iterrows()]

    def regions(self, client, term, timeframe, geo):
        def fetch():
            client.build_payload([term], timeframe=timeframe, geo=geo)
            return client.interest_by_region(resolution="COUNTRY", inc_low_vol=True, inc_geo_code=True)
        frame = self.call(fetch)
        if frame.empty:
            return []
        return [{"name": name, "code": row.get("geoCode", ""), "interest": int(row[term])}
                for name, row in frame.iterrows()]


def collect_title(trends, title, anchor, timeframe, complete, override):
    term, label = (override, override) if override else trends.topic(search_names(title))
    return {
        "complete": complete,  # False while the window is still running: fetched again on the next run
        "term": term,
        "label": label,
        "daily": trends.india_daily(term, anchor, timeframe),
        # For geo="IN" Google returns states; the COUNTRY resolution only applies worldwide.
        "states": trends.regions(trends.india, term, timeframe, "IN"),
        "countries": trends.regions(trends.world, term, timeframe, ""),
    }


def write_outputs(titles):
    terms, daily, states, countries = [], [], [], []
    for title in titles:
        path = CACHE / f"{title['anilist_id']}.json"
        if not path.exists():
            continue
        result = load_json(path)
        start_date = parse_date(title["start_date"])
        base = {"anilist_id": title["anilist_id"], "term": result["label"]}
        terms.append({"anilist_id": title["anilist_id"], "title": title["title_english"] or title["title_romaji"],
                      "term": result["term"], "label": result["label"], "complete": result["complete"]})
        daily += [{**base, **row, "days_from_start": (parse_date(row["date"]) - start_date).days}
                  for row in result["daily"]]
        states += [{**base, "state": r["name"], "state_code": r["code"], "interest": r["interest"]}
                   for r in result["states"]]
        countries += [{**base, "country": r["name"], "country_code": r["code"], "interest": r["interest"]}
                      for r in result["countries"]]
    write_csv(data_file(TERMS_CSV), terms, TERMS_FIELDS)
    write_csv(data_file(DAILY_CSV), daily, DAILY_FIELDS)
    write_csv(data_file(STATES_CSV), states, STATES_FIELDS)
    write_csv(data_file(COUNTRIES_CSV), countries, COUNTRIES_FIELDS)
    print(f"Saved Trends data for {len(terms)} titles to {data_file(TERMS_CSV).parent / 'trends_*.csv'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=200, help="the N most popular titles")
    parser.add_argument("--anchor", default="Naruto",
                        help="fixed term in every India request, so titles are on one scale; never change it mid-collection")
    parser.add_argument("--pause", type=float, default=15, help="seconds to wait before each request")
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir)

    titles = read_titles(args.limit)
    overrides_path = data_file(OVERRIDES_CSV)
    overrides = {row["anilist_id"]: row["term"] for row in read_csv(overrides_path)} if overrides_path.exists() else {}
    trends = Trends(args.pause)
    yesterday = date.today() - timedelta(days=1)
    anchor_path = CACHE / "_anchor.json"
    anchor = cached(anchor_path, lambda: {"name": args.anchor, "term": trends.topic([args.anchor])[0]})
    if anchor["name"] != args.anchor:
        raise SystemExit(f"Data so far was collected with anchor {anchor['name']!r}. "
                         f"Delete {CACHE} to start over with a new anchor.")

    try:
        for i, title in enumerate(titles, 1):
            start_date = parse_date(title["start_date"])
            path = CACHE / f"{title['anilist_id']}.json"
            if not start_date or (path.exists() and load_json(path)["complete"]):
                continue
            first = start_date - timedelta(days=DAYS_BEFORE)
            last = min(start_date + timedelta(days=DAYS_AFTER), yesterday)
            if first >= last:
                continue
            print(f"[{i}/{len(titles)}] {title['title_english'] or title['title_romaji']}")
            timeframe = f"{first.isoformat()} {last.isoformat()}"
            complete = last == start_date + timedelta(days=DAYS_AFTER)
            try:
                result = collect_title(trends, title, anchor["term"], timeframe, complete, overrides.get(title["anilist_id"]))
                save_json(path, result)
            except RateLimited:
                raise
            except Exception as error:  # one odd title should not stop an overnight run
                print(f"  skipped: {type(error).__name__}: {error}")
    except RateLimited:
        print("Google is still rate-limiting after long waits. Try again in a few hours or from another network.")
    except KeyboardInterrupt:
        print("Stopped. Rerun to continue; finished titles are kept.")
    finally:
        write_outputs(titles)


if __name__ == "__main__":
    main()

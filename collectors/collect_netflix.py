"""Step 3: weeks each title spent in Netflix India's Top 10 (or the folder's market's, see markets.py).

Downloads Netflix's public Top 10 history (weekly, per country, from June 2021)
and keeps the market's rows in data/netflix_india_top10.csv (netflix_<market>_top10.csv elsewhere).
Then matches them to titles.csv by name into data/netflix_matches.csv.

Check the matches by eye: names are matched loosely, and live-action remakes
(One Piece, Yu Yu Hakusho) share their anime's name. Titles that started before
June 2021 have no chart data at all.

To drop a wrong match, list it in data/netflix_match_exclusions.csv (columns: anilist_id,show_title,reason)
and rerun. Every match of that title to that Netflix show is removed; copy both from netflix_matches.csv.

If the download is blocked, open https://top10.netflix.com, download
"all-weeks-countries.tsv" from its downloads section, save it as
data/raw/netflix/all-weeks-countries.tsv and rerun.

    python collectors/collect_netflix.py
    python collectors/collect_netflix.py --refresh   # download the latest weeks again
"""

import argparse
import csv
import sys

import requests

from common import (RAW_DIR, add_data_dir_argument, current_market, data_file, normalize, parse_date, read_csv,
                    read_titles, session, use_data_dir, write_csv)

NETFLIX_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
TSV_PATH = RAW_DIR / "netflix" / "all-weeks-countries.tsv"
CHART_CSV = "netflix_{market}_top10.csv"  # netflix_india_top10.csv for India
MATCHES_CSV = "netflix_matches.csv"
EXCLUSIONS_CSV = "netflix_match_exclusions.csv"  # optional, written by hand: anilist_id,show_title,reason

CHART_FIELDS = ["week", "category", "weekly_rank", "show_title", "season_title", "cumulative_weeks_in_top_10"]
MATCH_FIELDS = ["anilist_id", "title_english", "title_romaji", "days_from_start", *CHART_FIELDS]


def download():
    print(f"Downloading {NETFLIX_URL}")
    TSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    partial = TSV_PATH.with_suffix(".part")
    try:
        with session.get(NETFLIX_URL, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(partial, "wb") as f:
                for chunk in response.iter_content(1 << 20):
                    f.write(chunk)
    except requests.RequestException as error:
        sys.exit(f"Download failed ({error}).\nDownload it by hand instead; see the steps at the top of this script.")
    partial.replace(TSV_PATH)


def read_chart_rows(country):
    """The weekly Top 10 rows of one country (Netflix's two-letter code, e.g. IN)."""
    with open(TSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = {"country_iso2", *CHART_FIELDS} - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"Netflix's file format has changed; missing columns: {sorted(missing)}")
        return [{field: row[field] for field in CHART_FIELDS} for row in reader if row["country_iso2"] == country]


def title_names(title):
    names = [title["title_english"], title["title_romaji"], *title["synonyms"].split("|")]
    return {normalize(name) for name in names if name}


def same_show(names, show):
    """A title's name equals the chart's show name, or starts with it when that is two words or more
    ("jujutsu kaisen" matches "jujutsu kaisen season 2"; "monster" does not match "monster musume")."""
    return any(n == show or (" " in show and n.startswith(show + " ")) for n in names)


def match(chart_rows, titles):
    """Pair each chart row with the title whose name it matches and that started most recently before that week."""
    names = {title["anilist_id"]: title_names(title) for title in titles}
    candidates_by_show = {}
    for show in {normalize(row["show_title"]) for row in chart_rows}:
        candidates_by_show[show] = [
            title for title in titles if title["start_date"] and same_show(names[title["anilist_id"]], show)
        ]

    matches = []
    for row in chart_rows:
        week = parse_date(row["week"])
        started = [t for t in candidates_by_show.get(normalize(row["show_title"]), []) if parse_date(t["start_date"]) <= week]
        if not started:
            continue
        title = max(started, key=lambda t: t["start_date"])
        matches.append({
            "anilist_id": title["anilist_id"],
            "title_english": title["title_english"],
            "title_romaji": title["title_romaji"],
            "days_from_start": (week - parse_date(title["start_date"])).days,
            **row,
        })
    return matches


def drop_excluded(matches):
    """Remove the matches of every (anilist_id, show_title) pair listed in the exclusions file, if there is one."""
    path = data_file(EXCLUSIONS_CSV)
    if not path.exists():
        return matches
    excluded = {(row["anilist_id"], normalize(row["show_title"])) for row in read_csv(path)}
    pair = lambda m: (m["anilist_id"], normalize(m["show_title"]))
    kept = [m for m in matches if pair(m) not in excluded]
    print(f"Dropped {len(matches) - len(kept)} rows listed in {path}")
    for anilist_id, show in sorted(excluded - {pair(m) for m in matches}):
        print(f"  no match for {anilist_id} / {show}; check that line of the exclusions file")
    return kept


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="download the file again even if it is already saved")
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir, args.market)

    if args.refresh or not TSV_PATH.exists():
        download()

    market = current_market()
    chart_rows = read_chart_rows(market["code"])
    chart_csv = data_file(CHART_CSV.format(market=market["name"].lower()))
    write_csv(chart_csv, chart_rows, CHART_FIELDS)
    print(f"Saved {len(chart_rows)} {market['name']} Top 10 rows to {chart_csv}")

    matches = drop_excluded(match(chart_rows, read_titles()))
    write_csv(data_file(MATCHES_CSV), matches, MATCH_FIELDS)
    print(f"Matched {len(matches)} rows to {len({m['anilist_id'] for m in matches})} titles; saved {data_file(MATCHES_CSV)}")


if __name__ == "__main__":
    main()

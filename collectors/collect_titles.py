"""Step 1: build data/titles.csv, the list of anime every other collector works from.

Uses the AniList GraphQL API (free, no key needed). For each season it keeps the
most popular Japanese anime and records names, MyAnimeList ID, genres, studio,
source material, streaming sites and whether the title is a sequel.

    python collectors/collect_titles.py
    python collectors/collect_titles.py --start-year 2021 --end-year 2025 --per-season 50
"""

import argparse
import time

from common import TITLES_CSV, request_json, write_csv

ANILIST_URL = "https://graphql.anilist.co"
SEASONS = ["WINTER", "SPRING", "SUMMER", "FALL"]
PER_PAGE = 25  # larger pages risk AniList's query-complexity limit
PAUSE_SECONDS = 2.5  # AniList currently allows about 30 requests a minute

QUERY = """
query ($season: MediaSeason, $year: Int, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(season: $season, seasonYear: $year, type: ANIME, countryOfOrigin: "JP",
          isAdult: false, format_in: [TV, TV_SHORT, ONA, MOVIE], sort: POPULARITY_DESC) {
      id
      idMal
      title { romaji english native }
      synonyms
      format
      episodes
      source
      genres
      startDate { year month day }
      studios(isMain: true) { nodes { name } }
      popularity
      averageScore
      externalLinks { site type }
      relations { edges { relationType node { id type } } }
    }
  }
}
"""

FIELDS = [
    "anilist_id", "mal_id", "title_english", "title_romaji", "title_japanese", "synonyms",
    "season", "year", "start_date", "format", "episodes", "source", "genres", "studio",
    "streaming_sites", "is_sequel", "prequel_anilist_id", "popularity", "average_score",
]


def to_row(anime, season, year):
    start = anime["startDate"]
    start_date = ""
    if start["year"] and start["month"] and start["day"]:
        start_date = f"{start['year']:04d}-{start['month']:02d}-{start['day']:02d}"
    edges = (anime.get("relations") or {}).get("edges") or []
    prequels = [e["node"]["id"] for e in edges if e["relationType"] == "PREQUEL" and e["node"]["type"] == "ANIME"]
    streaming = sorted({link["site"] for link in anime.get("externalLinks") or [] if link["type"] == "STREAMING"})
    return {
        "anilist_id": anime["id"],
        "mal_id": anime["idMal"] or "",
        "title_english": anime["title"]["english"] or "",
        "title_romaji": anime["title"]["romaji"] or "",
        "title_japanese": anime["title"]["native"] or "",
        "synonyms": "|".join(anime["synonyms"] or []),
        "season": season,
        "year": year,
        "start_date": start_date,
        "format": anime["format"] or "",
        "episodes": anime["episodes"] or "",
        "source": anime["source"] or "",
        "genres": "|".join(anime["genres"] or []),
        "studio": "|".join(node["name"] for node in anime["studios"]["nodes"]),
        "streaming_sites": "|".join(streaming),
        "is_sequel": int(bool(prequels)),
        "prequel_anilist_id": prequels[0] if prequels else "",
        "popularity": anime["popularity"] or 0,
        "average_score": anime["averageScore"] or "",
    }


def fetch_season(season, year, limit):
    rows, page = [], 1
    while len(rows) < limit:
        variables = {"season": season, "year": year, "page": page, "perPage": PER_PAGE}
        data = request_json("POST", ANILIST_URL, json={"query": QUERY, "variables": variables})
        result = data["data"]["Page"]
        rows += [to_row(anime, season, year) for anime in result["media"]]
        time.sleep(PAUSE_SECONDS)
        if not result["pageInfo"]["hasNextPage"]:
            break
        page += 1
    return rows[:limit]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--per-season", type=int, default=50, help="keep this many of each season's most popular titles")
    args = parser.parse_args()

    rows = []
    for year in range(args.start_year, args.end_year + 1):
        for season in SEASONS:
            season_rows = fetch_season(season, year, args.per_season)
            print(f"{season} {year}: {len(season_rows)} titles")
            rows += season_rows

    write_csv(TITLES_CSV, rows, FIELDS)
    print(f"Saved {len(rows)} titles to {TITLES_CSV}")


if __name__ == "__main__":
    main()

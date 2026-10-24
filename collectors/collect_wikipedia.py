"""Step 2: daily Wikipedia pageviews around each title's launch, in English, Japanese, Hindi, Tamil and Telugu.

First it finds each title's article in each language, through Wikidata's links
from MyAnimeList IDs, falling back to an English Wikipedia search, and saves the
list to data/wiki_articles.csv. Check that file: rows marked "search" were
guessed and may point at the wrong article (often the franchise article for a
sequel season). Fix rows by hand and rerun; titles already in the file are never
looked up again.

Then it downloads daily views by people (bots excluded) from 120 days before to
120 days after each title's Japanese start date, into data/wikipedia_daily.csv.

    python collectors/collect_wikipedia.py
"""

import argparse
import hashlib
from datetime import date, datetime, timedelta
from urllib.parse import quote, unquote

import requests

from common import (RAW_DIR, add_data_dir_argument, cached, data_file, parse_date, read_csv, read_titles, request_json,
                    use_data_dir, write_csv)

LANGS = ["en", "ja", "hi", "ta", "te"]
DAYS_BEFORE = 120
DAYS_AFTER = 120
FIRST_DAY = date(2015, 7, 1)  # the pageviews API has no earlier data

ARTICLES_CSV = "wiki_articles.csv"
DAILY_CSV = "wikipedia_daily.csv"
CACHE = RAW_DIR / "wikipedia"

SPARQL_URL = "https://query.wikidata.org/sparql"
EN_API_URL = "https://en.wikipedia.org/w/api.php"
PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "{lang}.wikipedia/all-access/user/{article}/daily/{start}/{end}"
)

# P4086 is Wikidata's "MyAnimeList anime ID".
SPARQL = """
SELECT ?mal ?lang ?article WHERE {
  VALUES ?mal { %s }
  ?item wdt:P4086 ?mal .
  VALUES (?lang ?site) {
    ("en" <https://en.wikipedia.org/>) ("ja" <https://ja.wikipedia.org/>)
    ("hi" <https://hi.wikipedia.org/>) ("ta" <https://ta.wikipedia.org/>) ("te" <https://te.wikipedia.org/>)
  }
  ?article schema:about ?item ; schema:isPartOf ?site .
}
"""

ARTICLE_FIELDS = ["anilist_id", "title", *LANGS, "match_method"]
DAILY_FIELDS = ["anilist_id", "lang", "article", "date", "days_from_start", "views"]


def wikidata_articles(mal_ids):
    """{mal_id: {lang: article title}} for the MyAnimeList IDs Wikidata knows."""
    found = {}
    mal_ids = [m for m in mal_ids if m.isdigit()]
    for start in range(0, len(mal_ids), 100):
        values = " ".join(f'"{m}"' for m in mal_ids[start:start + 100])
        data = request_json("GET", SPARQL_URL, params={"query": SPARQL % values, "format": "json"})
        for binding in data["results"]["bindings"]:
            article = unquote(binding["article"]["value"].split("/wiki/", 1)[1]).replace("_", " ")
            found.setdefault(binding["mal"]["value"], {}).setdefault(binding["lang"]["value"], article)
    return found


def search_english(title):
    for name in (title["title_english"], title["title_romaji"]):
        if not name:
            continue
        params = {"action": "query", "list": "search", "srsearch": f"{name} anime", "srlimit": 1,
                  "format": "json", "formatversion": 2}
        hits = request_json("GET", EN_API_URL, params=params)["query"]["search"]
        if hits:
            return hits[0]["title"]
    return None


def langlinks(article):
    """{lang: article title} for the other-language versions of an English article."""
    params = {"action": "query", "prop": "langlinks", "titles": article, "lllimit": "max",
              "redirects": 1, "format": "json", "formatversion": 2}
    pages = request_json("GET", EN_API_URL, params=params)["query"]["pages"]
    return {link["lang"]: link["title"] for link in pages[0].get("langlinks", []) if link["lang"] in LANGS}


def find_articles(titles):
    """Load data/wiki_articles.csv, look up titles missing from it, save it, and return {anilist_id: row}."""
    path = data_file(ARTICLES_CSV)
    known = {row["anilist_id"]: row for row in read_csv(path)} if path.exists() else {}
    new = [t for t in titles if t["anilist_id"] not in known]
    if new:
        print(f"Finding Wikipedia articles for {len(new)} titles")
        by_mal = wikidata_articles([t["mal_id"] for t in new])
        for i, title in enumerate(new, 1):
            articles = dict(by_mal.get(title["mal_id"], {}))
            method = "wikidata" if articles else "none"
            if "en" not in articles:
                english = search_english(title)
                if english:
                    articles = {"en": english, **langlinks(english), **articles}
                    method = "search"
            known[title["anilist_id"]] = {
                "anilist_id": title["anilist_id"],
                "title": title["title_english"] or title["title_romaji"],
                **{lang: articles.get(lang, "") for lang in LANGS},
                "match_method": method,
            }
            if i % 50 == 0:
                print(f"  {i}/{len(new)}")
        write_csv(path, list(known.values()), ARTICLE_FIELDS)
        print(f"Saved {path}; check the rows marked 'search'")
    return known


def fetch_views(lang, article, first, last):
    url = PAGEVIEWS_URL.format(lang=lang, article=quote(article.replace(" ", "_"), safe=""),
                               start=first.strftime("%Y%m%d"), end=last.strftime("%Y%m%d"))
    try:
        return request_json("GET", url)["items"]
    except requests.HTTPError as error:
        if error.response.status_code == 404:  # no views recorded in this window
            return []
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_dir_argument(parser)
    use_data_dir(parser.parse_args().data_dir)

    titles = read_titles()
    articles = find_articles(titles)
    yesterday = date.today() - timedelta(days=1)

    rows = []
    for i, title in enumerate(titles, 1):
        start_date = parse_date(title["start_date"])
        if not start_date:
            continue
        first = max(start_date - timedelta(days=DAYS_BEFORE), FIRST_DAY)
        last = min(start_date + timedelta(days=DAYS_AFTER), yesterday)
        if first > last:
            continue
        window_complete = last == start_date + timedelta(days=DAYS_AFTER)
        for lang in LANGS:
            article = articles[title["anilist_id"]][lang]
            if not article:
                continue
            key = hashlib.md5(article.encode()).hexdigest()[:8]
            path = CACHE / f"{title['anilist_id']}_{lang}_{key}.json"
            # A window that is still running is fetched fresh each time instead of cached.
            items = cached(path, lambda: fetch_views(lang, article, first, last), save=window_complete)
            for item in items:
                day = datetime.strptime(item["timestamp"][:8], "%Y%m%d").date()
                rows.append({
                    "anilist_id": title["anilist_id"],
                    "lang": lang,
                    "article": article,
                    "date": day.isoformat(),
                    "days_from_start": (day - start_date).days,
                    "views": item["views"],
                })
        if i % 100 == 0:
            print(f"Pageviews: {i}/{len(titles)} titles")

    write_csv(data_file(DAILY_CSV), rows, DAILY_FIELDS)
    print(f"Saved {len(rows)} daily rows to {data_file(DAILY_CSV)}")


if __name__ == "__main__":
    main()

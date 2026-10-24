"""Step 2: daily Wikipedia pageviews around each title's launch, in English, Japanese, Hindi, Tamil and Telugu.

Hindi, Tamil and Telugu are India's languages; a folder for another market reads its own instead (markets.py).

First it finds each title's article in each language, through Wikidata's links
from MyAnimeList IDs, falling back to an English Wikipedia search, and saves the
list to data/wiki_articles.csv. Check that file: rows marked "search" were
guessed and may point at the wrong article (often the franchise article for a
sequel season). Fix rows by hand and rerun; titles already in the file are never
looked up again.

Then it downloads daily views by people (bots excluded) from 120 days before to
120 days after each title's Japanese start date, into data/wikipedia_daily.csv.

An English article with no views at all in that window was usually written after launch
(e.g. "Demon Slayer: Kimetsu no Yaiba season 1", split from the main article later). For those
it tries the names readers used back then (the main article, "List of ... episodes") and keeps
the one with the most views, among those that link to the article (so "Lazarus (Japanese TV
series)" never becomes the Bible's Lazarus). Each swap is saved in wiki_articles.csv (match_method "fallback")
and listed in wiki_articles_fixes.csv (action "fallback"); check them like the "search" rows.

    python collectors/collect_wikipedia.py
"""

import argparse
import hashlib
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote, unquote

import requests

from common import (RAW_DIR, add_data_dir_argument, cached, current_market, data_file, parse_date, read_csv, read_titles,
                    request_json, use_data_dir, write_csv)

GLOBAL_LANGS = ["en", "ja"]  # global buzz, read in every market
DAYS_BEFORE = 120
DAYS_AFTER = 120
FIRST_DAY = date(2015, 7, 1)  # the pageviews API has no earlier data

MIN_FALLBACK_VIEWS = 1000  # over the whole window; less is a redirect or an unrelated stub
ARTICLES_CSV = "wiki_articles.csv"
FIXES_CSV = "wiki_articles_fixes.csv"
FIX_FIELDS = ["anilist_id", "title", "old_en", "action", "new_en"]  # then the market's languages
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
  VALUES (?lang ?site) { %s }
  ?article schema:about ?item ; schema:isPartOf ?site .
}
"""

DAILY_FIELDS = ["anilist_id", "lang", "article", "date", "days_from_start", "views"]


def langs():
    """English and Japanese, then the current market's languages (India: hi, ta, te)."""
    return GLOBAL_LANGS + current_market()["wiki"]


def article_fields():
    return ["anilist_id", "title", *langs(), "match_method"]


def wikidata_articles(mal_ids):
    """{mal_id: {lang: article title}} for the MyAnimeList IDs Wikidata knows."""
    found = {}
    mal_ids = [m for m in mal_ids if m.isdigit()]
    sites = " ".join(f'("{lang}" <https://{lang}.wikipedia.org/>)' for lang in langs())
    for start in range(0, len(mal_ids), 100):
        values = " ".join(f'"{m}"' for m in mal_ids[start:start + 100])
        data = request_json("GET", SPARQL_URL, params={"query": SPARQL % (values, sites), "format": "json"})
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
    return {link["lang"]: link["title"] for link in pages[0].get("langlinks", []) if link["lang"] in langs()}


def links_to(page, article):
    """True if English Wikipedia's `page` (not a redirect) links to `article` today.

    A disambiguation page ("Lazarus", "Look Back") links to every namesake, so it never counts.
    """
    params = {"action": "query", "prop": "links|pageprops", "ppprop": "disambiguation", "titles": page,
              "pltitles": article, "format": "json", "formatversion": 2}
    pages = request_json("GET", EN_API_URL, params=params)["query"]["pages"]
    return bool(pages and pages[0].get("links") and "disambiguation" not in pages[0].get("pageprops", {}))


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
                **{lang: articles.get(lang, "") for lang in langs()},
                "match_method": method,
            }
            if i % 50 == 0:
                print(f"  {i}/{len(new)}")
        write_csv(path, list(known.values()), article_fields())
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


def launch_names(article):
    """Names an English article may have had at launch, before it was split off or renamed; best guess first."""
    base = re.sub(r"\s+(?:season \d+|\(season \d+\)|\((?:\d{4} )?(?:Japanese )?(?:TV series|film|anime)\))$", "", article)
    names = [base] if base != article else []
    if " – " in base:  # "Demon Slayer: Kimetsu no Yaiba – The Movie: Mugen Train"
        names.append(base.split(" – ")[0])
    names += [f"List of {name} episodes" for name in names or [article]]
    return list(dict.fromkeys(n for n in names if n != article))


def launch_article(article, fetch, related):
    """(name, items) of the older name with the most views in the window, or None if none has MIN_FALLBACK_VIEWS.

    `fetch(name)` returns the pageview items for that name in the window; `related(name, article)` says
    whether that page is about the same show (it links to the article).
    """
    best = None
    for name in launch_names(article):
        if not related(name, article):
            continue
        items = fetch(name)
        total = sum(item["views"] for item in items)
        if total >= MIN_FALLBACK_VIEWS and (best is None or total > best[2]):
            best = (name, items, total)
    return best[:2] if best else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_dir_argument(parser)
    args = parser.parse_args()
    use_data_dir(args.data_dir, args.market)

    titles = read_titles()
    articles = find_articles(titles)
    yesterday = date.today() - timedelta(days=1)

    rows, fixes = [], []
    for i, title in enumerate(titles, 1):
        start_date = parse_date(title["start_date"])
        if not start_date:
            continue
        first = max(start_date - timedelta(days=DAYS_BEFORE), FIRST_DAY)
        last = min(start_date + timedelta(days=DAYS_AFTER), yesterday)
        if first > last:
            continue
        window_complete = last == start_date + timedelta(days=DAYS_AFTER)
        for lang in langs():
            row = articles[title["anilist_id"]]
            article = row[lang]
            if not article:
                continue

            def views(name):
                key = hashlib.md5(name.encode()).hexdigest()[:8]
                path = CACHE / f"{title['anilist_id']}_{lang}_{key}.json"
                # A window that is still running is fetched fresh each time instead of cached.
                return cached(path, lambda: fetch_views(lang, name, first, last), save=window_complete)

            items = views(article)
            if not items and lang == "en" and window_complete:
                found = launch_article(article, views, links_to)
                if found:
                    fixes.append({"anilist_id": title["anilist_id"], "title": row["title"], "old_en": article,
                                  "action": "fallback", "new_en": found[0],
                                  **{k: row[k] for k in current_market()["wiki"]}})
                    article, items = found
                    row.update(en=article, match_method="fallback")
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

    if fixes:
        write_csv(data_file(ARTICLES_CSV), list(articles.values()), article_fields())
        old = read_csv(data_file(FIXES_CSV)) if data_file(FIXES_CSV).exists() else []
        write_csv(data_file(FIXES_CSV), old + fixes, FIX_FIELDS + current_market()["wiki"])
        print(f"Swapped {len(fixes)} English articles that did not exist at launch; see {FIXES_CSV} (action 'fallback')")
    write_csv(data_file(DAILY_CSV), rows, DAILY_FIELDS)
    print(f"Saved {len(rows)} daily rows to {data_file(DAILY_CSV)}")


if __name__ == "__main__":
    main()

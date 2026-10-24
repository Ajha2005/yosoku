"""Shared helpers for the Yosoku collectors: file paths, HTTP with retries, caching and CSV files."""

import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

import markets

ROOT = Path(__file__).resolve().parent.parent
# Cached API responses, so a rerun skips work already done. Shared by every data folder:
# entries are keyed by title or article, so released and upcoming titles never collide.
RAW_DIR = ROOT / "data" / "raw"
_data_dir = ROOT / "data"
_market = markets.profile(markets.DEFAULT)

load_dotenv(ROOT / ".env")

# Wikimedia asks every API client to name itself and say how to reach its owner.
CONTACT = os.getenv("YOSOKU_CONTACT") or "https://github.com/ajha2005/yosoku"
session = requests.Session()
session.headers["User-Agent"] = f"YosokuResearch/0.1 ({CONTACT}) python-requests"


def request_json(method, url, retries=5, **kwargs):
    """Send an HTTP request and return the decoded JSON body.

    Waits and retries when the server is rate-limiting (429), briefly failing (5xx)
    or unreachable. Any other error status raises requests.HTTPError with the
    server's message.
    """
    for attempt in range(retries):
        wait = 10 * 2**attempt
        try:
            response = session.request(method, url, timeout=60, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            print(f"  network error ({type(error).__name__}); retrying in {wait}s")
            time.sleep(wait)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            wait = _retry_after(response, wait)
            print(f"  {url} answered {response.status_code}; retrying in {wait}s")
            time.sleep(wait)
            continue
        if response.status_code >= 400:
            # Name `url`, not response.url: the full URL can carry an API key.
            message = f"{response.status_code} from {url}: {response.text[:500]}"
            raise requests.HTTPError(message, response=response)
        return response.json()
    raise RuntimeError(f"Gave up on {url} after {retries} attempts")


def _retry_after(response, default):
    try:
        return int(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return default


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def add_data_dir_argument(parser):
    parser.add_argument("--data-dir", default="data",
                        help="folder holding titles.csv and the outputs (default: data); "
                             "use e.g. data/upcoming for unreleased titles so they stay out of the training data")
    parser.add_argument("--market", help="country the folder is collected for, e.g. ID; remembered by the folder "
                                          "(default: the folder's saved market, else IN; see collectors/markets.py)")


def use_data_dir(folder, market=None):
    """Point every data_file() at `folder`, and settle its market (see markets.py)."""
    global _data_dir, _market
    _data_dir = ROOT / folder
    _market = markets.of_folder(_data_dir, market)


def current_market():
    """The market of the current data folder: {code, name, wiki, note}."""
    return _market


def india_only(step):
    """Stop a step that only works for India (its word lists or search region are India's) in another market's folder."""
    if _market["code"] not in markets.COMMENT_MARKETS:
        sys.exit(f"{step} works for India only so far; {_market['name']} gets its index from Wikipedia and Netflix.")


def data_file(name):
    """Path of a file in the current data folder: data/ unless --data-dir chose another."""
    return _data_dir / name


def cached(path, fetch, save=True):
    """Return the JSON stored at `path`; if there is none, call fetch(), store its result and return it."""
    if path.exists():
        return load_json(path)
    result = fetch()
    if save:
        save_json(path, result)
    return result


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    """Write rows (dicts) to a CSV that Excel opens with Japanese and Indic text intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_titles(limit=None):
    """Rows of titles.csv, most popular first; only the first `limit` rows if given."""
    path = data_file("titles.csv")
    if not path.exists():
        sys.exit(f"{path} not found. Run `python collectors/collect_titles.py` first (with the same --data-dir).")
    titles = read_csv(path)
    titles.sort(key=lambda row: int(row["popularity"] or 0), reverse=True)
    return titles[:limit] if limit else titles


def parse_date(text):
    """date from 'YYYY-MM-DD', or None for a blank cell."""
    return date.fromisoformat(text[:10]) if text else None


# A title's data stops changing once its last window closes: the buzz windows end on day +6 after the Japanese start
# date, the India Demand Index's on day +27 and its Netflix weeks on day +90. Until then it is worth collecting again;
# after that it never is, so daily work grows with the titles in play, not with the archive.
LAST_WINDOW_DAY = 90


def is_active(start_date, today):
    """True while a title's data can still change: its start date is unknown, still to come, or at most 90 days ago."""
    return start_date is None or (today - start_date).days <= LAST_WINDOW_DAY


def normalize(text):
    """Lowercase text without punctuation or repeated spaces, for matching names across sources."""
    text = unicodedata.normalize("NFKC", text).replace("×", " x ").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


SEASON_SUFFIX = re.compile(
    r"\s*[:\-]?\s*(season\s*\d+|\d+(st|nd|rd|th)\s+season|part\s*\d+|cour\s*\d+|the final season)\b.*$",
    re.IGNORECASE,
)


def search_names(title):
    """Names people might search for a title, best first: the English name, shorter forms, then romaji."""
    names = []
    for name in (title["title_english"], title["title_romaji"]):
        if name:
            names += [name, SEASON_SUFFIX.sub("", name), name.split(":")[0]]
    return list(dict.fromkeys(n.strip() for n in names if n.strip()))

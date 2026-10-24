"""Markets: the country a data folder is collected for. India is the default and the only one fully built.

A market is the Netflix chart country plus the Wikipedia languages read there. English and Japanese
Wikipedia are always collected as global buzz; the market's own languages are its local signal.
Adding a market is one line here. Then, in its own folder:

    python collectors/collect_titles.py --data-dir data/markets/id --market ID
    python collectors/collect_wikipedia.py --data-dir data/markets/id
    python collectors/collect_netflix.py --data-dir data/markets/id
    python collectors/merge.py --data-dir data/markets/id
    python -m yosoku.labels --data-dir data/markets/id --out-dir out/id

The folder remembers its market (market.txt), so later steps need no --market. Trailer comments
(collect_youtube.py) are India only: the word list that finds Indian commenters has no
equivalent for other countries yet, so other markets get an index from Wikipedia and Netflix.
"""

DEFAULT = "IN"
MARKETS = {  # Netflix's country code: name, local Wikipedia languages, how local those languages are
    "IN": {"name": "India", "wiki": ["hi", "ta", "te"], "note": "Hindi, Tamil and Telugu are read almost only in India"},
    "ID": {"name": "Indonesia", "wiki": ["id"], "note": "Indonesian is read almost only in Indonesia"},
    "TH": {"name": "Thailand", "wiki": ["th"], "note": "Thai is read almost only in Thailand"},
    "BR": {"name": "Brazil", "wiki": ["pt"], "note": "Portuguese also counts Portugal and Lusophone Africa"},
    "MX": {"name": "Mexico", "wiki": ["es"], "note": "Spanish counts all of Latin America and Spain: weakly local"},
}
MARKET_FILE = "market.txt"
COMMENT_MARKETS = {"IN"}  # markets whose trailer comments can be told apart (collectors/india_signals.py)


def profile(code):
    """{code, name, wiki, note} of a market; stops with the known codes if it is unknown."""
    code = code.upper()
    if code not in MARKETS:
        raise SystemExit(f"Unknown market {code!r}. Known: {', '.join(MARKETS)} (add one in collectors/markets.py).")
    return {"code": code, **MARKETS[code]}


def of_folder(folder, chosen=None):
    """The market of a data folder: `chosen` (saved to market.txt the first time) or the saved one, else India.

    A folder holds one market, so choosing a different one for a folder that already has one stops.
    """
    path = folder / MARKET_FILE
    saved = path.read_text(encoding="utf-8").strip().upper() if path.exists() else None
    if chosen:
        market = profile(chosen)
        if saved and saved != market["code"]:
            raise SystemExit(f"{folder} holds market {saved}; use another --data-dir for {market['code']}.")
        if not saved and market["code"] != DEFAULT:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(market["code"] + "\n", encoding="utf-8")
        return market
    return profile(saved or DEFAULT)

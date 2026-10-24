"""The data behind the website's Demand guide: what India has actually been watching, from what we collected.

    python -m yosoku.guide              # writes web/data/guide.json
    python -m yosoku.export_web         # also runs this, and fetches the covers

Two real signals, both counted rather than modelled:
- Netflix India's weekly Top 10 (which anime reached it, for how many weeks, at what rank);
- India-flagged YouTube trailer comments (how many comments from India per title, and in which language hub).

One row per title with its attributes, so the page can split the evidence by genre, intended audience, source,
format, sequel and year, and so a visitor can describe their own title and see how similar ones fared.
The page shows every count next to its percentage: only 15 anime have ever reached the chart.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from yosoku.data import HUBS, load_titles

ROOT = Path(__file__).resolve().parent.parent


def num(value, digits=None):
    """A JSON-safe number: None for blanks and NaN."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits) if digits is not None else int(value)


def read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else None


def build(data_dir):
    titles = load_titles(data_dir)
    chart = read_csv(data_dir / "netflix_india_top10.csv")
    matches = read_csv(data_dir / "netflix_matches.csv")
    if matches is None or chart is None:
        matches = pd.DataFrame(columns=["anilist_id", "week", "weekly_rank", "category"])
        chart = pd.DataFrame(columns=["week", "category", "weekly_rank"])

    # What reached India's Top 10, one row per title.
    seen = matches.groupby("anilist_id").agg(
        weeks=("week", "nunique"), best_rank=("weekly_rank", "min"), first=("week", "min"), last=("week", "max"),
        category=("category", "first"))
    listed = titles["streaming_sites"].fillna("").str.contains("Netflix")

    comments = titles["yt_comments_month1"].fillna(0)
    voice = titles.index[comments > 0]
    universe = titles.index[listed | titles.index.isin(seen.index) | titles.index.isin(voice)]

    def row(anilist_id):
        t = titles.loc[anilist_id]
        hit = seen.loc[anilist_id] if anilist_id in seen.index else None
        return {
            "id": int(anilist_id), "name": t["name"], "jp": t["title_japanese"] if isinstance(t["title_japanese"], str) else "",
            "year": num(t["year"]), "genres": t["genre_list"], "audience": t["demographic"], "source": t["source"], "format": t["format"],
            "sequel": int(t["is_sequel"]), "netflix": int(bool(listed.get(anilist_id)) or hit is not None),
            "weeks": int(hit["weeks"]) if hit is not None else 0, "best": int(hit["best_rank"]) if hit is not None else None,
            "comments": num(comments.get(anilist_id)) if anilist_id in voice else None,
            "india": num(t["yt_india_month1"]) if anilist_id in voice else None,
        }

    rows = [row(i) for i in universe]

    weeks = sorted(chart["week"].unique())
    timeline = [{"week": week, "titles": [{"id": int(r.anilist_id), "rank": int(r.weekly_rank)} for r in group.itertuples()]}
                for week, group in matches.groupby("week")]

    # Which Indian languages show up in the trailer comments, as comment counts (shares are of each title's comments).
    scored = titles.loc[voice]
    hub_comments = {name: num((scored[f"yt_share_{key}"].fillna(0) * scored["yt_comments_month1"]).sum(), 1) for key, (name, _) in HUBS.items()}
    wikipedia = {name: {"titles": int((titles[f"wiki_{code}_month1"].fillna(0) > 0).sum()), "views": num(titles[f"wiki_{code}_month1"].fillna(0).sum())}
                 for name, code in (("Hindi", "hi"), ("Tamil", "ta"), ("Telugu", "te"))}

    return {
        "generated": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "netflix": {"weeks": len(weeks), "from": weeks[0] if weeks else None, "to": weeks[-1] if weeks else None,
                    "slots": int(len(chart)), "anime_slots": int(len(matches)), "titles": int(len(seen)),
                    "listed": int(listed.sum()), "universe": int(len(titles))},
        "watched": sorted((r for r in rows if r["weeks"]), key=lambda r: (-r["weeks"], r["best"])),
        "timeline": timeline,
        "titles": rows,
        "voice": {"titles": int(len(voice)), "comments": num(comments.sum()), "india": num(scored["yt_india_month1"].sum()),
                  "hubs": hub_comments, "wikipedia": wikipedia},
        "hubs": {name: description for name, description in HUBS.values()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data", help="folder with dataset.csv and the Netflix files (default: data)")
    parser.add_argument("--out", default="web/data/guide.json", help="where the site reads it (default: web/data/guide.json)")
    args = parser.parse_args()
    guide = build(ROOT / args.data_dir)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(guide, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    net = guide["netflix"]
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB): {net['titles']} anime reached India's Top 10 "
          f"({net['anime_slots']} of {net['slots']} slots over {net['weeks']} weeks)")


if __name__ == "__main__":
    main()

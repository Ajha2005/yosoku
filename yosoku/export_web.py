"""Prepare the static dashboard (web/) for deployment: copy the forecasts and fetch the anime cover art.

    python -m yosoku.export_web                 # predictions/predictions.json (or the mock) + covers from AniList
    python -m yosoku.export_web --no-covers     # forecasts only, e.g. when offline

Writes web/data/predictions.json and web/data/covers.json. Commit both; Vercel serves them as-is.

Covers are links to AniList's image servers, not copies of the images. Mock forecasts use made-up ids that
collide with real AniList ids, so covers are never fetched for them.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collectors"))
from common import request_json  # noqa: E402  (retrying HTTP helper shared with the collectors)

ANILIST_URL = "https://graphql.anilist.co"
BATCH = 50
QUERY = """
query ($ids: [Int]) {
  Page(perPage: %d) {
    media(id_in: $ids, type: ANIME) { id coverImage { extraLarge color } bannerImage }
  }
}
""" % BATCH


def referenced_ids(predictions):
    """Every title the dashboard can show a poster for: the forecast titles and their lookalikes."""
    ids = set()
    for title in predictions["titles"]:
        ids.add(title["anilist_id"])
        for forecast in title["forecasts"].values():
            ids.update(look["anilist_id"] for look in forecast["lookalikes"])
    return sorted(ids)


def cover_entry(media):
    """The compact record the page reads: c = cover, b = banner (optional), k = dominant colour."""
    cover = media["coverImage"]
    entry = {"c": cover["extraLarge"], "k": cover.get("color") or ""}
    if media.get("bannerImage"):
        entry["b"] = media["bannerImage"]
    return entry


def fetch_covers(ids, pause=1.0):
    covers = {}
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        data = request_json("POST", ANILIST_URL, json={"query": QUERY, "variables": {"ids": batch}})
        for media in data["data"]["Page"]["media"]:
            if media["coverImage"]["extraLarge"]:
                covers[str(media["id"])] = cover_entry(media)
        print(f"  covers {min(start + BATCH, len(ids))}/{len(ids)}")
        time.sleep(pause)   # AniList allows about 90 requests a minute; we use far fewer
    return covers


def shown(path):
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {shown(path)} ({path.stat().st_size / 1024:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", default="predictions/predictions.json",
                        help="forecasts written by `python -m yosoku.run`; the mock is used if this is missing")
    parser.add_argument("--out-dir", default="web/data", help="where the site reads its data (default: web/data)")
    parser.add_argument("--no-covers", action="store_true", help="skip the AniList lookup and keep covers.json as it is")
    args = parser.parse_args()

    source = ROOT / args.predictions
    if not source.exists():
        source = ROOT / "app" / "mock_predictions.json"
        print(f"{args.predictions} not found; using the mock forecasts ({shown(source)})")
    predictions = json.loads(source.read_text(encoding="utf-8"))
    out = ROOT / args.out_dir
    write_json(out / "predictions.json", predictions)

    covers_file = out / "covers.json"
    if predictions.get("mock"):
        write_json(covers_file, {})
        print("mock forecasts: no covers fetched (their ids belong to other, real anime)")
    elif not args.no_covers:
        ids = referenced_ids(predictions)
        print(f"fetching covers for {len(ids)} titles from AniList")
        write_json(covers_file, fetch_covers(ids))
    print("Done. Preview: python -m http.server -d web 8000   then open http://localhost:8000")


if __name__ == "__main__":
    main()

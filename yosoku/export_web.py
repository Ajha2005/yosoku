"""Prepare the static dashboard (web/) for deployment: copy the forecasts, build the demand guide, fetch the cover art.

    python -m yosoku.export_web                 # predictions/predictions.json (or the mock) + guide + covers from AniList
    python -m yosoku.export_web --no-covers     # no AniList lookup, e.g. when offline

Writes web/data/predictions.json, guide.json and covers.json, and copies the sealed forecasts and the daily job's
alerts.json when they exist. Commit them; Vercel serves them as-is.

Covers are links to AniList's image servers, not copies of the images. Mock forecasts use made-up ids that
collide with real AniList ids, so covers are never fetched for them (the guide uses real titles, so it gets its own).
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collectors"))
from common import request_json  # noqa: E402  (retrying HTTP helper shared with the collectors)
from yosoku import guide as demand_guide  # noqa: E402
from yosoku.money import MONEY  # noqa: E402  (a partner's amounts, published only with --with-money)

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


def with_money(predictions, path):
    """The forecasts with each one's amount range from yosoku.money, and a summary of the fit (not the partner's figures)."""
    if not path.exists():
        raise SystemExit(f"{shown(path)} not found: run `python -m yosoku.money` first.")
    money = json.loads(path.read_text(encoding="utf-8"))
    fit = money["fit"]
    predictions = {**predictions, "money": {"unit": money["unit"], "symbol": money["symbol"],
                                            **{k: fit[k] for k in ("titles", "per_10_points", "rank_correlation", "median_miss")}}}
    for title in predictions["titles"]:
        for moment, forecast in title["forecasts"].items():
            amount = money["forecasts"].get(str(title["anilist_id"]), {}).get(moment)
            if amount:
                forecast["money"] = amount
    return predictions


def guide_ids(guide):
    """Titles the demand guide shows posters for: every anime that reached India's Top 10, and every one India asks for."""
    return sorted({row["id"] for row in guide["watched"]} | {row["id"] for row in (guide.get("asks") or {}).get("titles", [])})


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
    parser.add_argument("--data-dir", default="data", help="collected data for the demand guide (default: data)")
    parser.add_argument("--no-covers", action="store_true", help="skip the AniList lookup and keep covers.json as it is")
    parser.add_argument("--with-money", action="store_true",
                        help="add the amounts from data/partner/money.json (python -m yosoku.money); only for a site the "
                             "partner has agreed to, never the public one")
    args = parser.parse_args()

    source = ROOT / args.predictions
    if not source.exists():
        source = ROOT / "web" / "data" / "mock_predictions.json"
        print(f"{args.predictions} not found; using the mock forecasts ({shown(source)})")
    predictions = json.loads(source.read_text(encoding="utf-8"))
    if args.with_money:
        predictions = with_money(predictions, ROOT / MONEY)
    out = ROOT / args.out_dir
    write_json(out / "predictions.json", predictions)

    # Sealed forecasts (python -m yosoku.seal) are copied byte for byte, so their fingerprints still match on the site.
    sealed = ROOT / "predictions" / "sealed"
    if sealed.is_dir():
        (out / "sealed").mkdir(parents=True, exist_ok=True)
        for path in sealed.iterdir():
            if path.suffix in (".json", ".md"):
                (out / "sealed" / path.name).write_bytes(path.read_bytes())

    # The daily job's status and alerts (python -m yosoku.daily) name real titles, so never beside mock forecasts.
    alerts, shown_alerts = ROOT / "predictions" / "alerts.json", out / "alerts.json"
    if alerts.exists() and not predictions.get("mock"):
        shown_alerts.write_bytes(alerts.read_bytes())
    elif shown_alerts.exists():
        shown_alerts.unlink()

    guide = demand_guide.build(ROOT / args.data_dir)
    write_json(out / "guide.json", guide)

    ids = set(guide_ids(guide))
    if not predictions.get("mock"):
        ids |= set(referenced_ids(predictions))
    if not args.no_covers:
        note = " (the guide's only: mock ids collide with real ones)" if predictions.get("mock") else ""
        print(f"fetching covers for {len(ids)} titles from AniList{note}")
        write_json(out / "covers.json", fetch_covers(sorted(ids)))
    print("Done. Preview: python -m http.server -d web 8000   then open http://localhost:8000")


if __name__ == "__main__":
    main()

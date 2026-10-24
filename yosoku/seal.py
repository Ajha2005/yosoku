"""Seal the forecasts for unreleased titles, so anyone can check later that they were made before launch.

A seal is a JSON file in predictions/sealed/ holding every upcoming title's forecasts, written in a fixed form
(sorted keys, no spaces) so its SHA-256 fingerprint is reproducible. The fingerprint goes in
predictions/sealed/LEDGER.md and is committed with it; git's history then dates it. A seal is never rewritten:
sealing again on the same day stops, and a new day makes a new file.

    python -m yosoku.seal               # seal today's upcoming forecasts from predictions/predictions.json
    python -m yosoku.seal --verify      # recompute every fingerprint in the ledger
    python -m yosoku.seal --score       # once sealed titles have aired and been labelled: how did we do?

Anyone can verify a seal without Python: `sha256sum predictions/sealed/<file>.json` (or `certutil -hashfile
<file> SHA256` on Windows) must print the fingerprint in the ledger.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date

import pandas as pd
from scipy.stats import spearmanr

from yosoku.data import ROOT, folder

SEALED = "predictions/sealed"
LEDGER_HEAD = ["# Sealed forecasts", "",
               "Each row is a file of forecasts for titles that had not been released when it was made. Its SHA-256 "
               "fingerprint was recorded here at the time; `python -m yosoku.seal --verify` checks them all.", "",
               "| Sealed on | File | Titles | Model commit | SHA-256 |", "| --- | --- | --- | --- | --- |"]


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def sealed_titles(predictions):
    """The upcoming titles, reduced to what was forecast: id, name, season, date and each moment's numbers."""
    keep = ("index", "low", "high", "verdict")
    return [{"anilist_id": t["anilist_id"], "name": t["name"], "season": t["season"], "start_date": t["start_date"],
             "forecasts": {m: {k: f[k] for k in keep} for m, f in t["forecasts"].items()}}
            for t in predictions["titles"] if t["group"] == "upcoming"]


def ledger_rows(out_dir):
    path = out_dir / SEALED / "LEDGER.md"
    if not path.exists():
        return []
    rows = [line.strip("| ").split(" | ") for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("| 20")]
    return [{"date": r[0], "file": r[1].strip("`"), "titles": int(r[2]), "commit": r[3].strip("`"), "sha256": r[4].strip("`")}
            for r in rows]


def sealed_forecasts(out_dir):
    """{anilist_id: {date, file, methods, lines, forecasts}}: each title's forecasts as last sealed.

    Seals are read in ledger order, so a later seal of the same title wins; a file that no longer matches its
    fingerprint is skipped (and reported), so the site never shows numbers anyone could tell apart from the seal."""
    found = {}
    for r in ledger_rows(out_dir):
        path = out_dir / SEALED / r["file"]
        if not path.exists() or sha256(path) != r["sha256"]:
            print(f"Skipped {r['file']}: missing or not matching its fingerprint (python -m yosoku.seal --verify)")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        lines = {m: {k: v[k] for k in ("launch_line", "hold_line")} for m, v in payload["thresholds"].items()}
        for t in payload["titles"]:
            found[t["anilist_id"]] = {"date": r["date"], "file": r["file"], "methods": payload["methods"], "lines": lines,
                                      "forecasts": t["forecasts"]}
    return found


def seal(out_dir, today):
    predictions = json.loads((out_dir / "predictions" / "predictions.json").read_text(encoding="utf-8"))
    if predictions.get("mock"):
        raise SystemExit("predictions.json is mock data: nothing to seal.")
    titles = sealed_titles(predictions)
    if not titles:
        raise SystemExit("No upcoming titles in predictions.json: collect data/upcoming/ and run `python -m yosoku.run`.")
    seasons = sorted({t["season"] for t in titles})
    name = f"{today}-{'-'.join(s.lower().replace(' ', '') for s in seasons)}.json"
    path = out_dir / SEALED / name
    if path.exists():
        raise SystemExit(f"{path.relative_to(out_dir)} exists: a seal is never rewritten. Seal again on another day.")
    payload = {"sealed_on": today, "model_commit": commit(), "seasons": seasons,
               "methods": {m: v.get("method") for m, v in predictions["thresholds"].items()},
               "thresholds": predictions["thresholds"], "titles": titles}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(payload))
    digest = sha256(path)
    rows = ledger_rows(out_dir) + [{"date": today, "file": name, "titles": len(titles), "commit": payload["model_commit"],
                                    "sha256": digest}]
    lines = LEDGER_HEAD + [f"| {r['date']} | `{r['file']}` | {r['titles']} | `{r['commit']}` | `{r['sha256']}` |" for r in rows]
    (out_dir / SEALED / "LEDGER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / SEALED / "latest.json").write_text(json.dumps(rows[-1], indent=1) + "\n", encoding="utf-8")
    print(f"Sealed {len(titles)} forecasts in {path.relative_to(out_dir)}\nSHA-256 {digest}\n"
          "Commit predictions/sealed/ now: the commit dates the seal.")


def verify(out_dir):
    rows = ledger_rows(out_dir)
    if not rows:
        raise SystemExit("No seals in the ledger yet.")
    bad = 0
    for r in rows:
        path = out_dir / SEALED / r["file"]
        ok = path.exists() and sha256(path) == r["sha256"]
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {r['file']} ({r['titles']} titles, sealed {r['date']})")
    if bad:
        sys.exit(f"{bad} seal(s) do not match their fingerprint.")


def score(out_dir):
    """Sealed forecasts against the India Demand Index of the titles that have since been labelled."""
    labels = pd.read_csv(out_dir / "labels" / "label_v1.csv").set_index("anilist_id")["idi"].dropna()
    for r in ledger_rows(out_dir):
        sealed = json.loads((out_dir / SEALED / r["file"]).read_text(encoding="utf-8"))
        print(f"\n{r['file']} (sealed {r['date']}):")
        for moment in ("cold", "t-28", "t+7"):
            rows = [(f["forecasts"][moment], labels[f["anilist_id"]]) for f in sealed["titles"]
                    if moment in f["forecasts"] and f["anilist_id"] in labels.index]
            if len(rows) < 5:
                print(f"  {moment}: {len(rows)} of these titles are labelled so far; need 5 to score")
                continue
            points = [f["index"] for f, _ in rows]
            actual = [a for _, a in rows]
            inside = sum(f["low"] <= a <= f["high"] for f, a in rows) / len(rows)
            print(f"  {moment}: {len(rows)} titles, rank correlation {spearmanr(points, actual).statistic:.2f}, "
                  f"{inside:.0%} inside the 80% range")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=".", help="where predictions/ and labels/ are (default: repo root)")
    parser.add_argument("--verify", action="store_true", help="check every sealed file against its fingerprint")
    parser.add_argument("--score", action="store_true", help="score sealed forecasts against titles labelled since")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    out_dir = folder(args.out_dir)
    if args.verify:
        verify(out_dir)
    elif args.score:
        score(out_dir)
    else:
        seal(out_dir, args.today)


if __name__ == "__main__":
    main()

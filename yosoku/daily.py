"""The daily job: keep the forecasts of titles still in play up to date, log every one, and flag those that move.

Most of the data never changes again: a title's buzz windows close on day +6 after its Japanese premiere, its India
Demand Index on day +27 and its Netflix weeks on day +90 (collectors/common.py, is_active). So each day only the
titles before that point are collected and forecast again. The daily work grows with the seasons in play, not with
the archive; refitting and the backtests (python -m yosoku.run) only need rerunning when titles get their labels.

  1. collect   the collectors for the upcoming folder: titles (--keep), Wikipedia, Netflix's weekly charts (fetched
               again on Wednesdays), YouTube in --refresh mode (new comments only, view counts logged), merge
  2. label     upcoming titles whose 28 days are over get their India Demand Index (yosoku.labels)
  3. forecast  every title in play, as of today: data up to yesterday, the decision clock's model and range
  4. log       predictions/history.csv, one row per title per day: the forecast as it stood that day
  5. alert     reports/alerts.md: a forecast that left the 80% range of the title's last verdict, or crossed a line
  6. publish   yosoku.decision and export_web, so the site shows the day's verdicts and each title's history

    python -m yosoku.daily                  # the whole job (network, and a YouTube key for step 1)
    python -m yosoku.daily --no-collect     # steps 2-6 from the files already collected
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date

import pandas as pd

from yosoku import features as feat
from yosoku.clock import DAYS
from yosoku.data import ROOT, add_folder_arguments, folder, load_daily, load_reddit, load_titles, read
from yosoku.evaluate import prepare
from yosoku.models import forecast
from yosoku.split import split_of

sys.path.insert(0, str(ROOT / "collectors"))
from common import is_active  # noqa: E402  (when a title's data stops changing, shared with the collectors)

HISTORY = "predictions/history.csv"
HISTORY_FIELDS = ["date", "anilist_id", "name", "day", "index", "low", "high"]
STAGE_DAYS = {"t-28": -28, "t+7": 7}


def clock_day(start, today):
    """The decision clock day of a forecast made today: days since the premiere, capped at the clock's last day,
    or "cold" before the clock's first day (and while the start date is unknown)."""
    if pd.isna(start) or (today - start).days < DAYS[0]:
        return "cold"
    return min((today - start).days, DAYS[-1])


def in_play(upcoming, today):
    return upcoming.index[[is_active(None if pd.isna(s) else s.date(), today.date()) for s in upcoming["start"]]]


def nowcasts(data_dir, upcoming_dir, out_dir, today):
    """DataFrame of today's forecast for every upcoming title in play: day, index, low, high."""
    titles, labels, _ = prepare(data_dir, out_dir, moments=[])
    split = split_of(titles)
    train = split.index[split.isin(["train", "validate"])].intersection(labels.index)  # never the 2025 test titles
    upcoming = load_titles(upcoming_dir)
    clock = json.loads((out_dir / "reports" / "clock.json").read_text(encoding="utf-8"))["days"]
    width = {d["day"]: d["width_live"] for d in clock}
    days = pd.Series({i: clock_day(upcoming.at[i, "start"], today) for i in in_play(upcoming, today)}, dtype=object)
    sources = [(titles, *load_daily(data_dir, titles), load_reddit(data_dir)),
               (upcoming, *load_daily(upcoming_dir, upcoming), load_reddit(upcoming_dir))]
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    rows = []
    for day, ids in days.groupby(days, sort=False).groups.items():
        moment = "cold" if day == "cold" else day - 1  # made on that day: data up to the day before
        f = pd.concat([feat.build(t.loc[t.index.isin(train) | t.index.isin(ids)], wiki, comments, moment, genres, reddit)
                       for t, wiki, comments, reddit in sources])
        out = forecast(moment, f, pd.concat([titles, upcoming]), labels, train, pd.Index(ids))
        # The range of the latest clock day this one has reached (an earlier day's range is never narrower).
        half = width["cold" if day == "cold" else max(d for d in DAYS if d <= day)]
        for anilist_id, value in out["forecast"].items():
            rows.append({"anilist_id": anilist_id, "name": upcoming.at[anilist_id, "name"], "day": day,
                         "index": round(float(value), 1), "low": round(max(0.0, value - half), 1),
                         "high": round(min(100.0, value + half), 1)})
    return pd.DataFrame(rows, columns=HISTORY_FIELDS[1:]).assign(date=today.date().isoformat())[HISTORY_FIELDS]


def log(history_path, today_rows):
    """Append today's rows to the history; running twice on one day keeps the later run."""
    old = read(history_path, required=False)
    if old is not None:
        old = old[old["date"] != today_rows["date"].iloc[0]] if len(today_rows) else old
    both = today_rows if old is None else pd.concat([old, today_rows], ignore_index=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    both.to_csv(history_path, index=False, encoding="utf-8-sig")
    return both


def alerts(today_rows, predictions):
    """Plain-language alerts: a forecast outside the range of the title's latest verdict, or across a verdict line.

    Only once buzz is in: before that, a difference from the cold verdict is two methods disagreeing, not news."""
    stages = {t["anilist_id"]: t for t in predictions["titles"] if t["group"] == "upcoming"}
    found = []
    for row in today_rows.to_dict("records"):
        title = stages.get(row["anilist_id"])
        if row["day"] == "cold" or title is None or not title["forecasts"]:
            continue
        stage = [m for m in feat.MOMENTS if m in title["forecasts"]][-1]
        f, lines = title["forecasts"][stage], predictions["thresholds"][stage]
        head = f"**{row['name']}** (day {row['day']:+d})"
        if not f["low"] <= row["index"] <= f["high"]:
            found.append(f"{head}: forecast {row['index']:.0f}, {'above' if row['index'] > f['high'] else 'below'} the "
                         f"{f['low']:.0f}–{f['high']:.0f} range of its {stage} verdict ({f['verdict']}).")
        if row["low"] >= lines["launch_line"] and f["verdict"] != "Launch":
            found.append(f"{head}: even the low end of today's range ({row['low']:.0f}) clears the launch line "
                         f"({lines['launch_line']}); its {stage} verdict was {f['verdict']}.")
        elif row["high"] < lines["hold_line"] and f["verdict"] != "Hold":
            found.append(f"{head}: even the high end of today's range ({row['high']:.0f}) is under the hold line "
                         f"({lines['hold_line']}); its {stage} verdict was {f['verdict']}.")
    return found


def report(today, today_rows, found):
    lines = [f"# Alerts, {today.date().isoformat()}", "", "Generated by `python -m yosoku.daily`; do not edit by hand.", "",
             f"{len(today_rows)} titles in play, forecast today with data up to yesterday "
             f"({(today_rows['day'] == 'cold').sum()} still before any buzz). "
             "Verdicts change only at the stages; these say where the evidence has moved since.", ""]
    lines += [f"- {a}" for a in found] if found else ["No alerts: every title in play is inside the range of its last verdict."]
    return "\n".join(lines) + "\n"


def run(module, *args, check=True):
    print(f"== {module} {' '.join(args)}")
    command = [sys.executable, *(["-m", module] if "/" not in module else [module]), *args]
    return subprocess.run(command, cwd=ROOT, check=check).returncode


def collect(upcoming_dir, today):
    """Step 1: the collectors for the titles still in play. A collector that fails is reported, not fatal."""
    titles = read(upcoming_dir / "titles.csv")
    years, seasons = titles["year"].astype(int), sorted(set(titles["season"]))
    folder_args = ["--data-dir", str(upcoming_dir)]
    # --keep: a title that slips out of the top of its season stays tracked, so its sealed forecast can still be scored.
    steps = [("collectors/collect_titles.py", [*folder_args, "--keep", "--start-year", str(years.min()),
                                               "--end-year", str(years.max()), "--seasons", *seasons]),
             ("collectors/collect_wikipedia.py", folder_args),
             # Aired titles need their Netflix weeks for the label; Netflix publishes the week's lists on Tuesdays.
             ("collectors/collect_netflix.py", [*folder_args, *(["--refresh"] if today.weekday() == 2 else [])])]
    if os.getenv("YOUTUBE_API_KEY"):
        steps.append(("collectors/collect_youtube.py", [*folder_args, "--refresh"]))
    else:
        print("No YOUTUBE_API_KEY: skipped YouTube; the forecasts use the comments collected so far.")
    steps.append(("collectors/merge.py", folder_args))
    failed = [name for name, args in steps if run(name, *args, check=False)]
    if failed:
        print(f"These collectors failed and will be retried tomorrow: {', '.join(failed)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_folder_arguments(parser)
    parser.add_argument("--upcoming-dir", default="data/upcoming")
    parser.add_argument("--no-collect", action="store_true", help="skip step 1 and use the files already collected")
    parser.add_argument("--no-publish", action="store_true", help="skip step 6 (decision and export_web)")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    data_dir, upcoming_dir, out_dir = folder(args.data_dir), folder(args.upcoming_dir), folder(args.out_dir)
    today = pd.Timestamp(args.today)
    if not (out_dir / "reports" / "clock.json").exists():
        raise SystemExit("reports/clock.json not found. Run `python -m yosoku.run` once first.")
    folders = ["--data-dir", args.data_dir, "--out-dir", args.out_dir]

    if not args.no_collect:
        collect(upcoming_dir, today)
    run("yosoku.labels", *folders, "--upcoming-dir", args.upcoming_dir)
    today_rows = nowcasts(data_dir, upcoming_dir, out_dir, today)
    log(out_dir / HISTORY, today_rows)
    if not args.no_publish:
        run("yosoku.decision", *folders, "--upcoming-dir", args.upcoming_dir, "--today", args.today)
    predictions = json.loads((out_dir / "predictions" / "predictions.json").read_text(encoding="utf-8"))
    found = alerts(today_rows, predictions)
    (out_dir / "reports" / "alerts.md").write_text(report(today, today_rows, found), encoding="utf-8")
    print(f"{len(today_rows)} titles in play; {len(found)} alerts in reports/alerts.md; history in {HISTORY}")
    if not args.no_publish and out_dir == ROOT:
        run("yosoku.export_web", "--no-covers")


if __name__ == "__main__":
    main()

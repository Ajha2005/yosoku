"""Phase 5: turn forecasts into Launch, Test-market or Hold, with reasons, and write predictions.json.

Verdict rule: Launch if the low end of the 80% range clears the launch line, Hold if the high end is
under the hold line, otherwise Test-market. The two lines start at 60 and 40 and are tuned on the
2024 validation titles so that at least 70% of Launch titles end up in the top third of the index
(and 70% of Hold titles in the bottom third). Release-window clashes are flagged, never scored.

    python -m yosoku.decision             # 2024 backtest plus upcoming titles in data/upcoming/
    python -m yosoku.decision --final     # also the 2025 test titles (after evaluate --final)
"""

import argparse
import json
from datetime import date

import numpy as np
import pandas as pd

from yosoku import features as feat
from yosoku.data import HUBS, add_folder_arguments, folder, load_daily, load_titles
from yosoku.evaluate import prepare
from yosoku.models import forecast
from yosoku.split import guard_test, split_of

LAUNCH_LINE, HOLD_LINE = 60, 40
PRECISION_TARGET = 0.70
VERDICT_JA = {"Launch": "投入推奨", "Test-market": "テスト販売", "Hold": "見送り"}
WINDOW_CLASHES = [  # (months, warning)
    ({10, 11}, "Festive season (Diwali, Oct–Nov): crowded release slate, high leisure spend"),
    ({2, 3}, "Board exams (Feb–Mar): students, the core audience, watch less"),
    ({3, 4, 5}, "IPL cricket (late Mar–May): competes for evening screen time"),
]


def verdict(low, high, launch_line, hold_line):
    if low >= launch_line:
        return "Launch"
    if high < hold_line:
        return "Hold"
    return "Test-market"


def tune(point, actual, width):
    """(launch line, hold line) tuned on validation titles; the defaults if the data can't support a change."""
    both = pd.concat([point.rename("point"), actual.rename("actual")], axis=1).dropna()
    if len(both) < 15 or np.isnan(width):
        return LAUNCH_LINE, HOLD_LINE
    top, bottom = both["actual"].quantile(2 / 3), both["actual"].quantile(1 / 3)
    launch = next((line for line in range(30, 85, 5)
                   if (picked := both[both["point"] - width >= line]).shape[0] >= 3
                   and (picked["actual"] >= top).mean() >= PRECISION_TARGET), LAUNCH_LINE)
    hold = next((line for line in range(70, 15, -5)
                 if (picked := both[both["point"] + width < line]).shape[0] >= 3
                 and (picked["actual"] <= bottom).mean() >= PRECISION_TARGET), HOLD_LINE)
    return launch, min(hold, launch)


def window_flags(start):
    if pd.isna(start):
        return []
    return [warning for months, warning in WINDOW_CLASHES if start.month in months]


def available_moments(start, today):
    """Moments whose cutoff day has passed; the rest would need data from the future."""
    if pd.isna(start):
        return ["cold"]
    days = (pd.Timestamp(today) - start).days
    return ["cold"] + [m for m in ("t-28", "t+7") if days > feat.CUTOFF[m]]


def reasons(point, low, high, label, looks, drivers, names, labels):
    shown = [f"{names.get(i, i)} ({labels.get(i, float('nan')):.0f})" for i, _ in looks[:3]]
    en = f"{label}: India Demand Index forecast {point:.0f} (80% range {low:.0f}–{high:.0f})."
    ja = f"判定：{VERDICT_JA[label]}。インド需要指数の予測 {point:.0f}（80%範囲 {low:.0f}–{high:.0f}）。"
    if shown:
        en += " Closest past titles: " + ", ".join(shown) + "."
        ja += "類似作品：" + "、".join(shown) + "。"
    if drivers:
        name, points = drivers[0]
        en += f" Biggest driver: {name} ({points:+.0f} points)."
    return en, ja


def entries(titles, labels, out, width, lines):
    names = titles["name"].to_dict()
    label_map = labels.to_dict()
    result = {}
    for anilist_id, row in out.iterrows():
        point = float(row["forecast"])
        low, high = max(0.0, point - width), min(100.0, point + width)
        label = verdict(low, high, *lines)
        en, ja = reasons(point, low, high, label, row["lookalikes"], row["drivers"], names, label_map)
        result[anilist_id] = {
            "index": round(point, 1), "low": round(low, 1), "high": round(high, 1), "verdict": label,
            "reason_en": en, "reason_ja": ja,
            "drivers": [{"name": n, "points": p} for n, p in row["drivers"]],
            "lookalikes": [{"anilist_id": i, "name": names.get(i, str(i)), "similarity": s,
                            "year": int(titles.loc[i, "start"].year) if i in titles.index and pd.notna(titles.loc[i, "start"]) else None,
                            "india_index": round(label_map[i], 1) if i in label_map else None}
                           for i, s in row["lookalikes"][:5]],
            "regions": {k: v for k, v in row["region"].items() if not k.startswith("_")},
            "region_titles": row["region"].get("_titles", 0),
        }
    return result


def title_info(titles, anilist_id, group, labels, today):
    row = titles.loc[anilist_id]
    actual = labels.get(anilist_id)
    return {
        "anilist_id": int(anilist_id), "group": group, "name": row["name"],
        "title_japanese": row.get("title_japanese", ""), "start_date": row["start_date"],
        "season": f"{str(row['season']).title()} {row['year']}", "format": row["format"], "source": row["source"],
        "genres": row["genre_list"], "audience": row["demographic"], "is_sequel": bool(row["is_sequel"]),
        "synopsis": str(row.get("synopsis", "") or "")[:600],
        "actual_index": None if actual is None or pd.isna(actual) else round(float(actual), 1),
        "release_window_flags": window_flags(row["start"]),
        "moments_available": available_moments(row["start"], today) if group == "upcoming" else feat.MOMENTS,
        "forecasts": {},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_folder_arguments(parser)
    parser.add_argument("--upcoming-dir", default="data/upcoming", help="unreleased titles (skipped if missing)")
    parser.add_argument("--final", action="store_true", help="include the 2025 test titles")
    parser.add_argument("--mock", action="store_true", help="mark the output as mock data (made-up numbers)")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    data_dir, out_dir = folder(args.data_dir), folder(args.out_dir)

    titles, labels, features = prepare(data_dir, out_dir)
    evaluation_file = out_dir / "reports" / "evaluation.json"
    if not evaluation_file.exists():
        raise SystemExit(f"{evaluation_file} not found. Run `python -m yosoku.evaluate` first.")
    evaluation = json.loads(evaluation_file.read_text(encoding="utf-8"))
    split = split_of(titles)
    train = split.index[split == "train"].intersection(labels.index)
    validate = split.index[split == "validate"].intersection(labels.index)
    train_all = split.index[split.isin(["train", "validate"])].intersection(labels.index)
    test = split.index[split == "test"].intersection(labels.index)

    upcoming_dir = folder(args.upcoming_dir)
    upcoming = None
    if (upcoming_dir / "titles.csv").exists():
        upcoming = load_titles(upcoming_dir)
        wiki, comments = load_daily(upcoming_dir, upcoming)
        genres = [c[len("genre_"):] for c in features["cold"].columns if c.startswith("genre_")]
        titles = pd.concat([titles, upcoming])
        for m in feat.MOMENTS:
            features[m] = pd.concat([features[m], feat.build(upcoming, wiki, comments, m, genres)])

    records = {}
    report = ["# Decisions on the 2024 validation titles", "", "Generated by `python -m yosoku.decision`.", "",
              "| Moment | Launch line | Hold line | Median index: Launch | Test-market | Hold | Titles per verdict |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    thresholds = {}
    for moment in feat.MOMENTS:
        info = evaluation["moments"].get(moment)
        if info is None:
            continue
        width = info["width"]
        val = forecast(moment, features[moment], titles, labels, train, validate)
        lines = tune(val["forecast"], labels.loc[validate], width)
        thresholds[moment] = {"launch_line": lines[0], "hold_line": lines[1], "range_half_width": round(width, 1),
                              "range_coverage": info["coverage"]}
        groups = [("validation", val)]
        if args.final:
            guard_test(test, titles, final=True)
            groups.append(("test", forecast(moment, features[moment], titles, labels, train_all, test)))
        if upcoming is not None:
            groups.append(("upcoming", forecast(moment, features[moment], titles, labels, train_all, upcoming.index)))
        for group, out in groups:
            for anilist_id, entry in entries(titles, labels, out, width, lines).items():
                record = records.setdefault(anilist_id, title_info(titles, anilist_id, group, labels, args.today))
                if moment in record["moments_available"]:
                    record["forecasts"][moment] = entry
        verdicts = pd.Series({i: records[i]["forecasts"][moment]["verdict"] for i in validate})
        medians = labels.loc[validate].groupby(verdicts).median()
        counts = verdicts.value_counts()
        report.append(f"| {moment} | {lines[0]} | {lines[1]} | " + " | ".join(
            f"{medians.get(v, float('nan')):.0f}" for v in ("Launch", "Test-market", "Hold")) + " | "
            + ", ".join(f"{v} {counts.get(v, 0)}" for v in ("Launch", "Test-market", "Hold")) + " |")
    report += ["", "Gate G5: median index of Launch > Test-market > Hold at each moment. "
               "Thresholds are tuned on these same titles, so this table is optimistic; the 2025 test is the honest check."]

    payload = {
        "generated": args.today, "mock": args.mock, "thresholds": thresholds,
        "hubs": {name: states for name, states in HUBS.values()},
        "evaluation": evaluation, "titles": list(records.values()),
    }
    (out_dir / "predictions").mkdir(parents=True, exist_ok=True)
    (out_dir / "predictions" / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=float),
                                                               encoding="utf-8")
    (out_dir / "reports" / "decision.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    counts = pd.Series([r["group"] for r in records.values()]).value_counts().to_dict()
    print(f"Wrote predictions/predictions.json ({counts}) and reports/decision.md")


if __name__ == "__main__":
    main()

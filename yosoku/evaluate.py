"""Phase 3-4: score the baselines and models the same way, on titles they never saw.

For each forecast moment it trains on 2019-2023 and scores 2024 (validation), and repeats the
season-by-season rolling check from Winter 2020 to Fall 2024. Scores: rank correlation (Spearman)
with a bootstrap 95% interval, top-20% hit rate, mean absolute error, and errors by segment.
The rolling errors also set the width of the 80% ranges, which are then checked on 2024, separately for the
titles whose index includes YouTube. Titles not released yet take their range from those titles' misses only:
every upcoming title gets YouTube data, so its index will include it too (labels.youtube_part).

    python -m yosoku.evaluate            # writes reports/evaluation.md and reports/evaluation.json
    python -m yosoku.evaluate --final    # also scores the 2025 test titles once: reports/final.md
"""

import argparse
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from yosoku import features as feat
from yosoku.data import add_folder_arguments, folder, load_daily, load_reddit, load_titles, read
from yosoku.labels import youtube_part
from yosoku.models import baselines, conformal_width, forecast
from yosoku.split import guard_test, rolling_folds, split_of

MAIN = {"cold": "Blend", "t-28": "Blend", "t+7": "Blend"}
MIN_TRAIN, MIN_TARGET = 20, 5
MIN_MISSES = 30  # past misses needed before a range is set from one group of titles alone
TOP_SHARE = 0.20


def live_width(misses, youtube):
    """Half-width of the range for titles not released yet, from out-of-sample misses (a Series by anilist_id).

    Only the misses of titles whose index includes YouTube, as an upcoming title's will (labels.youtube_part); all
    misses while there are too few of those."""
    own = misses[youtube.reindex(misses.index, fill_value=False).to_numpy()]
    return conformal_width(own.to_numpy() if len(own.dropna()) >= MIN_MISSES else misses.to_numpy())


def prepare(data_dir, out_dir, version="v1", moments=feat.MOMENTS):
    """(titles, labels, {moment: features}); a moment is a stage name or a cutoff day (features.stage)."""
    titles = load_titles(data_dir)
    labels = read(out_dir / "labels" / f"label_{version}.csv").set_index("anilist_id")["idi"].dropna()
    wiki, comments = load_daily(data_dir, titles)
    reddit = load_reddit(data_dir)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    features = {m: feat.build(titles, wiki, comments, m, genres, reddit) for m in moments}
    return titles, labels, features


def predict_all(moment, features, titles, labels, train_ids, target_ids):
    """DataFrame of every method's forecasts for target_ids, plus the main model's details."""
    main = forecast(moment, features, titles, labels, train_ids, target_ids)
    methods = pd.DataFrame(baselines(moment, features, titles, labels, train_ids, target_ids))
    methods["Lookalike"] = main["lookalike"]
    methods["Blend"] = main["forecast"]
    return methods.astype(float), main


def scores(pred, actual):
    both = pd.concat([pred.rename("pred"), actual.rename("actual")], axis=1).dropna()
    if len(both) < 3:
        return {"titles": len(both), "spearman": np.nan, "top20": np.nan, "mae": np.nan}
    k = max(1, int(round(len(both) * TOP_SHARE)))
    top_actual = set(both["actual"].nlargest(k).index)
    top_pred = set(both["pred"].nlargest(k).index)
    return {"titles": len(both), "spearman": spearmanr(both["pred"], both["actual"]).statistic,
            "top20": len(top_actual & top_pred) / k, "mae": float((both["pred"] - both["actual"]).abs().mean())}


def bootstrap(pred, actual, seed=0, n=1000):
    both = pd.concat([pred, actual], axis=1).dropna().to_numpy()
    if len(both) < 5:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    stats = [spearmanr(*both[rng.integers(0, len(both), len(both))].T).statistic for _ in range(n)]
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))


def rolling(moment, features, titles, labels):
    """Out-of-sample forecasts for every rolling season, with the season name."""
    frames = []
    for name, train, target in rolling_folds(titles):
        train, target = train.intersection(labels.index), target.intersection(labels.index)
        if len(train) < MIN_TRAIN or len(target) < MIN_TARGET:
            continue
        methods, _ = predict_all(moment, features[moment], titles, labels, train, target)
        frames.append(methods.assign(season=name))
    return pd.concat(frames) if frames else pd.DataFrame()


def fmt(x, digits=2):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}f}"


def share(x):
    return "–" if x is None else f"{x:.0%}"


def evaluate(titles, labels, features):
    split = split_of(titles)
    train = split.index[split == "train"].intersection(labels.index)
    validate = split.index[split == "validate"].intersection(labels.index)
    guard_test(validate, titles, final=False)
    results = {"moments": {}, "titles": {"train": len(train), "validate": len(validate)}}
    lines = ["# Evaluation", "", "Generated by `python -m yosoku.evaluate`; do not edit by hand.", "",
             f"Labelled titles: {len(train)} train (2019–2023), {len(validate)} validation (2024). "
             "2025 test titles are not scored here.", ""]
    if len(train) < MIN_TRAIN or len(validate) < MIN_TARGET:
        lines.append("Not enough labelled titles to evaluate yet.")
        return "\n".join(lines) + "\n", results

    sequel = titles["is_sequel"]
    youtube = youtube_part(titles)
    for moment in feat.MOMENTS:
        methods, _ = predict_all(moment, features[moment], titles, labels, train, validate)
        actual = labels.loc[validate]
        roll = rolling(moment, features, titles, labels)
        main = MAIN[moment]
        before_validation = roll[~roll["season"].str.endswith(str(2024))] if len(roll) else roll

        table = []
        for method in methods.columns:
            s = scores(methods[method], actual)
            low, high = bootstrap(methods[method], actual)
            new = scores(methods[method][sequel.loc[validate] == 0], actual)
            seq = scores(methods[method][sequel.loc[validate] == 1], actual)
            per_season = [spearmanr(*g[[method]].join(labels).dropna().to_numpy().T).statistic
                          for _, g in roll.groupby("season") if len(g) >= MIN_TARGET] if len(roll) else []
            table.append({"method": method, **s, "low": low, "high": high, "new_spearman": new["spearman"],
                          "sequel_spearman": seq["spearman"],
                          "rolling_spearman": float(np.nanmean(per_season)) if per_season else np.nan,
                          "rolling_seasons": len(per_season)})
        table = pd.DataFrame(table).set_index("method")
        others = table.drop(index=[m for m in ("Lookalike", "Blend") if m in table.index])
        best = others["spearman"].idxmax() if others["spearman"].notna().any() else None
        beats = best is not None and table.loc[main, "spearman"] > others.loc[best, "spearman"] \
            and table.loc[main, "top20"] >= others.loc[best, "top20"] \
            and table.loc[main, "new_spearman"] > others.loc[best, "new_spearman"]
        # Gate G4's fallback: where the model does not beat the best simple rule, that rule makes the forecasts.
        used = main if beats or best is None else best
        width = conformal_width((before_validation[used] - labels.reindex(before_validation.index)).to_numpy()) \
            if len(before_validation) else np.nan
        if np.isnan(width):  # too few rolling seasons: fall back to validation errors, and say so
            width = conformal_width((methods[used] - actual).to_numpy())
        miss = (methods[used] - actual).abs()
        inside = (miss <= width).mean()
        # Checked apart: the titles whose index includes YouTube, picked (for past titles) by how popular they are today.
        has = youtube.reindex(validate, fill_value=False).to_numpy()
        held = {"youtube": float((miss[has] <= width).mean()) if has.any() else None, "youtube_titles": int(has.sum()),
                "other": float((miss[~has] <= width).mean()) if (~has).any() else None, "other_titles": int((~has).sum())}
        # Titles not released yet: every season whose outcome is known now, the 2024 misses included, and only the
        # titles whose index includes YouTube, as theirs will.
        live = live_width(roll[used] - labels.reindex(roll.index), youtube) if len(roll) else np.nan
        live = width if np.isnan(live) else live

        lines += [f"## Moment: {moment}", "",
                  "| Method | Spearman (95% interval) | Top-20% hit | MAE | New shows | Sequels | Rolling seasons |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for method, r in table.iterrows():
            mark = (" **(main)**" if method == main else "") + (" **(used)**" if method == used else "")
            lines.append(f"| {method}{mark} | {fmt(r.spearman)} ({fmt(r.low)} to {fmt(r.high)}) | {fmt(r.top20)} | "
                         f"{fmt(r.mae, 1)} | {fmt(r.new_spearman)} | {fmt(r.sequel_spearman)} | "
                         f"{fmt(r.rolling_spearman)} over {int(r.rolling_seasons)} |")
        lines += ["", f"- Best baseline: {best}. {main} beats it overall, on top-20% hits and for new shows: "
                      f"**{'yes' if beats else 'no'}**.",
                  f"- Forecasts and verdicts use: **{used}**."
                  + ("" if used == main else " The model does not beat this rule, so the rule is shipped (gate G4 fallback)."),
                  f"- 80% range ({used}): ± {fmt(width, 1)} points; contains the truth for **{inside:.0%}** of 2024 titles "
                  f"(target 70–90%): {share(held['other'])} of the {held['other_titles']} whose index has no YouTube part, "
                  f"{share(held['youtube'])} of the {held['youtube_titles']} that have one.",
                  f"- 80% range for titles not released yet: ± {fmt(live, 1)} points, from the misses of the titles whose index "
                  "includes YouTube, in every rolling season including 2024.", ""]
        results["moments"][moment] = {"main": main, "used": used, "width": width, "width_live": live, "coverage": float(inside),
                                      "coverage_by_part": held,
                                      "beats_baseline": bool(beats), "best_baseline": best,
                                      "table": json.loads(table.to_json())}
    passed = all(m["beats_baseline"] for m in results["moments"].values())
    lines += ["## Why the 2024 ranges miss", "",
              "YouTube comments were collected only for the 200 titles most popular on AniList today. A 2024 title has had "
              "less time to get there, so the 2024 titles whose index includes YouTube are mostly hits, and they beat their "
              "forecasts; the ranges hold for the others. Every upcoming title gets YouTube data from the daily job, so its "
              "range comes from the misses of the titles whose index includes YouTube, which makes it wider. Collecting "
              "YouTube for every title (label v2) removes the cause.", ""]
    lines += ["## Gate G4", "", f"Main model beats the best baseline at every moment: **{'PASS' if passed else 'FAIL'}**. "
              "Where it does not, the best baseline makes the forecasts and the model's lookalikes are kept as evidence "
              "(marked **(used)** above)."]
    return "\n".join(lines) + "\n", results


def final(titles, labels, features):
    split = split_of(titles)
    train = split.index[split.isin(["train", "validate"])].intersection(labels.index)
    test = split.index[split == "test"].intersection(labels.index)
    guard_test(test, titles, final=True)
    lines = ["# Final test: 2025 titles, scored once", "", f"{len(train)} training titles (2019–2024), {len(test)} test titles.", ""]
    for moment in feat.MOMENTS:
        methods, _ = predict_all(moment, features[moment], titles, labels, train, test)
        lines += [f"## {moment}", "", "| Method | Spearman (95% interval) | Top-20% hit | MAE |", "| --- | --- | --- | --- |"]
        for method in methods.columns:
            s = scores(methods[method], labels.loc[test])
            low, high = bootstrap(methods[method], labels.loc[test])
            lines.append(f"| {method} | {fmt(s['spearman'])} ({fmt(low)} to {fmt(high)}) | {fmt(s['top20'])} | {fmt(s['mae'], 1)} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_folder_arguments(parser)
    parser.add_argument("--final", action="store_true", help="also score the 2025 test titles (do this once)")
    args = parser.parse_args()
    data_dir, out_dir = folder(args.data_dir), folder(args.out_dir)

    titles, labels, features = prepare(data_dir, out_dir)
    text, results = evaluate(titles, labels, features)
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    (out_dir / "reports" / "evaluation.md").write_text(text, encoding="utf-8")
    (out_dir / "reports" / "evaluation.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("Wrote reports/evaluation.md")
    if args.final:
        (out_dir / "reports" / "final.md").write_text(final(titles, labels, features), encoding="utf-8")
        print("Wrote reports/final.md (2025 test titles)")


if __name__ == "__main__":
    main()

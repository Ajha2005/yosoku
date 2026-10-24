"""Phase 2: the India Demand Index (IDI), one number per released title, plus the checks behind it.

Three parts, all measured over days 0-27 after the Japanese start date. Google Trends is not
collected this round (see docs/decisions.md), so its 40% is left out and the weights below are
rescaled exactly as for any other missing part:

  YouTube from India           30%  yt_india_month1: trailer comments by people in India
                                    (Indian scripts, Hinglish or naming India; collectors/india_signals.py)
  Streaming                    20%  netflix_top10_weeks_90d
  Wikipedia                    10%  wiki_hi/ta/te/en_month1, summed (English plus the market's own
                                    languages: every language but Japanese; see collectors/markets.py)

Each part is log-transformed and turned into a percentile rank among the titles that have it.
The index averages the parts a title has, rescaling the weights; fewer than two parts, no label.

    python -m yosoku.labels                   # writes labels/label_v1.csv and reports/label.md
"""

import argparse
import re
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

from yosoku.data import add_folder_arguments, folder, load_titles, read

WEIGHTS = {"youtube": 0.30, "streaming": 0.20, "wikipedia": 0.10}
MIN_PARTS = 2
WEIGHT_SHIFT = 0.10  # stability check: move each weight by this much
STABILITY_TARGET = 0.9


def raw_parts(titles):
    """DataFrame of each part's raw value; NaN means no data, never zero."""
    parts = pd.DataFrame(index=titles.index)
    if "yt_india_month1" in titles:
        parts["youtube"] = titles["yt_india_month1"]
    if "netflix_top10_weeks_90d" in titles:
        parts["streaming"] = titles["netflix_top10_weeks_90d"]
    wiki = [c for c in titles.columns if re.fullmatch(r"wiki_[a-z]+_month1", c) and c != "wiki_ja_month1"]
    if wiki:
        parts["wikipedia"] = titles[wiki].sum(axis=1, min_count=1)
    return parts


def percentiles(parts):
    """Each part as a 0-1 percentile rank after log1p, among the titles that have it."""
    return np.log1p(parts).rank(pct=True)


def index(ranks, weights=WEIGHTS):
    """IDI 0-100 from percentile ranks, rescaling weights over the parts each title has."""
    w = pd.Series({part: weights[part] for part in ranks.columns})
    available = ranks.notna()
    total = (ranks.fillna(0) * w).sum(axis=1) / (available * w).sum(axis=1)
    return (100 * total).where(available.sum(axis=1) >= MIN_PARTS)


def agreement(parts):
    rows = []
    for a, b in combinations(parts.columns, 2):
        both = parts[[a, b]].dropna()
        rho = spearmanr(both[a], both[b]).statistic if len(both) >= 3 else np.nan
        rows.append({"pair": f"{a} vs {b}", "titles": len(both), "spearman": rho})
    return pd.DataFrame(rows)


def against_rest(parts, ranks):
    """DataFrame per part: titles with data, and Spearman with the index of the other parts (so it is not compared with itself)."""
    rows = []
    for part in parts.columns:
        others = ranks.drop(columns=part)
        w = pd.Series({p: WEIGHTS[p] for p in others.columns})
        rest = (others.fillna(0) * w).sum(axis=1) / (others.notna() * w).sum(axis=1)
        both = pd.concat([ranks[part], rest.where(others.notna().any(axis=1))], axis=1).dropna()
        rows.append({"part": part, "titles": int(parts[part].notna().sum()), "pairs": len(both),
                     "spearman": spearmanr(both.iloc[:, 0], both.iloc[:, 1]).statistic if len(both) >= 3 else np.nan})
    return pd.DataFrame(rows).set_index("part")


def stability(ranks, base):
    rows = []
    for part in ranks.columns:
        for shift in (-WEIGHT_SHIFT, WEIGHT_SHIFT):
            weights = dict(WEIGHTS)
            weights[part] = max(weights[part] + shift, 0.01)
            moved = index(ranks, weights)
            both = pd.concat([base, moved], axis=1).dropna()
            rows.append({"weight": f"{part} {shift:+.2f}", "kendall_tau": kendalltau(both.iloc[:, 0], both.iloc[:, 1]).statistic})
    return pd.DataFrame(rows)


def money_check(idi, data_dir, seed=0):
    """Spearman of the index with India box office (data/india_box_office.csv, filled in by hand), with a bootstrap 95% interval."""
    films = read(data_dir / "india_box_office.csv", required=False)
    if films is None or "india_gross_inr" not in films:
        return None
    joined = films.set_index("anilist_id")["india_gross_inr"].to_frame().join(idi.rename("idi")).dropna()
    if len(joined) < 5:
        return {"films": len(joined), "spearman": np.nan, "low": np.nan, "high": np.nan}
    rng = np.random.default_rng(seed)
    boot = [spearmanr(*joined.iloc[rng.integers(0, len(joined), len(joined))].T.values).statistic for _ in range(2000)]
    return {"films": len(joined), "spearman": spearmanr(joined["idi"], joined["india_gross_inr"]).statistic,
            "low": np.nanpercentile(boot, 2.5), "high": np.nanpercentile(boot, 97.5)}


def box_office(idi, data_dir):
    """[{film, India box office, its index}], biggest first, for the Method page; [] without data/india_box_office.csv."""
    films = read(data_dir / "india_box_office.csv", required=False)
    if films is None or "india_gross_inr" not in films:
        return []
    rows = []
    for row in films.sort_values("india_gross_inr", ascending=False).itertuples():
        value = idi.get(row.anilist_id)
        rows.append({"anilist_id": int(row.anilist_id), "name": row.title, "india_gross_inr": int(row.india_gross_inr),
                     "basis": row.basis, "source": row.source,
                     "india_index": None if value is None or pd.isna(value) else round(float(value), 1)})
    return rows


def checks(labels, parts, ranks, data_dir):
    """Gate G2 in plain terms for the dashboard: do the parts agree, does the ranking hold, and the box-office films."""
    agree = agreement(parts)
    stable = stability(ranks, labels["idi"])
    positive = bool((agree["spearman"] > 0).all()) if len(agree) else False
    weakest = stable.loc[stable["kendall_tau"].idxmin()] if len(stable) else None
    steady = bool(weakest is not None and weakest["kendall_tau"] >= STABILITY_TARGET)
    return {"parts_agree": positive, "ranking_holds": steady, "passed": positive and steady,
            "weight_shift": WEIGHT_SHIFT, "weakest_shift": None if weakest is None else weakest["weight"].split()[0],
            "box_office": box_office(labels["idi"], data_dir)}


def build(titles):
    """(labels DataFrame, raw parts, percentile ranks) for released titles."""
    released = titles[titles["start"].notna() & (titles["start"] + pd.Timedelta(days=27) < pd.Timestamp.today())]
    parts = raw_parts(released)
    ranks = percentiles(parts)
    labels = pd.DataFrame({"idi": index(ranks), "parts": ranks.notna().sum(axis=1)})
    labels = labels.join(ranks.add_prefix("p_")).join(parts.add_prefix("raw_"))
    return labels, parts, ranks


def report(labels, parts, ranks, data_dir):
    labelled = labels["idi"].notna()
    agree = agreement(parts)
    stable = stability(ranks, labels["idi"])
    money = money_check(labels["idi"], data_dir)
    positive = bool((agree["spearman"] > 0).all()) if len(agree) else False
    steady = bool(stable["kendall_tau"].min() >= STABILITY_TARGET) if len(stable) else False
    rescaled = {part: WEIGHTS[part] / sum(WEIGHTS[p] for p in parts.columns) for part in parts.columns}

    lines = ["# Label v1: India Demand Index", "", "Generated by `python -m yosoku.labels`; do not edit by hand.", "",
             f"- Released titles: {len(labels)}; labelled (two or more parts): **{labelled.sum()}**",
             "- Weights after leaving out Search (no Trends this round): "
             + ", ".join(f"{part} {w:.0%}" for part, w in rescaled.items()), "",
             "## Coverage", "", "| Part | Titles with data |", "| --- | --- |"]
    lines += [f"| {part} | {parts[part].notna().sum()} |" for part in parts.columns]
    lines += ["", "## Agreement (Spearman between parts; expect all positive, most above 0.3)", "",
              "| Pair | Titles | Spearman |", "| --- | --- | --- |"]
    lines += [f"| {r.pair} | {r.titles} | {r.spearman:.2f} |" for r in agree.itertuples()]
    rest = against_rest(parts, ranks)
    lines += ["", "## Each part against the rest (Spearman with the index of the other parts)", "",
              "| Part | Titles | Spearman |", "| --- | --- | --- |"]
    lines += [f"| {part} | {int(r.pairs)} | {r.spearman:.2f} |" for part, r in rest.iterrows()]
    lines += ["", f"## Stability (Kendall's tau after moving one weight by {WEIGHT_SHIFT:.2f}; target {STABILITY_TARGET})", "",
              "| Weight | Kendall's tau |", "| --- | --- |"]
    lines += [f"| {r.weight} | {r.kendall_tau:.3f} |" for r in stable.itertuples()]
    lines += ["", "## Money check (India box office)", ""]
    if money is None:
        lines.append("Not run: `data/india_box_office.csv` (anilist_id, india_gross_inr, source) does not exist yet.")
    else:
        lines.append(f"{money['films']} films, Spearman {money['spearman']:.2f} "
                     f"(95% interval {money['low']:.2f} to {money['high']:.2f}). A sanity check, not proof.")
    lines += ["", "## Gate G2", "",
              f"- All part pairs positive: **{'yes' if positive else 'no'}**",
              f"- Rankings hold at tau >= {STABILITY_TARGET}: **{'yes' if steady else 'no'}**",
              f"- Gate: **{'PASS' if positive and steady else 'FAIL'}**"]
    return "\n".join(lines) + "\n", positive and steady


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_folder_arguments(parser)
    parser.add_argument("--version", default="v1")
    args = parser.parse_args()
    data_dir, out_dir = folder(args.data_dir), folder(args.out_dir)

    labels, parts, ranks = build(load_titles(data_dir))
    text, passed = report(labels, parts, ranks, data_dir)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    labels.to_csv(out_dir / "labels" / f"label_{args.version}.csv", encoding="utf-8-sig")
    (out_dir / "reports" / "label.md").write_text(text, encoding="utf-8")
    print(f"Labelled {labels['idi'].notna().sum()} of {len(labels)} released titles; gate G2 {'PASS' if passed else 'FAIL'}")
    print(f"Wrote labels/label_{args.version}.csv and reports/label.md")


if __name__ == "__main__":
    main()

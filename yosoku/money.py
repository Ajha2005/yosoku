"""Forecasts in money, once a partner shares what past titles earned in India.

The India Demand Index measures attention, not money. A rights holder or platform that shares, for 30 or more past
titles, what each earned in India over one fixed window (or its viewing hours) in data/partner/revenue.csv turns
every forecast into an amount:

  fit     log(amount) against each title's India Demand Index, a straight line (amounts are skewed: one hit earns
          what ten small titles do, so the line runs on the log)
  check   leave one out: every partner title forecast from the fit on the others; their rank correlation with what
          the titles earned, and the median miss in percent
  range   from the low end of a forecast's 80% index range, less what the line under-called for 1 title in 10 left
          out, to the high end plus what it over-called for 1 in 10: the forecast's own doubt and the money's

Partner figures are confidential, so data/partner/ is never committed (only its README and template are) and the
amounts go to data/partner/money.json, not to predictions.json. The website shows them only when it is exported
with `python -m yosoku.export_web --with-money`, for a private deployment the partner has agreed to.

    python -m yosoku.money          # after yosoku.run: needs data/partner/revenue.csv (see data/partner/README.md)
"""

import argparse
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from yosoku.data import ROOT, folder, read

PARTNER = "data/partner"
REVENUE = f"{PARTNER}/revenue.csv"
MONEY = f"{PARTNER}/money.json"
MIN_TITLES = 30  # fewer than this and a line through the points says too little
UNITS = {"JPY": "¥", "INR": "₹", "USD": "$", "HOURS": "h"}
TAIL = 0.10  # each end of the 80% range


def load(path, labels):
    """(amounts, index) for the partner's titles that have an India Demand Index, as two Series by anilist_id."""
    rows = read(path)
    missing = {"anilist_id", "amount", "unit"} - set(rows.columns)
    if missing:
        raise SystemExit(f"{path} lacks the columns {sorted(missing)}; see {PARTNER}/README.md")
    units = set(rows["unit"].str.upper())
    if len(units) != 1 or not units <= set(UNITS):
        raise SystemExit(f"Use one unit for every row, one of {', '.join(UNITS)}; found {sorted(units)}")
    rows = rows[pd.to_numeric(rows["amount"], errors="coerce") > 0].drop_duplicates("anilist_id").set_index("anilist_id")
    known = rows.index.intersection(labels.index)
    if len(known) < MIN_TITLES:
        raise SystemExit(f"{len(known)} of the partner's {len(rows)} titles have an India Demand Index; "
                         f"{MIN_TITLES} are needed to fit money to the index.")
    return rows.loc[known, "amount"].astype(float), labels.loc[known], units.pop()


def fit(amounts, index):
    """The line from the index to log(amount), with its leave-one-out check and the tails of its misses."""
    x, y = index.to_numpy(float), np.log(amounts.to_numpy(float))
    slope, intercept = np.polyfit(x, y, 1)
    left_out = np.array([np.polyval(np.polyfit(np.delete(x, i), np.delete(y, i), 1), x[i]) for i in range(len(x))])
    misses = y - left_out
    return {"titles": len(x), "intercept": float(intercept), "slope": float(slope),
            "per_10_points": float(np.exp(10 * slope) - 1),  # +35% means 10 more index points earn 35% more
            "rank_correlation": float(spearmanr(left_out, y).statistic),
            "median_miss": float(np.median(np.abs(np.expm1(misses)))),
            "under": float(np.quantile(misses, TAIL)), "over": float(np.quantile(misses, 1 - TAIL))}


def amounts_for(line, forecast):
    """{point, low, high} for one forecast entry (index, low, high), from a fit()."""
    at = lambda x: line["intercept"] + line["slope"] * x  # noqa: E731
    return {"point": float(np.exp(at(forecast["index"]))), "low": float(np.exp(at(forecast["low"]) + line["under"])),
            "high": float(np.exp(at(forecast["high"]) + line["over"]))}


def build(predictions, line, unit):
    """What data/partner/money.json holds: the fit, and an amount range for every forecast. Partner titles' own amounts
    are never written out: only what the line says about forecasts."""
    return {"unit": unit, "symbol": UNITS[unit], "fit": line,
            "forecasts": {str(t["anilist_id"]): {m: {k: round(v, -2 if unit != "HOURS" else 0) for k, v in amounts_for(line, f).items()}
                                                 for m, f in t["forecasts"].items()}
                          for t in predictions["titles"]}}


def report(money):
    line, sym = money["fit"], money["symbol"]
    return (f"Fitted on {line['titles']} titles. Each 10 points of the India Demand Index go with {line['per_10_points']:+.0%} "
            f"in {money['unit']}. Left out one at a time, the fit ranks the partner's titles at "
            f"{line['rank_correlation']:.2f} and misses by {line['median_miss']:.0%} at the median "
            f"({len(money['forecasts'])} titles get amounts in {sym}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=".", help="where labels/ and predictions/ are (default: repo root)")
    args = parser.parse_args()
    out_dir = folder(args.out_dir)
    path = ROOT / REVENUE
    if not path.exists():
        raise SystemExit(f"No partner data: put {REVENUE} in place first ({PARTNER}/revenue_template.csv shows the columns).")
    labels = read(out_dir / "labels" / "label_v1.csv").set_index("anilist_id")["idi"].dropna()
    amounts, index, unit = load(path, labels)
    predictions = json.loads((out_dir / "predictions" / "predictions.json").read_text(encoding="utf-8"))
    money = build(predictions, fit(amounts, index), unit)
    (ROOT / MONEY).write_text(json.dumps(money, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(report(money) + f"\nWrote {MONEY} (never committed). Publish it only with export_web --with-money.")


if __name__ == "__main__":
    main()

"""Forecasts in money from a partner's figures (yosoku/money.py), on made-up amounts."""

import json

import numpy as np
import pandas as pd
import pytest

from yosoku import export_web, money


def partner(n, seed=0):
    """(index, rows of a partner file): amounts that grow 49% per 10 index points, with noise."""
    rng = np.random.default_rng(seed)
    index = pd.Series(rng.uniform(10, 95, n), index=pd.RangeIndex(1, n + 1, name="anilist_id"))
    amount = np.exp(14 + 0.04 * index + rng.normal(0, 0.3, n))
    return index, pd.DataFrame({"anilist_id": index.index, "title": "x", "amount": amount, "unit": "JPY", "notes": ""})


def test_fit_recovers_the_line_and_checks_itself():
    index, rows = partner(40)
    line = money.fit(rows.set_index("anilist_id")["amount"], index)
    assert line["per_10_points"] == pytest.approx(np.exp(0.4) - 1, abs=0.15)
    assert line["rank_correlation"] > 0.8 and line["under"] < 0 < line["over"]
    amounts = money.amounts_for(line, {"index": 60, "low": 50, "high": 70})
    assert amounts["low"] < amounts["point"] < amounts["high"]


def test_too_few_titles_or_mixed_units_are_refused(tmp_path):
    path = tmp_path / "revenue.csv"
    index, rows = partner(29)
    rows.to_csv(path, index=False)
    with pytest.raises(SystemExit, match="30 are needed"):
        money.load(path, index)
    index, rows = partner(40)
    rows.loc[0, "unit"] = "USD"
    rows.to_csv(path, index=False)
    with pytest.raises(SystemExit, match="one unit"):
        money.load(path, index)


def test_amounts_reach_the_site_only_through_the_fit(tmp_path):
    index, rows = partner(40)
    line = money.fit(rows.set_index("anilist_id")["amount"], index)
    predictions = {"titles": [{"anilist_id": 7, "forecasts": {"t+7": {"index": 60, "low": 50, "high": 70}}}]}
    built = money.build(predictions, line, "JPY")
    assert set(built) == {"unit", "symbol", "fit", "forecasts"} and set(built["forecasts"]) == {"7"}  # no partner title
    path = tmp_path / "money.json"
    path.write_text(json.dumps(built), encoding="utf-8")
    shown = export_web.with_money(json.loads(json.dumps(predictions)), path)
    assert shown["money"]["titles"] == 40 and shown["titles"][0]["forecasts"]["t+7"]["money"]["point"] > 0
    assert "intercept" not in shown["money"]  # the site gets a summary of the fit, not the fit

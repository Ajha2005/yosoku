"""The fixed split by Japanese start date, and the rolling season-by-season check.

  train     2019-2023
  validate  2024
  test      2025, scored once with --final after everything else is settled
"""

import numpy as np
import pandas as pd

TRAIN_END, VALIDATE_YEAR, TEST_YEAR = 2023, 2024, 2025
SEASON_ORDER = {"WINTER": 0, "SPRING": 1, "SUMMER": 2, "FALL": 3}
ROLLING_FIRST, ROLLING_LAST = (2020, 0), (2024, 3)  # Winter 2020 to Fall 2024


def split_of(titles):
    year = titles["start"].dt.year
    return pd.Series(np.select([year <= TRAIN_END, year == VALIDATE_YEAR, year == TEST_YEAR],
                               ["train", "validate", "test"], "other"), index=titles.index)


def season_key(titles):
    return list(zip(titles["year"].astype(int), titles["season"].map(SEASON_ORDER)))


def rolling_folds(titles):
    """[(season name, train ids, test ids)]: train on every earlier season, forecast this one. Never touches the test year."""
    keys = pd.Series(season_key(titles), index=titles.index)
    keys = keys[titles["start"].dt.year < TEST_YEAR]
    folds = []
    for key in sorted(set(keys)):
        if ROLLING_FIRST <= key <= ROLLING_LAST:
            name = f"{[s for s, o in SEASON_ORDER.items() if o == key[1]][0].title()} {key[0]}"
            folds.append((name, keys.index[keys < key], keys.index[keys == key]))
    return folds


def guard_test(ids, titles, final):
    """Stop if test titles would be scored without --final."""
    if not final and (titles.loc[ids, "start"].dt.year == TEST_YEAR).any():
        raise SystemExit(f"Refusing to score {TEST_YEAR} test titles without --final.")


"""Run with: python -m pytest tests"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from yosoku import features as feat
from yosoku.data import ROOT, load_daily, load_titles
from yosoku.labels import index, percentiles, raw_parts
from yosoku.split import guard_test

sys.path.insert(0, str(Path(__file__).parent))
import fake_data  # noqa: E402


@pytest.fixture(scope="session")
def fake(tmp_path_factory):
    folder = tmp_path_factory.mktemp("fake")
    fake_data.main(folder, per_season=12)
    subprocess.run([sys.executable, "collectors/merge.py", "--data-dir", str(folder)], cwd=ROOT, check=True)
    return folder


def test_leakage(fake):
    """Inputs at a moment must not change when data after its cutoff day changes."""
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    for moment, cutoff in feat.CUTOFF.items():
        before = feat.build(titles, wiki, comments, moment, genres)
        if cutoff is None:
            later_wiki, later_comments = wiki.iloc[0:0], comments.iloc[0:0]  # cold: no activity at all
        else:
            later_wiki = wiki.assign(views=np.where(wiki["days_from_start"] > cutoff, 10**7, wiki["views"]))
            later_comments = pd.concat([comments, comments.assign(days_from_start=cutoff + 1, text="नमस्ते")])
        after = feat.build(titles, later_wiki, later_comments, moment, genres)
        if cutoff is None:
            assert list(before.columns) == list(after.columns)
        pd.testing.assert_frame_equal(before, after)


def test_window_past_cutoff_is_refused():
    rows = pd.DataFrame({"anilist_id": [1], "days_from_start": [0], "views": [5]})
    with pytest.raises(ValueError):
        feat.window_total(rows, "views", -28, 0, -29, [1])


def test_blank_is_not_zero():
    parts = pd.DataFrame({"youtube": [10, np.nan, 5], "streaming": [np.nan, np.nan, 2], "wikipedia": [100, 50, np.nan]})
    idi = index(percentiles(parts))
    assert idi.notna().tolist() == [True, False, True]  # the middle title has only one part


def test_test_titles_need_final(fake):
    titles = load_titles(fake)
    test_ids = titles.index[titles["start"].dt.year == 2025]
    with pytest.raises(SystemExit):
        guard_test(test_ids, titles, final=False)
    guard_test(test_ids, titles, final=True)


def test_end_to_end(fake):
    out = fake / "out"
    for module, extra in (("yosoku.labels", []), ("yosoku.evaluate", []),
                          ("yosoku.decision", ["--upcoming-dir", str(fake / "upcoming"), "--mock", "--today", "2026-10-24"])):
        subprocess.run([sys.executable, "-m", module, "--data-dir", str(fake), "--out-dir", str(out), *extra],
                       cwd=ROOT, check=True)
    payload = json.loads((out / "predictions" / "predictions.json").read_text(encoding="utf-8"))
    groups = {t["group"] for t in payload["titles"]}
    assert groups == {"validation", "upcoming"}  # no 2025 test titles without --final
    for title in payload["titles"]:
        for moment, forecast in title["forecasts"].items():
            assert moment in title["moments_available"]
            assert forecast["low"] <= forecast["index"] <= forecast["high"]
            assert forecast["verdict"] in {"Launch", "Test-market", "Hold"}
    upcoming = [t for t in payload["titles"] if t["group"] == "upcoming"]
    assert all(set(t["forecasts"]) == {"cold"} for t in upcoming)  # Winter 2027 is months away


def test_india_comments():
    from yosoku.data import classify
    found = classify(pd.Series([
        "Bhai ye Dan Da Dan ka Ep 2 hindi dub mai kab aayega",  # Hinglish, names Hindi
        "Please release in India",                               # mentions India, no hub
        "tamil dub pls",                                         # names Tamil
        "चाला बागुंदी नमस्ते",                                     # Devanagari script
        "hai hai ka ke ki",                                      # common words only: Japanese romaji, not Hindi
        "The voices and dubbing quality are great",              # English, no India signal
    ]))
    assert found["india"].tolist() == [True, True, True, True, False, False]
    assert found["hindi"].tolist() == [True, False, False, True, False, False]
    assert found["tamil"].tolist() == [False, False, True, False, False, False]


def test_youtube_part_is_india_comments():
    titles = pd.DataFrame({"yt_india_month1": [0.0, 3.0, np.nan], "netflix_top10_weeks_90d": [1, 2, 3],
                           "wiki_en_month1": [1, 2, 3]})
    parts = raw_parts(titles)
    assert parts["youtube"].tolist()[:2] == [0.0, 3.0] and np.isnan(parts["youtube"].iloc[2])

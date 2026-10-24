"""Run with: python -m pytest tests"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from yosoku import features as feat
from yosoku.data import ROOT, load_daily, load_reddit, load_titles
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
    reddit = load_reddit(fake)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    for moment, cutoff in feat.CUTOFF.items():
        before = feat.build(titles, wiki, comments, moment, genres, reddit)
        if cutoff is None:
            later_wiki, later_comments, later_reddit = wiki.iloc[0:0], comments.iloc[0:0], reddit.iloc[0:0]  # cold: no activity at all
        else:
            later_wiki = wiki.assign(views=np.where(wiki["days_from_start"] > cutoff, 10**7, wiki["views"]))
            later_comments = pd.concat([comments, comments.assign(days_from_start=cutoff + 1, text="नमस्ते")])
            later_reddit = pd.concat([reddit, reddit.assign(days_from_start=cutoff + 1)])
        after = feat.build(titles, later_wiki, later_comments, moment, genres, later_reddit)
        if cutoff is None:
            assert list(before.columns) == list(after.columns)
        pd.testing.assert_frame_equal(before, after)


def test_reddit_features(fake):
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    reddit = load_reddit(fake)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    columns = {m: set(feat.build(titles, wiki, comments, m, genres, reddit).columns) for m in feat.MOMENTS}
    without = set(feat.build(titles, wiki, comments, "t+7", genres).columns)
    assert not any(c.startswith("reddit_") for c in columns["cold"])
    assert {c for c in columns["t-28"] if c.startswith("reddit_")} == {"reddit_posts_early"}
    assert {c for c in columns["t+7"] if c.startswith("reddit_")} == {"reddit_posts_early", "reddit_posts_pre", "reddit_posts_launch"}
    assert not any(c.startswith("reddit_") for c in without)  # no Reddit data, no Reddit inputs
    early = feat.build(titles, wiki, comments, "t-28", genres, reddit)["reddit_posts_early"]
    assert early.isna().any() and early.notna().any()  # titles that were not searched are blank, not zero


def test_article_written_after_cutoff_is_blank(fake):
    """An article with no views by the cutoff did not exist yet: its views are unknown, also when it appears later."""
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    late = wiki["anilist_id"].iloc[0]
    wiki = wiki[~((wiki["anilist_id"] == late) & (wiki["lang"] == "en") & (wiki["days_from_start"] <= -29))]
    features = feat.build(titles, wiki, comments, "t-28", genres)
    assert np.isnan(features.loc[late, "wiki_en_early"])
    assert features["wiki_en_early"].notna().sum() > len(titles) / 2


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
    for moment, info in payload["evaluation"]["moments"].items():  # gate G4 fallback
        assert info["used"] == (info["main"] if info["beats_baseline"] else info["best_baseline"])
        assert payload["thresholds"][moment]["method"] == info["used"]


def test_simple_rule_makes_the_forecast(fake):
    """When a simple rule is used, its forecasts replace the model's; the lookalikes stay."""
    from yosoku.decision import predict
    from yosoku.models import baselines
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    features = feat.build(titles, wiki, comments, "t-28", genres)
    labels = pd.Series(np.linspace(0, 100, len(titles)), index=titles.index)
    train, target = titles.index[:-10], titles.index[-10:]
    out = predict("t-28", "Genre average", features, titles, labels, train, target)
    rule = baselines("t-28", features, titles, labels, train, target)["Genre average"]
    pd.testing.assert_series_equal(out["forecast"], rule.reindex(target), check_names=False)
    assert all(d == [] for d in out["drivers"]) and out["lookalikes"].notna().all()


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


def test_indiclid_only_counts_with_hindi_words():
    from yosoku.data import classify, indic_flags
    comments = pd.DataFrame({"comment_id": ["a", "b", "c", "d"], "text": [
        "Kab release hogi ye movie",       # Hinglish the word rules miss
        "Qué llegue enero yaaa",           # Spanish that IndicLID calls Malayalam
        "Download kha se hogi",            # Hinglish, but IndicLID was unsure
        "Kab release hogi ye movie",       # same words, IndicLID says English
    ]})
    languages = pd.DataFrame({"comment_id": ["a", "b", "c", "d"],
                              "language": ["hin_Latn", "mal_Latn", "asm_Latn", "eng_Latn"],
                              "probability": [0.95, 0.97, 0.3, 0.9]})
    assert classify(comments["text"])["india"].tolist() == [False] * 4
    found = classify(comments["text"], indic_flags(comments, languages))
    assert found["india"].tolist() == [True, False, False, False]
    assert found["hindi"].tolist() == [True, False, False, False]
    assert indic_flags(comments, None) is None


def test_youtube_part_is_india_comments():
    titles = pd.DataFrame({"yt_india_month1": [0.0, 3.0, np.nan], "netflix_top10_weeks_90d": [1, 2, 3],
                           "wiki_en_month1": [1, 2, 3]})
    parts = raw_parts(titles)
    assert parts["youtube"].tolist()[:2] == [0.0, 3.0] and np.isnan(parts["youtube"].iloc[2])


def test_wikipedia_launch_article():
    """An English article written after launch is swapped for the related page readers used then."""
    sys.path.insert(0, str(ROOT / "collectors"))
    from collect_wikipedia import launch_article, launch_names
    assert launch_names("Frieren (TV series)") == ["Frieren", "List of Frieren episodes"]
    assert launch_names("Demon Slayer: Kimetsu no Yaiba – The Movie: Mugen Train")[0] == "Demon Slayer: Kimetsu no Yaiba"
    views = {"Demon Slayer: Kimetsu no Yaiba": 50_000, "List of Demon Slayer: Kimetsu no Yaiba episodes": 9_000,
             "Lazarus": 80_000, "List of Lazarus episodes": 500}
    fetch = lambda name: [{"views": views[name]}] if name in views else []  # noqa: E731
    links = {"Demon Slayer: Kimetsu no Yaiba", "List of Demon Slayer: Kimetsu no Yaiba episodes", "List of Lazarus episodes"}
    related = lambda page, article: page in links  # noqa: E731
    assert launch_article("Demon Slayer: Kimetsu no Yaiba season 1", fetch, related)[0] == "Demon Slayer: Kimetsu no Yaiba"
    assert launch_article("Lazarus (Japanese TV series)", fetch, related) is None  # the Bible's Lazarus does not link to it; the list has too few views

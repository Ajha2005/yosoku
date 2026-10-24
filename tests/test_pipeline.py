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
    """Inputs at a moment must not change when data after its cutoff day changes, or is not there at all.

    Also for the in-between days of the decision clock. One title gets a Hindi article that only appears after
    the cutoff: whether such an article exists is not known at the forecast moment either.
    """
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    reddit = load_reddit(fake)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    late = titles.index[0]
    for moment in [*feat.MOMENTS, -50, -15, 2, 13]:
        cutoff = feat.stage(moment)[0]
        planted = wiki
        if cutoff is not None:
            row = wiki[wiki["anilist_id"] == late].iloc[[0]]
            planted = pd.concat([wiki[~((wiki["anilist_id"] == late) & wiki["lang"].isin(["hi", "ta", "te"]))],
                                 row.assign(lang="hi", days_from_start=cutoff + 1, views=50)])
        before = feat.build(titles, planted, comments, moment, genres, reddit)
        if cutoff is None:
            later = [(wiki.iloc[0:0], comments.iloc[0:0], reddit.iloc[0:0])]  # cold: no activity at all
        else:
            changed = (planted.assign(views=np.where(planted["days_from_start"] > cutoff, 10**7, planted["views"])),
                       pd.concat([comments, comments.assign(days_from_start=cutoff + 1, text="नमस्ते", india=1)]),
                       pd.concat([reddit, reddit.assign(days_from_start=cutoff + 1)]))
            removed = tuple(frame[frame["days_from_start"] <= cutoff] for frame in (planted, comments, reddit))
            later = [changed, removed]
        for later_wiki, later_comments, later_reddit in later:
            after = feat.build(titles, later_wiki, later_comments, moment, genres, later_reddit)
            if cutoff is None:
                assert list(before.columns) == list(after.columns)
            pd.testing.assert_frame_equal(before, after)
        if cutoff is not None:
            assert before.loc[late, "has_india_article"] == 0  # its Hindi article was written after the cutoff
            assert not any(c.startswith("has_youtube") for c in before.columns)  # chosen by today's popularity


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


def test_comment_counts_replace_the_text(fake, tmp_path):
    """Without the comment text, the daily counts merge.py keeps give the same dataset and the same model inputs."""
    import shutil
    titles = load_titles(fake)
    wiki, comments = load_daily(fake, titles)
    genres = sorted({g for gs in titles["genre_list"] for g in gs})
    copy = tmp_path / "no-text"
    shutil.copytree(fake, copy, ignore=shutil.ignore_patterns("youtube_comments.csv", "dataset.csv", "out", "upcoming"))
    subprocess.run([sys.executable, "collectors/merge.py", "--data-dir", str(copy)], cwd=ROOT, check=True)
    assert (copy / "dataset.csv").read_bytes() == (fake / "dataset.csv").read_bytes()
    _, counts = load_daily(copy, titles)
    assert "text" not in counts and len(counts) < len(comments)
    for moment in [*feat.MOMENTS, -15, 13]:
        pd.testing.assert_frame_equal(feat.build(titles, wiki, comments, moment, genres),
                                      feat.build(titles, wiki, counts, moment, genres))


def test_labels_do_not_move_when_titles_are_added():
    """With the ranking pool frozen, adding titles never changes an existing label; a new one is placed among the pool."""
    rng = np.random.default_rng(1)
    parts = pd.DataFrame({"youtube": rng.poisson(5, 40).astype(float), "streaming": rng.poisson(1, 40).astype(float),
                          "wikipedia": rng.lognormal(8, 1, 40)})
    before = index(percentiles(parts))
    new = pd.DataFrame({"youtube": [1000.0, 0.0], "streaming": [50.0, 0.0], "wikipedia": [1e9, 1.0]}, index=[100, 101])
    after = index(percentiles(pd.concat([parts, new]), reference=parts.index))
    pd.testing.assert_series_equal(before, after.loc[parts.index])  # nobody moved
    assert after.loc[100] == 100 and after.loc[101] < before.quantile(0.1)
    moved = index(percentiles(pd.concat([parts, new])))  # without the frozen pool, everyone shifts
    assert not np.allclose(before, moved.loc[parts.index])


def test_aired_upcoming_titles_are_labelled_on_the_frozen_scale():
    from yosoku.labels import build, placed
    start = pd.Timestamp("2024-01-10")
    ids = pd.Index([1, 2, 3, 4], name="anilist_id")
    titles = pd.DataFrame({"start": start, "yt_india_month1": [0, 2, 5, 9.0], "netflix_top10_weeks_90d": [0, 0, 1, 3.0],
                           "wiki_en_month1": [100, 900, 5000, 20000.0]}, index=ids)
    upcoming = pd.DataFrame({"start": [start, pd.Timestamp.today() + pd.Timedelta(days=30)], "yt_india_month1": [9.0, 1.0],
                             "netflix_top10_weeks_90d": [3.0, 0.0], "wiki_en_month1": [20000.0, 1.0]},
                            index=pd.Index([7, 8], name="anilist_id"))
    aired = placed(titles, upcoming, ids)
    assert list(aired.index) == [7]  # 8 has not had its 28 days yet
    assert aired.loc[7, "idi"] == pytest.approx(90)  # ties title 4 everywhere: as if it alone joined the pool, 4.5th of 5
    assert build(titles, ids)[0]["idi"].equals(build(titles)[0]["idi"])  # the pool itself is ranked as before


def test_test_titles_need_final(fake):
    titles = load_titles(fake)
    test_ids = titles.index[titles["start"].dt.year == 2025]
    with pytest.raises(SystemExit):
        guard_test(test_ids, titles, final=False)
    guard_test(test_ids, titles, final=True)


def test_end_to_end(fake):
    out = fake / "out"
    upcoming_dir = ["--upcoming-dir", str(fake / "upcoming")]
    for module, extra in (("yosoku.labels", upcoming_dir), ("yosoku.evaluate", []), ("yosoku.ablation", []), ("yosoku.clock", []),
                          ("yosoku.decision", [*upcoming_dir, "--mock", "--today", "2026-10-24"])):
        subprocess.run([sys.executable, "-m", module, "--data-dir", str(fake), "--out-dir", str(out), *extra],
                       cwd=ROOT, check=True)
    assert (out / "labels" / "reference_v1.csv").exists()  # the first run froze the ranking pool
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
        assert info["main"] == "Blend"  # at every stage, cold included
        # Titles not released yet get the range from every known season, the 2024 misses included (evaluate.live_width).
        live = payload["thresholds"][moment]["range_half_width_live"]
        assert all(t["forecasts"][moment]["high"] - t["forecasts"][moment]["index"] <= live + 0.11
                   for t in upcoming if moment in t["forecasts"])
    clock = payload["clock"]  # the decision clock: cold, then each day, the stages marked
    assert clock[0]["day"] == "cold" and [d["day"] for d in clock[1:]] == sorted(d["day"] for d in clock[1:])
    assert {d["stage"] for d in clock if d["stage"]} == {"cold", "t-28", "t+7"}
    assert all(d["nowcast"] == (d["day"] != "cold" and d["day"] >= 0) for d in clock)
    validation = [t for t in payload["titles"] if t["group"] == "validation"]
    assert all(len(t["trajectory"]) == len(clock) for t in validation)
    t28 = next(i for i, d in enumerate(clock) if d["stage"] == "t-28")
    if payload["thresholds"]["t-28"]["method"] == "Blend":  # the clock's T-28 day is the T-28 stage's forecast
        assert all(t["trajectory"][t28] == pytest.approx(t["forecasts"]["t-28"]["index"], abs=0.11) for t in validation)
    assert set(payload["window_evidence"]) == {"Festive season (Oct–Nov)", "Board exams (Feb–Mar)",
                                               "IPL cricket (Apr–May)", "Other months"}
    assert sum(w["n"] for w in payload["window_evidence"].values()) > 0
    for moment, result in payload["ablation"].items():  # what each signal is worth
        assert "All inputs" in result["variants"] and len(result["variants"]) > 2
        assert result["variants"]["All inputs"]["loss"] == 0
    sources = payload["sources"]  # the Method page's scorecard
    assert set(sources["parts"]) <= {"youtube", "streaming", "wikipedia"} and sources["released"] > 0
    for part in sources["parts"].values():
        assert part["pairs"] <= part["titles"] <= sources["released"]
    checks = payload["label_checks"]  # the Method page's index checks (gate G2)
    assert checks["passed"] == (checks["parts_agree"] and checks["ranking_holds"])
    assert checks["weakest_shift"] in sources["parts"]
    gross = [film["india_gross_inr"] for film in checks["box_office"]]
    assert gross == sorted(gross, reverse=True)
    for title in payload["titles"]:
        assert title["release_window"] in payload["window_evidence"]
        for forecast in title["forecasts"].values():
            dub = forecast["dub_demand"]
            assert (dub["share"] is None) == (dub["titles"] == 0)
            if forecast["regions"]:  # the map says how many comments it rests on
                assert forecast["region_comments"] is not None and forecast["region_comments"] >= 0


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


def test_dub_requests():
    from yosoku.data import classify
    text = pd.Series(["Hindi dub kab aayega", "please dub in tamil", "Tamil dubbed", "love from India",
                      "Now in Hindi Dub on Crunchyroll! https://bit.ly/x", "dubbed version when"])
    found = classify(text)
    assert found["dub_ask"].tolist() == [True, True, True, False, False, False]  # links are channels announcing, not fans asking
    assert (found["india"] | ~found["dub_ask"]).all()  # every dub request also counts as an Indian comment


def test_watch_and_dub_language_asks():
    from yosoku.data import classify
    text = pd.Series(["Hindi dub kab aayega", "please dub in tamil", "india me kab aayega bhai", "when is season 2 coming",
                      "Telugu dubbed version please", "india me kab aayega? Hindi dub here https://bit.ly/x"])
    found = classify(text)
    assert found["dub_hindi"].tolist() == [True, False, False, False, False, False]
    assert found["dub_tamil"].tolist() == [False, True, False, False, False, False]
    assert found["dub_telugu"].tolist() == [False, False, False, False, True, False]
    assert found["watch_ask"].tolist() == [True, False, True, False, False, False]  # Indian comments only, and no links


def test_daily_asks_keep_only_days_with_an_ask():
    from india_signals import daily_asks
    comments = pd.DataFrame({"anilist_id": [1, 1, 1, 2], "video_id": ["a", "a", "a", "b"],
                             "published_at": ["2026-01-01T10:00:00Z", "2026-01-01T12:00:00Z", "2026-01-02T10:00:00Z",
                                              "2026-01-01T10:00:00Z"],
                             "text": ["Hindi dub kab aayega", "tamil dub pls", "great trailer", "india me kab aayega"]})
    asks = daily_asks(comments)
    assert asks[["anilist_id", "date"]].values.tolist() == [[1, "2026-01-01"], [2, "2026-01-01"]]  # no ask on 2 Jan
    first = asks.iloc[0]
    assert (first["ask"], first["dub_ask"], first["dub_hindi"], first["dub_tamil"], first["watch_ask"]) == (2, 2, 1, 1, 1)


def test_live_range_comes_from_titles_with_a_youtube_part():
    from yosoku.evaluate import MIN_MISSES, live_width
    ids = pd.RangeIndex(100)
    misses = pd.Series(np.r_[np.full(50, 20.0), np.full(50, 2.0)], index=ids)
    youtube = pd.Series(ids >= 50, index=ids)  # the titles whose index includes YouTube missed by 2 points
    assert live_width(misses, youtube) == pytest.approx(2)
    assert live_width(misses, youtube & (ids < 50 + MIN_MISSES - 1)) == pytest.approx(20)  # too few of them: every miss counts


def test_sealed_stage_shows_the_sealed_numbers():
    from yosoku.decision import show_sealed
    today = {"index": 55.3, "low": 33.4, "high": 77.2, "verdict": "Test-market", "drivers": [],
             "lookalikes": [{"name": "A", "india_index": 50.0}], "reason_en": "", "reason_ja": ""}
    record = {"forecasts": {"cold": today}}
    show_sealed(record, {"date": "2026-10-24", "file": "f.json", "methods": {"cold": "Genre average"},
                         "lines": {"cold": {"launch_line": 60, "hold_line": 40}},
                         "forecasts": {"cold": {"index": 55.5, "low": 41.2, "high": 69.7, "verdict": "Test-market"},
                                       "t-28": {"index": 60.0, "low": 50.0, "high": 70.0, "verdict": "Test-market"}}})
    f = record["forecasts"]["cold"]
    assert (f["index"], f["low"], f["high"]) == (55.5, 41.2, 69.7) and f["now"]["low"] == 33.4
    assert f["sealed"] == {"date": "2026-10-24", "file": "f.json", "launch_line": 60, "hold_line": 40}
    assert "41–70" in f["reason_en"] and "Genre average" in f["reason_en"] and "ジャンル平均" in f["reason_ja"]
    assert set(record["forecasts"]) == {"cold"} and record["sealed"]["file"] == "f.json"  # a stage not reached stays unreached


def test_precedents_say_what_they_share():
    from yosoku.decision import common_ground
    titles = pd.DataFrame({"prequel_anilist_id": [np.nan, 1, np.nan], "genre_list": [["Action", "Drama"], ["Action"], ["Drama"]],
                           "tag_list": [["a", "b"], ["a"], ["c"]], "studio": ["MAPPA", "MAPPA", "Bones"],
                           "source": ["MANGA", "MANGA", "ORIGINAL"], "format": ["TV", "TV", "MOVIE"],
                           "demographic": ["Teens (boys)", "Teens (boys)", "Not tagged"]}, index=[1, 2, 3])
    assert common_ground(titles, 2, 1) == {"franchise": True, "genres": ["Action"], "studio": "MAPPA", "source": "MANGA",
                                           "format": "TV", "audience": "Teens (boys)", "tags": 1}
    other = common_ground(titles, 2, 3)
    assert other["franchise"] is False and other["genres"] == [] and other["studio"] is None and other["audience"] is None


def test_alerts_judge_a_sealed_verdict_on_its_own_lines():
    from yosoku.daily import alerts
    predictions = {"thresholds": {"cold": {"launch_line": 60, "hold_line": 40}},
                   "titles": [{"anilist_id": 1, "group": "upcoming", "forecasts": {"cold": {
                       "index": 50, "low": 40, "high": 60, "verdict": "Test-market",
                       "sealed": {"date": "2026-10-24", "file": "f.json", "launch_line": 70, "hold_line": 40}}}}]}
    today = pd.DataFrame([{"anilist_id": 1, "name": "A", "day": 3, "index": 66.0, "low": 62.0, "high": 70.0}])
    # 62 clears today's launch line (60) but not the sealed one (70): only the range alert.
    assert [a["text"] for a in alerts(today, predictions)] == [
        "Forecast 66, above the 40–60 range of its sealed Cold verdict (Test-market)."]


def test_wikipedia_disambiguation_is_not_related(monkeypatch):
    """A disambiguation page links to the show's article, but is not about the show."""
    sys.path.insert(0, str(ROOT / "collectors"))
    import collect_wikipedia

    def page(pageprops):
        return lambda *args, **kwargs: {"query": {"pages": [{"title": "Lazarus", "pageprops": pageprops,
                                                             "links": [{"title": "Lazarus (Japanese TV series)"}]}]}}

    monkeypatch.setattr(collect_wikipedia, "request_json", page({"disambiguation": ""}))
    assert not collect_wikipedia.links_to("Lazarus", "Lazarus (Japanese TV series)")
    monkeypatch.setattr(collect_wikipedia, "request_json", page({}))
    assert collect_wikipedia.links_to("Lazarus", "Lazarus (Japanese TV series)")


def test_seal(fake, tmp_path):
    """A seal records a fingerprint, can be verified, is never rewritten, and catches a changed file."""
    import shutil
    out = tmp_path / "out"
    shutil.copytree(fake / "out", out)  # test_end_to_end wrote predictions.json there, upcoming titles included
    predictions = out / "predictions" / "predictions.json"
    payload = json.loads(predictions.read_text(encoding="utf-8"))
    predictions.write_text(json.dumps({**payload, "mock": False}), encoding="utf-8")  # the seal refuses mock data
    run = lambda *extra: subprocess.run([sys.executable, "-m", "yosoku.seal", "--out-dir", str(out), "--today", "2026-10-24", *extra],
                                        cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    assert run().returncode == 0
    from yosoku.seal import sealed_forecasts  # what the site shows for each sealed title
    assert set(sealed_forecasts(out)) == {t["anilist_id"] for t in payload["titles"] if t["group"] == "upcoming"}
    sealed = list((out / "predictions" / "sealed").glob("2026-10-24-*.json"))
    assert len(sealed) == 1
    assert json.loads(sealed[0].read_text(encoding="utf-8"))["titles"]
    assert run("--verify").returncode == 0
    assert run().returncode != 0  # the same day again: never rewritten
    sealed[0].write_bytes(sealed[0].read_bytes().replace(b'"index":', b'"index": '))
    assert run("--verify").returncode != 0
    assert sealed_forecasts(out) == {}  # a file that no longer matches its fingerprint is never shown


def test_daily_job(fake, tmp_path):
    """The daily job forecasts only the titles still in play, logs one row per title per day, and publishes the log."""
    import shutil
    from yosoku.clock import DAYS
    out = tmp_path / "out"
    shutil.copytree(fake / "out", out)  # test_end_to_end's full run: clock.json, predictions.json, the frozen pool

    def run(today, *extra):
        subprocess.run([sys.executable, "-m", "yosoku.daily", "--data-dir", str(fake), "--out-dir", str(out), "--upcoming-dir",
                        str(fake / "upcoming"), "--no-collect", "--today", today, *extra], cwd=ROOT, check=True)
        return pd.read_csv(out / "predictions" / "history.csv", encoding="utf-8-sig", dtype={"day": str})

    upcoming = load_titles(fake / "upcoming")  # Winter 2027: all in play in January
    history = run("2027-01-20", "--no-publish")
    assert len(history) == len(upcoming) and (history["low"] <= history["index"]).all() and (history["index"] <= history["high"]).all()
    expected = ((pd.Timestamp("2027-01-20") - upcoming["start"]).dt.days.clip(upper=DAYS[-1])
                .map(lambda d: "cold" if d < DAYS[0] else str(d)))
    assert history.set_index("anilist_id")["day"].to_dict() == expected.to_dict()
    assert len(run("2027-01-20", "--no-publish")) == len(upcoming)  # twice on one day: the later run replaces the earlier
    assert len(run("2027-01-21")) == 2 * len(upcoming)
    assert (out / "reports" / "alerts.md").read_text(encoding="utf-8").startswith("# Alerts, 2027-01-21")
    status = json.loads((out / "predictions" / "alerts.json").read_text(encoding="utf-8"))  # what the site shows
    assert status["date"] == "2027-01-21" and status["in_play"] == len(upcoming) and 0 <= status["before_buzz"] <= len(upcoming)
    assert all({"anilist_id", "name", "day", "text"} <= set(a) and a["day"] != "cold" for a in status["alerts"])
    payload = json.loads((out / "predictions" / "predictions.json").read_text(encoding="utf-8"))
    for title in (t for t in payload["titles"] if t["group"] == "upcoming"):
        assert title["history"][-1]["date"] == "2027-01-21"  # the log reaches the forecast sheet
        assert len({str(h["day"]) for h in title["history"]}) == len(title["history"])  # one point per clock day
    assert len(run("2027-06-01", "--no-publish")) == 2 * len(upcoming)  # past day 90 nothing is in play

"""Run with: python -m pytest tests/test_export_web.py   (no network needed)"""

import json

import pytest

from yosoku import export_web
from yosoku.data import ROOT

MOCK = ROOT / "app" / "mock_predictions.json"


def media(cover="https://img.example/c.jpg", color="#e4ae50", banner=None):
    return {"id": 7, "coverImage": {"extraLarge": cover, "color": color}, "bannerImage": banner}


def test_referenced_ids_cover_titles_and_their_lookalikes():
    predictions = json.loads(MOCK.read_text(encoding="utf-8"))
    ids = export_web.referenced_ids(predictions)
    assert ids == sorted(set(ids))
    assert {t["anilist_id"] for t in predictions["titles"]} <= set(ids)
    lookalikes = {look["anilist_id"] for t in predictions["titles"] for f in t["forecasts"].values() for look in f["lookalikes"]}
    assert lookalikes <= set(ids)


def test_cover_entry_keeps_banner_only_when_there_is_one():
    assert export_web.cover_entry(media()) == {"c": "https://img.example/c.jpg", "k": "#e4ae50"}
    assert export_web.cover_entry(media(banner="https://img.example/b.jpg"))["b"] == "https://img.example/b.jpg"
    assert export_web.cover_entry(media(color=None))["k"] == ""


def test_fetch_covers_batches_and_skips_titles_without_a_cover(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        ids = kwargs["json"]["variables"]["ids"]
        calls.append(ids)
        return {"data": {"Page": {"media": [{"id": i, "coverImage": {"extraLarge": None if i == 2 else f"https://img.example/{i}.jpg", "color": None}, "bannerImage": None}
                                          for i in ids]}}}

    monkeypatch.setattr(export_web, "request_json", fake_request)
    covers = export_web.fetch_covers(list(range(1, 121)), pause=0)
    assert [len(c) for c in calls] == [50, 50, 20]
    assert "2" not in covers and covers["3"]["c"] == "https://img.example/3.jpg" and len(covers) == 119


def test_mock_forecasts_never_fetch_covers(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("mock ids collide with real AniList ids, so no lookup is allowed")

    monkeypatch.setattr(export_web, "request_json", forbidden)
    monkeypatch.setattr("sys.argv", ["export_web", "--predictions", "does/not/exist.json", "--out-dir", str(tmp_path)])
    export_web.main()
    written = json.loads((tmp_path / "predictions.json").read_text(encoding="utf-8"))
    assert written["mock"] is True and written["titles"]
    assert json.loads((tmp_path / "covers.json").read_text(encoding="utf-8")) == {}


def test_real_forecasts_get_covers(tmp_path, monkeypatch):
    predictions = json.loads(MOCK.read_text(encoding="utf-8"))
    predictions["mock"] = False
    source = tmp_path / "predictions.json"
    source.write_text(json.dumps(predictions), encoding="utf-8")
    out = tmp_path / "web"
    monkeypatch.setattr(export_web, "fetch_covers", lambda ids: {str(i): {"c": f"https://img.example/{i}.jpg", "k": ""} for i in ids[:3]})
    monkeypatch.setattr("sys.argv", ["export_web", "--predictions", str(source), "--out-dir", str(out)])
    # --predictions is resolved against the repo root; an absolute path replaces it.
    export_web.main()
    assert len(json.loads((out / "covers.json").read_text(encoding="utf-8"))) == 3

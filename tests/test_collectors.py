"""Run with: python -m pytest tests/test_collectors.py   (no network: a fake YouTube answers)"""

import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from yosoku.data import ROOT

sys.path.insert(0, str(ROOT / "collectors"))
import collect_youtube  # noqa: E402
import common  # noqa: E402


def thread(comment_id):
    return {"id": comment_id, "snippet": {"totalReplyCount": 0, "topLevelComment": {"snippet": {
        "publishedAt": "2027-01-10T12:00:00Z", "likeCount": 0, "textDisplay": comment_id}}}}


class FakeYouTube:
    """Answers like the YouTube Data API from pages the test sets, and counts the quota units spent."""

    def __init__(self):
        self.units_used, self.pages, self.results, self.calls = 0, {}, {}, []

    def get(self, endpoint, cost, **params):
        self.units_used += cost
        self.calls.append(endpoint)
        if endpoint == "commentThreads":
            pages, page = self.pages[params["videoId"]], int(params.get("pageToken", 0))
            more = {"nextPageToken": str(page + 1)} if page + 1 < len(pages) else {}
            return {"items": [thread(c) for c in pages[page]], **more}
        if endpoint == "search":
            return {"items": [{"id": {"videoId": v}} for v in self.results[params["q"]]]}
        if endpoint == "videos":
            return {"items": [{"id": v, "snippet": {"title": v}, "statistics": {"viewCount": "100"}} for v in params["id"].split(",")]}
        raise AssertionError(f"unexpected call to {endpoint}")


def cached_ids(video_id):
    return [c["comment_id"] for c in collect_youtube.load_json(collect_youtube.comments_path(video_id))]


def test_refresh_adds_only_the_new_comments(tmp_path, monkeypatch):
    """A daily refresh reads newest first and stops at the newest comment it already has."""
    monkeypatch.setattr(collect_youtube, "CACHE", tmp_path)
    youtube = FakeYouTube()
    youtube.pages["v1"] = [["c3", "c2", "c1"]]
    assert collect_youtube.refresh_comments(youtube, "v1", 10) == 3
    youtube.pages["v1"] = [["c8", "c7"], ["c6", "c5"], ["c4", "c3"], ["c2", "c1"]]
    youtube.units_used = 0
    assert collect_youtube.refresh_comments(youtube, "v1", 10) == 5
    assert youtube.units_used == 3  # the page holding c3 is the last one read
    assert cached_ids("v1") == ["c8", "c7", "c6", "c5", "c4", "c3", "c2", "c1"]
    youtube.pages["v1"] = [["c8", "c7"]]
    assert collect_youtube.refresh_comments(youtube, "v1", 10) == 0  # nothing new: one page, nothing written twice
    assert cached_ids("v1") == ["c8", "c7", "c6", "c5", "c4", "c3", "c2", "c1"]
    youtube.pages["v1"] = [["c1", "c10", "c9"], ["c8", "c7"]]  # an old comment out of order at the top, e.g. pinned
    assert collect_youtube.refresh_comments(youtube, "v1", 10) == 2
    assert cached_ids("v1")[:3] == ["c10", "c9", "c8"]


def test_titles_in_play_are_searched_again_weekly(tmp_path, monkeypatch):
    monkeypatch.setattr(collect_youtube, "CACHE", tmp_path)
    youtube = FakeYouTube()
    title = {"anilist_id": "7", "title_english": "Show", "title_romaji": "", "start_date": "2027-01-10"}
    args = SimpleNamespace(search_every=7, videos_per_query=3)
    query, start = "Show official trailer", date(2027, 1, 10)
    search = lambda today: collect_youtube.refresh_search(youtube, title, "trailer", query, start, args, today)  # noqa: E731
    youtube.results[query] = ["v1"]
    assert search(date(2026, 12, 1)) == ["v1"]
    stamp = datetime(2026, 12, 1, 12).timestamp()
    os.utime(collect_youtube.search_path(title, "trailer"), (stamp, stamp))  # searched on 1 December
    youtube.results[query] = ["v2", "v1"]  # a second trailer is out
    assert search(date(2026, 12, 5)) == ["v1"]  # four days later: the cached search
    assert search(date(2026, 12, 8)) == ["v1", "v2"]  # a week later: searched again, the new video after the old
    assert youtube.calls.count("search") == 2


def test_refresh_leaves_finished_titles_alone(tmp_path, monkeypatch):
    """With --refresh, a title past its last window is read from the cache: no quota is spent on it."""
    monkeypatch.setattr(collect_youtube, "CACHE", tmp_path)
    youtube = FakeYouTube()
    today = date.today()  # the search cache is dated by the clock, so the test runs on today's date
    old = {"anilist_id": "1", "title_english": "Old", "title_romaji": "", "start_date": (today - timedelta(days=200)).isoformat()}
    new = {"anilist_id": "2", "title_english": "New", "title_romaji": "", "start_date": (today + timedelta(days=60)).isoformat()}
    args = SimpleNamespace(budget=9000, hindi=False, refresh=True, search_every=7, videos_per_query=3, comment_pages=10)
    youtube.results = {"Old official trailer": ["v-old"], "New official trailer": ["v-new"]}
    youtube.pages = {"v-old": [["a2", "a1"]], "v-new": [["b1"]]}
    assert collect_youtube.collect(youtube, [old, new], args, today)
    spent = youtube.units_used
    youtube.pages = {"v-old": [["a3", "a2", "a1"]], "v-new": [["b2", "b1"]]}
    assert collect_youtube.collect(youtube, [old, new], args, today)
    assert youtube.units_used - spent == 1  # one comment page for the title in play; nothing for the finished one
    assert cached_ids("v-old") == ["a2", "a1"] and cached_ids("v-new") == ["b2", "b1"]


def test_view_counts_are_logged_once_a_day_and_kept_30_days(tmp_path, monkeypatch):
    monkeypatch.setattr(collect_youtube, "CACHE", tmp_path / "raw")
    monkeypatch.setattr(common, "_data_dir", tmp_path)
    youtube = FakeYouTube()
    log = lambda day: collect_youtube.append_stats(collect_youtube.log_stats(youtube, ["v1", "v2"], day), day)  # noqa: E731
    for day in (date(2026, 12, 1), date(2026, 12, 1), date(2026, 12, 2)):
        log(day)
    rows = lambda: [(r["video_id"], r["collected_on"]) for r in common.read_csv(tmp_path / collect_youtube.STATS_CSV)]  # noqa: E731
    assert rows() == [("v1", "2026-12-01"), ("v2", "2026-12-01"), ("v1", "2026-12-02"), ("v2", "2026-12-02")]
    assert youtube.units_used == 3  # one call per day for both videos
    log(date(2026, 12, 31))  # 30 days after 1 December: that day's counts are dropped (YouTube's API policies)
    assert rows() == [("v1", "2026-12-02"), ("v2", "2026-12-02"), ("v1", "2026-12-31"), ("v2", "2026-12-31")]


def test_titles_are_active_until_their_last_window_closes():
    today = date(2026, 10, 24)
    assert common.is_active(None, today)  # start date not announced
    assert common.is_active(date(2027, 1, 10), today)
    assert common.is_active(date(2026, 7, 26), today)  # day 90: Netflix weeks still counting
    assert not common.is_active(date(2026, 7, 25), today)


def test_title_list_refresh_keeps_titles_that_slipped(tmp_path, monkeypatch):
    """--keep: a refresh updates the titles it finds and keeps the ones that fell out of the top of their season."""
    import collect_titles
    monkeypatch.setattr(collect_titles, "PAUSE_SECONDS", 0)
    monkeypatch.setattr(common, "_data_dir", tmp_path)  # main() points the collectors at --data-dir; undone after the test
    media = lambda anilist_id, day: {  # noqa: E731
        "id": anilist_id, "idMal": None, "title": {"romaji": f"Show {anilist_id}", "english": None, "native": None},
        "synonyms": [], "format": "TV", "episodes": 12, "source": "MANGA", "genres": ["Action"], "tags": [],
        "description": "", "startDate": {"year": 2027, "month": 1, "day": day}, "studios": {"nodes": []},
        "popularity": 100, "averageScore": None, "externalLinks": [], "relations": {"edges": []}}
    page = {"data": {"Page": {"pageInfo": {"hasNextPage": False}, "media": [media(1, 10)]}}}
    monkeypatch.setattr(collect_titles, "request_json", lambda *args, **kwargs: page)
    common.write_csv(tmp_path / "titles.csv", [collect_titles.to_row(media(1, None), "WINTER", 2027),
                                               collect_titles.to_row(media(2, 5), "WINTER", 2027)], collect_titles.FIELDS)
    args = ["collect_titles.py", "--data-dir", str(tmp_path), "--start-year", "2027", "--end-year", "2027", "--seasons", "WINTER"]
    monkeypatch.setattr(sys, "argv", [*args, "--keep"])
    collect_titles.main()
    rows = {r["anilist_id"]: r for r in common.read_csv(tmp_path / "titles.csv")}
    assert set(rows) == {"1", "2"} and rows["1"]["start_date"] == "2027-01-10"  # its start date was announced
    monkeypatch.setattr(sys, "argv", args)
    collect_titles.main()
    assert [r["anilist_id"] for r in common.read_csv(tmp_path / "titles.csv")] == ["1"]  # without --keep, the list is replaced


def test_daily_job_labels_new_comments_with_indiclid(tmp_path, monkeypatch, capsys):
    """IndicLID runs between the YouTube refresh and the merge when fastText is installed; without it the daily job
    says what is missing and carries on."""
    from yosoku import daily
    common.write_csv(tmp_path / "titles.csv", [{"anilist_id": 1, "season": "WINTER", "year": 2027}], ["anilist_id", "season", "year"])
    calls = []

    def fake_run(script, *args, check=True):
        calls.append(script.rsplit("/", 1)[1])
        if script.endswith("collect_youtube.py"):  # the refresh writes the comments
            (tmp_path / "youtube_comments.csv").write_text("comment_id,text\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(daily, "run", fake_run)
    monkeypatch.setenv("YOUTUBE_API_KEY", "not-a-real-key")
    for installed in (True, False):
        monkeypatch.setattr(daily, "has_fasttext", lambda installed=installed: installed)
        calls.clear()
        daily.collect(tmp_path, pd.Timestamp("2027-01-20"))
        assert calls == ["collect_titles.py", "collect_wikipedia.py", "collect_netflix.py", "collect_youtube.py",
                         *(["detect_languages.py"] if installed else []), "merge.py"]
    assert "pip install fasttext" in capsys.readouterr().out


def test_country_charts_match_strictly(tmp_path, monkeypatch):
    """Abroad, a film row matches only an anime film by its exact name, a TV row only a series, within 180 days."""
    import collect_netflix
    titles = [{"anilist_id": "1", "title_english": "The Boy and the Heron", "title_romaji": "Kimitachi wa Dou Ikiru ka",
               "synonyms": "", "start_date": "2023-07-14", "format": "MOVIE"},
              {"anilist_id": "2", "title_english": "Jujutsu Kaisen Season 2", "title_romaji": "Jujutsu Kaisen 2nd Season",
               "synonyms": "", "start_date": "2023-07-06", "format": "TV"}]

    def row(show, category, week):
        return {"country_name": "Philippines", "country_iso2": "PH", "week": week, "category": category, "weekly_rank": "3",
                "show_title": show, "season_title": "N/A", "cumulative_weeks_in_top_10": "1"}

    rows = [row("The Boy", "Films", "2023-08-06"),  # another film: films match by their exact name only
            row("The Boy and the Heron", "Films", "2023-08-06"),
            row("Jujutsu Kaisen", "TV", "2023-07-16"),  # a series, by the start of its name
            row("Jujutsu Kaisen", "Films", "2023-07-16"),  # a film row never matches a series
            row("Jujutsu Kaisen", "TV", "2024-06-30")]  # past 180 days
    monkeypatch.setattr(collect_netflix, "data_file", lambda name: tmp_path / name)  # no exclusions file
    found = collect_netflix.country_matches(rows, titles)
    assert [(m["anilist_id"], m["show_title"], m["category"]) for m in found] == [
        ("1", "The Boy and the Heron", "Films"), ("2", "Jujutsu Kaisen", "TV")]

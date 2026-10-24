"""Where else a title could travel: Netflix's weekly Top 10 in every country where anime has charted.

data/netflix_countries.csv (collectors/collect_netflix.py) holds the weeks each past title spent in each country's
Top 10 within 180 days of its Japanese start. For a title being forecast, this takes the 10 most similar past titles
that charted somewhere (the lookalike's similarity: genres, tags, source, format, studio, audience, synopsis), all
started before it, and gives each country the similarity-weighted share of them that charted there, beside the
share of all those past titles that did (typical), Japan left out. It answers: if this title reaches Netflix, where
else is it likeliest to chart?

Counted, not modelled, and Netflix only: a title must be on Netflix to chart, and the Top 10 hides the rest. check()
backtests it the same way, past titles only: per country, does the share rank the titles that charted there above
the ones that did not (AUC, 0.5 is chance), against the share among titles of the same main genre?
"""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from yosoku.data import read
from yosoku.models import Lookalike

NEIGHBOURS = 10
HOME = "JP"  # where every title starts: never "elsewhere", so left out of the lists and their check
SHOWN = 6  # countries listed per title, India added if it is not among them
MIN_POOL = 20  # past titles that charted somewhere, needed before a title gets a list
MIN_CHECKED = 10  # a country enters the check with this many titles that charted there, and that did not


def charted(data_dir):
    """({anilist_id: set of country codes}, {code: country name}) from netflix_countries.csv; empty if not collected."""
    rows = read(data_dir / "netflix_countries.csv", required=False)
    if rows is None or rows.empty:
        return {}, {}
    reach = rows.groupby("anilist_id")["country_iso2"].apply(set).to_dict()
    return reach, rows.drop_duplicates("country_iso2").set_index("country_iso2")["country_name"].to_dict()


def neighbours(titles, reach, target_ids):
    """{target: [(past title, similarity)]}: the most similar titles that charted somewhere and started before it."""
    pool = pd.Index(sorted(reach)).intersection(titles.index)
    look = Lookalike().fit(titles, pd.Series(0.0, index=pool))
    sims = look.similarities(titles.loc[target_ids])
    starts = titles.loc[pool, "start"].to_numpy()
    found = {}
    for row, target in enumerate(target_ids):
        start = titles.at[target, "start"]
        past = (starts < start) if pd.notna(start) else np.ones(len(pool), bool)
        past &= np.asarray(pool != target)
        if past.sum() < MIN_POOL:
            continue
        order = [j for j in np.argsort(-sims[row]) if past[j] and sims[row, j] > 0][:NEIGHBOURS]
        found[target] = ([(pool[j], float(sims[row, j])) for j in order], pool[past])
    return found


def travel(titles, reach, names, target_ids):
    """{anilist_id: {"of": neighbours used, "countries": [{iso2, name, share, titles, typical}]}}, most likely first."""
    out = {}
    for target, (near, past) in neighbours(titles, reach, list(target_ids)).items():
        if not near:
            continue
        weight = sum(s for _, s in near)
        countries = ({c for i, _ in near for c in reach[i]} | {"IN"}) - {HOME}
        rows = [{"iso2": c, "name": names.get(c, c),
                 "share": round(sum(s for i, s in near if c in reach[i]) / weight, 3),
                 "titles": sum(c in reach[i] for i, _ in near),
                 "typical": round(float(np.mean([c in reach[i] for i in past])), 3)} for c in countries]
        rows.sort(key=lambda r: (-r["share"], -r["typical"], r["iso2"]))  # the code last, so ties never reorder
        shown = rows[:SHOWN] + [r for r in rows[SHOWN:] if r["iso2"] == "IN"]
        out[int(target)] = {"of": len(near), "countries": shown}
    return out


def check(titles, reach):
    """How well the shares pick where a title charts, on past titles only: mean AUC over the countries with enough
    titles, against the same share among titles of the same main genre."""
    ids = [i for i in sorted(reach) if i in titles.index]
    near = neighbours(titles, reach, ids)
    genre = titles["main_genre"]
    rows = []
    for target, (close, past) in near.items():
        if not close:
            continue
        weight = sum(s for _, s in close)
        same = [i for i in past if genre[i] == genre[target]] or list(past)
        for c in {c for i in past for c in reach[i]} - {HOME}:
            rows.append((c, c in reach[target], sum(s for i, s in close if c in reach[i]) / weight,
                         np.mean([c in reach[i] for i in same])))
    frame = pd.DataFrame(rows, columns=["country", "hit", "similar", "genre"])
    scores = [(roc_auc_score(g["hit"], g["similar"]), roc_auc_score(g["hit"], g["genre"]))
              for _, g in frame.groupby("country") if g["hit"].sum() >= MIN_CHECKED and (~g["hit"]).sum() >= MIN_CHECKED]
    if not scores:
        return {"countries_checked": 0, "auc": None, "genre_auc": None}
    similar, by_genre = np.mean(scores, axis=0)
    return {"countries_checked": len(scores), "auc": round(float(similar), 2), "genre_auc": round(float(by_genre), 2)}


def summary(titles, reach, names):
    """The world view for the site: how many titles reached each country's Top 10, and India's place."""
    counts = pd.Series([c for i in reach for c in reach[i]]).value_counts()
    counts = counts.loc[sorted(counts.index, key=lambda c: (-counts[c], c))]  # ties by code, the same every run
    return {"titles": len(reach), "countries": len(counts), **check(titles, reach),
            "india_rank": int((counts > counts["IN"]).sum()) + 1 if "IN" in counts else None,  # ties share a place
            "india_tied": int((counts == counts["IN"]).sum()) - 1 if "IN" in counts else 0,
            "by_country": [{"iso2": c, "name": names.get(c, c), "titles": int(n)} for c, n in counts.items()]}

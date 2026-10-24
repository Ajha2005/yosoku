"""Phase 4: the lookalike model, the blend, the baselines, 80% ranges and the regional profile.

With a few hundred labelled titles, simple models that hold up beat clever ones that overfit:

  Lookalike  the 10 most similar past titles by genres, tags, source, format, studio, audience and
             synopsis words; the forecast is their India index, weighted by similarity.
  Blend      ridge regression on the moment's features plus the lookalike forecast and the prequel's
             index. Its drivers are exact: coefficient x standardised value.
  Ranges     split conformal: the 80th percentile of out-of-sample errors from the rolling seasons.
"""

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, normalize

from yosoku.data import HUBS
from yosoku.features import prequel_label, signal

K = 10
SYNOPSIS_WEIGHT = 0.5  # synopsis words count half as much as the hand-curated genres and tags
COVERAGE = 0.80


def meta_tokens(titles):
    tokens = []
    for row in titles.itertuples():
        found = [f"genre:{g}" for g in row.genre_list] + [f"tag:{t}" for t in row.tag_list]
        found += [f"source:{row.source}", f"format:{row.format}", f"audience:{row.demographic}"]
        found += [f"studio:{s}" for s in str(row.studio).split("|") if s and s != "nan"]
        tokens.append(found)
    return tokens


def region_profiles(titles):
    """Share of each language hub among a title's hub-pointing trailer comments (rows sum to 1, or NaN)."""
    columns = [f"yt_share_{hub}" for hub in HUBS]
    if not set(columns) <= set(titles.columns):
        return pd.DataFrame(np.nan, index=titles.index, columns=list(HUBS))
    shares = titles[columns].set_axis(list(HUBS), axis=1)
    total = shares.sum(axis=1)
    return shares.div(total.where(total > 0), axis=0)


class Lookalike:
    def fit(self, titles, labels):
        self.train = titles.loc[labels.index]
        self.labels = labels
        self.meta = TfidfVectorizer(analyzer=lambda tokens: tokens)
        self.words = TfidfVectorizer(stop_words="english", max_features=5000, min_df=2)
        synopsis = self.train["synopsis"].fillna("") if "synopsis" in self.train else pd.Series("", index=self.train.index)
        self.use_words = synopsis.str.len().sum() > 0
        if self.use_words:
            self.words.fit(synopsis)
        self.matrix = self._vectors(self.train, fit=True)
        self.regions = region_profiles(self.train)
        return self

    def _vectors(self, titles, fit=False):
        meta = (self.meta.fit_transform if fit else self.meta.transform)(meta_tokens(titles))
        parts = [meta]
        if self.use_words:
            synopsis = titles["synopsis"].fillna("") if "synopsis" in titles else pd.Series("", index=titles.index)
            parts.append(SYNOPSIS_WEIGHT * self.words.transform(synopsis))
        return normalize(hstack(parts).tocsr())

    def predict(self, titles):
        """DataFrame: forecast, lookalikes [(anilist_id, similarity)], and the regional profile."""
        sims = (self._vectors(titles) @ self.matrix.T).toarray()
        train_ids = np.asarray(self.labels.index)
        rows = []
        for i, anilist_id in enumerate(titles.index):
            sim = sims[i].copy()
            sim[train_ids == anilist_id] = -1  # never your own lookalike
            top = [j for j in np.argsort(-sim)[:K] if sim[j] > 0]
            if not top:
                rows.append({"forecast": self.labels.mean(), "lookalikes": [], "region": {}})
                continue
            weights = sim[top]
            forecast = float(np.average(self.labels.iloc[top], weights=weights))
            profiles = self.regions.iloc[top]
            has = profiles.notna().all(axis=1).to_numpy()
            region = {}
            if has.any():
                mix = np.average(profiles[has].to_numpy(), axis=0, weights=weights[has])
                region = {HUBS[hub][0]: round(float(v), 3) for hub, v in zip(HUBS, mix)}
                region["_titles"] = int(has.sum())
            rows.append({"forecast": forecast,
                         "lookalikes": [(int(train_ids[j]), round(float(sim[j]), 3)) for j in top],
                         "region": region})
        return pd.DataFrame(rows, index=titles.index)


class Blend:
    """Ridge regression on standardised features; keeps the columns it was fitted on."""

    def fit(self, X, y):
        self.columns = [c for c in X.columns if X[c].std() > 0]
        self.model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3, 25)))
        self.model.fit(X[self.columns], y)
        return self

    def predict(self, X):
        return pd.Series(np.clip(self.model.predict(X[self.columns]), 0, 100), index=X.index)

    def drivers(self, X, top=3):
        """{anilist_id: [(signal, points)]}: the largest contributions against an average title, per business signal."""
        scaler, ridge = self.model.named_steps["standardscaler"], self.model.named_steps["ridgecv"]
        contributions = pd.DataFrame(scaler.transform(X[self.columns]) * ridge.coef_, index=X.index, columns=self.columns)
        grouped = contributions.T.groupby([signal(c) for c in self.columns]).sum().T
        out = {}
        for anilist_id, row in grouped.iterrows():
            biggest = row.reindex(row.abs().sort_values(ascending=False).index)[:top]
            out[anilist_id] = [(name, round(float(points), 1)) for name, points in biggest.items() if abs(points) >= 0.5]
        return out


def stacked_inputs(features, titles, labels, train_ids, target_ids):
    """Add the lookalike forecast and prequel index to the features. Training rows get leave-one-out lookalikes."""
    look = Lookalike().fit(titles, labels.loc[train_ids])
    train_look, target_look = look.predict(titles.loc[train_ids]), look.predict(titles.loc[target_ids])
    prequel = prequel_label(titles, labels)
    mean = labels.loc[train_ids].mean()

    fill = features.loc[train_ids].mean()  # blank inputs (e.g. not searched on YouTube) count as an average title

    def add(ids, lookalike):
        X = features.loc[ids].fillna(fill).fillna(0)
        X["lookalike"] = lookalike["forecast"]
        X["has_prequel_label"] = prequel.loc[ids].notna().astype(int)
        X["prequel_label"] = prequel.loc[ids].fillna(mean)
        return X

    return add(train_ids, train_look), add(target_ids, target_look), target_look


def forecast(moment, features, titles, labels, train_ids, target_ids):
    """Point forecasts for target_ids from a model trained on train_ids, with lookalikes, drivers and region."""
    X_train, X_target, look = stacked_inputs(features, titles, labels, train_ids, target_ids)
    out = look.copy()
    out["lookalike"] = look["forecast"]
    if moment == "cold":
        out["drivers"] = [[] for _ in range(len(out))]
        return out
    blend = Blend().fit(X_train, labels.loc[train_ids])
    out["forecast"] = blend.predict(X_target)
    drivers = blend.drivers(X_target)
    out["drivers"] = [drivers[i] for i in out.index]
    return out


def baselines(moment, features, titles, labels, train_ids, target_ids):
    """{name: Series of forecasts} for the simple rules a model must beat."""
    train = labels.loc[train_ids]
    genre_mean = train.groupby(titles.loc[train_ids, "main_genre"]).mean()
    genre = titles.loc[target_ids, "main_genre"].map(genre_mean).fillna(train.mean())
    out = {"Genre average": genre}
    prequel = prequel_label(titles, labels).loc[target_ids]
    out["Sequel carry-over"] = prequel.fillna(genre)
    window = {"t-28": "early", "t+7": "launch"}.get(moment)
    if window:
        for name, columns in (("Global buzz (en+ja Wikipedia)", [f"wiki_en_{window}", f"wiki_ja_{window}"]),
                              ("India Wikipedia alone", [f"wiki_india_{window}"]),
                              ("India YouTube alone", [f"yt_india_{window}"])):
            if set(columns) <= set(features.columns):
                x = features[columns].sum(axis=1, min_count=len(columns))
                x = x.fillna(x.loc[train_ids].mean())
                slope, intercept = np.polyfit(x.loc[train_ids], train, 1) if x.loc[train_ids].std() > 0 else (0, train.mean())
                out[name] = (intercept + slope * x.loc[target_ids]).clip(0, 100)
    return out


def conformal_width(errors):
    """Half-width of an 80% range from absolute out-of-sample errors."""
    errors = np.abs(np.asarray(errors, dtype=float))
    errors = errors[~np.isnan(errors)]
    if len(errors) == 0:
        return np.nan
    n = len(errors)
    return float(np.quantile(errors, min(1.0, np.ceil((n + 1) * COVERAGE) / n)))

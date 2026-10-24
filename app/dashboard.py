"""Yosoku executive dashboard: India launch verdicts for Japanese anime, with the evidence behind them.

    streamlit run app/dashboard.py

Reads predictions/predictions.json (written by `python -m yosoku.decision`). Until that exists it
shows app/mock_predictions.json, made from fake data, with a banner saying so. Everything is
precomputed: the dashboard never calls an outside service, so it runs offline.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
REAL, MOCK = ROOT / "predictions" / "predictions.json", ROOT / "app" / "mock_predictions.json"

# Colours (light mode): status colours for verdicts, always shown with an icon and a label;
# blue/red as the diverging pair for drivers; muted ink for chrome.
VERDICT_STYLE = {"Launch": ("#0ca30c", "✅"), "Test-market": ("#fab219", "⚠️"), "Hold": ("#d03b3b", "⛔")}
UP, DOWN, SERIES = "#2a78d6", "#e34948", "#2a78d6"
INK, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
MOMENT_NAMES = {"cold": "Cold: before any buzz (metadata only)", "t-28": "T−28: four weeks before launch",
                "t+7": "T+7: after launch week"}
GROUP_NAMES = {"upcoming": "Upcoming (not released yet)", "validation": "Backtest: 2024 titles", "test": "Final test: 2025 titles"}

SOURCES = pd.DataFrame([
    ["YouTube trailer comments", "India's own voice: comments written in Devanagari, Tamil, Telugu, Bengali, Kannada, Malayalam scripts",
     "Most popular 200 titles only; newest 1,000 comments per video, so launch-week comments of big hits can be missing; "
     "Hinglish typed in Latin letters is not detected", "Strong for language hubs; noisy for small titles (few comments)"],
    ["Netflix India Top 10", "Real viewing in India, published by Netflix", "Only Netflix titles, only from June 2021; a top-10 list "
     "hides everything below rank 10", "Reliable but coarse; blank (not zero) for titles not on Netflix"],
    ["Wikipedia pageviews (en, ja, hi, ta, te)", "Daily attention, bots excluded, in five languages", "English views are global, not "
     "India-only; Indian-language articles exist mostly for big titles", "Very reliable counts; weak India specificity"],
    ["AniList metadata", "Genres, tags, source, studio, audience, sequel links", "Today's popularity and score include the outcome, "
     "so they are never model inputs", "Reliable; audience tags are the only age proxy in public data"],
    ["Google Trends", "Not used this round (time)", "Would add state-level search; the method takes it as a fourth part when collected", "—"],
], columns=["Source", "What it tells us", "Bias and gaps", "Reliability"])


@st.cache_data
def load():
    path = REAL if REAL.exists() else MOCK
    return json.loads(path.read_text(encoding="utf-8")), path == MOCK


def style(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK), showlegend=False)
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def range_chart(f, lines):
    color, _ = VERDICT_STYLE[f["verdict"]]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=f["low"], x1=f["high"], y0=0.3, y1=0.7, fillcolor=color, opacity=0.25, line_width=0)
    fig.add_trace(go.Scatter(x=[f["index"]], y=[0.5], mode="markers", marker=dict(size=16, color=color, line=dict(width=2, color=SURFACE)),
                             hovertemplate="Forecast %{x:.0f}<extra></extra>"))
    marks = [(lines["hold_line"], "Hold below", "top left"), (lines["launch_line"], "Launch above", "top right")]
    if lines["hold_line"] == lines["launch_line"]:
        marks = [(lines["launch_line"], "Hold below · Launch above", "top")]
    for value, name, position in marks:
        fig.add_vline(x=value, line=dict(color=MUTED, width=1, dash="dot"), annotation_position=position,
                      annotation=dict(text=f"{name} {value}", font=dict(color=MUTED, size=11)))
    fig.update_xaxes(range=[0, 100], title="India Demand Index (0–100, percentile of past titles)")
    fig.update_yaxes(visible=False, range=[0, 1])
    return style(fig, 170)


def drivers_chart(drivers):
    frame = pd.DataFrame(drivers).iloc[::-1]
    fig = go.Figure(go.Bar(x=frame["points"], y=frame["name"], orientation="h",
                           marker=dict(color=[UP if p > 0 else DOWN for p in frame["points"]], cornerradius=4),
                           text=[f"{p:+.0f}" for p in frame["points"]], textposition="outside", textfont=dict(color=INK),
                           hovertemplate="%{y}: %{x:+.1f} points<extra></extra>"))
    fig.update_xaxes(title="Points added to or taken from the index, against an average title")
    return style(fig, 60 + 50 * len(frame))


def regions_chart(regions, hubs):
    frame = pd.Series(regions).sort_values()
    fig = go.Figure(go.Bar(x=frame.values * 100, y=frame.index, orientation="h", marker=dict(color=SERIES, cornerradius=4),
                           text=[f"{v:.0%}" for v in frame.values], textposition="outside", textfont=dict(color=INK),
                           customdata=[hubs.get(h, "") for h in frame.index],
                           hovertemplate="%{y} (%{customdata}): %{x:.0f}%<extra></extra>"))
    fig.update_xaxes(title="Share of Indian-language engagement (%)", range=[0, max(frame.max() * 130, 10)])
    return style(fig, 300)


def backtest_chart(rows, moment):
    fig = go.Figure()
    fig.add_shape(type="line", x0=0, y0=0, x1=100, y1=100, line=dict(color=AXIS, width=1, dash="dot"))
    for verdict, (color, icon) in VERDICT_STYLE.items():
        part = rows[rows["verdict"] == verdict]
        fig.add_trace(go.Scatter(x=part["forecast"], y=part["actual"], mode="markers", name=f"{icon} {verdict}",
                                 marker=dict(size=10, color=color, line=dict(width=2, color=SURFACE)), text=part["name"],
                                 hovertemplate="%{text}<br>Forecast %{x:.0f}, actual %{y:.0f}<extra>" + verdict + "</extra>"))
    fig.update_xaxes(title=f"Forecast at {moment}", range=[0, 100])
    fig.update_yaxes(title="Actual India Demand Index", range=[0, 100])
    style(fig, 420).update_layout(showlegend=True, legend=dict(orientation="h", y=1.08))
    return fig


def verdict_badge(f):
    color, icon = VERDICT_STYLE[f["verdict"]]
    st.markdown(f"<div style='border-left:6px solid {color};padding:6px 14px;margin:4px 0 10px'>"
                f"<div style='font-size:15px;color:#52514e'>Verdict</div>"
                f"<div style='font-size:30px;font-weight:700'>{icon} {f['verdict']}</div>"
                f"<div style='font-size:15px'>India Demand Index <b>{f['index']:.0f}</b> "
                f"(80% range {f['low']:.0f}–{f['high']:.0f})</div></div>", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="Yosoku 予測", page_icon="📈", layout="wide")
    data, mock = load()
    st.title("Yosoku 予測 — India launch forecasts for Japanese anime")
    if mock:
        st.warning("Showing MOCK data made from fake numbers. Run the pipeline (`python -m yosoku.run`) to see real forecasts.")
    titles = data["titles"]

    with st.sidebar:
        groups = [g for g in GROUP_NAMES if any(t["group"] == g for t in titles)]
        group = st.radio("Titles", groups, format_func=GROUP_NAMES.get)
        pool = sorted((t for t in titles if t["group"] == group), key=lambda t: t["name"])
        title = st.selectbox("Title", pool, format_func=lambda t: f"{t['name']} ({t['season']})")
        moments = [m for m in title["moments_available"] if m in title["forecasts"]]
        moment = st.radio("Forecast moment", moments, index=len(moments) - 1, format_func=MOMENT_NAMES.get)
        st.caption("Later moments use more data and are more accurate; the 80% range shows how sure the model is.")
    f = title["forecasts"][moment]
    lines = data["thresholds"][moment]

    tabs = st.tabs(["Verdict", "Why", "Regions", "Slate", "Backtest", "Method & data"])
    with tabs[0]:
        left, right = st.columns([3, 2])
        with left:
            verdict_badge(f)
            st.plotly_chart(range_chart(f, lines), use_container_width=True)
            st.markdown(f["reason_en"])
            st.markdown(f"<span lang='ja'>{f['reason_ja']}</span>", unsafe_allow_html=True)
            st.caption("Japanese text is machine-templated; have a fluent speaker check it before external use.")
        with right:
            st.subheader(title["name"])
            if title.get("title_japanese"):
                st.markdown(f"<span lang='ja'>{title['title_japanese']}</span>", unsafe_allow_html=True)
            st.markdown(f"**Starts in Japan:** {title['start_date']} · **Format:** {title['format']} · "
                        f"**Source:** {str(title['source']).replace('_', ' ').title()}  \n"
                        f"**Genres:** {', '.join(title['genres'])}  \n**Audience:** {title['audience']} · "
                        f"**Sequel:** {'yes' if title['is_sequel'] else 'no'}")
            for flag in title["release_window_flags"]:
                st.info(f"📅 Release window: {flag}")
            if title["actual_index"] is not None:
                st.metric("What actually happened (India Demand Index)", f"{title['actual_index']:.0f}",
                          delta=f"{title['actual_index'] - f['index']:+.0f} vs forecast", delta_color="off")
            if title.get("synopsis"):
                with st.expander("Synopsis"):
                    st.write(title["synopsis"])

    with tabs[1]:
        st.subheader("What moves this forecast")
        if f["drivers"]:
            st.plotly_chart(drivers_chart(f["drivers"]), use_container_width=True)
            st.caption("Exact contributions from the linear model: blue raises the index, red lowers it.")
        else:
            st.info("At the cold moment there is no buzz yet: the forecast is the India index of the most similar past titles below.")
        st.subheader("Closest past titles and how they did in India")
        looks = pd.DataFrame(f["lookalikes"])
        if len(looks):
            looks = looks.rename(columns={"name": "Title", "year": "Year", "similarity": "Similarity", "india_index": "India index"})
            st.dataframe(looks[["Title", "Year", "Similarity", "India index"]], hide_index=True, use_container_width=True)
            st.caption("Similarity combines genres, tags, source, format, studio, audience and synopsis words (1 = identical).")

    with tabs[2]:
        st.subheader("Where in India: language hubs")
        if f["regions"]:
            st.plotly_chart(regions_chart(f["regions"], data["hubs"]), use_container_width=True)
            st.caption(f"Estimated from trailer comments written in Indian scripts on the {f['region_titles']} closest past titles "
                       "that had any. English-language fans are spread across India and are not counted here; Hindi includes "
                       "Marathi (both use Devanagari).")
            st.dataframe(pd.DataFrame({"Hub": list(data["hubs"]), "States": list(data["hubs"].values())}), hide_index=True)
        else:
            st.info("None of the closest past titles had trailer comments in Indian scripts, so there is no regional estimate.")

    with tabs[3]:
        st.subheader(f"{GROUP_NAMES[group]}: every title at a glance")
        rows = [{"Title": t["name"], "Season": t["season"], "Verdict": f"{VERDICT_STYLE[x['verdict']][1]} {x['verdict']}",
                 "Index": x["index"], "Low": x["low"], "High": x["high"], "Audience": t["audience"],
                 "Main genre": (t["genres"] or ["–"])[0]}
                for t in pool if (x := t["forecasts"].get(moment))]
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Index", ascending=False), hide_index=True, use_container_width=True)
        else:
            st.info("No titles have a forecast at this moment yet.")

    with tabs[4]:
        st.subheader("Would we have called it? Forecasts against what happened")
        done = [t for t in titles if t["group"] in ("validation", "test") and moment in t["forecasts"] and t["actual_index"] is not None]
        if done:
            rows = pd.DataFrame([{"name": t["name"], "forecast": t["forecasts"][moment]["index"], "actual": t["actual_index"],
                                  "verdict": t["forecasts"][moment]["verdict"]} for t in done])
            st.plotly_chart(backtest_chart(rows, moment), use_container_width=True)
            medians = rows.groupby("verdict")["actual"].agg(["count", "median"]).reindex(list(VERDICT_STYLE)).dropna()
            st.dataframe(medians.rename(columns={"count": "Titles", "median": "Median actual index"}), use_container_width=True)
        info = data["evaluation"]["moments"].get(moment)
        if info:
            table = pd.DataFrame(info["table"])[["spearman", "low", "high", "top20", "mae"]].round(2)
            table.columns = ["Rank correlation", "95% low", "95% high", "Top-20% hit rate", "Mean error (points)"]
            st.markdown(f"**2024 validation, never seen in training.** Main model: {info['main']}. "
                        f"The 80% range held for {info['coverage']:.0%} of titles. "
                        f"Beats the best simple rule ({info['best_baseline']}): **{'yes' if info['beats_baseline'] else 'no'}**.")
            st.dataframe(table, use_container_width=True)

    with tabs[5]:
        st.subheader("How the India Demand Index is built")
        st.markdown(
            "- Measured over the **first 28 days** after the Japanese premiere, from three public signals: "
            "**YouTube comments in Indian scripts (50%)**, **Netflix India Top-10 weeks (33%)**, **Wikipedia views (17%)**.\n"
            "- Each signal becomes a percentile among past titles; a missing signal is **left out, never counted as zero**, "
            "and the weights are rescaled. A title needs two signals to get an index.\n"
            "- Forecasts only use data available at the forecast moment; an automatic test fails the build if any input "
            "comes from later (no hindsight).\n"
            "- Models are trained on 2019–2023, checked on 2024, and tested once on 2025. They must beat simple rules "
            "(genre average, sequel carry-over, global buzz) to be used.\n"
            "- It measures **attention in India, not revenue**.")
        st.subheader("Data sources: what they tell us and where they mislead")
        st.dataframe(SOURCES, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()

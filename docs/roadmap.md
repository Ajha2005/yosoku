# Review and roadmap

Written 24 October 2026. Numbers come from `reports/` on this branch. The experiments in section 3 were run once
on the committed data, scored on the 2024 split and the 20 rolling seasons; the 2025 test titles were not touched.

## 1. The verdict

Yosoku is a rigorous MVP. Its decisions are fixed in advance, a test fails the build on hindsight, every model has
to beat simple rules, and forecasts are sealed with a public fingerprint before the titles air. That discipline is
rare, and it is the strongest thing to sell. As a product, three gaps would surface in the first meeting with a buyer:

1. **The decision that pays gets the weakest forecast.** Licences are signed months before the Japanese premiere.
   At that stage the forecast ranks the 2024 titles at 0.12 (the genre average makes it), and all 52 are Test-market.
2. **The India Demand Index is mostly not about India.** Only 53 of the 319 labelled titles (14 of the 52 in 2024)
   have any India-specific part above zero. The rest are ranked by English Wikipedia views, which are worldwide
   (rank correlation 0.57 with the index).
3. **It answers with an index**, not with a decision in money, timing or deal terms.

This branch fixes what the data in the repo allowed: two hindsight inputs, a label scale that moved with every
collection, comments IndicLID had never read, collectors that could not run daily, comment text the pipeline
depended on. It adds the decision clock
and a daily job. The rest needs data (section 6), licences (section 7) and partners (section 5).

## 2. What the review found

| # | Finding | Evidence | Status |
| --- | --- | --- | --- |
| 1 | Two model inputs carried information from after the forecast | `has_youtube` marked the YouTube top 200, chosen by today's AniList popularity; `has_india_article` counted article views up to day +120 | **Fixed.** 2024: T−28 0.27 → 0.25, T+7 0.69 → 0.66. The leakage test now also removes post-cutoff rows |
| 2 | The label scale moved with every collection | Adding the 2025 titles moved the 2019–2024 labels by 1.0 point on average, up to 3.0 | **Fixed.** Frozen ranking pool, `labels/reference_v1.csv`; today's labels unchanged byte for byte |
| 3 | The index is mostly global attention | Netflix part 0 for 195 of 208 titles; India YouTube comments 0 for 152 of 200; the Wikipedia part is almost all English views | **Open:** label v2 (section 6) |
| 4 | The index drifts up by year | Mean 47.1 (2019) → 62.5 (2025). Some is real growth; some is how it is measured: Netflix's charts start June 2021, comments were capped at the newest 1,000 per trailer | **Partly fixed:** daily capture removes the cap from now on |
| 5 | 80% ranges held 63–67% of 2024 titles | Set season by season from earlier seasons only, they held 78–82% of titles up to 2023. In 2024 they held for 79–85% of the 33 titles whose index has no YouTube part and 37–47% of the 19 that have one: YouTube was collected for the 200 titles most popular today, so the 2024 ones are mostly hits, which beat their forecasts | **Partly fixed:** titles not released yet, which all get YouTube data, take their range from the misses of the titles whose index includes YouTube (± 21.9 / 18.7 / 12.7). Label v2 item 4 removes the cause |
| 6 | One 52-title season cannot pick a method | A rank correlation on 52 titles has a 95% interval about ± 0.27 wide. The 2024 split and the 20 rolling seasons disagreed on the best method at least four times (section 3) | **Proposal:** pick on the rolling seasons, pre-registered before the next seal |
| 7 | The collectors could not run daily | YouTube comments and searches were cached forever after the first fetch, so an upcoming title never got its launch-week comments or its later trailers | **Fixed:** `collect_youtube.py --refresh`, `collect_titles.py --keep`, `yosoku/daily.py` |
| 8 | Personal data in a public repo | 25 MB of YouTube comment text is committed, against decision 6 in `docs/decisions.md` | **Fixed:** the pipeline runs from per-day counts (2 MB, no text) and the text file is no longer committed. It remains in git's history (section 7) |
| 9 | Commercial terms unchecked | AniList needs a licence above $150 a month of revenue; YouTube limits keeping API data without the channel owner's authorisation to 30 days | **Open** (section 7). The new view-count log keeps 30 days only |
| 10 | IndicLID read only 45% of the comments | Its labels predated the full YouTube rerun: 74,542 of 167,323 comments in Latin letters had one, and 92 of 197 titles had comments read by the word list alone | **Fixed:** every comment labelled (37 more India comments in the first 28 days, 661 → 698); the daily job labels new ones |
| 11 | One comment can move a title by 30 points | 152 of 200 titles have no India comment in their first 28 days, all tied at the bottom of the YouTube part, which weighs 50%. Kaguya-sama Season 3's first one moved it from 50 to 82 | **Open:** label v2 (section 6, item 5) |
| 12 | The site's numbers were not the sealed ones | The 50 upcoming titles showed today's forecasts beside "Sealed 24 Oct 2026"; all 50 differed from the downloadable file | **Fixed:** a sealed stage shows the sealed numbers and lines, today's forecast beside them; alerts judge the sealed verdict |
| 13 | Busy trailers lost their earliest comments | The one-time collection kept the newest 1,000 comments per video. 103 of 600 trailers hit that, on 80 of the 200 titles: on 66 the pre-premiere windows are at least partly cut, and on 14 (13 titles) none of the index's 28 days is left. They are busy trailers (a median of 9,234 comments), so popular titles | **Open:** collect those 103 in full (at most about 6,700 quota units, one day of the default 10,000), then rerun as label v2. New titles are collected every day, so they lose nothing |

## 3. Model experiments: what did not help

Each was scored like `yosoku.evaluate` scores the stages. Rolling is the mean rank correlation over 20 seasons
(Winter 2020 to Fall 2024, each forecast from the seasons before it): about four times as many forecasts as 2024 alone.
The first row was measured when that change was made; the rest were run again after every comment got its IndicLID label.

| Change | Stage | 2024 | Rolling | Outcome |
| --- | --- | --- | --- | --- |
| Remove the two hindsight inputs | T−28 / T+7 | 0.27 → 0.25 / 0.69 → 0.66 | 0.34 → 0.33 / 0.63 → 0.62 | Adopted: integrity |
| Blend at cold (metadata, lookalike, prequel), against the genre average | Cold | 0.05 against 0.12 | 0.18 against 0.09 (sequel carry-over 0.20) | Main model at cold; the genre average still ships, because the rule picks on 2024 |
| Prequel's own attention, studio's India record | Cold | worse | 0.15–0.16 | Rejected |
| Gradient-boosted trees | Cold | 0.25, the best on 2024 | 0.16 | Rejected: worse on the rolling seasons |
| One model per index part, also trained on the 944 titles with only one part | All | better at T−28 (0.41) | worse (0.27 against 0.32) | Rejected |
| Buzz from days −120 to −57 | T−28 / T+7 | 0.23 / 0.66 | 0.34 / 0.60 (against 0.32 / 0.61) | Rejected: +0.02 and −0.01, within noise |
| Year trend or level correction | All | lower error on 2024 | no change | Rejected: fix the measurement instead |
| Chance of a top-third result | Cold / T−28 / T+7; clock days | | Brier skill 0.02 / 0.07 / 0.19; day +3 0.15, day +14 0.22 | Shipped where the skill is 0.10 or more: T+7 and from day +3 |
| AniList's dated list count (users with the title on their list, from AniList's daily trend history) | 90 days out / day −49 / T−28 / T+7 | 0.05 → 0.07 / 0.15 → 0.16 / 0.23 → 0.25 / 0.66 → 0.66 | 0.18 → 0.24 / 0.29 → 0.30 / 0.32 → 0.33 / 0.61 → 0.62 | **Promising:** the largest gain found, at the stage where licences are signed. Next to adopt; it needs an AniList collector, at 30 requests a minute, and AniList's licence |
| Season, episode count, Wikipedia momentum, dub requests before the cutoff, first-trailer timing | All | within ±0.04 | within ±0.02 | Rejected |
| Ranges per title (misses scaled by a model of each title's difficulty) | All | | interval score 53 / 51 / 41 against 53 / 49 / 40 | Rejected |
| Earlier seasons sell again when a new one airs ("series heat") | | 0 of 5 earlier seasons re-entered Netflix India's Top 10 | | Rejected |
| Countries of similar titles, for the next market | | | AUC per country 0.70 (0.55 by genre); top-5 countries 83% (85% for the most common) | Shipped, each country beside its typical rate |

Two conclusions. With today's data the limit is the data, not the model: nothing beat the Blend on the rolling
seasons. And the 2024 split cannot referee small differences, so the gate should read the rolling seasons first.

## 4. The data grows every day: how Yosoku scales

### 4.1 Most data freezes

A title's data only changes until its last window closes. The buzz windows end on day +6 after the Japanese
premiere, the index's on day +27 and Netflix's weeks on day +90 (`collectors/common.py`, `is_active`). After that
nothing about it needs collecting or computing again. So the daily work is set by the titles in play, one or two
seasons (100 titles at today's 50 a season), and not by the archive. The archive grows; the daily work does not.

| Days from the premiere | What happens |
| --- | --- |
| Before day −49, or date unknown | Cold forecast; titles list and Wikipedia refreshed daily |
| −49 to −1 | Buzz windows fill; forecast daily; T−28 verdict on day −28 |
| 0 to +14 | Nowcast; T+7 verdict on day +7. The decision clock's biggest jump is days 0 to +3 |
| +15 to +27 | The index's own window; label written once day +27 has passed |
| +28 to +90 | Only Netflix weeks still counting |
| After +90 | Frozen: never collected or recomputed again |

### 4.2 What runs now (this branch)

- `python -m yosoku.daily`: collects for the titles in play, labels aired titles on the frozen scale, forecasts
  each title in play as of today with the decision clock's model, logs it to `predictions/history.csv`, writes
  `reports/alerts.md` when buzz moves a forecast out of its verdict's range, and republishes the site, which shows
  the day's status and alerts, a *Moved* badge on those titles, and each upcoming title's forecast moving on its
  sheet. Under a minute on today's data, collection aside.
- `collect_youtube.py --refresh`: new comments only (newest first, until a cached one), a new search each week for
  later trailers, today's view counts kept for 30 days. A title in play costs a page or two of comments per video
  a day and one search a week.
- `collect_titles.py --keep`: picks up announced start dates (39 of the 50 Winter 2027 titles have none yet) and keeps
  titles that slip out of the top 50, so their sealed forecasts can still be scored.
- `data/youtube_comment_daily.csv`: comments counted per title, video and day. 25.4 MB of text becomes 2.1 MB of
  counts; the dataset built from them is byte-identical, and so are the model inputs (tested).
- The frozen label pool: new titles never re-score old ones, and sealed forecasts are graded on their own scale.

### 4.3 Next: run it every morning

- **Where:** a machine whose disk persists, because the comment refresh builds on the cache in `data/raw/`. A
  laptop or a small server with cron, for example `30 6 * * * cd ~/yosoku && .venv/bin/python -m yosoku.daily`,
  then commit `data/upcoming`, `predictions/history.csv`, `reports/alerts.md` and `web/data`. GitHub Actions starts
  with an empty disk each run, so it would need the cache restored from storage first.
- **Refit:** `python -m yosoku.run` weekly, or whenever titles get labels. A new model replaces the old one only
  through the gates, scored on the rolling seasons.
- **Alerts out:** post `reports/alerts.md` to the team's channel by webhook: email, Slack, Microsoft Teams or LINE WORKS.

### 4.4 At scale

Volume is not the constraint. Wikipedia is about 390 rows per title, 58 bytes each as CSV: 300 titles a season would
add about 27 MB of CSV a year, a few MB as Parquet. The comment counts are 41,000 rows for 198 titles. The
forecast log grows by one row per title in play per day. The constraints are API quotas, correctness over time and
operations, in that order:

- **Quota:** find trailers through official channels' upload playlists (a playlist page costs 1 unit; a search 100).
  A larger quota goes through YouTube's compliance audit, which section 7 prepares for.
- **Correctness over time:** every collected row carries its collection date; AniList metadata (tags, start dates)
  is versioned, so any forecast can be rebuilt as it was made. A seal should record a fingerprint of the data it
  was made from, not only the model commit.
- **Storage, when the universe outgrows a laptop** (all Japanese anime, several markets): Parquet files partitioned
  by source and month in object storage, queried with DuckDB. Git keeps the code, the frozen pools, the seals and
  small summaries, not the raw data.
- **Operations:** with more than a handful of jobs, an orchestrator (Dagster or Prefect), a check per source (rows,
  schema, freshness) and a weekly calibration report: does the 80% range still hold 80% on the titles labelled since?

## 5. What makes a Japanese company buy

Japan's government aims to quadruple overseas sales of its content industries to ¥20 trillion by 2033 (the 2024 Cool
Japan strategy; about ¥5.8 trillion in 2023). Rights holders will need evidence for each new market, and India is a
large one where demand for anime is barely measured.

### 5.1 Who decides what

| Buyer | Decision | What Yosoku must answer |
| --- | --- | --- |
| Rights holders and production committees (publishers, studios, producers) | Whether to sell India rights, to whom, exclusive or not, at what minimum guarantee | Which titles will travel to India, how sure we are, compared with which past titles |
| Their overseas sales teams | Which titles to push this season; which market next | A ranked slate with honest ranges; where else a title travels |
| Platforms and distributors serving India | What to license, dub and promote, in which languages, when | Dub demand by language hub; the day the evidence is good enough to decide |

### 5.2 The selling points, in order

1. **The decision clock, and deals built on it.** Before the premiere, waiting buys little: over 20 seasons the
   ranking goes from 0.29 at day −49 to 0.38 at day −7. Three days after the premiere it reaches 0.53 (0.64 on
   2024). So: license with a small minimum guarantee and an escalator tied to the day-3 or day-7 reading, and
   order the dub between day 3 and day 7. That turns forecast uncertainty into contract terms, which a dashboard
   of scores does not do. *Built: the clock, each title's forecast path, and from day 3 a chance of a top-third
   result (at T+7, 94% of its calls of 70% or more came true). Next: a deal-structure note on each sheet.*
2. **Sealed, graded forecasts.** Every forecast for an unreleased title is frozen with a SHA-256 fingerprint in a
   public ledger, and graded once the title airs, on a scale that no longer moves. In a market that values
   accountability, a published track record is the moat: no competitor can backfill one. *Built: seals, frozen
   scale, aired titles labelled, and the site shows the sealed numbers. Next: a public scorecard page from February
   2027, data fingerprints in seals, and then a guarantee: a season free if fewer than 70% of its titles land inside
   the 80% ranges. With 50 titles and ranges that really hold 80%, that happens about one season in 30; offer it only
   once sealed seasons show the ranges hold (in 2024 they did not, row 5).*
3. **India's own voice, by language.** Hinglish read with AI4Bharat's IndicLID, language hubs (Hindi, Tamil, Telugu,
   Bengali, Kannada, Malayalam) and dub requests such as "hindi dub kab aayega". *Built, and the Demand guide lists
   what India asks for, title by title: 1,197 comments on 68 titles ask for a dub (Hindi 1,016, Tamil 50, Telugu 23)
   or for when and where to watch (160). Next: join where each title can already be watched in India (JustWatch's
   partner API, or TMDB's provider data under a commercial licence), which turns it into a sales list of titles
   India asks for and cannot get; and comments on Indian distributors' own channels.*
4. **Living forecasts and alerts.** Titles in play are forecast every day; a title that leaves its verdict's range
   is flagged, so a Tamil dub can be brought forward while it still matters. *Built: daily job, history on each
   sheet, alerts file. Next: delivery to the buyer's chat tool, and alerts per language hub.*
5. **Japanese-first decision papers.** A brief per title and per slate that can go straight into a 稟議書 (ringi-sho,
   the internal approval document): 件名, 結論, 根拠, 前例, リスク, 次の判断日, with boxes for the approvers' seals.
   Business Japanese, reviewed by a native speaker, with an Excel export. *Built: the one-page brief per title (the 稟
   button on each sheet). Next: native review, a slate version, the Excel export.* The Japanese is machine-templated,
   and the page says so; for a Japanese buyer, polished Japanese is the minimum, not a feature.
6. **Comparable titles with reasons.** Licensing teams argue by comparables (類似作品). Show why each one is close
   (shared tags, studio, source) and how it did in India. *Built: the closest five, and in the Japanese brief the
   closest three with what they share (series, genres, studio, source, format, audience, tags). Next: the same on the sheet.*
7. **The next market, from the same engine.** Netflix's Top 10 file covers nearly 100 countries and territories; the
   collector reads only India's rows today. "Where else does this title travel?" (Indonesia, the Philippines,
   Brazil, Mexico, the Gulf) is a short step, and comment language is easier to read there than Hinglish.
   *Built: every forecast lists where its closest earlier titles charted (88 countries; AUC 0.70 per country against
   0.55 by genre), and the Demand guide shows where anime charts: India comes joint 36th of 88. Next: platforms beyond Netflix.*
8. **Money, once a partner shares it.** The index measures attention. India revenue or viewing hours for 30–50 titles
   from one rights holder or platform would let Yosoku forecast money. That is the single most valuable partnership to seek.
   *Built: the plumbing (`yosoku/money.py`): 30 or more titles of partner figures turn every forecast into a range in
   yen, private unless the partner agrees to publish it. Next: the partner.*

### 5.3 What not to claim

- Not "AI predicts hits". Say what is knowable when, and how sure, with the graded record to prove it.
- Not revenue, until a partner's data backs it.
- Not precision for small titles: their evidence is thin, and the sheets say so.

## 6. Label v2: make the index India's

1. **India-only Wikipedia views.** Wikimedia publishes daily pageviews by country, project and article, made private
   with differential privacy: from 2017 to February 2023, rows above 450 views a day; since February 2023, above
   90 to 1,000 views a day depending on the country. Views from India of the English article replace worldwide
   views. Small titles fall under the threshold, so treat a missing row as "below", not as zero.
2. **Google Trends for India, without the anchor.** Google's Trends API (alpha since July 2025) returns consistently
   scaled daily interest, five years back, with sub-regions, which means Indian states. Apply for access: it brings
   back the Search part (40% in the original design) and a state-level map from searches, not only comments.
3. **Indian distributors' channels.** Comments on their uploads, and views of Hindi-dub episodes. With the channel
   owner's authorisation, the YouTube Analytics API gives their views and watch time from India, and authorised
   data can be kept for as long as the authorisation lasts (it is re-checked every 30 days).
4. **The same measurement for every title.** YouTube for every title in the universe, not the top 200 by today's
   popularity, captured daily from now on, and the 103 trailers cut at 1,000 comments collected in full (section 2,
   row 13). The selection is also what broke the 2024 ranges (row 5).
5. **Below the chart is not zero.** Netflix's Top 10 hides everything below rank 10, so a title that did not chart
   is censored, not measured at zero; model it that way. YouTube has the same problem: 152 of 200 titles have no
   India comment in their first 28 days, tied at the bottom, so a single comment can move a title 30 points
   (section 2, row 11). More comments per title (item 3) and a part that grows smoothly from zero both help.
6. **A new version, a new pool.** Label v2 gets its own frozen pool; v1 stays to grade the October 2026 seal.

Dated pre-launch signals worth testing: AniList's daily trend records (popularity, trending), if their history
reaches before past premieres; trailer view growth in the first 72 hours; the source manga's Wikipedia attention
before the anime was announced.

## 7. Licences and compliance, before the first invoice

| Source | What the terms say (check the current text) | Action |
| --- | --- | --- |
| AniList API | Free for non-commercial use, and for services under $150 a month of revenue; above that a commercial licence (contact@anilist.co). No use as a backup or data store, no "hoarding or mass collection" | Ask for a licence before the first paying customer |
| YouTube Data API | API data, statistics included, may be kept at most 30 days without the channel owner's authorisation (Google's example: a channel's subscriber count); larger quotas need a compliance audit | Take the comment text out of the public repo; keep caches refreshed or deleted within 30 days; get authorised data through partners |
| Netflix Top 10 | Public weekly lists, nearly 100 countries since June 2021 | Check the site's terms for commercial reuse |
| Wikimedia pageviews | Open data | Attribute; the per-country counts carry noise by design |
| Comment text | Personal data: India's Digital Personal Data Protection Act 2023; Japan's APPI for Japanese clients | Keep counts, not text |

The comment text is out of the public repo's files (`data/youtube_comments.csv` is git-ignored; the pipeline runs from
`data/youtube_comment_daily.csv`). Anyone who pulls the removal should first keep a private copy, or keep
`data/raw/youtube/`, because git deletes the file from working copies. It stays in git's history. Removing it from there
means rewriting it (`git filter-repo`) and force-pushing, after which everyone clones again. That is the repo owner's
decision.

## 8. Plan

**Next two weeks**
- Merge this branch; show the decision clock in the demo.
- Collect the 103 trailers cut at 1,000 comments in full (needs the YouTube key; one day of quota).
- Adopt AniList's dated list counts as an input: the largest gain found where licences are signed (90 days out,
  0.18 → 0.24 over the rolling seasons). Write the collector and check AniList's commercial terms first.
- Run `yosoku.daily` every morning on one machine with fastText installed; collect YouTube for the 50 Winter 2027
  titles in refresh mode.
- Before sealing Spring 2027: pre-register picking methods on the rolling seasons, and add a data fingerprint to seals.
- Have a native speaker review the Japanese; add an Excel export of the slate.
- Apply for the Google Trends API; write to AniList about commercial terms.

**Next three months** (Winter 2027 airs from January; its labels arrive from February)
- Grade the October 2026 seal with `python -m yosoku.seal --score`, and publish the result, whatever it is.
- Build label v2 (per-country Wikipedia, Trends if granted, Indian channels) and backtest it against v1.
- Send alerts to a chat tool, per language hub.
- Pilots: one Japanese rights holder (a review of its Spring and Summer 2027 slate) and one Indian distributor
  (channel analytics and dub results in exchange for forecasts).

**Next twelve months**
- Forecast money with a partner's data.
- The next markets from Netflix's country charts.
- Enterprise basics: Japanese interface, data kept in Japan, single sign-on, an API; price per season's slate plus per-title briefs.
- Storage and orchestration upgrades when the universe outgrows a laptop (section 4.4).

## 9. 日本語サマリー

**Yosoku（予測）：日本のアニメがインドでどれだけ見られるかを、放送前と放送直後に予測します。**

- **何がわかるか**：作品ごとに「投入推奨・テスト販売・見送り」の判定と、その根拠（類似作品のインドでの実績、言語圏別の反応、吹替需要）を示します。
- **判断のタイミング（ディシジョン・クロック）**：過去20シーズンの検証では、放送前の数週間は予測の精度があまり上がらず（順位相関 0.29 → 0.38）、放送開始から3日で大きく上がります（0.53）。そこで、ライセンスは低めの最低保証と放送後の実績連動で結び、吹替は放送3〜7日後に決める、という段階的な判断を提案できます。
- **検証できる実績**：未放送作品の予測は、放送前にSHA-256で封印して公開台帳に記録しています。後から書き換えることはできず、放送後にそのまま採点されます。
- **インドの声を言語圏別に**：ヒングリッシュ（ローマ字のヒンディー語）を含むインドからのコメントを、ヒンディー、タミル、テルグなどの言語圏別に数え、「ヒンディー語吹替はいつ？」といった吹替の要望も測ります。
- **毎日更新**：放送前後の作品は毎日予測し直し、判定の範囲を外れた作品をアラートでお知らせします。
- **稟議書をそのまま出力**：各作品のページから、結論・根拠・前例（類似作品とその共通点、インドでの実績）・リスク・次の判断日をまとめた1枚の稟議書（案）を印刷できます。
- **ヒットの確率**：放送3日後から、インドで上位3分の1に入る確率を示します（放送7日後の検証では、70%以上とした予測の94%が的中）。
- **他の市場**：Netflixの88か国のTop 10から、類似作品がヒットした国を作品ごとに示します（インドは88か国中36位タイ）。
- **売上見込み**：パートナーから過去30作品以上のインドでの実績をご提供いただければ、すべての予測に円建ての範囲を付けられます（非公開で運用）。
- **インドが求めている作品**：インドのファンが吹替や視聴方法を求めたコメント（68作品、1,197件。うちヒンディー語吹替1,016件）を作品ごとに一覧にしています。
- **現状の課題も正直に**：放送前（コールド）の予測はまだ弱く、指数の多くはインド固有ではない英語版Wikipediaの閲覧数に依存しています。インドからのWikipedia閲覧数、Google Trends API、インドの配信事業者のYouTubeチャンネルで、指数をインド固有のものにしていきます。
- **お願いしたいこと**：インドでの売上または視聴時間（30〜50作品分）をご提供いただければ、注目度ではなく収益を予測できるようになります。

※ この要約はAIが作成しました。社外で使う前に、日本語を母語とする方の確認を受けてください。

## Sources

- Japan's 2033 target: [Gulf Times (AFP)](https://www.gulf-times.com/article/684125/international/japan-aims-to-quadruple-overseas-market-for-anime-games),
  [Adnkronos (Yomiuri report)](https://english.adnkronos.com/2026/01/13/tokyo-report-japan-to-boost-aid-for-games-anime-as-new-pillar-of-growth/)
- Wikimedia per-country pageviews: [current dataset README](https://analytics.wikimedia.org/published/datasets/country_project_page/00_README.html),
  [2017–2023 README](https://analytics.wikimedia.org/published/datasets/country_project_page_historical/00_README.html),
  [Differential privacy on Meta](https://meta.wikimedia.org/wiki/Differential_privacy)
- [AniList API terms of use](https://docs.anilist.co/guide/terms-of-use)
- [YouTube API Services developer policies](https://developers.google.com/youtube/terms/developer-policies)
- [Google Trends API (alpha) announcement](https://developers.google.com/search/blog/2025/07/trends-api)
- [Netflix Top 10](https://top10.netflix.com)

These pages were read through search results, not opened directly; check each against its current text before
quoting it to a client.

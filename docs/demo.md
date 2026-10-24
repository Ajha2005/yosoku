# 3-minute demo

Open the site on the Overview tab. Numbers below are from the 2024 backtest as committed; the page always shows the
current ones.

| Time | Where | Say |
| --- | --- | --- |
| 0:00 | Overview, hero | "Yosoku asks one question for a Japanese studio or distributor: will this anime land in India?" |
| 0:20 | Forecasts, open any 2024 title | Open it at Cold: Test-market, and the real result is far off. Switch the stage to T+7: the range now holds the real result. "T+7 is a nowcast: that launch week is part of the 28 days we measure, and we say so. So: test-market first, decide at T+7." |
| 0:40 | Same sheet, *Launch plan* | "A verdict is not enough, so every title gets a plan": license small, the exact rule for deciding again at T+7, which dub first, whether to move the date. Every step comes from evidence lower on the sheet. |
| 0:50 | Same sheet, scroll | Dub demand (share of Indian comments asking for a Hindi/Tamil dub, against a typical title), the language-hub map with its evidence count and the *thin evidence* flag, and the release-window what-if ("the window makes no clear difference"). |
| 1:20 | Print icon on the sheet | "Every title prints as a one-page brief for an executive who will never open the site." |
| 1:40 | Track record | Forecast against reality for 2024. At Cold a simple rule (genre average) makes the forecasts, because our model did not beat it; the page says so. At T−28 and T+7 the model beats every simple rule. |
| 2:20 | Method | Source scorecard, then *What each signal is worth*: retrained without one input at a time, global Wikipedia carries T−28 and Wikipedia plus YouTube carry T+7; Indian-language Wikipedia, prequels and metadata add nothing. "We know which data matters, and which does not." |
| 2:45 | Forecasts, *Upcoming* | 50 Winter 2027 titles, sealed on 24 October 2026 with a SHA-256 fingerprint in a public ledger: "we cannot quietly change these. Check us when they air." |

## Questions to prepare for

- **Isn't T+7 just week 1 predicting month 1?** Partly, yes. Its inputs (launch-week views and comments) are inside the
  label window (days 0–27). That is why we call it a nowcast, and why a simple rule using India's launch-week YouTube comments does almost as well
  (average miss 9.5 against 8.3). The value is the decision rule: wait a week before committing.
- **Gate G2 fails. Is the index trustworthy?** Every pair of its parts now agrees positively (YouTube and Netflix 0.51),
  but lowering the Wikipedia weight by 0.10 still reshuffles the ranking more than our target allows. The parts measure
  different things (talk, viewing, reading). Six films' India box office ranks with the index at 0.43, but six is too
  few to prove anything (range −0.60 to 1.00).
- **How big are the samples?** 319 labelled titles of 1,400; 52 in the 2024 test. Titles were chosen by popularity, so
  hits are over-represented, and every result is measured on that set.
- **Why not more modelling?** The lookalike and blend models barely beat simple rules; the limit is data, not the
  model. More India-specific data (streaming beyond Netflix) would help most.
- **Why no X/Twitter or merchandise?** No usable public source by title and country.
- **How do we know you did not change the upcoming forecasts after the fact?** They are sealed: the file's SHA-256 is in
  `predictions/sealed/LEDGER.md`, dated by its git commit. `sha256sum` on the downloaded file must match it, and
  `python -m yosoku.seal --score` will grade them once the titles air.
- **Which data actually matters?** Method → *What each signal is worth*. Global Wikipedia attention and India's
  YouTube comments carry the forecasts; Indian-language Wikipedia and metadata add nothing measurable.

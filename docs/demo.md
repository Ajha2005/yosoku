# 3-minute demo

Open the site on the Overview tab. Numbers below are from the 2024 backtest as committed; the page always shows the
current ones.

| Time | Where | Say |
| --- | --- | --- |
| 0:00 | Overview, hero | "Yosoku asks one question for a Japanese studio or distributor: will this anime land in India?" |
| 0:20 | Overview, *Don't commit on a cold forecast* | "Our headline is a decision rule, not a score. Before launch nothing we tried ranks titles much better than chance (0.09). One week after launch we reach 0.42. So: test-market first, decide at T+7. And T+7 is a nowcast: that week is part of what we measure, and we say so." |
| 0:50 | *See it on one title* button | The button picks the 2024 title where waiting helped most (by rule, not by hand). Show Cold: Test-market, actual far off. Switch the stage to T+7: the verdict and range now hold the real result. |
| 1:20 | Same sheet, scroll | Dub demand (share of Indian comments asking for a Hindi/Tamil dub, against a typical title), the language-hub map with its evidence count and the *thin evidence* flag, and the release-window what-if ("the window makes no clear difference"). |
| 1:40 | Print icon on the sheet | "Every title prints as a one-page brief for an executive who will never open the site." |
| 2:00 | Track record | Forecast against reality for 2024. At T−28 a simple rule (sequel carry-over) makes the forecasts, because our model did not beat it; the page says so. |
| 2:20 | Method | Source scorecard: coverage, India-specificity, lead time, agreement, bias, and the sources we rejected and why (Trends, X, AniList popularity as leakage). |
| 2:45 | Forecasts, *Upcoming* | Dated forecasts for unreleased titles: "check us when they air." (Only once `data/upcoming/` is collected.) |

## Questions to prepare for

- **Isn't T+7 just week 1 predicting month 1?** Partly, yes. Its inputs (launch-week views and comments) are inside the
  label window (days 0–27). That is why we call it a nowcast, and why the simple global-buzz rule already gets 0.40.
  The value is the decision rule: wait a week before committing.
- **Gate G2 fails. Is the index trustworthy?** The three parts barely agree with each other today (Method → scorecard).
  They measure different things (talk, viewing, reading), few titles have more than one, and the Wikipedia part
  missed the biggest shows until its articles were fixed. Six films' India box office ranks with the index at 0.60,
  but six is too few to prove anything (range −0.50 to 1.00).
- **How big are the samples?** 234 labelled titles of 1,400; 48 in the 2024 test. Titles were chosen by popularity, so
  hits are over-represented, and every result is a rank correlation on that set.
- **Why not more modelling?** The lookalike and blend models barely beat simple rules; the limit is data, not the
  model. More India-specific data (Trends by state, streaming beyond Netflix) would help most.
- **Why no X/Twitter or merchandise?** No usable public source by title and country.

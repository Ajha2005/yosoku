# 3-minute demo

Open the site on the Overview tab. Numbers below are from the 2024 backtest as committed; the page always shows the
current ones.

| Time | Where | Say |
| --- | --- | --- |
| 0:00 | Overview, hero | "Yosoku asks one question for a Japanese studio or distributor: will this anime land in India?" |
| 0:20 | Forecasts, open any 2024 title | Open it at Cold: Test-market, and the real result is far off. Switch the stage to T+7: the range now holds the real result. "T+7 is a nowcast: that launch week is part of the 28 days we measure, and we say so. So: test-market first, decide at T+7." |
| 0:40 | Same sheet, *Launch plan* | "A verdict is not enough, so every title gets a plan": license small, the exact rule for deciding again at T+7, which dub first, whether to move the date. Every step comes from evidence lower on the sheet. |
| 0:50 | Same sheet, scroll | Dub demand (share of Indian comments asking for a Hindi/Tamil dub, against a typical title), the language-hub map with its evidence count and the *thin evidence* flag, and the release-window what-if ("the window makes no clear difference"). |
| 1:20 | Print icon, then 稟 on the sheet | "Every title prints as a one-page brief for an executive who will never open the site, or as a Japanese 稟議書: conclusion, grounds, the closest past titles and what they share, risks, the next decision dates, and boxes for the approvers' seals. It goes straight into the approval process." |
| 1:40 | Track record | Forecast against reality for 2024. At Cold a simple rule (genre average) makes the forecasts, because our model did not beat it; the page says so. From T−28 on, our model beats every simple rule. |
| 2:00 | Track record, *When will we know?* | The decision clock: "Before the premiere, waiting helps little: 0.29 seven weeks out, 0.38 one week out. Three days after it, 0.53. So: license small and early, decide the dub on day 3 to 7." Then open Solo Leveling's sheet, *How the forecast moved*: 53 at Cold, 58 at T−28, 83 by day 3; it ended at 80. |
| 2:15 | Demand guide, *What India is asking for* | "1,197 Indian comments on 68 titles ask for a dub, mostly Hindi, or for when and where they can watch. Join where each title is already available in India, and this is a sales list: the titles India asks for and cannot get." |
| 2:30 | Method | How a forecast becomes a verdict (and which method makes each stage), the index checks with the six India box office films beside their index. Then *What each signal is worth*: genre, format, source and audience carry Cold, global Wikipedia carries T−28, Wikipedia plus YouTube carry T+7, and Indian-language Wikipedia and prequels add nothing. |
| 2:50 | Forecasts, *Upcoming* | 50 Winter 2027 titles, sealed on 24 October 2026 with a SHA-256 fingerprint in a public ledger: "we cannot quietly change these. Check us when they air." Each sheet shows the sealed numbers, with today's forecast beside them. |

## Questions to prepare for

- **Isn't T+7 just week 1 predicting month 1?** Partly, yes. Its inputs (launch-week views and comments) are inside the
  label window (days 0–27). That is why we call it a nowcast, and why a simple rule (India trailer comments alone) comes close (average miss
  9.5 against 8.4). The value is the decision rule: wait until day 3 to 7 before committing, and the decision clock shows why.
- **The forecast numbers went down since the last version. Why?** Two inputs leaked: one flagged the titles we had
  searched on YouTube, which were picked by today's popularity, and one counted Indian-language Wikipedia articles
  written after the forecast date. Removing them cost 0.02 to 0.03 of rank correlation. Honest numbers over flattering ones.
- **What happens as data keeps coming in?** A title's data stops changing 90 days after its premiere, so the daily
  job only collects and forecasts the titles still in play, and the archive never has to be recomputed. Labels sit on a
  frozen scale, so new titles never move old ones. `docs/roadmap.md`, section 4.
- **Gate G2 fails. Is the index trustworthy?** Narrowly. All three parts now agree positively (YouTube and Netflix most,
  at 0.50), but moving the Wikipedia weight by 0.10 reshuffles the ranking more than our target allows (details in
  `reports/label.md`; the Method tab shows the pass/fail in plain words). The parts measure different things (talk, viewing,
  reading) and few titles have all three. Six films' India box office ranks with the index at 0.43, but six is too few to
  prove anything (range −0.60 to 1.00); the Method tab lists the six beside their index.
- **How big are the samples?** 319 labelled titles of 1,400; 52 in the 2024 validation set. Titles were chosen by popularity, so
  hits are over-represented, and every result is measured on that set.
- **Why not more modelling?** The models beat simple rules once buzz exists, but cold forecasts stay near chance; the limit is data, not the
  model. More India-specific data (streaming beyond Netflix) would help most.
- **Why no X/Twitter or merchandise?** No usable public source by title and country.
- **The 80% ranges held for only 67% of 2024 titles. Why trust them?** The misses are the 19 titles whose index
  includes YouTube: 37–47% inside, against 79–85% of the other 33. YouTube was collected for the 200 titles most
  popular today, so the 2024 ones are mostly hits. Upcoming titles all get YouTube data, so their ranges are set from
  those titles' misses, and are wider (± 22 at Cold). Collecting YouTube for every title removes the cause.
- **Are the numbers on the site the sealed ones?** Yes, for every sealed stage; the sheet shows today's forecast beside
  them when it differs.
- **How do we know you did not change the upcoming forecasts after the fact?** They are sealed: the file's SHA-256 is in
  `predictions/sealed/LEDGER.md`, dated by its git commit. `sha256sum` on the downloaded file must match it, and
  `python -m yosoku.seal --score` will grade them once the titles air.
- **Which data actually matters?** Method → *What each signal is worth*. Global Wikipedia attention and India's
  YouTube comments carry the forecasts; Indian-language Wikipedia adds nothing measurable, and genre, format, source
  and audience matter only at Cold.

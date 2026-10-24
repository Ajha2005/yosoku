# 3-minute demo

Open the site on the Overview tab. Numbers below are from the 2024 backtest as committed; the page always shows the
current ones.

## The business story in one breath

> "Indian platforms, Japanese licensors, cinema chains and dubbing studios make decisions worth crores about which anime
> to bring to India, with little India-specific evidence. Yosoku tells them **what** to license, **when** to commit and **which language to dub
> first**, before launch. On 2024 titles it never trained on, 10 of the 11 shows it called *Launch* at T+7 were real
> hits. Its forecasts for next season are sealed, so you can check us. And the same pipeline runs for Indonesia,
> Thailand, Brazil or Mexico by changing one setting."

Judges here weigh the business case, scale and money most, so every stop below ends on what a buyer gets.

| Time | Where | Say |
| --- | --- | --- |
| 0:00 | Overview, hero | "Yosoku asks one question for a Japanese studio or distributor: will this anime land in India?" |
| 0:20 | Forecasts, open any 2024 title | Open it at Cold: Test-market, and the real result is far off. Switch the stage to T+7: the range now holds the real result. "T+7 is a nowcast: that launch week is part of the 28 days we measure, and we say so. So: test-market first, decide at T+7." |
| 0:40 | Same sheet, *Launch plan* | "A verdict is not enough, so every title gets a plan": license small, the exact rule for deciding again at T+7, which dub first, whether to move the date. Every step comes from evidence lower on the sheet. |
| 0:50 | Same sheet, scroll | Dub demand (share of Indian comments asking for a Hindi/Tamil dub, against a typical title), the language-hub map with its evidence count and the *thin evidence* flag, and the release-window what-if ("the window makes no clear difference"). |
| 1:15 | Print icon, then 稟 on the sheet | "Every title prints as a one-page brief for an executive who will never open the site, or as a Japanese 稟議書: conclusion, grounds, the closest past titles and what they share, risks, the next decision dates, and boxes for the approvers' seals. It goes straight into a Japanese licensor's approval process." |
| 1:35 | Track record, *When will we know?* | "At Cold our model did not beat a simple rule (genre average), so the rule makes those forecasts and the page says so." Then the decision clock: "Before the premiere, waiting helps little: 0.29 seven weeks out, 0.38 one week out. Three days after it, 0.53. So: license small and early, decide the dub on day 3 to 7." |
| 1:55 | **Business**, *What following our calls would have been worth* | "This is what a buyer gets. At T+7, 10 of the 11 titles we called *Launch* ended in the top third of real India demand; picking at random lands there one time in three. The lines were tuned on these titles, so that is optimistic: the sealed forecasts are the honest check." |
| 2:15 | Business, *Who pays* | Four customers and the decision each makes: platforms (what to license, when, whether to dub), Japanese licensors (which titles to offer India, how to price the rights), cinema chains (which films, which languages), dubbing studios (which titles and languages). "The money is real: Demon Slayer: Infinity Castle took about ₹66 crore in Indian cinemas." |
| 2:30 | Business, *Expansion* | "A market is a setting: the same collectors and model, with that country's Netflix chart and Wikipedia languages. India runs today; Indonesia, Thailand, Brazil and Mexico are set up. Outside India the index has two parts until a comment word list exists for their languages." Then *Why us*: built around the launch decision, India-specific signals, honest about its limits, cheap to run. |
| 2:45 | Forecasts, *Upcoming* | 50 Winter 2027 titles, sealed on 24 October 2026 with a SHA-256 fingerprint in a public ledger: "we cannot quietly change these. Check us when they air. Every season adds to a dated track record a newcomer cannot copy." |

If there is time, or a judge asks how it works: **Demand guide → What India is asking for** ("1,197 Indian comments
on 68 titles ask for a dub or for where to watch: joined with availability, that is a sales list") and **Method** (how
a forecast becomes a verdict, the index checks with the six box office films, and *What each signal is worth*).

## Business questions to prepare for

- **Who pays?** Whoever makes an India launch decision with money on it: streaming platforms and TV channels (rights,
  timing, dubs), Japanese studios and licensors (which titles to offer India, at what price), cinema chains and film
  distributors (which anime films, which languages), dubbing studios (which titles to pitch). The Business tab lists them.
- **How do you make money?** A season subscription for buyers (every new title at all three stages, refreshed as data
  arrives), one-page title briefs sold one at a time, and later a partner tier that adds a platform's own pre-launch
  signals. We have not tested prices with a buyer yet; say so if asked for numbers.
- **Why would they pay?** One wrong rights deal or dub costs more than the forecasts. Demon Slayer: Infinity Castle took
  about ₹66 crore in Indian cinemas; the stakes per title are in crores, and little India-specific evidence exists before launch.
- **How does it scale?** Every source is public and free, the model reruns on 1,400 titles in about 30 seconds, and
  collection runs daily for the titles still in play. A new market is one line in `collectors/markets.py` plus the same
  collectors; Netflix publishes weekly charts for about 90 countries.
- **Has it run outside India?** Not yet: Indonesia, Thailand, Brazil and Mexico are set up, none is collected. Outside
  India the index has two parts (Netflix and Wikipedia) until a comment word list exists for that country's languages.
- **Who else does this?** Global demand-measurement firms such as Parrot Analytics sell cross-country TV demand data to
  studios, which shows buyers pay for this kind of answer. Yosoku is narrower and cheaper: a launch verdict with reasons,
  India-specific signals, built on public data.
- **What stops someone copying it?** The code can be copied; the dated track record cannot. Every season adds sealed
  forecasts scored against what happened, and more labelled titles.
- **What would make it much better?** Pre-launch signals from inside a streaming platform (watchlist saves, Notify me,
  "not for me"), split by age, region and language. That is exactly what Cold lacks today, and it needs a partner.
- **What is still unproven?** A buyer who says yes, the 2025 test (scored once, at the end), and a second market.

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

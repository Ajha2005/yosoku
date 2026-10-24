// Static copy for the Method section: how the India Demand Index is built and where its data comes from.

export const INDEX_PARTS = [
  { key: "yt", weight: 50, name: "YouTube comments from India", detail: "Trailer comments in Indian scripts, Hinglish or naming India." },
  { key: "nf", weight: 33, name: "Netflix India Top 10", detail: "Weeks a title spent in India's weekly chart." },
  { key: "wp", weight: 17, name: "Wikipedia views", detail: "Daily views of the English, Hindi, Tamil and Telugu articles, bots excluded." },
];

export const PRINCIPLES = [
  { n: "01", title: "Percentiles, not raw counts", body: "Each signal becomes a percentile among past titles. A missing signal is left out, never counted as zero, and the weights are rescaled. A title needs two signals to get an index." },
  { n: "02", title: "No hindsight", body: "Forecasts only use data available at the forecast moment. An automatic test fails the build if any input comes from later." },
  { n: "03", title: "Tested on the future", body: "Models train on 2019–2023, are checked on 2024, and are tested once on 2025. Each is compared with simple rules (genre average, sequel carry-over, global buzz)." },
  { n: "04", title: "Attention, not revenue", body: "The index measures how much India talks about, searches for and watches a title in its first 28 days. It does not measure sales." },
];

export const SOURCES = [
  { name: "YouTube trailer comments", tells: "India's own voice: comments in Indian scripts, Hinglish typed in Latin letters (“bhai hindi dub kab aayega”), or naming India, an Indian language or city. About 1 in 100 comments. AI4Bharat's IndicLID language model also catches short Hinglish the word list misses.",
    bias: "Most popular 200 titles only; newest 1,000 comments per video; a word list, so it misses some Indian English and catches a few non-Indian comments.", reliability: "Strong signal for big titles; sparse for small ones (many have none)." },
  { name: "Netflix India Top 10", tells: "Real viewing in India, published by Netflix.",
    bias: "Only Netflix titles, only from June 2021; a top-10 list hides everything below rank 10.", reliability: "Reliable but coarse; blank (not zero) for titles not on Netflix." },
  { name: "Wikipedia pageviews", tells: "Daily attention, bots excluded, in five languages (en, ja, hi, ta, te).",
    bias: "English views are global, not India-only; Indian-language articles exist mostly for big titles.", reliability: "Very reliable counts; weak India specificity." },
  { name: "AniList metadata", tells: "Genres, tags, source, studio, audience and sequel links.",
    bias: "Today's popularity and score include the outcome, so they are never model inputs.", reliability: "Reliable; audience tags are the only age proxy in public data." },
];

// The source scorecard on the Method page. Coverage comes from the data (predictions.json "sources");
// the columns here are judgements, written once. `part` links a row to its numbers.
export const SCORECARD = [
  { part: "youtube", name: "YouTube trailer comments from India", role: "Index 50% · model input",
    india: "High: Indian scripts, Hinglish or naming India", lead: "Months: trailers come out before launch",
    bias: "Top 200 titles only; newest 1,000 comments per video; misses Indian English" },
  { part: "streaming", name: "Netflix India Top 10", role: "Index 33%",
    india: "High: India's own chart", lead: "None: only after release",
    bias: "Netflix titles only, from June 2021; a top-10 list hides the rest" },
  { part: "wikipedia", name: "Wikipedia pageviews", role: "Index 17% · model input",
    india: "Low: English views are global", lead: "Weeks: articles exist before launch",
    bias: "Indian-language articles exist mostly for big titles" },
  { name: "AniList metadata", role: "Model input", coverage: "1,400 of 1,400",
    india: "None: describes the show", lead: "Full: known at announcement",
    bias: "Popularity and score are today's values, so they are never inputs" },
  { name: "India box office", role: "Check only", coverage: "6 films",
    india: "High", lead: "None: only after release",
    bias: "Six films with an India release; figures mix net and gross and some runs were unfinished" },
];

export const NOT_USED = [
  { name: "X / Twitter", why: "No usable free public API for historical posts." },
  { name: "AniList popularity and score", why: "Measured today, so they include how the show turned out: using them would be hindsight (leakage)." },
  { name: "Merchandise and ticket sales", why: "No public source by title and country." },
  { name: "Reddit", why: "A collector is built (Arctic Shift archive), but no Reddit data is in the current forecasts. It is global rather than India-specific, so it would only ever be a model input, never part of the index." },
];

// How a forecast becomes a verdict, for the Method page. The per-stage table under it is read from the data.
export const FORECAST_STEPS = [
  { title: "Closest past titles", body: "Find the 10 past titles most like this one by genres, tags, source, format, studio, audience and synopsis words, and average their India Demand Index, closest counting most." },
  { title: "Blend", body: "From T−28 on, a linear model weighs that average with the stage's buzz (Wikipedia views, trailer comments) and how the prequel did in India. Each forecast lists what moved it, in index points." },
  { title: "Beat a simple rule, or step aside", body: "Every stage is scored on the 2024 titles against simple rules anyone could apply. Where our model does not beat the best one, that rule makes the forecasts instead, and the forecast sheet says so." },
  { title: "An honest range", body: "The 80% range comes from how far forecasts missed on past seasons the model had not seen, so it is wide where the model is unsure." },
  { title: "Verdict from the range", body: "Launch only if even the low end of the range clears the launch line; Hold only if even the high end is under the hold line; anything else is Test-market. The lines are tuned on the 2024 titles." },
];

// What each simple rule does, shown wherever a rule makes the forecasts (keys match evaluation "used").
export const RULE_NOTES = {
  "Genre average": "the average India Demand Index of past titles in the same main genre",
  "Sequel carry-over": "the India Demand Index of its prequel, or the genre average if it has none",
  "Global buzz (en+ja Wikipedia)": "a straight line from English and Japanese Wikipedia views alone",
  "India Wikipedia alone": "a straight line from Hindi, Tamil and Telugu Wikipedia views alone",
  "India YouTube alone": "a straight line from trailer comments by people in India alone",
};

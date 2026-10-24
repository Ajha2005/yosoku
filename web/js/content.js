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
  { name: "YouTube trailer comments", tells: "India's own voice: comments in Indian scripts, Hinglish typed in Latin letters (“bhai hindi dub kab aayega”), or naming India, an Indian language or city. About 1 in 70 comments. AI4Bharat's IndicLID language model also catches short Hinglish the word list misses.",
    bias: "Most popular 200 titles only; newest 1,000 comments per video, unless the title is kept up to date daily; a word list, so it misses some Indian English and catches a few non-Indian comments.", reliability: "Strong signal for big titles; sparse for small ones (many have none, so one comment can move a title a long way)." },
  { name: "Netflix India Top 10", tells: "Real viewing in India, published by Netflix.",
    bias: "Only Netflix titles, only from June 2021; a top-10 list hides everything below rank 10.", reliability: "Reliable but coarse; blank (not zero) for titles not on Netflix." },
  { name: "Wikipedia pageviews", tells: "Daily attention, bots excluded, in five languages (en, ja, hi, ta, te).",
    bias: "English views are global, not India-only; Indian-language articles exist mostly for big titles.", reliability: "Very reliable counts; weak India specificity." },
  { name: "AniList metadata", tells: "Genres, tags, source, studio, audience and sequel links.",
    bias: "Today's popularity and score include the outcome, so they are never model inputs.", reliability: "Reliable; audience tags are the only age proxy in public data." },
];

// How a forecast becomes a verdict, for the Method page. The per-stage table under it is read from the data.
export const FORECAST_STEPS = [
  { title: "Closest past titles", body: "Find the 10 past titles most like this one by genres, tags, source, format, studio, audience and synopsis words, and average their India Demand Index, closest counting most." },
  { title: "Blend", body: "A linear model weighs that average with genre, format, source and audience, the stage's buzz (none at Cold; Wikipedia views and trailer comments from T−28 on) and how the prequel did in India. Each forecast lists what moved it, in index points." },
  { title: "Beat a simple rule, or step aside", body: "Every stage is scored on the 2024 titles against simple rules anyone could apply. Where our model does not beat the best one, that rule makes the forecasts instead, and the forecast sheet says so." },
  { title: "An honest range", body: "The 80% range comes from how far forecasts missed on past seasons the model had not seen, so it is wide where the model is unsure. For titles not released yet it also counts the latest season's misses, and only those of titles whose index includes YouTube, as theirs will." },
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

// How the project keeps up with data that arrives every day (Method page): what happens to a title as days pass.
export const STAYS_CURRENT = [
  { title: "Before the buzz", body: "From announcement to seven weeks before the premiere: a cold forecast from genre, source, studio and the closest past titles. The title list is refreshed daily, so announced start dates arrive on their own." },
  { title: "The run-up", body: "Days −49 to −1: Wikipedia views and trailer comments come in daily, new trailers are searched for weekly, and the forecast is made again every morning. The T−28 verdict is made on day −28." },
  { title: "Launch week", body: "Days 0 to +14: the forecast moves fastest here, and the T+7 verdict is made on day 7. A title that moves out of the range of its last verdict is flagged that day." },
  { title: "Measured", body: "Day +28: the India Demand Index is written, on the same scale as every past title, and the sealed forecast for the title can be graded. Netflix weeks keep counting to day +90." },
  { title: "Frozen", body: "After day +90 nothing about the title changes again, so it is never collected or recomputed: it joins the history the next titles are forecast from." },
];

// What keeps the record comparable as it grows (Method page).
export const KEPT_HONEST = [
  { name: "A frozen scale", why: "Each part of the index is ranked among a fixed set of past titles, so collecting new titles never moves an old label, and a sealed forecast is graded on the scale it was made on." },
  { name: "Every comment read the same way", why: "AI4Bharat's IndicLID reads each new comment the day it is collected, as it read the old ones." },
  { name: "No comment is missed", why: "Titles in play are fetched newest first until the newest comment already kept, every day, so a busy trailer no longer loses its launch week to a 1,000-comment cap." },
  { name: "Counts, not text", why: "Comments are kept as counts per title and day, with no text; view counts are kept for 30 days, as YouTube's rules require." },
  { name: "Ranges that learn", why: "Titles not released yet get 80% ranges from every season's misses so far, the latest one included, on the titles measured the way theirs will be: with YouTube." },
];

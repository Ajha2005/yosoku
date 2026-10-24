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
  { name: "YouTube trailer comments", tells: "India's own voice: comments in Indian scripts, Hinglish typed in Latin letters (“bhai hindi dub kab aayega”), or naming India, an Indian language or city. About 1 in 100 comments.",
    bias: "Most popular 200 titles only; newest 1,000 comments per video; a word list, so it misses some Indian English and catches a few non-Indian comments.", reliability: "Strong signal for big titles; sparse for small ones (many have none)." },
  { name: "Netflix India Top 10", tells: "Real viewing in India, published by Netflix.",
    bias: "Only Netflix titles, only from June 2021; a top-10 list hides everything below rank 10.", reliability: "Reliable but coarse; blank (not zero) for titles not on Netflix." },
  { name: "Wikipedia pageviews", tells: "Daily attention, bots excluded, in five languages (en, ja, hi, ta, te).",
    bias: "English views are global, not India-only; Indian-language articles exist mostly for big titles.", reliability: "Very reliable counts; weak India specificity." },
  { name: "AniList metadata", tells: "Genres, tags, source, studio, audience and sequel links.",
    bias: "Today's popularity and score include the outcome, so they are never model inputs.", reliability: "Reliable; audience tags are the only age proxy in public data." },
];

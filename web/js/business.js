// The Business tab: what the forecasts are worth to a buyer, who pays, and how the method travels to other markets.

import { MOMENTS, esc, pct, formatDate } from "./data.js?v=7";
import { verdictIcon } from "./charts.js?v=7";

const CUSTOMERS = [
  { who: "Indian streaming platforms and TV channels", decides: "Which titles to license, when to commit, and whether to dub.",
    buys: "A season subscription: every new title at all three stages." },
  { who: "Japanese studios and licensors", decides: "Which titles to offer India, and how to price India rights.",
    buys: "An India-readiness report on their catalogue. Every reason is already written in Japanese too." },
  { who: "Cinema chains and film distributors", decides: "Which anime films to bring to Indian cinemas, and in which languages.",
    buys: "A per-film brief before booking screens." },
  { who: "Dubbing studios", decides: "Which titles and Indian languages to pitch dubs for.",
    buys: "Dub demand and the language-hub map for each title." },
];

// Prices are starting hypotheses to test with buyers, not quotes.
const TIERS = [
  { name: "Title brief", price: "₹25–50k per title", body: "The one-page brief for a single title: verdict, 80% range, launch plan, closest past titles, dub demand and where in India." },
  { name: "Season subscription", price: "₹5–20 lakh a year", body: "Every new season's titles at Cold, T−28 and T+7, refreshed weekly, plus the Demand guide and the sealed track record." },
  { name: "Partner", price: "Custom or revenue share", body: "Adds a platform's own pre-launch signals (watchlist saves, Notify me, “not for me”) as model inputs, the signal our Cold forecasts lack today." },
];

const EDGE = [
  ["Built around the launch decision", "A verdict with its range and reasons, not a dashboard of numbers to interpret."],
  ["India-specific signals", "Hinglish and Indian-script trailer comments, Indian-language Wikipedia and Netflix India's own chart."],
  ["Honest about its limits", "Where our model loses to a simple rule, the rule is shipped and the page says so."],
  ["Cheap to run", "Public data only, so the cost of one more title or market is close to nothing."],
];

const ROADMAP = [
  ["Now", "Japanese anime in India", "1,400 titles, three forecast stages, sealed forecasts for the coming season."],
  ["Next", "The same anime in more markets", "Indonesia, Thailand, Brazil and Mexico are set up in the collectors: Netflix charts and local Wikipedia are ready; trailer-comment signals are India only so far."],
  ["Later", "More content, any direction", "K-dramas and Japanese films in India, and Indian films abroad, with partner signals from streaming platforms."],
];

/** Linear-interpolated quantile, as pandas computes it. */
function quantile(sorted, q) {
  const at = (sorted.length - 1) * q, lo = Math.floor(at), hi = Math.ceil(at);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (at - lo);
}

/** Per stage: how the backtest's Launch and Hold calls turned out against the real top and bottom thirds. */
function callsByStage(data) {
  const scored = data.titles.filter((t) => t.group === "validation" && t.actual_index != null);
  if (!scored.length) return { n: 0, rows: [] };
  const actual = scored.map((t) => t.actual_index).sort((a, b) => a - b);
  const top = quantile(actual, 2 / 3), bottom = quantile(actual, 1 / 3);
  const rows = Object.keys(MOMENTS).filter((m) => scored.some((t) => t.forecasts[m])).map((m) => {
    const called = (v) => scored.filter((t) => t.forecasts[m]?.verdict === v);
    const launch = called("Launch"), hold = called("Hold");
    return { moment: m, launch: launch.length, hits: launch.filter((t) => t.actual_index >= top).length,
             hold: hold.length, flops: hold.filter((t) => t.actual_index <= bottom).length };
  });
  return { n: scored.length, rows };
}

function proof(data, seal) {
  const { n, rows } = callsByStage(data);
  if (!n) return "";
  const best = [...rows].filter((r) => r.launch).sort((a, b) => b.launch - a.launch)[0];
  const headline = best ? `<div class="biz-proof">
      <span class="biz-big">${best.hits}<small> of ${best.launch}</small></span>
      <p><b>${MOMENTS[best.moment].label} Launch calls that were real hits.</b> On the ${n} titles of 2024, which the model never trained on,
        ${best.hits} of the ${best.launch} titles it called <i>Launch</i> at ${MOMENTS[best.moment].label} ended in the top third of real India demand.
        Picking at random lands there about one time in three.</p>
    </div>` : "";
  const cold = rows.find((r) => r.moment === "cold");
  const coldAllTest = cold && !cold.launch && !cold.hold;
  const table = rows.map((r) => `<tr><th scope="row">${MOMENTS[r.moment].label}<small>${esc(MOMENTS[r.moment].long)}</small></th>
      <td>${r.launch ? `${r.hits} of ${r.launch} <small>(${pct(r.hits / r.launch)})</small>` : "none called"}</td>
      <td>${r.hold ? `${r.flops} of ${r.hold}` : "none called"}</td></tr>`).join("");
  const sealed = seal?.sha256 ? `<p class="callout biz-seal"><b>Check us on the future, too.</b> ${esc(seal.titles)} forecasts for titles that have not aired were
      sealed on ${esc(formatDate(seal.date))} with a SHA-256 fingerprint. When they air they are scored against that file, so the track record
      grows every season and cannot be edited after the fact. <a href="#/forecasts">See the upcoming forecasts</a>.</p>` : "";
  return `<div class="scorecard-wrap reveal">
      <h2>What following our calls would have been worth</h2>
      ${headline}
      <div class="table-scroll" tabindex="0" role="region" aria-label="Backtest calls per stage, scrolls sideways on narrow screens"><table class="srccard biz-calls">
        <thead><tr><th scope="col">Stage</th><th scope="col">${verdictIcon("Launch")}Launch calls in the real top third</th><th scope="col">${verdictIcon("Hold")}Hold calls in the real bottom third</th></tr></thead>
        <tbody>${table}</tbody></table></div>
      <p class="note">The Launch and Hold lines were tuned on these same 2024 titles, so these rates are optimistic; the sealed 2025 test is the honest check.
        ${coldAllTest ? "At Cold every title is Test-market: before any buzz the ranges are too wide to call, which is itself the advice. Test small, then decide at T+7." : ""}</p>
      ${sealed}
    </div>`;
}

function customers(data) {
  const films = data.label_checks?.box_office || [];
  const biggest = films[0];
  const money = biggest ? `<p class="lead-sm">The money is real: <b>${esc(biggest.name)}</b> took about
      <b>₹${Math.round(biggest.india_gross_inr / 1e7)} crore</b> in Indian cinemas (sources on the <a href="#/method">Method</a> tab). One wrong rights deal or dub costs more than years of a subscription.</p>` : "";
  return `<div class="scorecard-wrap reveal">
      <h2>Who pays, and for which decision</h2>
      ${money}
      <div class="table-scroll" tabindex="0" role="region" aria-label="Customers, scrolls sideways on narrow screens"><table class="srccard">
        <thead><tr><th scope="col">Customer</th><th scope="col">The decision they make</th><th scope="col">What they buy</th></tr></thead>
        <tbody>${CUSTOMERS.map((c) => `<tr><th scope="row">${esc(c.who)}</th><td>${esc(c.decides)}</td><td>${esc(c.buys)}</td></tr>`).join("")}</tbody></table></div>
      <h3>Pricing <small class="biz-small">starting hypotheses, to test with buyers</small></h3>
      <div class="principles">${TIERS.map((t, i) => `<article class="principle reveal" style="--i:${i}"><span class="biz-price">${esc(t.price)}</span><h3>${esc(t.name)}</h3><p>${esc(t.body)}</p></article>`).join("")}</div>
    </div>`;
}

function scale(data) {
  const markets = Object.entries(data.markets || {});
  const titles = data.sources?.released;
  const rows = markets.map(([code, m]) => `<tr><th scope="row">${esc(m.name)}<small>${esc(code)}</small></th>
      <td>Netflix ${esc(m.name)} Top 10</td><td>${esc(m.wiki.join(", "))}<small>${esc(m.note)}</small></td>
      <td>${m.comments ? "Yes" : "Not yet"}</td><td>${code === "IN" ? "<b>Running</b>" : "Ready to collect"}</td></tr>`).join("");
  return `<div class="scorecard-wrap reveal">
      <h2>How it scales</h2>
      <ul class="notused">
        <li><b>A new market is a setting</b><span>Each data folder is collected for one country. Adding one is a line in <code>collectors/markets.py</code>
          (its Netflix chart and Wikipedia languages), then the same four collectors and the same model. Netflix publishes weekly charts for about 90 countries.</span></li>
        <li><b>A new title costs almost nothing</b><span>Every source is public and free: AniList, Wikipedia, Netflix's Top 10 file and YouTube's free quota.
          ${titles ? `The whole model reruns on ${Number(titles).toLocaleString("en-IN")} titles` : "The whole model reruns"} in about 30 seconds.</span></li>
        <li><b>It runs without an analyst</b><span>Collecting is scripted and resumable, forecasts are dated and sealed, and the site is static,
          so a season's update is a few commands and a push.</span></li>
      </ul>
      ${rows ? `<h3>Markets set up today</h3>
      <div class="table-scroll" tabindex="0" role="region" aria-label="Markets, scrolls sideways on narrow screens"><table class="srccard">
        <thead><tr><th scope="col">Market</th><th scope="col">Viewing</th><th scope="col">Local Wikipedia</th><th scope="col">Trailer comments</th><th scope="col">Status</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <p class="note">Outside India the index has two parts, Netflix and Wikipedia, until a comment word list exists for that country's languages.</p>` : ""}
      <h3>Roadmap</h3>
      <ol class="steps roadmap">${ROADMAP.map(([when, what, body]) => `<li><span class="pn">${esc(when)}</span><span><b>${esc(what)}</b>${esc(body)}</span></li>`).join("")}</ol>
    </div>`;
}

function edge() {
  return `<div class="scorecard-wrap reveal">
      <h2>Why us</h2>
      <p class="lead-sm">Global demand-measurement firms such as Parrot Analytics already sell cross-country TV demand data to studios, so buyers pay for this kind of answer.
        Yosoku's place is narrower and cheaper:</p>
      <ul class="notused">${EDGE.map(([head, body]) => `<li><b>${esc(head)}</b><span>${esc(body)}</span></li>`).join("")}</ul>
      <h3>What gets harder to copy every season</h3>
      <p class="lead-sm">Each season adds sealed forecasts scored against what happened, and more labelled titles to learn from. A newcomer can copy the code, not the dated track record.</p>
      <h3>What we still have to prove</h3>
      <ul class="notused">
        <li><b>A buyer who says yes</b><span>The prices above are hypotheses until a platform, licensor or distributor tests them.</span></li>
        <li><b>The 2025 test</b><span>Scored once, at the very end, so it cannot be tuned. It will show whether the 2024 rates hold.</span></li>
        <li><b>A second market</b><span>The collectors are ready for Indonesia, Thailand, Brazil and Mexico; none has been collected yet.</span></li>
      </ul>
    </div>`;
}

export function renderBusiness(app, host) {
  host.innerHTML = `${proof(app.data, app.seal)}${customers(app.data)}${scale(app.data)}${edge()}`;
}

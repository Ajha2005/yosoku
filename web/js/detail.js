// The forecast sheet: one title, its verdict and the evidence behind it, in a modal drawer.

import { VERDICTS, MOMENTS, safeUrl, esc, round, pct, formatDate, titleCase, momentsOf, latestMoment, ruleText } from "./data.js?v=8";
import { posterHTML } from "./art.js?v=8";
import { gauge, seal, verdictIcon, drivers, lookalikes, regionMap, bindRegions, stageTimeline, trajectoryChart } from "./charts.js?v=8";
import { showTip, hideTip, showToast } from "./tip.js?v=8";
import { RULE_NOTES } from "./content.js?v=8";
import { ringiHTML } from "./ringi.js?v=8";

const THIN_REGION = 30;   // fewer hub-pointing comments than this behind a map: say so on the page
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const CALENDAR = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7ZM4 10h16M8 3v4M16 3v4"/></svg>';
const LOCK = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 11h12v9H6v-9ZM8.5 11V8a3.5 3.5 0 0 1 7 0v3"/></svg>';

export function countUp(el, to, ms = 900) {
  if (reduced) { el.textContent = to; return; }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min(1, (now - start) / ms);
    el.textContent = Math.round(to * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** How past titles did in each release window, with this title's window marked. Describes, does not predict. */
function windowSection(t, evidence, minN) {
  if (!evidence) return "";
  const shown = Object.entries(evidence).filter(([, w]) => w.n >= minN && w.mean != null);
  if (shown.length < 2) return "";
  const own = evidence[t.release_window];
  const base = own && own.n >= minN ? own.mean : null;
  const spread = Math.max(...shown.map(([, w]) => w.mean)) - Math.min(...shown.map(([, w]) => w.mean));
  const rows = Object.entries(evidence).map(([name, w]) => {
    const ok = w.n >= minN && w.mean != null, mine = name === t.release_window;
    const diff = ok && base != null && !mine ? w.mean - base : null;
    return `<li class="win${mine ? " is-mine" : ""}">
      <span class="win-name">${esc(name)}${mine ? "<em>this title</em>" : ""}</span>
      <span class="win-track" aria-hidden="true">${ok ? `<i style="width:${w.mean}%"></i>` : ""}</span>
      <span class="win-val">${ok ? round(w.mean) : "–"}</span>
      <span class="win-extra">${ok ? (diff == null ? `${w.n} titles` : `${diff >= 0 ? "+" : "−"}${Math.abs(diff).toFixed(1)}`) : `only ${w.n}`}</span>
    </li>`;
  }).join("");
  const verdict = spread < 5
    ? "Past titles did about equally well in every window, so moving the release date is unlikely to change much on its own."
    : "Past titles did noticeably better in some windows; weigh this against what else differed between them.";
  return `<ul class="wins">${rows}</ul>
    <p class="callout">${verdict}</p>
    <p class="note">Average India Demand Index of the labelled past titles that started in each window, and the difference from this title's window. Windows with fewer than ${esc(minN)} titles are not shown. An association, not a cause: few anime start in Feb–Mar because Japanese seasons start in January and April.</p>`;
}

/** A sealed stage shows the numbers in the sealed file, which the title will be graded on; say so, and what the
 *  current model says today if that differs. */
function sealedNote(f) {
  if (!f.sealed) return "";
  const now = f.now;
  const moved = now && ["index", "low", "high", "verdict"].some((k) => now[k] !== f[k]);
  const wider = moved && now.high - now.low > f.high - f.low + 1;
  return `<p class="flag sealed">${LOCK}<span><b>Sealed ${esc(formatDate(f.sealed.date))}.</b> These are the numbers in the sealed file; this title will be graded on them.${moved
    ? ` Today the current model says ${round(now.index)} (80% range ${round(now.low)}–${round(now.high)}), ${esc(now.verdict)}.${wider
      ? " Its range is wider: ranges for titles not released yet now come from the misses of past titles whose index includes YouTube, as this title's will." : ""}` : ""}</span></p>`;
}

/** The chance of a top-third result, given only at stages where it beats the base rate by enough (models.top_third),
 *  with how often its confident calls came true. */
function chanceLine(p, top) {
  if (p == null || !top) return "";
  const record = top.sure_calls ? ` When it says ${pct(top.sure)} or more, ${pct(top.sure_right)} of ${top.sure_calls} past calls came true.` : "";
  return `<p class="chance"><b>${pct(p)}</b><span>chance of a top-third result in India: an index of ${round(top.line_live)} or more.${record}</span></p>`;
}

/** An amount in the partner's unit: yen, rupees, dollars or viewing hours (yosoku/money.py). */
export function amountText(x, money) {
  const n = Math.round(x).toLocaleString("en-GB");
  return money.unit === "HOURS" ? `${n} hours` : `${money.symbol}${n}`;
}

/** What the forecast is worth: a range in money on a site exported with a partner's figures, else what it would take. */
function moneySection(f, money) {
  const body = f.money && money
    ? `<div class="dub"><span class="dub-n">${esc(amountText(f.money.point, money))}</span>
        <span>forecast for India (80% range ${esc(amountText(f.money.low, money))} to ${esc(amountText(f.money.high, money))}),
        from the India Demand Index forecast and what ${esc(money.titles)} past titles earned there.</span></div>
       <p class="note">Each 10 points of the index went with ${money.per_10_points >= 0 ? "+" : "−"}${pct(Math.abs(money.per_10_points))} in ${esc(money.unit)}.
        Left out one at a time, the fit ranked those titles at ${money.rank_correlation.toFixed(2)} and missed by ${pct(money.median_miss)} at the median.</p>`
    : `<p class="callout">Not on this site. With what 30 or more past titles earned in India, shared by a rights holder or platform,
        every forecast gets a range in yen (or rupees, or viewing hours). The figures stay private: see <code>data/partner/README.md</code>.</p>`;
  return `<section class="d-section d-money"><h3>What it's worth <small>in money, with a partner's figures</small></h3>${body}</section>`;
}

/** Where else a title could travel: the countries whose Netflix Top 10 its closest past titles reached
 *  (yosoku/markets.py), and, for a past title, where it did. India is always listed. */
function marketsSection(t, info) {
  const m = t.markets;
  if (!m && !t.charted?.length) return "";
  const own = t.charted?.length ? `<p class="callout">It reached Netflix's Top 10 in ${t.charted.length} ${t.charted.length === 1 ? "country" : "countries"}
      within six months of its Japanese start: ${esc(t.charted.join(", "))}.</p>` : "";
  const list = m ? `<ul class="wins">${m.countries.map((c) => `<li class="win${c.iso2 === "IN" ? " is-mine" : ""}">
      <span class="win-name">${esc(c.name)}</span>
      <span class="win-track" aria-hidden="true"><i style="width:${(100 * c.share).toFixed(0)}%"></i></span>
      <span class="win-val">${esc(c.titles)}/${esc(m.of)}</span>
      <span class="win-extra">typical ${pct(c.typical)}</span></li>`).join("")}</ul>
    <p class="note">Of the ${esc(m.of)} most similar past titles that reached a Netflix Top 10 anywhere, how many reached it in each
      country within six months of their Japanese start; typical is the share of all such titles. Netflix only: a title has to
      be on Netflix to chart.${info?.auc ? ` Checked on past titles, these shares rank the titles that charted in a country above
      the rest at ${info.auc.toFixed(2)} on average over ${esc(info.countries_checked)} countries (0.5 is chance; titles of the same
      genre: ${info.genre_auc.toFixed(2)}).` : ""}</p>` : "";
  return `<section class="d-section d-markets"><h3>Where else it could travel <small>Netflix's Top 10 in other countries</small></h3>${own}${list}</section>`;
}

/** What to do with this forecast: the decision, when to revisit it, which dub first and whether to move the date.
 *  Built from evidence on the sheet and the decision clock (Track record), so every step can be traced. */
function launchPlan(t, f, moment, data) {
  const later = data.thresholds["t+7"];
  const steps = [];
  const decide = {
    Launch: ["Commit to India", "License, market and schedule a full release now: the whole 80% range clears the launch line."],
    "Test-market": moment === "t+7"
      ? ["Stay in limited release", "A week in, it has shown neither enough to commit nor little enough to drop."]
      : ["License for a limited release", "Subtitled streaming with little marketing spend, and a small minimum guarantee with a top-up tied to the T+7 verdict: enough to learn, cheap to stop."],
    Hold: moment === "t+7"
      ? ["Drop or delay the India push", "Launch-week attention from India stayed low."]
      : ["Don't commit yet", "The whole range sits under the hold line. Revisit only if launch-week buzz appears."],
  }[f.verdict];
  steps.push(decide);
  if (moment !== "t+7" && later) {
    const rule = later.launch_line === later.hold_line
      ? `Launch if the low end of the range reaches ${later.launch_line}, Hold if the high end stays under it`
      : `Launch if the low end reaches ${later.launch_line}, Hold if the high end stays under ${later.hold_line}`;
    const ev = data.evaluation?.moments || {}, r = (k) => ev[k]?.table.spearman[ev[k].used ?? ev[k].main];
    const now = r(moment), then = r("t+7");
    // The decision clock says how fast the evidence arrives: little before the premiere, most in its first days.
    const clock = data.clock || [], at = (day) => clock.find((d) => d.day === day)?.rolling;
    const [before, day3, day7] = [at(-7), at(3), at(7)];
    const why = [before, day3, day7].every(Number.isFinite)
      ? ` Over ${clock[0].seasons} seasons of backtests, forecasts ranked titles at ${before.toFixed(2)} a week before the premiere, ${day3.toFixed(2)} three days after it and ${day7.toFixed(2)} at T+7: line up the dub and marketing from day 3, commit at T+7.`
      : Number.isFinite(now) && Number.isFinite(then) && then > now
        ? ` On 2024 titles, forecasts at this stage ranked titles at ${now.toFixed(2)}; a week after launch, at ${then.toFixed(2)}.` : "";
    steps.push(["Decide again at T+7", `One week after the Japanese premiere, with launch-week signals in. ${rule}.${why}`]);
  }
  const dub = f.dub_demand || {}, typical = data.dub_typical;
  const hubs = Object.entries(f.regions || {}).filter(([, s]) => s >= 0.1).sort((a, b) => b[1] - a[1]).map(([h]) => h);
  const thin = f.region_comments != null && f.region_comments < THIN_REGION;
  const order = hubs.length ? `${hubs[0]} first${hubs[1] ? `, then ${hubs.slice(1, 3).join(" and ")}` : ""}${thin ? ` (thin evidence${moment === "t+7" ? "" : ": confirm at T+7"})` : ""}` : "";
  if (dub.share != null && Number.isFinite(typical)) {
    const ratio = dub.share / typical;
    steps.push(ratio >= 1.2
      ? ["Plan a dub early", `Fans of similar titles asked for a dub ${pct(dub.share)} of the time, against ${pct(typical)} for a typical title.${order ? ` Language order from the hub map: ${order}.` : ""}`]
      : ratio <= 0.8
        ? ["Subtitles first", `Dub requests are below typical (${pct(dub.share)} against ${pct(typical)}). Add a dub only if ${moment === "t+7" ? "early viewing" : "T+7"} shows demand${order ? `; ${order}` : ""}.`]
        : ["Dub when the release widens", `Dub interest is typical (${pct(dub.share)} against ${pct(typical)}).${order ? ` Language order from the hub map: ${order}.` : ""}`]);
  } else if (order) {
    steps.push(["Dub languages", `No dub-request evidence, but the hub map points to ${order}.`]);
  }
  const ev = data.window_evidence, minN = data.min_evidence;
  if (ev) {
    const shown = Object.entries(ev).filter(([, w]) => w.n >= minN && w.mean != null);
    const own = ev[t.release_window];
    const best = shown.sort((a, b) => b[1].mean - a[1].mean)[0], worst = shown[shown.length - 1];
    const even = !best || best[1].mean - worst[1].mean < 5;
    if (!t.release_window) steps.push(["Release date", even
      ? "Not announced yet. Past titles did about equally well in every window, so there is no window to avoid."
      : `Not announced yet. Past titles did best in ${best[0]} (average ${round(best[1].mean)}). An association, not a promise.`]);
    else if (best && own && own.n >= minN && best[1].mean - own.mean >= 5 && best[0] !== t.release_window)
      steps.push(["Consider another window", `Past titles in ${best[0]} averaged ${round(best[1].mean)}, against ${round(own.mean)} in this title's window. An association, not a promise.`]);
    else steps.push(["Keep the date", "Past titles did about equally well in every release window."]);
  }
  return `<ol class="plan">${steps.map(([head, body], i) => `<li><span class="plan-n">${i + 1}</span><div><b>${esc(head)}</b><p>${esc(body)}</p></div></li>`).join("")}</ol>`;
}

/** The points for a title's forecast chart: a 2024 title's forecast on every clock day, or the forecasts the daily
 *  job (yosoku/daily.py) has logged so far for an upcoming one. */
function pathRows(t, clock) {
  if (t.trajectory) return clock.map((d, i) => ({ day: d.day, value: t.trajectory[i], lo: t.trajectory[i] - d.width, hi: t.trajectory[i] + d.width }));
  return (t.history || []).map((h) => ({ day: h.day, value: h.index, lo: h.low, hi: h.high, date: h.date, top: h.top_third }));
}

/** How a 2024 title's forecast moved over the decision clock; for an upcoming title, how it is moving (with the daily
 *  job's alert, if it moved out of its verdict's range) and when the next verdict comes. */
function movedSection(t, data, daily) {
  const clock = data.clock, rows = clock ? pathRows(t, clock) : [];
  const rules = Object.entries(data.thresholds).filter(([, th]) => th.method !== "Blend").map(([key]) => MOMENTS[key].label);
  const ruleNote = rules.length ? ` At ${esc(rules.join(" and "))} a simple rule makes the verdict instead, so the number above can differ.` : "";
  let chart = "";
  if (t.trajectory && rows.length) {
    const said = Object.entries(MOMENTS).map(([key, m]) => [m.label, rows.find((r) => (key === "cold" ? r.day === "cold" : clock.find((d) => d.day === r.day)?.stage === key))])
      .filter(([, r]) => r && Number.isFinite(r.value)).map(([label, r]) => `${round(r.value)} at ${label}`).join(", ");
    chart = `<section class="d-section d-moved"><h3>How the forecast moved <small>day by day, as the buzz came in</small></h3>
      <div class="traj-host" id="traj"></div>
      <p class="note">Our model's forecast for this title on each day of the decision clock: ${esc(said)}${t.actual_index != null ? `; it ended at ${round(t.actual_index)}` : ""}.
        Shaded: that day's 80% range. From the premiere on it is a nowcast.${ruleNote}</p></section>`;
  } else if (rows.length) {
    const first = rows[0], last = rows[rows.length - 1];
    const alerts = (daily?.alerts || []).filter((a) => a.anilist_id === t.anilist_id).map((a) => esc(a.text)).join(" ");
    chart = `<section class="d-section d-moved"><h3>How the forecast is moving <small>made again each day</small></h3>
      ${alerts ? `<p class="flag moved"><span><b>Moved since its last verdict</b> (${esc(formatDate(daily.date))}). ${alerts}</span></p>` : ""}
      <div class="traj-host" id="traj"></div>
      <p class="note">Our model's forecast for this title as the daily job has made it: ${round(first.value)} on ${esc(formatDate(first.date))}${rows.length > 1
        ? `, ${round(last.value)} on ${esc(formatDate(last.date))}` : ""}.${last.top != null ? ` Chance of a top-third result in India: ${pct(last.top)}.` : ""}
        Shaded: the 80% range on each day. It fills in as the premiere nears.${ruleNote}</p></section>`;
  }
  if (t.group !== "upcoming") return chart;
  const next = [["t-28", -28], ["t+7", 7]].filter(([key]) => !momentsOf(t).includes(key));
  if (!next.length) return chart;
  const on = (days) => formatDate(new Date(Date.parse(`${t.start_date}T00:00:00Z`) + days * 864e5).toISOString().slice(0, 10));
  return `${chart}<section class="d-section"><h3>Next verdicts <small>made at the stages, with the buzz in by then</small></h3>
    <p class="callout">${t.start_date
      ? `This title is judged again at ${next.map(([key, days]) => `<b>${MOMENTS[key].label}</b> on ${esc(on(days))}`).join(" and ")}.`
      : `The start date is not announced yet. Once it is, the title is judged again 28 days before the premiere and 7 days after it.`}</p></section>`;
}

let trajObserver;

export function createDetail(app, { requestClose }) {
  const dlg = document.getElementById("sheet");
  const body = document.getElementById("sheet-body");
  const scroller = document.getElementById("sheet-scroll");
  let order = [], current = null;

  const byId = (id) => app.data.titles.find((t) => t.anilist_id === Number(id));

  function neighbours() {
    const i = order.indexOf(current.id);
    if (i < 0 || order.length < 2) return [null, null];
    return [order[(i - 1 + order.length) % order.length], order[(i + 1) % order.length]];
  }

  function stageSwitch(title, moment) {
    const have = momentsOf(title);
    return `<div class="seg seg-sm" role="group" aria-label="Forecast stage">${Object.entries(MOMENTS).map(([key, m]) => {
      const ok = have.includes(key);
      return `<button type="button" data-moment="${key}" aria-pressed="${key === moment}" ${ok ? "" : "disabled"} title="${esc(ok ? m.long : "Not available yet: this title has not reached this stage")}">${m.label}</button>`;
    }).join("")}</div>`;
  }

  function render() {
    const t = byId(current.id);
    const moment = current.moment;
    const f = t.forecasts[moment];
    // A sealed stage is drawn on the lines it was sealed with, as the downloadable file has it.
    const lines = f.sealed ? { ...app.data.thresholds[moment], launch_line: f.sealed.launch_line, hold_line: f.sealed.hold_line } : app.data.thresholds[moment];
    const v = VERDICTS[f.verdict];
    const cover = app.covers[t.anilist_id];
    const banner = safeUrl(cover?.b);   // a still frame from the anime itself
    const actual = t.actual_index;
    const inside = actual != null && actual >= f.low && actual <= f.high;
    const [prev, next] = neighbours();
    document.getElementById("sheet-prev").disabled = document.getElementById("sheet-next").disabled = prev == null;
    if (prev != null) {
      document.getElementById("sheet-prev").title = `Previous: ${byId(prev).name}`;
      document.getElementById("sheet-next").title = `Next: ${byId(next).name}`;
    }

    const chips = [...t.genres.map(esc), t.audience !== "Not tagged" ? esc(t.audience) : "", t.is_sequel ? "Sequel" : ""].filter(Boolean)
      .map((c) => `<li>${c}</li>`).join("");
    const flags = t.release_window_flags.map((x) => `<p class="flag">${CALENDAR}<span><b>Release window.</b> ${esc(x)}</span></p>`).join("");
    const result = actual == null ? "" : `<div class="result ${inside ? "in" : "out"}">
        <span class="result-n">${round(actual)}</span>
        <span><b>What actually happened</b><br>India Demand Index ${round(actual)}, ${actual - f.index >= 0 ? "+" : "−"}${Math.abs(round(actual - f.index))} against the forecast.
        ${inside ? "Inside" : "Outside"} the 80% range.</span></div>`;
    const rule = RULE_NOTES[lines.method];
    const whySection = f.drivers.length
      ? `${drivers(f.drivers)}<p class="note">Exact contributions from the linear model: blue raises the index, red lowers it.</p>`
      : rule
        ? `<p class="callout">At this stage a simple rule makes the forecast: <b>${esc(lines.method)}</b>, ${esc(rule)}. It beat our model on the 2024 titles, so we use it. The closest past titles below still come from our model.</p>`
        : `<p class="callout">No single signal moved this forecast by half a point or more against an average title.</p>`;
    const regionsSection = f.regions && Object.keys(f.regions).length
      ? `${f.region_comments != null && f.region_comments < THIN_REGION ? `<p class="flag thin"><span><b>Thin evidence.</b> This map rests on only ${esc(f.region_comments)} comment${f.region_comments === 1 ? "" : "s"}; read it as a hint, not a measurement.</span></p>` : ""}
        ${regionMap(f.regions, app.data.hubs)}<p class="note">Estimated from ${f.region_comments != null ? `<b>${esc(f.region_comments)}</b> ` : ""}trailer comments that point to a language (its script, its name, or Hinglish for Hindi) on the ${esc(f.region_titles)} closest past titles that had any. English-speaking fans are spread across India and are not counted here; Hindi includes Marathi.</p>`
      : `<p class="callout">None of the closest past titles had trailer comments pointing to an Indian language, so there is no regional estimate.</p>`;

    const dub = f.dub_demand || {};
    const typical = app.data.dub_typical;
    const dubSection = dub.share == null
      ? `<p class="callout">None of the closest past titles had trailer comments from India, so there is no dub estimate.</p>`
      : `<div class="dub"><span class="dub-n">${pct(dub.share)}</span>
          <span>of Indian trailer comments on the ${esc(dub.titles)} closest past title${dub.titles > 1 ? "s" : ""} asked for or about a Hindi, Tamil or other Indian-language dub${
            Number.isFinite(typical) ? `, against ${pct(typical)} for a typical past title` : ""}.</span></div>
        <p class="note">Read from comments like "hindi dub kab aayega" or "please dub in tamil"; channel posts with links are left out. A high share suggests a dub would widen the audience beyond subtitle viewers.</p>`;
    const whatIf = windowSection(t, app.data.window_evidence, app.data.min_evidence);

    body.innerHTML = `<article class="detail v-${v.cls}" style="--k:${/^#[0-9a-f]{3,8}$/i.test(cover?.k) ? cover.k : "var(--k-default)"}">
      <header class="d-hero${banner ? " has-banner" : ""}">
        ${banner ? `<div class="d-backdrop" style="background-image:url('${banner}')"></div>` : ""}
        <div class="d-hero-inner">
          <div class="d-poster">${posterHTML(t, cover)}</div>
          <div class="d-head">
            <p class="eyebrow">${esc(t.season)} · ${esc(t.format)} · ${esc(titleCase(t.source))}</p>
            <h2 id="sheet-title">${esc(t.name)}</h2>
            ${t.title_japanese ? `<p class="d-jp" lang="ja">${esc(t.title_japanese)}</p>` : ""}
            <ul class="chips-static">${chips}</ul>
            <p class="d-date">Starts in Japan <b>${t.start_date ? esc(formatDate(t.start_date)) : `${esc(t.season)}, date not announced`}</b></p>
            ${flags}
          </div>
        </div>
      </header>

      <section class="d-verdict" aria-label="Verdict">
        <div class="d-verdict-top">
          <div class="stamp">${seal(f.verdict)}
            <div><span class="label">Verdict <span lang="ja" class="label-ja">${v.ja}</span></span><strong class="word">${verdictIcon(f.verdict)}${esc(f.verdict)}</strong></div>
          </div>
          <div class="stage"><span class="label">Forecast stage</span>${stageSwitch(t, moment)}</div>
        </div>
        <div class="d-score">
          <span class="d-big"><span data-count="${round(f.index)}">${round(f.index)}</span></span>
          <span class="d-score-text"><b>India Demand Index</b><br>80% range ${round(f.low)}–${round(f.high)}. ${esc(MOMENTS[moment].note)}</span>
        </div>
        ${chanceLine(f.top_third, app.data.evaluation?.moments?.[moment]?.top_third)}
        ${gauge(f, lines, actual)}
        <p class="note rule">${esc(ruleText(lines))}</p>
        ${sealedNote(f)}
        <div class="reason">
          <p>${esc(f.reason_en)}</p>
          <p lang="ja" class="ja">${esc(f.reason_ja)}</p>
        </div>
        ${result}
      </section>

      <section class="d-section d-plan"><h3>Launch plan <small>what to do with this forecast</small></h3>${launchPlan(t, f, moment, app.data)}</section>
      ${moneySection(f, app.data.money)}
      <section class="d-section"><h3>What moves this forecast</h3>${whySection}</section>
      <section class="d-section d-stage"><h3>What this forecast could see <small>${esc(MOMENTS[moment].label)}</small></h3>
        ${stageTimeline([moment], moment)}
        <p class="note">${esc(MOMENTS[moment].detail)}</p>
      </section>
      ${movedSection(t, app.data, app.daily)}
      <section class="d-section"><h3>Closest past titles <small>and how they did in India</small></h3>
        ${lookalikes(f.lookalikes, (l) => posterHTML({ anilist_id: l.anilist_id, title_japanese: "" }, app.covers[l.anilist_id]))}
        <p class="note">Similarity combines genres, tags, source, format, studio, audience and synopsis words. The badge is each past title's India Demand Index.</p>
      </section>
      ${marketsSection(t, app.data.markets)}
      <section class="d-section"><h3>Where in India <small>language hubs</small></h3>${regionsSection}</section>
      <section class="d-section d-dub"><h3>Dub demand <small>from fans of similar titles</small></h3>${dubSection}</section>
      ${whatIf ? `<section class="d-section d-whatif"><h3>Release window what-if <small>how past titles did</small></h3>${whatIf}</section>` : ""}
      ${t.synopsis ? `<details class="d-syn"><summary>Synopsis</summary><p>${esc(t.synopsis)}</p></details>` : ""}
    </article>`;

    const big = body.querySelector("[data-count]");
    if (big) countUp(big, Number(big.dataset.count));
    trajObserver?.disconnect();
    const traj = body.querySelector("#traj");
    if (traj) {
      const rows = pathRows(t, app.data.clock);
      trajObserver = new ResizeObserver(() => trajectoryChart(traj, app.data.clock, rows, t.actual_index));
      trajObserver.observe(traj);
    }
  }

  /** Print `content` on its own, in the light theme. */
  function printPage(content, kind = "") {
    const html = document.documentElement, theme = html.dataset.theme;
    const root = document.createElement("div");
    root.id = "print-root";
    root.className = kind;
    root.innerHTML = content;
    document.body.append(root);
    html.dataset.theme = "light";
    html.classList.add("printing");
    const done = () => { root.remove(); html.classList.remove("printing"); html.dataset.theme = theme; };
    addEventListener("afterprint", done, { once: true });
    print();
  }

  /** A one-page brief for executives: this title's sheet, on its own. */
  function printBrief() {
    printPage(`<p class="print-head"><b>Yosoku 予測</b> · India launch brief · ${esc(MOMENTS[current.moment].label)} forecast · ${esc(location.href)}</p>${body.innerHTML}`);
  }

  /** The same decision as a Japanese ringi-sho, the form a Japanese company approves it on (web/js/ringi.js). */
  function printRingi() {
    printPage(ringiHTML(byId(current.id), current.moment, app.data, app.seal), "ringi");
  }

  function show(id, moment) {
    const t = byId(id);
    if (!t) return false;
    const have = momentsOf(t);
    const chosen = have.includes(moment) ? moment : latestMoment(t);
    const changed = current && current.id !== t.anilist_id;
    current = { id: t.anilist_id, moment: chosen };
    const keep = scroller.scrollTop;
    render();
    scroller.scrollTop = changed || !dlg.open ? 0 : keep;
    if (!dlg.open) {
      dlg.showModal();
      document.documentElement.classList.add("locked");
    }
    return chosen;
  }

  function close() {
    if (!dlg.open) return;
    hideTip();
    const finish = () => { dlg.close(); document.documentElement.classList.remove("locked"); dlg.classList.remove("closing"); };
    if (reduced) return finish();
    dlg.classList.add("closing");
    setTimeout(finish, 180);
  }

  // Keep the address in step with the sheet, without adding history entries.
  const sync = () => history.replaceState(history.state, "", `#/title/${current.id}/${encodeURIComponent(current.moment)}`);

  function go(id) {
    if (id == null) return;
    show(id, current.moment);
    sync();
  }

  body.addEventListener("click", (e) => {
    const stage = e.target.closest("[data-moment]");
    if (stage && !stage.disabled) {
      current.moment = stage.dataset.moment;
      render(); sync();
      body.querySelector(`[data-moment="${current.moment}"]`)?.focus({ preventScroll: true });   // keep keyboard focus where it was
    }
  });

  document.getElementById("sheet-prev").addEventListener("click", () => go(neighbours()[0]));
  document.getElementById("sheet-next").addEventListener("click", () => go(neighbours()[1]));
  document.getElementById("sheet-close").addEventListener("click", requestClose);
  document.getElementById("sheet-share").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); showToast("Link copied"); }
    catch { showToast("Copy the address bar to share this forecast"); }
  });
  document.getElementById("sheet-print").addEventListener("click", printBrief);
  document.getElementById("sheet-ringi").addEventListener("click", printRingi);
  scroller.addEventListener("scroll", hideTip, { passive: true });
  dlg.addEventListener("cancel", (e) => { e.preventDefault(); requestClose(); });          // Esc
  dlg.addEventListener("click", (e) => { if (e.target === dlg) requestClose(); });          // click on the dimmed backdrop
  // On the document, not the dialog: re-rendering the sheet drops focus to <body>, which is outside the dialog.
  document.addEventListener("keydown", (e) => {
    if (!dlg.open || e.altKey || e.ctrlKey || e.metaKey || e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowLeft") go(neighbours()[0]);
    if (e.key === "ArrowRight") go(neighbours()[1]);
  });

  bindRegions(body);

  return {
    show, close,
    isOpen: () => dlg.open,
    setOrder: (ids) => { order = ids; },
    currentId: () => current?.id,
  };
}

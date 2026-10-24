// Charts, hand-built from HTML and SVG so they stay light, crisp and themeable. Each returns markup (or fills a node).

import { VERDICTS, MOMENTS, HUB_STATES, esc, round, pct, clamp, formatDate } from "./data.js?v=9";
import { INDIA } from "./india-map.js?v=9";
import { showTip, hideTip } from "./tip.js?v=9";

const vclass = (verdict) => VERDICTS[verdict]?.cls ?? "test";

export function verdictIcon(verdict) {
  return `<svg class="vicon" viewBox="0 0 24 24" aria-hidden="true">${VERDICTS[verdict].icon}</svg>`;
}

/** A hanko-style stamp: two characters from the verdict's Japanese label. Decoration only; the English word always sits beside it. */
export function seal(verdict) {
  const [a, b] = VERDICTS[verdict].seal;
  return `<span class="seal seal-${vclass(verdict)}" aria-hidden="true" lang="ja"><span>${a}</span><span>${b}</span></span>`;
}

/** The 0-100 index with its verdict zones, 80% range, forecast marker and (if known) what really happened. */
export function gauge(forecast, lines, actual) {
  const { index, low, high, verdict } = forecast;
  const hold = lines.hold_line, launch = lines.launch_line, single = hold === launch;
  const zones = single
    ? `<i class="z z-hold" style="left:0;width:${hold}%"></i><i class="z z-launch" style="left:${hold}%;width:${100 - hold}%"></i>`
    : `<i class="z z-hold" style="left:0;width:${hold}%"></i><i class="z z-test" style="left:${hold}%;width:${launch - hold}%"></i>` +
      `<i class="z z-launch" style="left:${launch}%;width:${100 - launch}%"></i>`;
  const marks = single
    ? `<span class="g-line" style="left:${hold}%"><em class="mid">Line ${hold}</em></span>`
    : `<span class="g-line" style="left:${hold}%"><em class="end">Hold line ${hold}</em></span>` +
      `<span class="g-line" style="left:${launch}%"><em class="start">Launch line ${launch}</em></span>`;
  const flag = actual == null ? "" :
    `<span class="g-actual" style="left:${clamp(actual, 0, 100)}%"><em>Actual ${round(actual)}</em></span>`;
  return `<div class="gauge g-${vclass(verdict)}" role="img"
      aria-label="India Demand Index forecast ${round(index)}, 80% range ${round(low)} to ${round(high)}, verdict ${esc(verdict)}${actual == null ? "" : `, actual ${round(actual)}`}">
    <div class="g-stage">
      ${marks}
      <div class="g-track">${zones}</div>
      <b class="g-range" style="left:${clamp(low, 0, 100)}%;width:${clamp(high, 0, 100) - clamp(low, 0, 100)}%"></b>
      <span class="g-marker" style="left:${clamp(index, 0, 100)}%"><em>${round(index)}</em></span>
      ${flag}
    </div>
    <div class="g-ticks" aria-hidden="true"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
  </div>`;
}

/** Tiny range bar for the poster cards. */
export function miniBar(forecast) {
  const { index, low, high, verdict } = forecast;
  return `<span class="mini mini-${vclass(verdict)}" aria-hidden="true">
    <i class="mini-range" style="left:${clamp(low, 0, 100)}%;width:${clamp(high, 0, 100) - clamp(low, 0, 100)}%"></i>
    <b class="mini-dot" style="left:${clamp(index, 0, 100)}%"></b></span>`;
}

// The timeline runs from day -56 to the end of launch week, counted from the Japanese premiere (day 0).
const DAY_FROM = -56, DAY_TO = 7;
const dayPos = (day) => ((day - DAY_FROM) / (DAY_TO - DAY_FROM)) * 100;
export const dayText = (day) => (day < 0 ? `−${-day}` : day > 0 ? `+${day}` : "0");

/** Where each stage's buzz window sits around the Japanese premiere. keys: the stages to draw; active: the one to highlight. */
export function stageTimeline(keys, active) {
  const ticks = [-56, -28, 0, 7].map((day, i, all) =>
    `<span class="st-tick${i === 0 ? " st-first" : i === all.length - 1 ? " st-last" : ""}" style="left:${dayPos(day)}%">${dayText(day)}</span>`).join("");
  const rows = keys.map((key) => {
    const m = MOMENTS[key], [from, to] = m.days ?? [];
    const label = m.days ? `${m.label} uses days ${dayText(from)} to ${dayText(to)} and is made on day ${dayText(m.made)}, counted from the Japanese premiere.`
      : `${m.label} uses no buzz data.`;
    return `<li class="st-row${key === active ? " is-active" : ""}">
      <div class="st-name"><b>${m.label}</b><span>${esc(m.long)}</span></div>
      <div class="st-track" role="img" aria-label="${esc(label)}">
        <i class="st-day0" style="left:${dayPos(0)}%"></i>
        ${m.days ? `<i class="st-fill" style="left:${dayPos(from)}%;width:${dayPos(to + 1) - dayPos(from)}%"></i><b class="st-made" style="left:${dayPos(m.made)}%"></b>`
          : `<span class="st-none">No buzz data</span>`}
      </div></li>`;
  }).join("");
  return `<div class="stages">
    <div class="st-axis" aria-hidden="true"><div class="st-axis-in"><span class="st-prem" style="left:${dayPos(0)}%">Japan premiere</span>${ticks}</div></div>
    <ol class="st-rows">${rows}</ol>
    <p class="st-key" aria-hidden="true"><span><i class="st-k-fill"></i>Buzz the forecast can see</span><span><i class="st-k-made"></i>Day it is made</span><span><i class="st-k-day0"></i>Premiere, day 0</span></p>
  </div>`;
}

/** Diverging bars: how many points each factor adds to or takes from the index. */
export function drivers(list) {
  const max = Math.max(...list.map((d) => Math.abs(d.points)), 1);
  const rows = [...list].sort((a, b) => Math.abs(b.points) - Math.abs(a.points)).map((d, i) => {
    const up = d.points >= 0, width = (Math.abs(d.points) / max) * 50;
    return `<li class="drv ${up ? "up" : "down"}" style="--i:${i}">
      <span class="drv-name">${esc(d.name)}</span>
      <span class="drv-track" aria-hidden="true"><i style="${up ? "left:50%" : `right:50%`};width:${width}%"></i></span>
      <span class="drv-val">${d.points > 0 ? "+" : d.points < 0 ? "−" : ""}${Math.abs(d.points).toFixed(1)}<small> pts</small></span>
    </li>`;
  });
  return `<ul class="drivers">${rows.join("")}</ul>`;
}

/** Closest past titles: a scrolling strip of mini posters. `poster` renders one cover (passed in to avoid a cycle). */
export function lookalikes(list, poster) {
  if (!list.length) return "";
  const cards = list.map((l, i) => `<li class="look" style="--i:${i}">
      <div class="look-art">${poster(l)}<span class="look-idx" title="India Demand Index of this past title">${round(l.india_index)}</span></div>
      <p class="look-name">${esc(l.name)}</p>
      <p class="look-meta">${esc(l.year)} · ${pct(l.similarity)} alike</p>
      <span class="look-sim" aria-hidden="true"><i style="width:${clamp(l.similarity * 100, 0, 100)}%"></i></span>
    </li>`);
  return `<ul class="looks" tabindex="0" aria-label="Closest past titles">${cards.join("")}</ul>`;
}

/** India's states shaded by each language hub's share of Indian-language engagement. */
export function regionMap(regions, hubs) {
  const entries = Object.entries(regions).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => v), 0.0001);
  const hubOf = {};
  for (const [hub, states] of Object.entries(HUB_STATES)) for (const s of states) hubOf[s] = hub;
  const [x, y, w, h] = INDIA.viewBox;
  const paths = Object.entries(INDIA.states).map(([name, s]) => {
    const hub = hubOf[name];
    const share = hub ? regions[hub] ?? 0 : null;
    const cls = hub ? (share > 0 ? "hub" : "hub zero") : "other";
    const style = hub ? ` style="--s:${(0.18 + 0.82 * (share / max)).toFixed(3)}"` : "";
    return `<path class="st ${cls}" d="${s.d}" data-state="${esc(name)}"${hub ? ` data-hub="${hub}"` : ""}${style}><title>${esc(name)}</title></path>`;
  }).join("");
  const map = `<svg class="india" viewBox="${x} ${y} ${w} ${h}" role="img" aria-label="Map of India with states shaded by language hub engagement">${paths}</svg>`;
  const rows = entries.map(([hub, share], i) => `<li class="hub-row${share === 0 ? " zero" : ""}" data-hub="${hub}" style="--i:${i}" tabindex="0">
      <span class="hub-name">${esc(hub)}</span>
      <span class="hub-bar" aria-hidden="true"><i style="width:${(share / max) * 100}%"></i></span>
      <span class="hub-val">${pct(share)}</span>
      <span class="hub-where">${esc(hubs[hub] ?? "")}</span>
    </li>`).join("");
  return `<div class="regions"><div class="map-wrap">${map}</div><ul class="hub-list">${rows}</ul></div>`;
}

/** Hovering a language hub or a state lights up both the list and the map. Call once on any container that holds region maps. */
export function bindRegions(root) {
  const light = (el, hub) => {
    const box = el.closest(".regions");
    if (box) box.querySelectorAll(".st.hub, .hub-row").forEach((x) => x.classList.toggle("dim", Boolean(hub) && x.dataset.hub !== hub));
  };
  const share = (target) => target.closest(".regions").querySelector(`.hub-row[data-hub="${target.dataset.hub}"] .hub-val`).textContent;
  const tip = (target, e) => showTip(`<b>${esc(target.dataset.state)}</b><br>${esc(target.dataset.hub)} hub · ${esc(share(target))} of Indian-language engagement`, e.clientX, e.clientY);
  root.addEventListener("pointerover", (e) => {
    const target = e.target.closest(".st.hub, .hub-row");
    if (!target) return;
    light(target, target.dataset.hub);
    if (target.classList.contains("st")) tip(target, e);
  });
  root.addEventListener("pointermove", (e) => {
    const target = e.target.closest(".st.hub");
    if (target && !document.getElementById("tip").hidden) tip(target, e);
  });
  root.addEventListener("pointerout", (e) => {
    const target = e.target.closest(".st.hub, .hub-row");
    if (target) { light(target, null); hideTip(); }
  });
  root.addEventListener("focusin", (e) => { const row = e.target.closest(".hub-row"); if (row) light(row, row.dataset.hub); });
  root.addEventListener("focusout", (e) => { const row = e.target.closest(".hub-row"); if (row) light(row, null); });
}

/** Forecast against actual, one dot per title. Sized to its container, so labels stay readable on phones. */
export function scatter(host, rows, lines, moment, hidden, onPick) {
  const width = Math.max(host.clientWidth, 280);
  const height = clamp(Math.round(width * 0.82), 320, 500);
  const m = { l: 44, r: 14, t: 30, b: 44 };
  const X = (v) => m.l + (v / 100) * (width - m.l - m.r);
  const Y = (v) => height - m.b - (v / 100) * (height - m.t - m.b);
  const grid = [0, 25, 50, 75, 100].map((v) =>
    `<line class="grid" x1="${m.l}" x2="${width - m.r}" y1="${Y(v)}" y2="${Y(v)}"/><line class="grid" y1="${m.t}" y2="${height - m.b}" x1="${X(v)}" x2="${X(v)}"/>` +
    `<text class="tick" x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${v}</text><text class="tick" x="${X(v)}" y="${height - m.b + 18}" text-anchor="middle">${v}</text>`).join("");
  // A forecast is Launch when its range (index ± half-width) clears the launch line, Hold when it stays under the hold line.
  const hw = lines.range_half_width ?? 0;
  const holdCut = clamp(lines.hold_line - hw, 0, 100), launchCut = clamp(lines.launch_line + hw, 0, 100);
  // A zone's name is only written when the zone is wide enough to hold it; narrow zones keep their tint.
  const band = (cls, a, b, label) => b - a < 3 ? "" :
    `<rect class="${cls}" x="${X(a)}" y="${m.t}" width="${X(b) - X(a)}" height="${height - m.t - m.b}"/>` +
    (X(b) - X(a) >= label.length * 8.2 + 8 ? `<text class="zone-label ${cls}-t" x="${(X(a) + X(b)) / 2}" y="${m.t - 10}" text-anchor="middle">${label}</text>` : "");
  const zones = band("zone-hold", 0, holdCut, "Hold") + band("zone-test", holdCut, launchCut, "Test-market") + band("zone-launch", launchCut, 100, "Launch");
  const dots = rows.filter((r) => !hidden.has(r.verdict)).map((r) =>
    `<circle class="dot dot-${vclass(r.verdict)}" cx="${X(r.forecast)}" cy="${Y(r.actual)}" r="6" tabindex="0" role="button"
      data-id="${r.id}" data-tip="${esc(r.name)}|${esc(r.verdict)}|${round(r.forecast)}|${round(r.actual)}" aria-label="${esc(r.name)}: forecast ${round(r.forecast)}, actual ${round(r.actual)}, ${esc(r.verdict)}"/>`).join("");
  host.innerHTML = `<svg class="scatter" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="group" aria-label="Forecast against actual India Demand Index at ${esc(moment)}">
      ${zones}${grid}<line class="diag" x1="${X(0)}" y1="${Y(0)}" x2="${X(100)}" y2="${Y(100)}"/>
      <text class="axis-title" x="${(m.l + width - m.r) / 2}" y="${height - 6}" text-anchor="middle">Forecast at ${esc(moment)}</text>
      <text class="axis-title" transform="translate(12 ${(m.t + height - m.b) / 2}) rotate(-90)" text-anchor="middle">Actual India Demand Index</text>
      ${dots}</svg>`;
  host.querySelectorAll(".dot").forEach((dot) => {
    dot.addEventListener("click", () => onPick(dot.dataset.id));
    dot.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(dot.dataset.id); } });
  });
}

/** Our model against the simple rules on the 2024 backtest: how far each one's forecasts were from what happened (lower is better). */
export function modelBars(info) {
  const t = info.table;
  const has = (n) => Number.isFinite(t.mae[n]);
  const names = Object.keys(t.mae).sort((a, b) => (has(b) - has(a)) || (t.mae[a] - t.mae[b]));
  const max = Math.max(...names.filter(has).map((n) => t.mae[n]), 1);
  const used = info.used ?? info.main;
  const tag = (n) => [n === info.main && "our model", n === used && used !== info.main && "used for verdicts"].filter(Boolean).map((x) => `<em>${x}</em>`).join("");
  const rows = names.map((n) => `<li class="mb${n === used ? " is-main" : ""}">
      <span class="mb-name">${esc(n)}${tag(n)}</span>
      <span class="mb-track" aria-hidden="true">${has(n) ? `<i style="width:${(t.mae[n] / max) * 100}%"></i>` : ""}</span>
      <span class="mb-val">${has(n) ? t.mae[n].toFixed(1) : "n/a"}</span>
      <span class="mb-extra">${Number.isFinite(t.top20[n]) ? pct(t.top20[n]) : "n/a"}</span>
    </li>`).join("");
  return `<div class="mb-head" aria-hidden="true"><span>Method</span><span>Average miss, in index points (shorter is better)</span><span></span><span class="mb-extra">Top-20% hits</span></div><ul class="mbs">${rows}</ul>`;
}

// ---------------------------------------------------------------- the decision clock

const fx2 = (v) => (Number.isFinite(v) ? v.toFixed(2) : "–");
const clockWhen = (d) => (d.day === "cold" ? "Cold, before any buzz"
  : `Made on day ${dayText(d.day)}${d.stage ? ` (${MOMENTS[d.stage].label})` : ""}`);

/** x for a clock day: Cold has its own slot on the left, then days to scale, so three days look like three days. */
function clockX(days, left, right) {
  const timed = days.filter((d) => d !== "cold"), lo = Math.min(...timed), hi = Math.max(...timed), slot = 56;
  return (d) => (d === "cold" ? left + 16 : left + slot + ((d - lo) / (hi - lo)) * (right - left - slot));
}

/** The nowcast zone from the premiere on, the premiere line, the verdict stages on top and day labels that never
 *  collide: Cold, the premiere and the stages are placed first, then whichever other days still fit. */
function clockFrame(days, X, top, bottom, right) {
  const first = (d) => d.day === "cold" || d.day === 0 || Boolean(d.stage);
  const placed = [];
  for (const d of [...days.filter(first), ...days.filter((d) => !first(d))]) {
    if (placed.every((p) => Math.abs(X(p.day) - X(d.day)) >= 26)) placed.push(d);
  }
  const ticks = placed.map((d) =>
    `<text class="tick" x="${X(d.day)}" y="${bottom + 18}" text-anchor="middle">${d.day === "cold" ? "Cold" : dayText(d.day)}</text>`).join("");
  const stages = days.filter((d) => d.stage && d.stage !== "cold").map((d) =>
    `<text class="ck-stage" x="${X(d.day)}" y="${top - 10}" text-anchor="middle">${MOMENTS[d.stage].label}</text>`).join("");
  return `<rect class="ck-now" x="${X(0)}" y="${top}" width="${right - X(0)}" height="${bottom - top}"/>
    <line class="ck-prem" x1="${X(0)}" x2="${X(0)}" y1="${top}" y2="${bottom}"/>
    <text class="ck-now-t" x="${X(0) + 6}" y="${top + 14}">Nowcast</text>${ticks}${stages}`;
}

const path = (rows, X, Y, key) => rows.filter((d) => Number.isFinite(d[key])).map((d, i) => `${i ? "L" : "M"}${X(d.day)},${Y(d[key])}`).join("");

function bindPointTips(host, tips) {
  host.querySelectorAll("[data-tip-i]").forEach((pt) => {
    const show = (x, y) => showTip(tips[pt.dataset.tipI], x, y);
    pt.addEventListener("pointerover", (e) => show(e.clientX, e.clientY));
    pt.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    pt.addEventListener("pointerout", hideTip);
    pt.addEventListener("focus", () => { const r = pt.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
    pt.addEventListener("blur", hideTip);
  });
}

/** How well a forecast made on each day ranks the titles: on 2024, with its 95% interval, and averaged over the
 *  rolling seasons. `days` is predictions.json "clock" (yosoku/clock.py). Sized to its container. */
export function clockChart(host, days) {
  const width = Math.max(host.clientWidth, 300);
  const height = clamp(Math.round(width * 0.5), 260, 360);
  const m = { l: 54, r: 14, t: 32, b: 46 };
  const X = clockX(days.map((d) => d.day), m.l, width - m.r);
  const Y = (v) => m.t + ((1 - clamp(v, -0.3, 1)) / 1.3) * (height - m.t - m.b);
  const timed = days.filter((d) => d.day !== "cold"), cold = days.find((d) => d.day === "cold");
  const banded = timed.filter((d) => Number.isFinite(d.low) && Number.isFinite(d.high));
  const band = banded.length > 1
    ? `<path class="ck-band" d="${path(banded, X, Y, "high")}${[...banded].reverse().map((d) => `L${X(d.day)},${Y(d.low)}`).join("")}Z"/>` : "";
  const coldBar = cold && Number.isFinite(cold.low) && Number.isFinite(cold.high)
    ? `<line class="ck-err" x1="${X("cold")}" x2="${X("cold")}" y1="${Y(cold.high)}" y2="${Y(cold.low)}"/>` : "";
  const grid = [0, 0.25, 0.5, 0.75, 1].map((v) => `<line class="grid${v ? "" : " ck-zero"}" x1="${m.l}" x2="${width - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>` +
    `<text class="tick" x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${v ? v.toFixed(2) : "0"}</text>`).join("");
  const tips = days.map((d) => `<b>${esc(clockWhen(d))}</b><br>2024 titles: ${fx2(d.spearman)} (95% interval ${fx2(d.low)} to ${fx2(d.high)})` +
    `<br>${esc(d.seasons)} rolling seasons: ${fx2(d.rolling)}<br>80% range ± ${Number.isFinite(d.width) ? round(d.width) : "–"} points` +
    (d.nowcast ? "<br><i>Nowcast: inside the 28 days measured</i>" : ""));
  const dots = days.map((d, i) => (Number.isFinite(d.rolling) ? `<circle class="ck-roll" cx="${X(d.day)}" cy="${Y(d.rolling)}" r="3"/>` : "") +
    (Number.isFinite(d.spearman) ? `<circle class="ck-pt" cx="${X(d.day)}" cy="${Y(d.spearman)}" r="5" tabindex="0" data-tip-i="${i}"
      aria-label="${esc(clockWhen(d))}: rank correlation ${fx2(d.spearman)} on 2024, ${fx2(d.rolling)} over the rolling seasons"/>` : "")).join("");
  host.innerHTML = `<svg class="scatter clock" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="group"
      aria-label="Rank correlation of forecasts with the actual India Demand Index, by the day the forecast is made">
    ${clockFrame(days, X, m.t, height - m.b, width - m.r)}${grid}${band}${coldBar}
    <path class="ck-rline" d="${path(timed, X, Y, "rolling")}"/><path class="ck-line" d="${path(timed, X, Y, "spearman")}"/>${dots}
    <text class="axis-title" x="${(m.l + width - m.r) / 2}" y="${height - 6}" text-anchor="middle">Day the forecast is made (0 = Japanese premiere)</text>
    <text class="axis-title" transform="translate(12 ${(m.t + height - m.b) / 2}) rotate(-90)" text-anchor="middle">Rank correlation with what happened</text></svg>`;
  bindPointTips(host, tips);
}

/** One title's forecasts with their 80% ranges, against what happened (if known), on the decision clock's days.
 *  domain: predictions.json "clock" (the days and stages to draw); rows: [{day, value, lo, hi, date?}], all or some days. */
export function trajectoryChart(host, domain, rows, actual) {
  const width = Math.max(host.clientWidth, 280);
  const height = clamp(Math.round(width * 0.42), 200, 260);
  const m = { l: 34, r: 14, t: 28, b: 40 };
  const X = clockX(domain.map((d) => d.day), m.l, width - m.r);
  const Y = (v) => m.t + ((100 - clamp(v, 0, 100)) / 100) * (height - m.t - m.b);
  const timed = rows.filter((r) => r.day !== "cold"), cold = rows.find((r) => r.day === "cold");
  const band = timed.length > 1 ? `<path class="tj-band" d="${path(timed, X, Y, "hi")}${[...timed].reverse().map((r) => `L${X(r.day)},${Y(r.lo)}`).join("")}Z"/>` : "";
  const coldBar = cold ? `<line class="tj-err" x1="${X("cold")}" x2="${X("cold")}" y1="${Y(cold.hi)}" y2="${Y(cold.lo)}"/>` : "";
  const grid = [0, 50, 100].map((v) => `<line class="grid" x1="${m.l}" x2="${width - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>` +
    `<text class="tick" x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${v}</text>`).join("");
  const truth = actual == null ? "" : `<line class="tj-actual" x1="${m.l}" x2="${width - m.r}" y1="${Y(actual)}" y2="${Y(actual)}"/>
    <text class="tj-actual-t" x="${m.l + 4}" y="${Y(actual) + (actual > 80 ? 14 : -6)}">Actual ${round(actual)}</text>`;
  const stageOf = Object.fromEntries(domain.map((d) => [d.day, d.stage]));
  const when = (r) => clockWhen({ day: r.day, stage: stageOf[r.day] }) + (r.date ? `, ${formatDate(r.date)}` : "");
  const tips = rows.map((r) => `<b>${esc(when(r))}</b><br>Forecast ${round(r.value)}, 80% range ${round(clamp(r.lo, 0, 100))}–${round(clamp(r.hi, 0, 100))}` +
    (actual == null ? "" : `<br>Actual ${round(actual)}`));
  const dots = rows.map((r, i) => `<circle class="tj-pt" cx="${X(r.day)}" cy="${Y(r.value)}" r="4.5" tabindex="0" data-tip-i="${i}"
      aria-label="${esc(when(r))}: forecast ${round(r.value)}"/>`).join("");
  host.innerHTML = `<svg class="scatter clock traj" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="group"
      aria-label="This title's India Demand Index forecast by the day it was made${actual == null ? "" : `, against the actual ${round(actual)}`}">
    ${clockFrame(domain, X, m.t, height - m.b, width - m.r)}${grid}${band}${coldBar}${truth}
    <path class="tj-line" d="${path(timed, X, Y, "value")}"/>${dots}</svg>`;
  bindPointTips(host, tips);
}

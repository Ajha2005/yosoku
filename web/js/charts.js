// Charts, hand-built from HTML and SVG so they stay light, crisp and themeable. Each returns markup (or fills a node).

import { VERDICTS, HUB_STATES, esc, round, pct, clamp } from "./data.js";
import { INDIA } from "./india-map.js";

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
  return `<ul class="looks">${cards.join("")}</ul>`;
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
  const band = (cls, a, b, label) => b - a < 3 ? "" :
    `<rect class="${cls}" x="${X(a)}" y="${m.t}" width="${X(b) - X(a)}" height="${height - m.t - m.b}"/>` +
    `<text class="zone-label ${cls}-t" x="${(X(a) + X(b)) / 2}" y="${m.t - 10}" text-anchor="middle">${label}</text>`;
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
  const rows = names.map((n) => `<li class="mb${n === info.main ? " is-main" : ""}">
      <span class="mb-name">${esc(n)}${n === info.main ? "<em>our model</em>" : ""}</span>
      <span class="mb-track" aria-hidden="true">${has(n) ? `<i style="width:${(t.mae[n] / max) * 100}%"></i>` : ""}</span>
      <span class="mb-val">${has(n) ? t.mae[n].toFixed(1) : "n/a"}</span>
      <span class="mb-extra">${Number.isFinite(t.top20[n]) ? pct(t.top20[n]) : "n/a"}</span>
    </li>`).join("");
  return `<div class="mb-head" aria-hidden="true"><span>Method</span><span>Average miss, in index points (shorter is better)</span><span></span><span class="mb-extra">Top-20% hits</span></div><ul class="mbs">${rows}</ul>`;
}

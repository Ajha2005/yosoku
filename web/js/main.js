// Yosoku dashboard: boots the page, renders the hero, slate, track record and method, and routes to the forecast sheet.

import { loadData, VERDICTS, MOMENTS, GROUPS, esc, round, pct, momentsOf, latestMoment, ruleText } from "./data.js?v=2";
import { posterHTML, artSVG, startPetals } from "./art.js?v=2";
import { miniBar, verdictIcon, scatter, modelBars } from "./charts.js?v=2";
import { createDetail, countUp } from "./detail.js?v=2";
import { renderGuide } from "./guide.js?v=2";
import { showTip, hideTip } from "./tip.js?v=2";
import { INDEX_PARTS, PRINCIPLES, SOURCES } from "./content.js?v=2";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

const app = { data: null, covers: {} };
const PAGE = 96;   // posters drawn at a time; the rest sit behind "Show more" to keep big slates fast
const state = { shown: PAGE, group: "upcoming", moment: "cold", momentPicked: false, verdict: "all", query: "", sort: "index", recordMoment: "t+7", hidden: new Set() };
let detail;
let sheetPushed = false;   // did the user open the sheet from the page (so Back should close it)?

// ---------------------------------------------------------------- helpers

const forecastOf = (t, moment) => t.forecasts[moment];
const groupTitles = (group) => app.data.titles.filter((t) => t.group === group);
const momentsInGroup = (group) => Object.keys(MOMENTS).filter((m) => groupTitles(group).some((t) => momentsOf(t).includes(m)));
const coverOf = (id) => app.covers[id];

function visibleTitles() {
  const q = state.query.trim().toLowerCase();
  const list = groupTitles(state.group).filter((t) => {
    const f = forecastOf(t, state.moment);
    if (!f || !momentsOf(t).includes(state.moment)) return false;
    if (state.verdict !== "all" && f.verdict !== state.verdict) return false;
    return !q || [t.name, t.title_japanese, t.season, ...t.genres].some((s) => String(s || "").toLowerCase().includes(q));
  });
  const idx = (t) => forecastOf(t, state.moment).index;
  const sorts = {
    index: (a, b) => idx(b) - idx(a),
    low: (a, b) => idx(a) - idx(b),
    name: (a, b) => a.name.localeCompare(b.name),
    date: (a, b) => a.start_date.localeCompare(b.start_date),
  };
  return list.sort(sorts[state.sort]);
}

// ---------------------------------------------------------------- theme and nav

function initTheme() {
  const button = $("#theme-toggle");
  const sync = () => {
    const light = document.documentElement.dataset.theme === "light";
    button.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
    $('meta[name="theme-color"]').content = light ? "#f5f0e6" : "#080b1a";
  };
  button.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("yosoku-theme", next); } catch { /* storage blocked */ }
    sync();
  });
  sync();
}

const PAGES = { home: "Overview", guide: "Demand guide", forecasts: "Forecasts", record: "Track record", method: "Method" };
const TITLE_HASH = /^#\/title\/(\d+)(?:\/([^/]+))?$/;
const pageFromHash = (hash) => (hash.match(/^#\/(guide|forecasts|record|method)\/?$/) || [, "home"])[1];

function updateNav() {
  // Every page opens on an ink band, so the bar is transparent at the top and turns solid once you scroll.
  $("#nav").classList.toggle("scrolled", scrollY > 24);
}

/** Shows one page and marks its tab. Pages stay in the DOM, so a page keeps its filters while you look at another. */
function showPage(page) {
  const changed = state.page !== page;
  state.page = page;
  $$(".page").forEach((el) => {
    const on = el.dataset.page === page;
    el.hidden = !on;
    if (on && changed && !reduced) { el.classList.remove("enter"); void el.offsetWidth; el.classList.add("enter"); }
  });
  $$("#tabs [role=tab]").forEach((tab) => {
    const on = tab.dataset.page === page;
    tab.setAttribute("aria-selected", on);
    tab.tabIndex = on ? 0 : -1;
  });
  document.title = page === "home" ? "Yosoku 予測 · India launch forecasts for anime" : `${PAGES[page]} · Yosoku 予測`;
  if (changed) scrollTo({ top: 0, behavior: "instant" });
  updateNav();
}

function initNav() {
  history.scrollRestoration = "manual";   // pages swap in place, so the browser's saved scroll positions would be wrong
  addEventListener("scroll", updateNav, { passive: true });
  // Arrow keys move between tabs, as in any tab bar.
  $("#tabs").addEventListener("keydown", (e) => {
    const tabs = $$("#tabs [role=tab]");
    const at = tabs.indexOf(document.activeElement);
    if (at < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (at + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    location.hash = tabs[next].getAttribute("href");
  });
}

function initReveal() {
  const items = $$(".reveal");
  if (reduced || !("IntersectionObserver" in window)) return items.forEach((el) => el.classList.add("in"));
  const watcher = new IntersectionObserver((entries) => {
    for (const entry of entries) if (entry.isIntersecting) { entry.target.classList.add("in"); watcher.unobserve(entry.target); }
  }, { threshold: 0.12 });
  items.forEach((el) => watcher.observe(el));
}

// ---------------------------------------------------------------- hero

function bestEvaluation() {
  const moments = app.data.evaluation?.moments || {};
  const key = ["t+7", "t-28", "cold"].find((m) => moments[m]);
  return key ? { key, info: moments[key] } : null;
}

function renderHero() {
  // A wall of posters drifting past: the strongest forecasts first, spread over two rows.
  const ranked = app.data.titles
    .map((t) => ({ t, f: forecastOf(t, latestMoment(t)) }))
    .filter(({ f }) => f)
    .sort((a, b) => b.f.index - a.f.index)
    .slice(0, 40)
    .map(({ t }) => t);
  const ROWS = 4, PER_ROW = 11;
  const rows = Array.from({ length: ROWS }, (_, r) => ranked.filter((_, i) => i % ROWS === r));
  $("#hero-wall").innerHTML = rows.map((row, r) => {
    // Repeat short rows so one half of the loop is always wider than the screen, then double it for a seamless drift.
    const half = Array.from({ length: Math.max(PER_ROW, row.length) }, (_, i) => row[(i + r * 3) % row.length]);
    const posters = half.map((t) => `<div class="wall-poster">${posterHTML(t, coverOf(t.anilist_id))}</div>`).join("");
    return `<div class="wall-row"><div class="wall-track">${posters}${posters}</div></div>`;
  }).join("");

  const evaluation = bestEvaluation();
  const stats = [
    { n: app.data.titles.length, suffix: "", label: "titles forecast" },
    { n: Object.keys(MOMENTS).length, suffix: "", label: "stages of the release cycle" },
  ];
  if (evaluation) {
    const { info } = evaluation, label = MOMENTS[evaluation.key].label;
    if (Number.isFinite(info.table.mae[info.main])) stats.push({ n: info.table.mae[info.main], suffix: "", label: `average miss, in index points, on the 2024 titles (${label})`, decimals: 1 });
    if (Number.isFinite(info.coverage)) stats.push({ n: Math.round(info.coverage * 100), suffix: "%", label: "of 2024 titles landed inside the 80% range" });
  }
  $("#hero-stats").innerHTML = stats.map((s) => `<div><dt>${s.label}</dt><dd data-to="${s.n}" data-dec="${s.decimals || 0}" data-suffix="${s.suffix}">${s.decimals ? s.n.toFixed(s.decimals) : s.n}${s.suffix}</dd></div>`).join("");
  const watcher = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    watcher.disconnect();
    $$("#hero-stats dd").forEach((dd) => {
      const to = Number(dd.dataset.to), dec = Number(dd.dataset.dec);
      if (reduced) return;
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / 1200);
        dd.textContent = (to * (1 - Math.pow(1 - t, 3))).toFixed(dec) + dd.dataset.suffix;
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  });
  watcher.observe($("#hero-stats"));
  startPetals($("#petals"));
}

// ---------------------------------------------------------------- slate

function renderControls() {
  const groups = Object.keys(GROUPS).filter((g) => groupTitles(g).length);
  $("#controls").innerHTML = `
    <div class="ctl-row">
      <div class="seg" role="group" aria-label="Which titles" id="seg-group">${groups.map((g) =>
        `<button type="button" data-group="${g}" aria-pressed="false">${GROUPS[g].label}<span class="count">${groupTitles(g).length}</span></button>`).join("")}</div>
      <div class="seg" role="group" aria-label="Forecast stage" id="seg-moment">${Object.entries(MOMENTS).map(([k, m]) =>
        `<button type="button" data-moment="${k}" aria-pressed="false" title="${esc(m.long)}">${m.label}</button>`).join("")}</div>
    </div>
    <div class="ctl-row">
      <div class="chips" role="group" aria-label="Verdict" id="chips"></div>
      <div class="ctl-tools">
        <label class="search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input type="search" id="q" placeholder="Search title, genre, season" autocomplete="off" aria-label="Search titles"></label>
        <label class="select"><span class="sr">Sort by</span><select id="sort" aria-label="Sort by">
          <option value="index">Highest index</option><option value="low">Lowest index</option>
          <option value="name">A to Z</option><option value="date">Release date</option></select></label>
      </div>
    </div>`;

  $("#seg-group").addEventListener("click", (e) => {
    const b = e.target.closest("[data-group]");
    if (!b) return;
    state.group = b.dataset.group;
    const have = momentsInGroup(state.group);
    // Follow the group to its most informative stage, unless the reader chose a stage themselves.
    if (!state.momentPicked || !have.includes(state.moment)) state.moment = have[have.length - 1];
    state.verdict = "all";
    state.shown = PAGE;
    renderSlate();
  });
  $("#seg-moment").addEventListener("click", (e) => {
    const b = e.target.closest("[data-moment]");
    if (b && !b.disabled) { state.moment = b.dataset.moment; state.momentPicked = true; state.shown = PAGE; renderSlate(); }
  });
  $("#more button").addEventListener("click", () => { state.shown += PAGE; renderSlate({ keepFocus: true }); });
  $("#chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-verdict]");
    if (b) { state.verdict = b.dataset.verdict; state.shown = PAGE; renderSlate(); }
  });
  $("#q").addEventListener("input", (e) => { state.query = e.target.value; state.shown = PAGE; renderSlate({ keepFocus: true }); });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; state.shown = PAGE; renderSlate(); });
  addEventListener("keydown", (e) => {
    if (e.key === "/" && !e.target.closest("input, textarea, select") && !detail.isOpen()) { e.preventDefault(); $("#q").focus(); }
  });
}

function cardHTML(t, i) {
  const f = forecastOf(t, state.moment), v = VERDICTS[f.verdict];
  return `<a class="card v-${v.cls}" href="#/title/${t.anilist_id}/${encodeURIComponent(state.moment)}" data-id="${t.anilist_id}" style="--i:${Math.min(i, 18)}">
    ${posterHTML(t, coverOf(t.anilist_id))}
    <span class="vtag">${verdictIcon(f.verdict)}${esc(f.verdict)}</span>
    <span class="card-info">
      <span class="card-title">${esc(t.name)}</span>
      <span class="card-sub">${esc(t.season)} · ${esc(t.format)}</span>
      <span class="card-score"><b><span class="sr">India Demand Index </span>${round(f.index)}</b>${miniBar(f)}</span>
    </span>
  </a>`;
}

function renderSlate({ keepFocus = false } = {}) {   // keepFocus: re-rendering while the user types in the search box
  const have = momentsInGroup(state.group);
  $$("#seg-group button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.group === state.group));
  $$("#seg-moment button").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.moment === state.moment);
    b.disabled = !have.includes(b.dataset.moment);
    if (b.disabled) b.title = "No title in this group has reached this stage yet";
  });
  $("#sort").value = state.sort;

  // Verdict chips show how the current group and stage split, ignoring the verdict filter itself.
  const base = groupTitles(state.group).filter((t) => momentsOf(t).includes(state.moment));
  const counts = { all: base.length };
  for (const t of base) counts[forecastOf(t, state.moment).verdict] = (counts[forecastOf(t, state.moment).verdict] || 0) + 1;
  $("#chips").innerHTML = [["all", "All"], ...Object.keys(VERDICTS).map((v) => [v, v])].map(([key, label]) => {
    const cls = key === "all" ? "" : `chip-${VERDICTS[key].cls}`;
    return `<button type="button" class="chip ${cls}" data-verdict="${esc(key)}" aria-pressed="${state.verdict === key}" ${counts[key] ? "" : "disabled"}>${key === "all" ? "" : verdictIcon(key)}${esc(label)}<span class="count">${counts[key] || 0}</span></button>`;
  }).join("");

  const m = MOMENTS[state.moment];
  $("#legend").innerHTML = `<b>${m.label} · ${m.long}.</b> ${esc(m.note)} <span>${esc(ruleText(app.data.thresholds[state.moment], true))}</span> <span>${GROUPS[state.group].full}.</span>`;

  const list = visibleTitles();
  $("#grid").classList.toggle("still", keepFocus);
  $("#grid").innerHTML = list.slice(0, state.shown).map(cardHTML).join("");
  const left = list.length - state.shown;
  $("#more").hidden = left <= 0;
  if (left > 0) $("#more button").textContent = `Show ${Math.min(PAGE, left)} more · ${left} left`;
  $("#empty").hidden = list.length > 0;
  detail.setOrder(list.map((t) => t.anilist_id));
}

// Tilt each poster toward the pointer. Skipped on touch screens and when motion is reduced.
function initTilt() {
  if (reduced || !matchMedia("(hover: hover)").matches) return;
  const grid = $("#grid");
  grid.addEventListener("pointermove", (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    card.style.setProperty("--rx", `${((0.5 - y) * 8).toFixed(2)}deg`);
    card.style.setProperty("--ry", `${((x - 0.5) * 8).toFixed(2)}deg`);
    card.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
    card.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
  });
  grid.addEventListener("pointerout", (e) => {
    const card = e.target.closest(".card");
    if (card && !card.contains(e.relatedTarget)) { card.style.removeProperty("--rx"); card.style.removeProperty("--ry"); }
  });
}

// ---------------------------------------------------------------- track record

let scatterObserver;

function renderRecord() {
  const host = $("#record-body");
  const done = (moment) => app.data.titles.filter((t) => ["validation", "test"].includes(t.group) && t.forecasts[moment] && t.actual_index != null);
  const available = Object.keys(MOMENTS).filter((m) => done(m).length);
  if (!available.length) {
    host.innerHTML = `<p class="callout">No backtest titles yet. Run <code>python -m yosoku.run</code> to score the 2024 titles.</p>`;
    return;
  }
  if (!available.includes(state.recordMoment)) state.recordMoment = available[available.length - 1];

  const moment = state.recordMoment;
  const rows = done(moment).map((t) => ({ id: t.anilist_id, name: t.name, forecast: t.forecasts[moment].index, actual: t.actual_index, verdict: t.forecasts[moment].verdict }));
  const info = app.data.evaluation?.moments?.[moment];
  const lines = app.data.thresholds[moment];

  const medians = Object.keys(VERDICTS).map((verdict) => {
    const part = rows.filter((r) => r.verdict === verdict).map((r) => r.actual).sort((a, b) => a - b);
    if (!part.length) return "";
    const mid = part.length % 2 ? part[(part.length - 1) / 2] : (part[part.length / 2 - 1] + part[part.length / 2]) / 2;
    return `<div class="tile tile-${VERDICTS[verdict].cls}"><span class="tile-label">${verdictIcon(verdict)}${verdict}</span><b>${round(mid)}</b><span class="tile-note">median actual index · ${part.length} title${part.length > 1 ? "s" : ""}</span></div>`;
  }).join("");

  const t = info?.table;
  const fx = (v, digits) => (Number.isFinite(v) ? v.toFixed(digits) : "n/a");
  const score = info ? `
    <div class="scorecard">
      <div class="tile"><span class="tile-label">Average miss</span><b>${fx(t.mae[info.main], 1)}</b><span class="tile-note">index points</span></div>
      <div class="tile"><span class="tile-label">80% range held</span><b>${Number.isFinite(info.coverage) ? pct(info.coverage) : "n/a"}</b><span class="tile-note">of titles</span></div>
      <div class="tile"><span class="tile-label">Top-20% hits</span><b>${Number.isFinite(t.top20[info.main]) ? pct(t.top20[info.main]) : "n/a"}</b><span class="tile-note">of the true top fifth, found</span></div>
    </div>
    <p class="verdict-line ${info.beats_baseline ? "yes" : "no"}">
      <b>${esc(info.main)}</b> ${info.beats_baseline ? "beats" : "does not yet beat"} the best simple rule (${esc(info.best_baseline)}).
      <span>Checked on the 2024 titles, which the model never saw in training.</span></p>` : "";

  host.innerHTML = `
    <div class="record-top">
      <div class="seg" role="group" aria-label="Forecast stage" id="rec-moment">${Object.entries(MOMENTS).map(([k, m]) =>
        `<button type="button" data-moment="${k}" aria-pressed="${k === moment}" ${available.includes(k) ? "" : "disabled"} title="${esc(m.long)}">${m.label}</button>`).join("")}</div>
      <div class="chips" role="group" aria-label="Show verdicts" id="rec-chips">${Object.keys(VERDICTS).map((v) =>
        `<button type="button" class="chip chip-${VERDICTS[v].cls}" data-verdict="${v}" aria-pressed="${!state.hidden.has(v)}">${verdictIcon(v)}${v}</button>`).join("")}</div>
    </div>
    <div class="record-grid">
      <div class="panel scatter-panel"><div id="scatter" class="scatter-host"></div>
        <p class="note">Each dot is one title. On the dotted line the forecast was exactly right. Open any dot to see why. The verdict lines were tuned on these same titles, so the Launch and Hold split looks a little better here than it will on new ones.</p></div>
      <div class="record-side">${score}<div class="tiles">${medians}</div></div>
    </div>
    ${info ? `<div class="panel models"><h2>Our model against simple rules</h2>${modelBars(info)}
      <p class="note">Average miss is how far a forecast was from the real India Demand Index, averaged over the 2024 titles. Top-20% hits is the share of the true top fifth that the method also ranked in its top fifth.</p></div>` : ""}`;

  const draw = () => scatter($("#scatter"), rows, lines, MOMENTS[moment].label, state.hidden, (id) => { location.hash = `#/title/${id}/${encodeURIComponent(moment)}`; });
  scatterObserver?.disconnect();
  scatterObserver = new ResizeObserver(() => draw());
  scatterObserver.observe($("#scatter"));

  $("#rec-moment").addEventListener("click", (e) => {
    const b = e.target.closest("[data-moment]");
    if (b && !b.disabled) { state.recordMoment = b.dataset.moment; renderRecord(); }
  });
  $("#rec-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-verdict]");
    if (!b) return;
    state.hidden.has(b.dataset.verdict) ? state.hidden.delete(b.dataset.verdict) : state.hidden.add(b.dataset.verdict);
    b.setAttribute("aria-pressed", !state.hidden.has(b.dataset.verdict));
    draw();
  });
}

// Tooltips for the scatter dots.
function initDotTips() {
  const host = $("#record-body");
  const show = (el, x, y) => {
    const [name, verdict, forecast, actual] = el.dataset.tip.split("|");
    showTip(`<b>${name}</b><br>Forecast ${forecast} · Actual ${actual}<br><span class="tip-v">${verdict}</span>`, x, y);
  };
  host.addEventListener("pointerover", (e) => { const d = e.target.closest(".dot"); if (d) show(d, e.clientX, e.clientY); });
  host.addEventListener("pointermove", (e) => { const d = e.target.closest(".dot"); if (d) show(d, e.clientX, e.clientY); });
  host.addEventListener("pointerout", (e) => { if (e.target.closest(".dot")) hideTip(); });
  host.addEventListener("focusin", (e) => {
    const d = e.target.closest(".dot");
    if (d) { const r = d.getBoundingClientRect(); show(d, r.left + r.width / 2, r.top); }
  });
  host.addEventListener("focusout", (e) => { if (e.target.closest(".dot")) hideTip(); });
}

// ---------------------------------------------------------------- method

function renderMethod() {
  $("#method-body").innerHTML = `
    <div class="composition reveal">
      <h2>Three signals, one index</h2>
      <div class="comp-bar" role="img" aria-label="${INDEX_PARTS.map((p) => `${p.name} ${p.weight}%`).join(", ")}">${INDEX_PARTS.map((p) =>
        `<span class="comp comp-${p.key}" style="flex:${p.weight}"><b>${p.weight}%</b></span>`).join("")}</div>
      <ul class="comp-legend">${INDEX_PARTS.map((p) => `<li><i class="swatch comp-${p.key}"></i><span><b>${esc(p.name)}</b>${esc(p.detail)}</span></li>`).join("")}</ul>
    </div>
    <div class="principles">${PRINCIPLES.map((p, i) => `<article class="principle reveal" style="--i:${i}"><span class="pn">${p.n}</span><h3>${esc(p.title)}</h3><p>${esc(p.body)}</p></article>`).join("")}</div>
    <h2 class="sources-title reveal">Where the data comes from, and where it can mislead</h2>
    <div class="sources">${SOURCES.map((s, i) => `<article class="source reveal" style="--i:${i}">
      <h3>${esc(s.name)}</h3>
      <dl><dt>What it tells us</dt><dd>${esc(s.tells)}</dd><dt>Bias and gaps</dt><dd>${esc(s.bias)}</dd><dt>Reliability</dt><dd>${esc(s.reliability)}</dd></dl></article>`).join("")}</div>`;
}

// ---------------------------------------------------------------- routing and boot

function route() {
  const match = location.hash.match(TITLE_HASH);
  if (!match) {
    sheetPushed = false;
    detail?.close();
    showPage(pageFromHash(location.hash));
    return;
  }
  if (!app.data) return;
  if (!state.page) showPage("forecasts");   // a shared link opens straight onto a title: draw a page behind the sheet
  const id = Number(match[1]);
  const moment = match[2] ? decodeURIComponent(match[2]) : null;
  const title = app.data.titles.find((x) => x.anilist_id === id);
  if (title && !visibleTitles().some((x) => x.anilist_id === id)) {
    // Not in the slate as it is filtered now (a deep link, or a dot in the track record): browse its own group instead.
    detail.setOrder(groupTitles(title.group).sort((a, b) => a.name.localeCompare(b.name)).map((x) => x.anilist_id));
  }
  if (detail.show(id, moment) === false) history.replaceState(null, "", pageHash(state.page));
}

const pageHash = (page) => location.pathname + location.search + (page === "home" ? "" : `#/${page}`);

function requestClose() {
  if (sheetPushed) { sheetPushed = false; history.back(); return; }
  history.replaceState(null, "", pageHash(state.page));   // opened from a shared link: there is no earlier page to go back to
  detail.close();
}

function showError(error) {
  showPage("forecasts");
  $("#grid").innerHTML = `<p class="callout error">${esc(error.message)}</p>`;
}

function initCovers() {
  // Covers fade in as they load; one that fails falls back to generated art. These events do not bubble, so listen while capturing.
  document.addEventListener("load", (e) => { if (e.target.classList?.contains("cover-img")) e.target.classList.add("ready"); }, true);
  document.addEventListener("error", (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement) || !img.classList.contains("cover-img")) return;
    const poster = img.closest(".poster");
    poster.classList.remove("has-cover");
    poster.insertAdjacentHTML("afterbegin", artSVG(poster.dataset.seed, poster.dataset.jp));
    img.remove();
  }, true);
}

async function boot() {
  initCovers();
  initTheme();
  initNav();
  let previous = location.hash;
  const first = TITLE_HASH.test(location.hash) ? "forecasts" : pageFromHash(location.hash);
  showPage(first);   // right away, so a link to another page never flashes the overview
  addEventListener("hashchange", () => {
    const wasTitle = TITLE_HASH.test(previous), isTitle = TITLE_HASH.test(location.hash);
    if (isTitle && !wasTitle) sheetPushed = true;
    previous = location.hash;
    route();
  });
  let loaded;
  try { loaded = await loadData(); } catch (error) { showError(error); initReveal(); return; }
  app.data = loaded.data;
  app.covers = loaded.covers;
  app.guide = loaded.guide;
  if (app.data.mock) $("#mock-banner").hidden = false;

  detail = createDetail(app, { requestClose });
  const firstGroup = Object.keys(GROUPS).find((g) => groupTitles(g).length);
  state.group = groupTitles("upcoming").length ? "upcoming" : firstGroup;
  const have = momentsInGroup(state.group);
  state.moment = have[have.length - 1] || "cold";

  renderHero();
  renderControls();
  renderSlate();
  renderRecord();
  initDotTips();
  renderMethod();
  renderGuide(app, $("#guide-body"));
  initTilt();
  initReveal();

  route();
}

boot();

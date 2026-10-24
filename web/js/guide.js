// The Demand guide: what India has actually been watching, told from two counted signals, Netflix India's weekly Top 10
// and the India-flagged trailer comments. Built for anyone deciding where demand lies, including those whose own title
// is unlikely to work: they can describe it and see how similar anime fared and what has worked nearby.

import { esc, pct, round, clamp, titleCase, formatDate } from "./data.js?v=3";
import { posterHTML } from "./art.js?v=3";
import { regionMap, bindRegions } from "./charts.js?v=3";
import { showTip, hideTip } from "./tip.js?v=3";

const MIN_TITLES = 8;       // a rate over fewer titles than this says nothing
const MIN_COMMENTS = 1000;  // likewise for the share of comments that came from India

const FORMATS = { TV: "TV", TV_SHORT: "TV short", MOVIE: "Movie", ONA: "Web (ONA)", OVA: "OVA", SPECIAL: "Special" };
const audienceName = (a) => (a === "Not tagged" ? "No audience tag" : a);
const sourceName = (s) => titleCase(s);
const formatName = (f) => FORMATS[f] || titleCase(f);

// The ways the evidence can be split. `of` gives the groups a title belongs to (a title has several genres).
const DIMENSIONS = {
  genre: { label: "Genre", of: (t) => t.genres, name: (k) => k },
  audience: { label: "Made for", of: (t) => [t.audience], name: audienceName },
  source: { label: "Based on", of: (t) => [t.source], name: sourceName },
  format: { label: "Format", of: (t) => [t.format], name: formatName },
  sequel: { label: "New or sequel", of: (t) => [String(t.sequel)], name: (k) => (k === "1" ? "Sequel or later season" : "New show") },
  year: { label: "Premiere year", of: (t) => [String(t.year)], name: (k) => k, chronological: true },
};
const SIGNALS = {
  netflix: { label: "Reached Netflix India's Top 10" },
  voice: { label: "India's share of trailer comments" },
};

const state = { dimension: "genre", signal: "netflix", audience: "all", profile: { genre: "any", audience: "any", source: "any", format: "any", sequel: "any" } };

const plural = (n, one, many = `${one}s`) => `${n.toLocaleString("en-GB")} ${n === 1 ? one : many}`;

export function renderGuide(app, host) {
  const G = app.guide;
  if (!G) {
    host.innerHTML = '<p class="callout">The demand guide has not been built yet. Run <code>python -m yosoku.export_web</code>.</p>';
    return;
  }
  const byId = new Map(G.titles.map((t) => [t.id, t]));
  const onNetflix = G.titles.filter((t) => t.netflix);
  const reached = onNetflix.filter((t) => t.weeks);
  const poster = (t) => posterHTML({ anilist_id: t.id, title_japanese: t.jp }, app.covers[t.id]);
  const net = G.netflix;
  const since = formatDate(net.from).replace(/^\d+ /, "");

  // ------------------------------------------------------------ 1. the headline and the hit list
  const headline = `
    <div class="g-stats reveal">
      <div class="tile"><span class="tile-label">Reached the chart</span><b>${net.titles}</b>
        <span class="tile-note">anime in ${net.weeks} weeks of Netflix India's weekly Top 10, since ${esc(since)}</span></div>
      <div class="tile"><span class="tile-label">Share of Top 10 slots</span><b>${(100 * net.anime_slots / net.slots).toFixed(1)}%</b>
        <span class="tile-note">${net.anime_slots} of ${net.slots.toLocaleString("en-GB")} slots went to anime</span></div>
      <div class="tile"><span class="tile-label">Share of anime on Netflix</span><b>${pct(reached.length / onNetflix.length)}</b>
        <span class="tile-note">${reached.length} of ${onNetflix.length} titles we track on Netflix</span></div>
    </div>`;

  const hits = `
    <section class="g-block reveal" aria-labelledby="g-hits">
      <h2 id="g-hits">What India actually watched</h2>
      <p class="g-sub">Every anime that reached Netflix India's weekly Top 10, by weeks spent there.</p>
      <ul class="hits">${G.watched.map((t, i) => `
        <li class="hit" style="--i:${i}">
          <div class="hit-art">${poster(t)}<span class="hit-weeks"><b>${t.weeks}</b> ${t.weeks === 1 ? "week" : "weeks"}</span></div>
          <p class="hit-name">${esc(t.name)}</p>
          <p class="hit-meta">Peak #${t.best} · ${esc(t.year)} · ${esc(t.genres.slice(0, 2).join(", "))}</p>
        </li>`).join("")}</ul>
      <div class="weekly-wrap">
        <h3>When it showed up</h3>
        <div id="g-weekly" class="weekly"></div>
        <p class="note">One bar per week in which an anime was in India's Top 10; taller means more titles at once. Hover a bar to see which.</p>
      </div>
    </section>`;

  // ------------------------------------------------------------ 2. what kind of title gets there
  const patterns = `
    <section class="g-block reveal" aria-labelledby="g-patterns">
      <h2 id="g-patterns">What kind of title gets there</h2>
      <p class="g-sub">The same evidence split by what a title is. Read each bar with its count: the numbers are small.</p>
      <div class="g-controls">
        <div class="seg" role="group" aria-label="Split by" id="g-dim">${Object.entries(DIMENSIONS).map(([k, d]) =>
          `<button type="button" data-dim="${k}" aria-pressed="${k === state.dimension}">${d.label}</button>`).join("")}</div>
        <div class="seg" role="group" aria-label="Signal" id="g-signal">${Object.entries(SIGNALS).map(([k, s]) =>
          `<button type="button" data-signal="${k}" aria-pressed="${k === state.signal}">${s.label}</button>`).join("")}</div>
      </div>
      <div class="g-filter" id="g-aud-wrap">
        <span class="g-filter-label" id="g-aud-label">Only titles made for</span>
        <div class="chips" role="group" aria-labelledby="g-aud-label" id="g-aud"></div>
      </div>
      <p class="g-insight" id="g-insight" aria-live="polite"></p>
      <ul class="gbars" id="g-bars"></ul>
      <p class="note" id="g-note"></p>
    </section>`;

  // ------------------------------------------------------------ 3. where in India
  const hubTotal = Object.values(G.voice.hubs).reduce((a, b) => a + b, 0);
  const shares = Object.fromEntries(Object.entries(G.voice.hubs).map(([k, v]) => [k, hubTotal ? v / hubTotal : 0]));
  const leader = Object.entries(shares).sort((a, b) => b[1] - a[1])[0];
  const wiki = G.voice.wikipedia;
  const where = `
    <section class="g-block reveal" aria-labelledby="g-where">
      <h2 id="g-where">Where in India</h2>
      <p class="g-sub">Which Indian languages show up in what viewers say about anime.</p>
      ${hubTotal >= 1 ? regionMap(shares, G.hubs) : ""}
      <p class="note">Of ${G.voice.comments.toLocaleString("en-GB")} trailer comments on ${G.voice.titles} titles, ${G.voice.india} came from India and about ${round(hubTotal)} could be placed in a language hub:
        <b>${pct(leader[1])} ${esc(leader[0])}</b>. The other hubs have too few comments to compare, so read this as "Hindi first, the rest unknown", not as a ranking.
        Indian-language Wikipedia pages show the same thin picture: Hindi pages drew views for ${plural(wiki.Hindi.titles, "title")}, Tamil for ${wiki.Tamil.titles}, Telugu for ${wiki.Telugu.titles}.</p>
    </section>`;

  // ------------------------------------------------------------ 4. check your title
  const count = (key, valueOf) => {
    const tally = new Map();
    for (const t of onNetflix) for (const v of [].concat(valueOf(t))) tally.set(v, (tally.get(v) || 0) + 1);
    return [...tally].sort((a, b) => b[1] - a[1]);
  };
  const options = {
    genre: count("genre", (t) => t.genres).filter(([, n]) => n >= 3).map(([v]) => [v, v]),
    audience: count("audience", (t) => t.audience).map(([v]) => [v, audienceName(v)]),
    source: count("source", (t) => t.source).map(([v]) => [v, sourceName(v)]),
    format: count("format", (t) => t.format).filter(([, n]) => n >= 3).map(([v]) => [v, formatName(v)]),
    sequel: [["0", "A new show"], ["1", "A sequel or later season"]],
  };
  const fields = [["genre", "Genre"], ["audience", "Made for"], ["source", "Based on"], ["format", "Format"], ["sequel", "New or sequel"]];
  const checker = `
    <section class="g-block reveal" aria-labelledby="g-check">
      <h2 id="g-check">Check your title</h2>
      <p class="g-sub">Describe a title to see how similar anime fared in India, and what has worked nearby.</p>
      <div class="ck-form">${fields.map(([k, label]) => `
        <label class="field"><span>${label}</span><select data-key="${k}">
          <option value="any">Any</option>${options[k].map(([v, text]) => `<option value="${esc(v)}">${esc(text)}</option>`).join("")}</select></label>`).join("")}
      </div>
      <div class="ck-out" id="g-check-out" aria-live="polite"></div>
    </section>`;

  host.innerHTML = headline + hits + patterns + where + checker;

  // ------------------------------------------------------------ the weekly strip
  const weekly = host.querySelector("#g-weekly");
  const drawWeekly = () => {
    const width = Math.max(weekly.clientWidth, 280), height = 170, m = { l: 8, r: 8, t: 14, b: 30 };
    const t0 = Date.parse(net.from), t1 = Date.parse(net.to), span = Math.max(t1 - t0, 1);
    const inner = width - m.l - m.r, base = height - m.b;
    const X = (iso) => m.l + ((Date.parse(iso) - t0) / span) * inner;
    const barW = clamp(inner / net.weeks - 1, 2, 9);
    const top = Math.max(...G.timeline.map((w) => w.titles.length), 1);
    const years = [];
    for (let y = new Date(t0).getUTCFullYear() + 1; Date.UTC(y, 0, 1) < t1; y++) years.push(y);
    const bars = G.timeline.map((w) => {
      const best = Math.min(...w.titles.map((x) => x.rank));
      const h = ((w.titles.length / top) * 0.78 + 0.22) * (base - m.t);
      const names = w.titles.map((x) => `${esc(byId.get(x.id)?.name ?? x.id)} · #${x.rank}`).join("<br>");
      return `<rect class="wk" role="img" tabindex="0" x="${(X(w.week) - barW / 2).toFixed(1)}" y="${(base - h).toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="1.5"
        style="opacity:${best <= 3 ? 1 : best <= 7 ? 0.72 : 0.5}" data-tip="<b>Week of ${esc(formatDate(w.week))}</b><br>${names}" aria-label="Week of ${esc(formatDate(w.week))}: ${w.titles.map((x) => esc(byId.get(x.id)?.name ?? "")).join(", ")}"/>`;
    }).join("");
    const ticks = years.map((y) => `<line class="yr" x1="${X(`${y}-01-01`).toFixed(1)}" x2="${X(`${y}-01-01`).toFixed(1)}" y1="${m.t}" y2="${base + 6}"/><text class="yr-t" x="${(X(`${y}-01-01`) + 5).toFixed(1)}" y="${base + 22}">${y}</text>`).join("");
    weekly.innerHTML = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="group" aria-label="Weeks in which an anime was in Netflix India's Top 10">
      <line class="axis" x1="${m.l}" x2="${width - m.r}" y1="${base}" y2="${base}"/>${ticks}${bars}
      <text class="yr-t" x="${m.l}" y="${base + 22}">${new Date(t0).getUTCFullYear()}</text></svg>`;
  };
  drawWeekly();
  new ResizeObserver(drawWeekly).observe(weekly);
  const tipFor = (e) => { const bar = e.target.closest(".wk"); if (bar) showTip(bar.dataset.tip, e.clientX, e.clientY); };
  weekly.addEventListener("pointerover", tipFor);
  weekly.addEventListener("pointermove", tipFor);
  weekly.addEventListener("pointerout", (e) => { if (e.target.closest(".wk")) hideTip(); });
  weekly.addEventListener("focusin", (e) => { const bar = e.target.closest(".wk"); if (bar) { const r = bar.getBoundingClientRect(); showTip(bar.dataset.tip, r.left + r.width / 2, r.top); } });
  weekly.addEventListener("focusout", hideTip);

  // ------------------------------------------------------------ the split bars
  const bars = host.querySelector("#g-bars");
  const tips = [];
  const audienceBox = host.querySelector("#g-aud");
  function drawAudience(signalPool, visible) {
    host.querySelector("#g-aud-wrap").hidden = !visible;
    if (!visible) return;
    const counts = new Map();
    for (const t of signalPool) counts.set(t.audience, (counts.get(t.audience) || 0) + 1);
    if (state.audience !== "all" && !counts.has(state.audience)) counts.set(state.audience, 0);   // keep the chosen chip, even if this signal has none
    const order = [...counts].sort((a, b) => b[1] - a[1]);
    audienceBox.innerHTML = [["all", "All audiences", signalPool.length], ...order.map(([a, n]) => [a, audienceName(a), n])].map(([key, label, n]) =>
      `<button type="button" class="chip" data-aud="${esc(key)}" aria-pressed="${state.audience === key}">${esc(label)}<span class="count">${n}</span></button>`).join("");
  }
  audienceBox.addEventListener("click", (e) => {
    const b = e.target.closest("[data-aud]");
    if (!b) return;
    state.audience = b.dataset.aud;
    drawBars();
  });
  function drawBars() {
    const dim = DIMENSIONS[state.dimension];
    const groups = new Map();
    const signalPool = state.signal === "netflix" ? onNetflix : G.titles.filter((t) => t.comments > 0);
    const splitByAudience = state.dimension !== "audience";
    if (!splitByAudience) state.audience = "all";
    const pool = state.audience === "all" ? signalPool : signalPool.filter((t) => t.audience === state.audience);
    drawAudience(signalPool, splitByAudience);
    for (const t of pool) {
      for (const k of dim.of(t)) {
        const g = groups.get(k) || { key: k, n: 0, hit: 0, comments: 0, india: 0, titles: [] };
        g.n++;
        if (state.signal === "netflix" && t.weeks) { g.hit++; g.titles.push(t); }
        if (state.signal === "voice") { g.comments += t.comments; g.india += t.india; if (t.india) g.titles.push(t); }
        groups.set(k, g);
      }
    }
    const enough = (g) => (state.signal === "netflix" ? g.n >= MIN_TITLES : g.comments >= MIN_COMMENTS);
    const rate = (g) => (state.signal === "netflix" ? g.hit / g.n : g.india / g.comments);
    const all = [...groups.values()];
    const shown = all.filter(enough).sort(dim.chronological ? (a, b) => a.key.localeCompare(b.key) : (a, b) => rate(b) - rate(a) || b.n - a.n);
    const small = all.filter((g) => !enough(g)).sort((a, b) => b.n - a.n);
    const max = Math.max(...shown.map(rate), 1e-9);
    const who = state.audience === "all" ? "" : audienceName(state.audience);
    const poolSize = state.signal === "netflix" ? pool.length : pool.reduce((sum, t) => sum + t.comments, 0);
    const tooThin = state.audience !== "all" && poolSize < (state.signal === "netflix" ? MIN_TITLES : MIN_COMMENTS);

    const lead = shown.find((g) => (state.signal === "netflix" ? g.hit : g.india) > 0);
    tips.length = 0;
    bars.innerHTML = shown.map((g, i) => {
      const value = state.signal === "netflix"
        ? `<b>${pct(rate(g))}</b><small>${g.hit} of ${g.n}</small>`
        : `<b>${(1000 * rate(g)).toFixed(0)}</b><small>per 1,000 · ${g.india} of ${g.comments.toLocaleString("en-GB")}</small>`;
      tips[i] = state.signal === "netflix"
        ? (g.hit ? `<b>${esc(dim.name(g.key))}</b><br>${[...g.titles].sort((a, b) => b.weeks - a.weeks).slice(0, 6).map((t) => `${esc(t.name)} · ${t.weeks} wk`).join("<br>")}` : `<b>${esc(dim.name(g.key))}</b><br>None of its ${g.n} titles has reached the chart`)
        : `<b>${esc(dim.name(g.key))}</b><br>${g.india} India comments in ${plural(g.n, "title")}`;
      return `<li class="gb${state.signal === "netflix" && !g.hit ? " none" : ""}${g === lead && !dim.chronological ? " lead" : ""}" data-i="${i}" tabindex="0">
        <span class="gb-name">${esc(dim.name(g.key))}</span>
        <span class="gb-track" aria-hidden="true"><i style="width:${(rate(g) / max) * 100}%;--i:${i}"></i></span>
        <span class="gb-val">${value}</span></li>`;
    }).join("") || `<li class="gb-empty">${tooThin
      ? (state.signal === "netflix" || poolSize
        ? `Only ${state.signal === "netflix" ? plural(pool.length, "title") : `${poolSize.toLocaleString("en-GB")} comments`} made for ${esc(who)} in our data: too few to say what ${state.signal === "netflix" ? "they go for" : "they draw"}.`
        : `No trailer comments on titles made for ${esc(who)} in our data.`)
      : "Not enough titles to show this split yet."}</li>`;

    // One sentence that says what the bars say.
    const insight = host.querySelector("#g-insight");
    const never = state.signal === "netflix" ? shown.filter((g) => !g.hit) : [];
    const scope = who ? `Among titles made for <b>${esc(who)}</b>: ` : "";
    if (!shown.length) insight.textContent = "";
    else if (dim.chronological && state.signal === "netflix") insight.innerHTML = `Reached the chart: ${shown.map((g) => `${esc(g.key)} ${g.hit} of ${g.n}`).join(" · ")}.`;
    else if (state.signal === "netflix") {
      const volume = [...shown].filter((g) => g.hit).sort((a, b) => b.hit - a.hit || a.n - b.n).slice(0, 2);
      insight.innerHTML = lead
        ? `${scope}Highest share to reach the chart: <b>${esc(dim.name(lead.key))}</b> (${lead.hit} of ${lead.n}). Most titles on the chart: ${volume.map((g) => `<b>${esc(dim.name(g.key))}</b> (${g.hit})`).join(", ")}.${never.length ? ` Not yet: ${never.slice(0, 4).map((g) => `${esc(dim.name(g.key))} (0 of ${g.n})`).join(", ")}${never.length > 4 ? ` and ${never.length - 4} more` : ""}.` : ""}`
        : "Nothing in this split has reached the chart yet.";
    } else insight.innerHTML = lead ? `${scope}Most comments from India per 1,000: <b>${esc(dim.name(lead.key))}</b> (${(1000 * rate(lead)).toFixed(0)}).` : "";

    const hidden = small.length ? `Too few ${state.signal === "netflix" ? "titles" : "comments"} to rank: ${small.slice(0, 8).map((g) => `${esc(dim.name(g.key))} (${state.signal === "netflix" ? g.n : g.comments.toLocaleString("en-GB")})`).join(", ")}${small.length > 8 ? ` and ${small.length - 8} more` : ""}. ` : "";
    const meaning = state.signal === "netflix"
      ? `Bars show the share of ${who ? `the ${pool.length} ${esc(who)} anime` : `the ${onNetflix.length} anime`} we track on Netflix that reached India's Top 10; titles count in every genre they have. `
      : `Bars show comments flagged as from India (Indian scripts, Hinglish, or naming India) per 1,000 trailer comments, over ${G.voice.titles} titles. Trailers draw a global crowd, so this is a weak signal. `;
    const caution = state.dimension === "audience" ? "“Made for” is who the title is aimed at (AniList's audience tags), not the age of the people watching: Netflix does not publish viewer ages. " : "";
    const thin = who && !tooThin && state.signal === "netflix" && pool.length < 30 ? `Only ${plural(pool.length, "title")} made for ${esc(who)}, so these bars are a hint, not a pattern. ` : "";
    host.querySelector("#g-note").innerHTML = thin + hidden + meaning + caution;
  }
  drawBars();

  host.querySelector("#g-dim").addEventListener("click", (e) => {
    const b = e.target.closest("[data-dim]");
    if (!b) return;
    state.dimension = b.dataset.dim;
    host.querySelectorAll("#g-dim button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    drawBars();
  });
  host.querySelector("#g-signal").addEventListener("click", (e) => {
    const b = e.target.closest("[data-signal]");
    if (!b) return;
    state.signal = b.dataset.signal;
    host.querySelectorAll("#g-signal button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    drawBars();
  });
  const rowTip = (e) => { const row = e.target.closest(".gb"); if (row && tips[row.dataset.i]) showTip(tips[row.dataset.i], e.clientX, e.clientY); };
  bars.addEventListener("pointerover", rowTip);
  bars.addEventListener("pointermove", rowTip);
  bars.addEventListener("pointerout", (e) => { if (e.target.closest(".gb")) hideTip(); });
  bars.addEventListener("focusin", (e) => { const row = e.target.closest(".gb"); if (row && tips[row.dataset.i]) { const r = row.getBoundingClientRect(); showTip(tips[row.dataset.i], r.left + 120, r.top); } });
  bars.addEventListener("focusout", hideTip);
  bindRegions(host);

  // ------------------------------------------------------------ check your title
  const fits = (t, p) => (p.genre === "any" || t.genres.includes(p.genre)) && (p.audience === "any" || t.audience === p.audience)
    && (p.source === "any" || t.source === p.source) && (p.format === "any" || t.format === p.format) && (p.sequel === "any" || String(t.sequel) === p.sequel);
  const tally = (p) => { const set = onNetflix.filter((t) => fits(t, p)); const hit = set.filter((t) => t.weeks); return { n: set.length, hit: hit.length, set, hits: hit }; };
  const phrase = {
    genre: (v) => `Genre: ${v}`, audience: (v) => `Made for ${audienceName(v)}`, source: (v) => `Based on ${sourceName(v).toLowerCase()}`,
    format: (v) => `As a ${formatName(v)}`, sequel: (v) => (v === "1" ? "As a sequel or later season" : "As a new show"),
  };
  const baseRate = reached.length / onNetflix.length;

  function drawCheck() {
    const p = state.profile;
    const out = host.querySelector("#g-check-out");
    const chosen = Object.entries(p).filter(([, v]) => v !== "any");
    const here = tally(p);
    if (!chosen.length) {
      out.innerHTML = `<p class="ck-hint">Across all ${onNetflix.length} anime we track on Netflix, ${reached.length} (${pct(baseRate)}) reached India's Top 10. Choose something above to compare.</p>`;
      return;
    }
    const rateHere = here.n ? here.hit / here.n : 0;
    let head;
    if (!here.n) head = `<b>No match</b><span>No anime we track on Netflix has this exact mix.</span>`;
    else if (here.n < MIN_TITLES) head = `<b>${here.hit} of ${here.n}</b><span>similar anime reached India's Top 10. Only ${plural(here.n, "title")} fit, which is too few to say anything firm.</span>`;
    else head = `<b>${here.hit} of ${here.n}</b><span>similar anime reached India's Top 10 (${pct(rateHere)}), against ${pct(baseRate)} for all anime we track on Netflix.</span>`;
    const tone = !here.n || here.n < MIN_TITLES ? "thin" : here.hit === 0 ? "none" : rateHere >= baseRate ? "up" : "down";
    const toneText = { thin: "Thin evidence", none: "No sign of demand yet", up: "Above average", down: "Below average" }[tone];

    // What has worked nearby: titles that fit and reached the chart, else the closest that did.
    const score = (t) => (p.genre !== "any" && t.genres.includes(p.genre) ? 2 : 0) + ["audience", "source", "format"].filter((k) => p[k] !== "any" && t[k] === p[k]).length
      + (p.sequel !== "any" && String(t.sequel) === p.sequel ? 1 : 0);
    const nearby = here.hits.length ? [...here.hits].sort((a, b) => b.weeks - a.weeks).slice(0, 6)
      : reached.filter((t) => score(t) > 0).sort((a, b) => score(b) - score(a) || b.weeks - a.weeks).slice(0, 4);
    const nearbyTitle = here.hits.length ? "Similar anime that reached it" : nearby.length ? "Closest anime that did reach it" : "";
    const nothingNear = !nearby.length ? `<p class="ck-none">None of the ${reached.length} anime that reached the chart shares any of this.</p>` : "";

    // If one thing changed: the best alternatives that have enough titles behind them.
    const tries = [];
    for (const key of Object.keys(p)) {
      for (const [value] of options[key]) {
        if (value === p[key]) continue;
        const next = tally({ ...p, [key]: value });
        if (next.n >= MIN_TITLES && next.hit > 0 && next.hit / next.n > rateHere) tries.push({ key, value, ...next, rate: next.hit / next.n });
      }
    }
    tries.sort((a, b) => b.rate - a.rate || b.n - a.n);

    out.innerHTML = `
      <div class="ck-result ck-${tone}">
        <div class="ck-head"><span class="ck-tone">${toneText}</span><div class="ck-line">${head}</div></div>
        ${nearby.length ? `<h3>${nearbyTitle}</h3><ul class="hits hits-sm">${nearby.map((t) => `
          <li class="hit"><div class="hit-art">${poster(t)}<span class="hit-weeks"><b>${t.weeks}</b> wk</span></div>
          <p class="hit-name">${esc(t.name)}</p><p class="hit-meta">${esc(t.genres.slice(0, 2).join(", "))} · ${esc(audienceName(t.audience))}</p></li>`).join("")}</ul>` : ""}
        ${nothingNear}
        ${tries.length ? `<h3>If one thing changed</h3><ul class="tries">${tries.slice(0, 4).map((x) => `
          <li><span>${esc(phrase[x.key](x.value))}${p[x.key] !== "any" ? ` <small>instead of ${esc(x.key === "sequel" ? (p.sequel === "1" ? "a sequel" : "a new show") : x.key === "audience" ? audienceName(p[x.key]) : x.key === "source" ? sourceName(p[x.key]) : x.key === "format" ? formatName(p[x.key]) : p[x.key])}</small>` : ""}</span>
          <b>${x.hit} of ${x.n}</b><em>${pct(x.rate)}</em></li>`).join("")}</ul>` : ""}
      </div>`;
  }
  host.querySelector(".ck-form").addEventListener("change", (e) => {
    const select = e.target.closest("select[data-key]");
    if (!select) return;
    state.profile[select.dataset.key] = select.value;
    drawCheck();
  });
  host.querySelectorAll(".ck-form select").forEach((s) => { s.value = state.profile[s.dataset.key]; });
  drawCheck();
}

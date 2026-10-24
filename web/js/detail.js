// The forecast sheet: one title, its verdict and the evidence behind it, in a modal drawer.

import { VERDICTS, MOMENTS, safeUrl, esc, round, pct, formatDate, titleCase, momentsOf, latestMoment, ruleText } from "./data.js?v=5";
import { posterHTML } from "./art.js?v=5";
import { gauge, seal, verdictIcon, drivers, lookalikes, regionMap, bindRegions, stageTimeline } from "./charts.js?v=5";
import { showTip, hideTip, showToast } from "./tip.js?v=5";
import { RULE_NOTES } from "./content.js?v=5";

const THIN_REGION = 30;   // fewer hub-pointing comments than this behind a map: say so on the page
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const CALENDAR = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7ZM4 10h16M8 3v4M16 3v4"/></svg>';

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
    const lines = app.data.thresholds[moment];
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
        : moment === "cold"
          ? `<p class="callout">At the cold stage there is no buzz yet, so the forecast is the India index of the most similar past titles below.</p>`
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
        ${gauge(f, lines, actual)}
        <p class="note rule">${esc(ruleText(lines))}</p>
        <div class="reason">
          <p>${esc(f.reason_en)}</p>
          <p lang="ja" class="ja">${esc(f.reason_ja)}</p>
        </div>
        ${result}
      </section>

      <section class="d-section"><h3>What moves this forecast</h3>${whySection}</section>
      <section class="d-section"><h3>What this forecast could see <small>${esc(MOMENTS[moment].label)}</small></h3>
        ${stageTimeline([moment], moment)}
        <p class="note">${esc(MOMENTS[moment].detail)}</p>
      </section>
      <section class="d-section"><h3>Closest past titles <small>and how they did in India</small></h3>
        ${lookalikes(f.lookalikes, (l) => posterHTML({ anilist_id: l.anilist_id, title_japanese: "" }, app.covers[l.anilist_id]))}
        <p class="note">Similarity combines genres, tags, source, format, studio, audience and synopsis words. The badge is each past title's India Demand Index.</p>
      </section>
      <section class="d-section"><h3>Where in India <small>language hubs</small></h3>${regionsSection}</section>
      <section class="d-section"><h3>Dub demand <small>from fans of similar titles</small></h3>${dubSection}</section>
      ${whatIf ? `<section class="d-section"><h3>Release window what-if <small>how past titles did</small></h3>${whatIf}</section>` : ""}
      ${t.synopsis ? `<details class="d-syn"><summary>Synopsis</summary><p>${esc(t.synopsis)}</p></details>` : ""}
    </article>`;

    const big = body.querySelector("[data-count]");
    if (big) countUp(big, Number(big.dataset.count));
  }

  /** A one-page brief for executives: this title's sheet, on its own, in the light theme. */
  function printBrief() {
    const html = document.documentElement, theme = html.dataset.theme;
    const root = document.createElement("div");
    root.id = "print-root";
    root.innerHTML = `<p class="print-head"><b>Yosoku 予測</b> · India launch brief · ${esc(MOMENTS[current.moment].label)} forecast · ${esc(location.href)}</p>${body.innerHTML}`;
    document.body.append(root);
    html.dataset.theme = "light";
    html.classList.add("printing");
    const done = () => { root.remove(); html.classList.remove("printing"); html.dataset.theme = theme; };
    addEventListener("afterprint", done, { once: true });
    print();
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

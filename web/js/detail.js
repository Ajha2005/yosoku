// The forecast sheet: one title, its verdict and the evidence behind it, in a modal drawer.

import { VERDICTS, MOMENTS, safeUrl, esc, round, pct, formatDate, titleCase, momentsOf, latestMoment, ruleText } from "./data.js";
import { posterHTML } from "./art.js";
import { gauge, seal, verdictIcon, drivers, lookalikes, regionMap } from "./charts.js";
import { showTip, hideTip, showToast } from "./tip.js";

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
    const whySection = f.drivers.length
      ? `${drivers(f.drivers)}<p class="note">Exact contributions from the linear model: blue raises the index, red lowers it.</p>`
      : `<p class="callout">At the cold stage there is no buzz yet, so the forecast is the India index of the most similar past titles below.</p>`;
    const regionsSection = f.regions && Object.keys(f.regions).length
      ? `${regionMap(f.regions, app.data.hubs)}<p class="note">Estimated from trailer comments that point to a language (its script, its name, or Hinglish for Hindi) on the ${esc(f.region_titles)} closest past titles that had any. English-speaking fans are spread across India and are not counted here; Hindi includes Marathi.</p>`
      : `<p class="callout">None of the closest past titles had trailer comments pointing to an Indian language, so there is no regional estimate.</p>`;

    body.innerHTML = `<article class="detail v-${v.cls}" style="--k:${/^#[0-9a-f]{3,8}$/i.test(cover?.k) ? cover.k : "var(--accent-2)"}">
      <header class="d-hero${banner ? " has-banner" : ""}">
        ${banner ? `<div class="d-backdrop" style="background-image:url('${banner}')"></div>` : ""}
        <div class="d-hero-inner">
          <div class="d-poster">${posterHTML(t, cover)}</div>
          <div class="d-head">
            <p class="eyebrow">${esc(t.season)} · ${esc(t.format)} · ${esc(titleCase(t.source))}</p>
            <h2 id="sheet-title">${esc(t.name)}</h2>
            ${t.title_japanese ? `<p class="d-jp" lang="ja">${esc(t.title_japanese)}</p>` : ""}
            <ul class="chips-static">${chips}</ul>
            <p class="d-date">Starts in Japan <b>${esc(formatDate(t.start_date))}</b></p>
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
      <section class="d-section"><h3>Closest past titles <small>and how they did in India</small></h3>
        ${lookalikes(f.lookalikes, (l) => posterHTML({ anilist_id: l.anilist_id, title_japanese: "" }, app.covers[l.anilist_id]))}
        <p class="note">Similarity combines genres, tags, source, format, studio, audience and synopsis words. The badge is each past title's India Demand Index.</p>
      </section>
      <section class="d-section"><h3>Where in India <small>language hubs</small></h3>${regionsSection}</section>
      ${t.synopsis ? `<details class="d-syn"><summary>Synopsis</summary><p>${esc(t.synopsis)}</p></details>` : ""}
    </article>`;

    const big = body.querySelector("[data-count]");
    if (big) countUp(big, Number(big.dataset.count));
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
  scroller.addEventListener("scroll", hideTip, { passive: true });
  dlg.addEventListener("cancel", (e) => { e.preventDefault(); requestClose(); });          // Esc
  dlg.addEventListener("click", (e) => { if (e.target === dlg) requestClose(); });          // click on the dimmed backdrop
  // On the document, not the dialog: re-rendering the sheet drops focus to <body>, which is outside the dialog.
  document.addEventListener("keydown", (e) => {
    if (!dlg.open || e.altKey || e.ctrlKey || e.metaKey || e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowLeft") go(neighbours()[0]);
    if (e.key === "ArrowRight") go(neighbours()[1]);
  });

  // Hovering a language hub or a state lights up both the list and the map.
  const regionsOf = (el) => el.closest(".regions");
  const light = (el, hub) => {
    const box = regionsOf(el);
    if (box) box.querySelectorAll(".st.hub, .hub-row").forEach((x) => x.classList.toggle("dim", Boolean(hub) && x.dataset.hub !== hub));
  };
  body.addEventListener("pointerover", (e) => {
    const target = e.target.closest(".st.hub, .hub-row");
    if (!target) return;
    const hub = target.dataset.hub;
    light(target, hub);
    const share = Number(target.closest(".regions").querySelector(`.hub-row[data-hub="${hub}"] .hub-val`).textContent.replace("%", ""));
    if (target.classList.contains("st")) showTip(`<b>${esc(target.dataset.state)}</b><br>${esc(hub)} hub · ${share}% of Indian-language engagement`, e.clientX, e.clientY);
  });
  body.addEventListener("pointermove", (e) => {
    const target = e.target.closest(".st.hub");
    if (target && !document.getElementById("tip").hidden) {
      const hub = target.dataset.hub;
      const share = target.closest(".regions").querySelector(`.hub-row[data-hub="${hub}"] .hub-val`).textContent;
      showTip(`<b>${esc(target.dataset.state)}</b><br>${esc(hub)} hub · ${esc(share)} of Indian-language engagement`, e.clientX, e.clientY);
    }
  });
  body.addEventListener("pointerout", (e) => {
    const target = e.target.closest(".st.hub, .hub-row");
    if (target) { light(target, null); hideTip(); }
  });
  body.addEventListener("focusin", (e) => { const row = e.target.closest(".hub-row"); if (row) light(row, row.dataset.hub); });
  body.addEventListener("focusout", (e) => { const row = e.target.closest(".hub-row"); if (row) light(row, null); });

  return {
    show, close,
    isOpen: () => dlg.open,
    setOrder: (ids) => { order = ids; },
    currentId: () => current?.id,
  };
}

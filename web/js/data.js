// Loading, labels and small helpers shared by every part of the page.

export const VERDICTS = {
  "Launch": {
    cls: "launch", seal: ["投", "入"], ja: "投入推奨",
    icon: '<path d="M7 17 17 7M8 7h9v9"/>',
  },
  "Test-market": {
    cls: "test", seal: ["試", "販"], ja: "テスト販売",
    icon: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3M7.5 14h9"/>',
  },
  "Hold": {
    cls: "hold", seal: ["見", "送"], ja: "見送り",
    icon: '<path d="M9 5v14M15 5v14"/>',
  },
};

export const MOMENTS = {
  "cold": { label: "Cold", long: "Before any buzz", note: "Metadata only: genre, studio, source, synopsis." },
  "t-28": { label: "T−28", long: "Four weeks before launch", note: "Adds trailer comments and Wikipedia attention." },
  "t+7": { label: "T+7", long: "After launch week", note: "Adds the first week of real reaction. Most accurate." },
};

export const GROUPS = {
  "upcoming": { label: "Upcoming", full: "Upcoming (not released yet)" },
  "validation": { label: "Backtest 2024", full: "Backtest: 2024 titles" },
  "test": { label: "Final test 2025", full: "Final test: 2025 titles" },
};

// Which states each language hub covers, for the region map. Mirrors the descriptions in data.hubs.
export const HUB_STATES = {
  "Hindi": ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan", "Delhi", "Haryana", "Uttarakhand",
            "Himachal Pradesh", "Chhattisgarh", "Jharkhand", "Chandigarh", "Maharashtra"],
  "Bengali": ["West Bengal", "Tripura"],
  "Tamil": ["Tamil Nadu"],
  "Telugu": ["Andhra Pradesh", "Telangana"],
  "Kannada": ["Karnataka"],
  "Malayalam": ["Kerala"],
};

/** How a verdict is decided (see yosoku/decision.py): it looks at the 80% range, not only the middle forecast. */
export function ruleText(lines, short = false) {
  const { launch_line: launch, hold_line: hold } = lines;
  return short
    ? `Launch if the low end of the 80% range is at or above ${launch}, Hold if its high end is below ${hold}, otherwise Test-market.`
    : `The bar is the 80% range. Launch needs its low end at or above ${launch}; Hold needs its high end below ${hold}; anything else is Test-market.`;
}

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** Only same-site paths and https links may end up in an image src or CSS url(); anything else is dropped. */
export function safeUrl(url) {
  return typeof url === "string" && /^(https:\/\/[^\s"'<>()\\]+|(?!\/)[\w./-]+)$/.test(url) ? url : "";
}

export const round = (n) => Math.round(Number(n));
export const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
export const pct = (n) => (Number.isFinite(n) ? `${Math.round(n * 100)}%` : "–");
/** n with `digits` decimals, or a dash when it is missing (e.g. a correlation that could not be computed). */
export const fixed = (n, digits) => (Number.isFinite(n) ? n.toFixed(digits) : "–");
export const titleCase = (s) => String(s).replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export function formatDate(iso) {
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? String(iso) : dateFormat.format(date);
}

async function fetchJson(url, optional) {
  try {
    const response = await fetch(url, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${response.status}`);
    return await response.json();
  } catch (error) {
    if (optional) return null;
    throw new Error(`Could not load ${url} (${error.message}). Serve the web/ folder over http, e.g. python -m http.server -d web.`);
  }
}

export async function loadData() {
  const [data, covers, guide] = await Promise.all([
    fetchJson("data/predictions.json"), fetchJson("data/covers.json", true), fetchJson("data/guide.json", true)]);
  const known = { ...(covers || {}) };
  if (data.mock) {
    // Mock ids are made up and collide with real AniList ids, so never show covers for them.
    for (const t of data.titles) {
      delete known[t.anilist_id];
      for (const f of Object.values(t.forecasts)) for (const l of f.lookalikes) delete known[l.anilist_id];
    }
  }
  return { data, covers: known, guide };
}

/** Forecast moments a title really has, in cycle order. */
export function momentsOf(title) {
  return Object.keys(MOMENTS).filter((m) => title.moments_available.includes(m) && title.forecasts[m]);
}

export function latestMoment(title) {
  const have = momentsOf(title);
  return have[have.length - 1];
}

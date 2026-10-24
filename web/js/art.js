// Poster art drawn in code: a different Japanese-print scene for every title, used when a cover is missing,
// plus the falling sakura petals in the hero.

const PALETTES = [
  { sky: ["#f7b7a3", "#fde8c8"], sun: "#e5412d", far: "#8d9bd0", near: "#46549b", water: "#1f2b66", line: "#9fb1ee", ink: "#1b1f4a" },
  { sky: ["#0a0e2c", "#2c3182"], sun: "#f6f0d6", far: "#2a3189", near: "#161b57", water: "#222a78", line: "#7f8df0", ink: "#e9ecff" },
  { sky: ["#ffcfe0", "#fff0f5"], sun: "#ff5d7a", far: "#d59ac0", near: "#9a62a8", water: "#5a3a8a", line: "#e7b8ff", ink: "#3a1f5e" },
  { sky: ["#c9e5bf", "#f3f6dd"], sun: "#d8453a", far: "#82ae7f", near: "#467a62", water: "#1e4b49", line: "#9fd3b5", ink: "#103532" },
  { sky: ["#f6c36b", "#fdebbf"], sun: "#c8302b", far: "#c47a3a", near: "#7a4220", water: "#3d2a1d", line: "#e8b27a", ink: "#2b1a0f" },
  { sky: ["#35266f", "#e08fb9"], sun: "#ffd86e", far: "#4b3a96", near: "#2a1f66", water: "#6e5bc9", line: "#bfb2ff", ink: "#150f3a" },
  { sky: ["#0d3a52", "#79c3c8"], sun: "#ffe6a8", far: "#1d6678", near: "#0b3247", water: "#0a2a40", line: "#8fe0e6", ink: "#031621" },
  { sky: ["#4d0f20", "#ee6a4a"], sun: "#ffe8b0", far: "#8c1f35", near: "#3f0c1c", water: "#2a0612", line: "#ff9d7f", ink: "#1a0409" },
];

import { esc, safeUrl } from "./data.js?v=10";

const W = 200, H = 300;
let uid = 0;

function rng(seed) {
  let a = (Number(seed) * 2654435761 + 12345) >>> 0 || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const f = (n) => Math.round(n * 10) / 10;
const clampX = (x) => Math.min(120, Math.max(80, x));   // keeps the torii gate fully on the poster

/** A smooth ridge line filled down to the bottom of the poster. */
function ridge(r, baseY, amp, steps, fill, opacity = 1) {
  const pts = [];
  for (let i = 0; i <= steps; i++) pts.push([(W / steps) * i, baseY - r() * amp]);
  let d = `M0 ${H}L0 ${f(pts[0][1])}`;
  for (let i = 1; i < pts.length; i++) {
    const [x, y] = pts[i], [px, py] = pts[i - 1];
    d += `Q${f(px)} ${f(py)} ${f((px + x) / 2)} ${f((py + y) / 2)}`;
  }
  return `<path d="${d}L${W} ${f(pts[steps][1])}L${W} ${H}Z" fill="${fill}" opacity="${opacity}"/>`;
}

/** Seigaiha, the overlapping-wave pattern. One tile, repeated. */
function seigaiha(id, p, size = 15) {
  const R = size;
  const circle = (cx, cy) => {
    let out = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="${p.water}" stroke="${p.line}" stroke-width=".7"/>`;
    for (const k of [0.74, 0.48, 0.22]) out += `<circle cx="${cx}" cy="${cy}" r="${f(R * k)}" fill="none" stroke="${p.line}" stroke-width=".7" opacity=".85"/>`;
    return out;
  };
  const tile = [[R, -R / 2], [0, 0], [2 * R, 0], [R, R / 2], [0, R], [2 * R, R], [R, (3 * R) / 2]].map(([x, y]) => circle(x, y)).join("");
  return `<pattern id="${id}" width="${2 * R}" height="${R}" patternUnits="userSpaceOnUse">${tile}</pattern>`;
}

function fuji(cx, apexY, baseY, p) {
  const half = 100;
  const body = `M${cx - 14} ${apexY}Q${cx - 40} ${baseY - 70} ${cx - half} ${baseY}L${cx + half} ${baseY}Q${cx + 40} ${baseY - 70} ${cx + 14} ${apexY}Z`;
  const cap = `M${cx - 14} ${apexY}Q${cx - 24} ${apexY + 28} ${cx - 31} ${apexY + 44}l9 -9 7 12 8 -13 7 12 8 -11 8 11 8 -11 6 8Q${cx + 24} ${apexY + 28} ${cx + 14} ${apexY}Z`;
  return `<path d="${body}" fill="${p.near}"/><path d="${cap}" fill="#fff" opacity=".88"/>`;
}

function torii(cx, topY, p) {
  const w = 54, post = 7;
  return `<g fill="${p.ink}">
    <path d="M${cx - w - 16} ${topY}Q${cx} ${topY + 8} ${cx + w + 16} ${topY}l5 -9Q${cx} ${topY - 2} ${cx - w - 21} ${topY - 9}Z"/>
    <rect x="${cx - w - 6}" y="${topY + 6}" width="${2 * w + 12}" height="6"/>
    <rect x="${cx - w}" y="${topY + 6}" width="${post}" height="62"/>
    <rect x="${cx + w - post}" y="${topY + 6}" width="${post}" height="62"/>
    <rect x="${cx - w - 2}" y="${topY + 26}" width="${2 * w + 4}" height="5"/>
  </g>`;
}

/** The Japanese title stacked top to bottom along the right edge, one character per line. */
function verticalTitle(jp, p) {
  const chars = [...String(jp)].slice(0, 9);
  if (!chars.length) return "";
  const dark = parseInt(p.sky[0].slice(1, 3), 16) < 120;
  const tspans = chars.map((c, i) => `<tspan x="180" dy="${i ? 16 : 0}">${c.replace(/[&<>]/g, "")}</tspan>`).join("");
  return `<text x="180" y="30" font-size="14" text-anchor="middle" lang="ja" fill="${dark ? "#fff" : p.ink}" opacity=".78">${tspans}</text>`;
}

/** The fallback poster: a seeded Japanese-print scene, 200 x 300. */
export function artSVG(seed, jp = "") {
  const r = rng(seed);
  const p = PALETTES[Math.floor(r() * PALETTES.length)];
  const kind = Math.floor(r() * 3);
  const n = ++uid;
  const sunX = 55 + r() * 90, sunY = 70 + r() * 55, sunR = 30 + r() * 18;
  let scene = "";

  if (kind === 0) {            // Fuji at dawn
    scene += `<circle cx="${f(sunX)}" cy="${f(sunY)}" r="${f(sunR)}" fill="${p.sun}"/>`;
    scene += ridge(r, 205, 26, 5, p.far, 0.9);
    scene += fuji(f(70 + r() * 60), 150 + r() * 14, 232, p);
    scene += ridge(r, 238, 14, 7, p.near);
  } else if (kind === 1) {     // moon and bamboo
    scene += `<circle cx="${f(sunX)}" cy="${f(sunY - 5)}" r="${f(sunR + 8)}" fill="${p.sun}"/>`;
    scene += `<rect y="150" width="${W}" height="60" fill="url(#m${n})"/>`;
    for (let i = 0; i < 5; i++) {
      const x = i < 3 ? 10 + i * 17 + r() * 8 : W - 70 + (i - 3) * 24 + r() * 8, w = 5 + r() * 3, top = r() * 40;
      scene += `<rect x="${f(x)}" y="${f(top)}" width="${f(w)}" height="${H}" fill="${p.ink}" opacity="${f(0.55 + r() * 0.4)}"/>`;
      for (let y = top + 24 + r() * 14; y < H; y += 44 + r() * 20) scene += `<rect x="${f(x - 1)}" y="${f(y)}" width="${f(w + 2)}" height="2.4" fill="${p.sky[0]}" opacity=".5"/>`;
      scene += `<ellipse cx="${f(x + w + 14)}" cy="${f(top + 60 + r() * 90)}" rx="15" ry="3.4" transform="rotate(${f(-20 + r() * 30)} ${f(x + w)} ${f(top + 80)})" fill="${p.ink}" opacity=".7"/>`;
    }
    scene += ridge(r, 240, 12, 6, p.near, 0.95);
  } else {                     // torii at sunset
    scene += `<circle cx="${f(clampX(sunX))}" cy="${f(sunY + 20)}" r="${f(sunR + 14)}" fill="${p.sun}"/>`;
    scene += ridge(r, 200, 20, 6, p.far, 0.85);
    scene += torii(f(clampX(sunX)), 160, p);
    scene += `<rect y="214" width="${W}" height="${H - 214}" fill="${p.near}" opacity=".9"/>`;
    for (let i = 0; i < 6; i++) scene += `<rect x="${f(clampX(sunX) - 46 + r() * 52)}" y="${f(222 + i * 7)}" width="${f(26 + r() * 40)}" height="1.6" fill="${p.sun}" opacity="${f(0.7 - i * 0.1)}"/>`;
  }

  const sea = kind === 1 ? "" : `<rect y="248" width="${W}" height="52" fill="url(#w${n})"/>`;
  return `<svg class="art" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="s${n}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.sky[0]}"/><stop offset="1" stop-color="${p.sky[1]}"/></linearGradient>
      <linearGradient id="m${n}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.sky[1]}" stop-opacity="0"/><stop offset="1" stop-color="${p.sky[1]}" stop-opacity=".8"/></linearGradient>
      ${seigaiha(`w${n}`, p)}
    </defs>
    <rect width="${W}" height="${H}" fill="url(#s${n})"/>${scene}${sea}${verticalTitle(jp, p)}
  </svg>`;
}

/**
 * Markup for a poster: the real cover when we have one (on its dominant colour), otherwise generated art.
 * If a cover fails to load, main.js swaps the art in using the data-seed and data-jp attributes.
 */
export function posterHTML(title, cover) {
  const seed = title.anilist_id, jp = title.title_japanese || "";
  const attrs = `data-seed="${seed}" data-jp="${esc(jp)}"`;
  if (cover && safeUrl(cover.c)) {
    return `<div class="poster has-cover" style="--k:${/^#[0-9a-f]{3,8}$/i.test(cover.k) ? cover.k : "#262c5a"}" ${attrs}>
      <img class="cover-img" src="${esc(safeUrl(cover.c))}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"></div>`;
  }
  return `<div class="poster" ${attrs}>${artSVG(seed, jp)}</div>`;
}

/** Slowly falling sakura petals on a canvas. Returns a function that stops the animation. */
export function startPetals(canvas) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return () => {};
  const ctx = canvas.getContext("2d");
  let width = 0, height = 0, petals = [], raf = 0, running = false;

  const spawn = (initial) => ({
    x: Math.random() * width, y: initial ? Math.random() * height : -20,
    size: 5 + Math.random() * 7, speed: 0.25 + Math.random() * 0.55, drift: 0.2 + Math.random() * 0.5,
    phase: Math.random() * 6.28, spin: (Math.random() - 0.5) * 0.02, angle: Math.random() * 6.28,
    alpha: 0.35 + Math.random() * 0.45,
  });

  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    width = canvas.clientWidth; height = canvas.clientHeight;
    canvas.width = width * dpr; canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    petals = Array.from({ length: Math.round(Math.min(26, Math.max(10, width / 55))) }, () => spawn(true));
  }

  function frame(time) {
    ctx.clearRect(0, 0, width, height);
    for (const p of petals) {
      p.y += p.speed; p.x += Math.sin(time / 1400 + p.phase) * p.drift; p.angle += p.spin;
      if (p.y > height + 20) Object.assign(p, spawn(false));
      ctx.save();
      ctx.translate(p.x, p.y); ctx.rotate(p.angle); ctx.globalAlpha = p.alpha;
      ctx.fillStyle = "#ffc2d8";
      ctx.beginPath();
      ctx.moveTo(0, -p.size);
      ctx.bezierCurveTo(p.size * 0.9, -p.size * 0.8, p.size * 0.8, p.size * 0.6, 0, p.size);
      ctx.bezierCurveTo(-p.size * 0.8, p.size * 0.6, -p.size * 0.9, -p.size * 0.8, 0, -p.size);
      ctx.fill();
      ctx.restore();
    }
    if (running) raf = requestAnimationFrame(frame);
  }

  const start = () => { if (!running) { running = true; raf = requestAnimationFrame(frame); } };
  const stop = () => { running = false; cancelAnimationFrame(raf); };
  // Resize with the canvas, which also covers the hero being shown again after another page; animate only while it is on screen.
  const sizer = new ResizeObserver(resize);
  sizer.observe(canvas);
  const watcher = new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop()));
  watcher.observe(canvas);
  return () => { stop(); watcher.disconnect(); sizer.disconnect(); };
}

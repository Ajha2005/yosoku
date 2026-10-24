// One shared tooltip and toast. A modal <dialog> sits in the browser's top layer, above everything else on the
// page, so both are moved inside the open dialog when there is one.

const tip = document.getElementById("tip");
const toast = document.getElementById("toast");
let toastTimer = 0;

const host = () => document.querySelector("dialog[open]") || document.body;

export function showTip(html, x, y) {
  const parent = host();
  if (tip.parentElement !== parent) parent.append(tip);
  tip.innerHTML = html;
  tip.hidden = false;
  const { width, height } = tip.getBoundingClientRect();
  const left = Math.min(Math.max(8, x - width / 2), innerWidth - width - 8);
  const top = y - height - 14 < 8 ? y + 18 : y - height - 14;
  tip.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
}

export function hideTip() {
  tip.hidden = true;
}

export function showToast(message) {
  const parent = host();
  if (toast.parentElement !== parent) parent.append(toast);
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2200);
}

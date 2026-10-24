// Runs before first paint so the page never flashes the wrong theme.
(function () {
  var theme = "dark";
  try {
    theme = localStorage.getItem("yosoku-theme") || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  } catch (e) { /* storage blocked: keep the default */ }
  document.documentElement.dataset.theme = theme;
})();

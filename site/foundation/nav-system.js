/* ================================================================
   PERMANENCE OS -- Unified Navigation System v2
   Provides: unified dropdowns, inline theme toggle,
   zoom in View dropdown, keyboard shortcuts.
   ================================================================ */

(function () {
  "use strict";

  // ── Zoom State ─────────────────────────────────────────────────
  var zoomKey = "ophtxn_zoom";
  var zoomLevels = [75, 80, 90, 100, 110, 125, 150];
  var zoomIdx = 3;
  try {
    var saved = parseInt(localStorage.getItem(zoomKey), 10);
    if (saved) {
      var si = zoomLevels.indexOf(saved);
      if (si >= 0) zoomIdx = si;
    }
  } catch (e) { /* ignore */ }

  function applyZoom() {
    document.documentElement.style.fontSize = zoomLevels[zoomIdx] + "%";
    try { localStorage.setItem(zoomKey, String(zoomLevels[zoomIdx])); } catch (e) { /* ignore */ }
    var el = document.getElementById("nav-zoom-label");
    if (el) el.textContent = zoomLevels[zoomIdx] + "%";
  }

  // ── Theme State ────────────────────────────────────────────────
  function getTheme() {
    try { return localStorage.getItem("ophtxn_site_brightness") || "dark"; } catch (e) { return "dark"; }
  }
  function setTheme(mode) {
    if (mode === "system") {
      mode = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    document.body.dataset.brightness = mode;
    try { localStorage.setItem("ophtxn_site_brightness", mode); } catch (e) { /* ignore */ }
    updateThemeToggle();
  }
  function updateThemeToggle() {
    var toggle = document.getElementById("navThemeToggle");
    if (!toggle) return;
    var mode = getTheme();
    toggle.dataset.mode = mode;
    // Cycle: dark -> light -> system
    toggle.title = mode === "dark" ? "Switch to light" : mode === "light" ? "Switch to system" : "Switch to dark";
  }

  // ── Replace "Dark" text with inline theme toggle ───────────────
  function createThemeToggle() {
    var existing = document.getElementById("mbTheme");
    if (!existing) return;

    var toggle = document.createElement("button");
    toggle.id = "navThemeToggle";
    toggle.className = "nav-theme-toggle";
    toggle.dataset.mode = getTheme();
    toggle.title = "Toggle theme";
    toggle.innerHTML =
      '<svg class="ico-dark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>' +
      '</svg>' +
      '<svg class="ico-light" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>' +
        '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' +
        '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>' +
        '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>' +
      '</svg>';

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      var cur = getTheme();
      if (cur === "dark") setTheme("light");
      else setTheme("dark");
    });

    existing.replaceWith(toggle);
    updateThemeToggle();
  }

  // ── Rebuild View Dropdown (zoom + colors) ──────────────────────
  function rebuildViewDropdown() {
    var ddView = document.getElementById("ddView") || document.getElementById("dd-view");
    if (!ddView) return;

    // Get existing color dots if any
    var existingColors = ddView.querySelector(".dd-color-track, .dd-theme-row");

    ddView.innerHTML =
      '<div class="dd-label">Zoom</div>' +
      '<div class="dd-row dd-zoom-row">' +
        '<button class="dd-zoom-btn" id="nav-zoom-out" title="Zoom out">-</button>' +
        '<span class="dd-zoom-val" id="nav-zoom-label">' + zoomLevels[zoomIdx] + '%</span>' +
        '<button class="dd-zoom-btn" id="nav-zoom-in" title="Zoom in">+</button>' +
        '<button class="dd-zoom-btn dd-zoom-reset" id="nav-zoom-reset" title="Reset">Reset</button>' +
      '</div>' +
      '<div class="dd-sep"></div>' +
      '<div class="dd-label">Color</div>' +
      '<div class="dd-row dd-color-row" id="ddThemeColor">' +
        '<button class="dd-color-dot" data-color="aurora" title="Aurora" style="background:linear-gradient(135deg,#00e5c4,#7b6fff)"></button>' +
        '<button class="dd-color-dot" data-color="copper" title="Copper" style="background:linear-gradient(135deg,#ffb347,#e8a87c)"></button>' +
        '<button class="dd-color-dot" data-color="ocean" title="Ocean" style="background:linear-gradient(135deg,#4a9eff,#00d4ff)"></button>' +
        '<button class="dd-color-dot" data-color="rose" title="Rose" style="background:linear-gradient(135deg,#ff5c8a,#ff8fab)"></button>' +
        '<button class="dd-color-dot" data-color="violet" title="Violet" style="background:linear-gradient(135deg,#9b6dff,#ff6fff)"></button>' +
        '<button class="dd-color-dot" data-color="forest" title="Forest" style="background:linear-gradient(135deg,#3ddc84,#00bfa5)"></button>' +
        '<button class="dd-color-dot" data-color="solar" title="Solar" style="background:linear-gradient(135deg,#ffd700,#ffb347)"></button>' +
        '<button class="dd-color-dot" data-color="frost" title="Frost" style="background:linear-gradient(135deg,#88d8f5,#b8e8ff)"></button>' +
        '<button class="dd-color-dot" data-color="void" title="Void" style="background:linear-gradient(135deg,#888,#555)"></button>' +
      '</div>';

    // Wire zoom
    document.getElementById("nav-zoom-out").addEventListener("click", function (e) {
      e.stopPropagation();
      if (zoomIdx > 0) { zoomIdx--; applyZoom(); }
    });
    document.getElementById("nav-zoom-in").addEventListener("click", function (e) {
      e.stopPropagation();
      if (zoomIdx < zoomLevels.length - 1) { zoomIdx++; applyZoom(); }
    });
    document.getElementById("nav-zoom-reset").addEventListener("click", function (e) {
      e.stopPropagation();
      zoomIdx = 3; applyZoom();
    });

    // Wire color dots
    ddView.querySelectorAll(".dd-color-dot").forEach(function (dot) {
      dot.addEventListener("click", function (e) {
        e.stopPropagation();
        var color = dot.dataset.color;
        document.body.dataset.theme = color;
        try { localStorage.setItem("ophtxn_site_theme", color); } catch (err) { /* ignore */ }
        ddView.querySelectorAll(".dd-color-dot").forEach(function (d) { d.classList.remove("active"); });
        dot.classList.add("active");
      });
    });

    // Mark active color
    var activeTheme = document.body.dataset.theme || "aurora";
    var activeDot = ddView.querySelector('[data-color="' + activeTheme + '"]');
    if (activeDot) activeDot.classList.add("active");
  }

  // ── Remove Go dropdown and its button ──────────────────────────
  function removeGoDropdown() {
    var ddGo = document.getElementById("ddGo") || document.getElementById("dd-go");
    if (ddGo) ddGo.remove();
    var btnGo = document.getElementById("mbGo");
    if (btnGo) btnGo.remove();
  }

  // ── Remove bottom page slider if it exists ─────────────────────
  function removePageSlider() {
    var slider = document.querySelector(".page-slider");
    if (slider) slider.remove();
  }

  // ── Keyboard Shortcuts ─────────────────────────────────────────
  function initKeyboard() {
    document.addEventListener("keydown", function (e) {
      // Cmd+= zoom in, Cmd+- zoom out, Cmd+0 reset
      if (e.metaKey && e.key === "=") { e.preventDefault(); if (zoomIdx < zoomLevels.length - 1) { zoomIdx++; applyZoom(); } }
      if (e.metaKey && e.key === "-") { e.preventDefault(); if (zoomIdx > 0) { zoomIdx--; applyZoom(); } }
      if (e.metaKey && e.key === "0") { e.preventDefault(); zoomIdx = 3; applyZoom(); }
    });
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    createThemeToggle();
    rebuildViewDropdown();
    removeGoDropdown();
    removePageSlider();
    initKeyboard();
    applyZoom();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

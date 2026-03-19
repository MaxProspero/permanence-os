/* ================================================================
   PERMANENCE OS -- Unified Navigation System v3

   Injects consistent dropdowns on ALL pages.
   Replaces per-page dropdown HTML with one shared system.

   Provides:
   - File dropdown (14 pages, current highlighted)
   - View dropdown (zoom + color picker)
   - Inline theme toggle (moon/sun icon in nav-right)
   - Keyboard shortcuts (Cmd+/- zoom)
   ================================================================ */

(function () {
  "use strict";

  // ── Page Registry ──────────────────────────────────────────────
  var PAGES = [
    { file: "index.html",            label: "Lobby",            section: "os" },
    { file: "local_hub.html",         label: "Control Room",     section: "os" },
    { file: "command_center.html",     label: "Command Center",   section: "os" },
    { file: "trading_room.html",       label: "Trading Room",     section: "os" },
    { file: "markets_terminal.html",   label: "Markets Terminal",  section: "os" },
    { file: "night_capital.html",      label: "Night Capital",    section: "os" },
    { file: "daily_planner.html",      label: "Daily Planner",    section: "os" },
    { file: "ophtxn_shell.html",       label: "Terminal",         section: "os" },
    { file: "rooms.html",              label: "Tower",            section: "os" },
    { file: "ai_school.html",          label: "AI School",        section: "platform" },
    { file: "official_app.html",       label: "App Studio",       section: "platform" },
    { file: "agent_view.html",         label: "Agent View",       section: "platform" },
    { file: "comms_hub.html",          label: "Comms Hub",        section: "platform" },
    { file: "press_kit.html",          label: "Mind Map",         section: "platform" },
  ];

  var currentFile = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  // ── Zoom ───────────────────────────────────────────────────────
  var zoomKey = "ophtxn_zoom";
  var zoomLevels = [75, 80, 90, 100, 110, 125, 150];
  var zoomIdx = 3;
  try {
    var s = parseInt(localStorage.getItem(zoomKey), 10);
    if (s) { var si = zoomLevels.indexOf(s); if (si >= 0) zoomIdx = si; }
  } catch (e) { /* */ }

  function applyZoom() {
    document.documentElement.style.fontSize = zoomLevels[zoomIdx] + "%";
    try { localStorage.setItem(zoomKey, String(zoomLevels[zoomIdx])); } catch (e) { /* */ }
    var el = document.getElementById("nav-zoom-label");
    if (el) el.textContent = zoomLevels[zoomIdx] + "%";
  }

  // ── Theme ──────────────────────────────────────────────────────
  function getTheme() {
    try { return localStorage.getItem("ophtxn_site_brightness") || "dark"; } catch (e) { return "dark"; }
  }
  function setTheme(mode) {
    if (mode === "system") {
      mode = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    document.body.dataset.brightness = mode;
    try { localStorage.setItem("ophtxn_site_brightness", mode); } catch (e) { /* */ }
    updateToggleIcon();
  }
  function updateToggleIcon() {
    var btn = document.getElementById("navThemeToggle");
    if (!btn) return;
    var m = getTheme();
    btn.dataset.mode = m;
    btn.title = m === "dark" ? "Switch to light mode" : "Switch to dark mode";
  }

  // ── Nuke all existing dropdowns ────────────────────────────────
  function removeOldDropdowns() {
    // Remove all known dropdown IDs (both old and new patterns)
    ["ddFile", "ddView", "ddGo", "dd-file", "dd-view", "dd-go"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });
    // Remove Go button from both patterns
    var btnGo = document.getElementById("mbGo");
    if (btnGo) btnGo.remove();
    document.querySelectorAll('button[onclick*="openDD"]').forEach(function (b) {
      if (b.textContent.trim() === "Go") b.remove();
    });
    // Remove "Powered by" footer
    var powered = document.querySelector(".mb-powered");
    if (powered) powered.remove();
  }

  // ── Replace theme toggle ───────────────────────────────────────
  function replaceThemeToggle() {
    // Find the theme element (different IDs on different pages)
    var existing = document.getElementById("mbTheme") || document.getElementById("themeToggle");
    if (!existing) return;

    var toggle = document.createElement("button");
    toggle.id = "navThemeToggle";
    toggle.className = "nav-theme-toggle";
    toggle.dataset.mode = getTheme();
    toggle.title = "Toggle theme";
    toggle.innerHTML =
      '<svg class="ico-dark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>' +
      '<svg class="ico-light" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      setTheme(getTheme() === "dark" ? "light" : "dark");
    });
    existing.replaceWith(toggle);
    updateToggleIcon();
  }

  // ── Inject unified dropdowns ───────────────────────────────────
  function injectDropdowns() {
    // ── File ──
    var ddFile = document.createElement("div");
    ddFile.className = "mb-dropdown";
    ddFile.id = "ddFile";
    ddFile.style.left = "72px";

    var html = '<div class="dd-label">Ophtxn OS</div>';
    var switched = false;
    PAGES.forEach(function (p) {
      if (p.section === "platform" && !switched) {
        html += '<div class="dd-sep"></div><div class="dd-label">Platform</div>';
        switched = true;
      }
      var active = p.file === currentFile ? ' class="dd-active"' : "";
      html += '<a href="' + p.file + '"' + active + '>' + p.label + '</a>';
    });
    ddFile.innerHTML = html;

    // ── View ──
    var ddView = document.createElement("div");
    ddView.className = "mb-dropdown";
    ddView.id = "ddView";
    ddView.style.left = "112px";

    var activeTheme = document.body.dataset.theme || "aurora";
    var colors = [
      { id: "aurora",  label: "Aurora",  bg: "linear-gradient(135deg,#00e5c4,#7b6fff)" },
      { id: "copper",  label: "Copper",  bg: "linear-gradient(135deg,#ffb347,#e8a87c)" },
      { id: "ocean",   label: "Ocean",   bg: "linear-gradient(135deg,#4a9eff,#00d4ff)" },
      { id: "rose",    label: "Rose",    bg: "linear-gradient(135deg,#ff5c8a,#ff8fab)" },
      { id: "violet",  label: "Violet",  bg: "linear-gradient(135deg,#9b6dff,#ff6fff)" },
      { id: "forest",  label: "Forest",  bg: "linear-gradient(135deg,#3ddc84,#00bfa5)" },
      { id: "solar",   label: "Solar",   bg: "linear-gradient(135deg,#ffd700,#ffb347)" },
      { id: "frost",   label: "Frost",   bg: "linear-gradient(135deg,#88d8f5,#b8e8ff)" },
      { id: "void",    label: "Void",    bg: "linear-gradient(135deg,#888,#555)" },
    ];

    var viewHTML =
      '<div class="dd-label">Zoom</div>' +
      '<div class="dd-row dd-zoom-row">' +
        '<button class="dd-zoom-btn" id="nav-zoom-out">-</button>' +
        '<span class="dd-zoom-val" id="nav-zoom-label">' + zoomLevels[zoomIdx] + '%</span>' +
        '<button class="dd-zoom-btn" id="nav-zoom-in">+</button>' +
        '<button class="dd-zoom-btn dd-zoom-reset" id="nav-zoom-reset">Reset</button>' +
      '</div>' +
      '<div class="dd-sep"></div>' +
      '<div class="dd-label">Color</div>' +
      '<div class="dd-row dd-color-row">';

    colors.forEach(function (c) {
      var act = c.id === activeTheme ? " active" : "";
      viewHTML += '<button class="dd-color-dot' + act + '" data-color="' + c.id + '" title="' + c.label + '" style="background:' + c.bg + '"></button>';
    });

    viewHTML += '</div>';
    ddView.innerHTML = viewHTML;

    // Append to body
    document.body.appendChild(ddFile);
    document.body.appendChild(ddView);

    // ── Wire File + View toggle ──
    var menus = { mbFile: "ddFile", mbView: "ddView" };
    var openDD = null;

    function closeAll() {
      document.querySelectorAll(".mb-dropdown.open").forEach(function (d) { d.classList.remove("open"); });
      // Clear active state on both old and new button patterns
      document.querySelectorAll(".mb-mi.open, .nav-item.open").forEach(function (b) { b.classList.remove("open"); });
      openDD = null;
    }

    // Wire both NEW (mb-mi with id) and OLD (nav-item with onclick) patterns
    Object.keys(menus).forEach(function (btnId) {
      var btn = document.getElementById(btnId);
      var dd = document.getElementById(menus[btnId]);
      if (!btn || !dd) return;

      // Remove old onclick if present
      btn.removeAttribute("onclick");

      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (openDD === dd) { closeAll(); return; }
        closeAll();
        dd.classList.add("open");
        btn.classList.add("open");
        openDD = dd;
      });
      btn.addEventListener("mouseenter", function () {
        if (openDD && openDD !== dd) {
          closeAll();
          dd.classList.add("open");
          btn.classList.add("open");
          openDD = dd;
        }
      });
    });

    // Also wire old-pattern buttons (index.html uses onclick="openDD('file',this)")
    document.querySelectorAll('button[onclick*="openDD"]').forEach(function (btn) {
      var text = btn.textContent.trim();
      var targetId = text === "File" ? "ddFile" : text === "View" ? "ddView" : null;
      if (!targetId) return;
      btn.removeAttribute("onclick");
      var dd = document.getElementById(targetId);
      if (!dd) return;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (openDD === dd) { closeAll(); return; }
        closeAll();
        dd.classList.add("open");
        btn.classList.add("open");
        openDD = dd;
      });
      btn.addEventListener("mouseenter", function () {
        if (openDD && openDD !== dd) {
          closeAll();
          dd.classList.add("open");
          btn.classList.add("open");
          openDD = dd;
        }
      });
    });

    document.addEventListener("click", function () { closeAll(); });

    // Hamburger (both patterns)
    var hb = document.getElementById("mbHamburger") || document.querySelector(".hamburger");
    if (hb) {
      hb.removeAttribute("onclick");
      hb.addEventListener("click", function (e) {
        e.stopPropagation();
        var dd = document.getElementById("ddFile");
        if (!dd) return;
        if (openDD === dd) { closeAll(); }
        else { closeAll(); dd.classList.add("open"); dd.style.left = "12px"; openDD = dd; }
      });
    }

    // ── Wire zoom ──
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

    // ── Wire color dots ──
    ddView.querySelectorAll(".dd-color-dot").forEach(function (dot) {
      dot.addEventListener("click", function (e) {
        e.stopPropagation();
        document.body.dataset.theme = dot.dataset.color;
        try { localStorage.setItem("ophtxn_site_theme", dot.dataset.color); } catch (err) { /* */ }
        ddView.querySelectorAll(".dd-color-dot").forEach(function (d) { d.classList.remove("active"); });
        dot.classList.add("active");
      });
    });
  }

  // ── Keyboard ───────────────────────────────────────────────────
  function initKeyboard() {
    document.addEventListener("keydown", function (e) {
      if (e.metaKey && e.key === "=") { e.preventDefault(); if (zoomIdx < zoomLevels.length - 1) { zoomIdx++; applyZoom(); } }
      if (e.metaKey && e.key === "-") { e.preventDefault(); if (zoomIdx > 0) { zoomIdx--; applyZoom(); } }
      if (e.metaKey && e.key === "0") { e.preventDefault(); zoomIdx = 3; applyZoom(); }
    });
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    removeOldDropdowns();
    replaceThemeToggle();
    injectDropdowns();
    initKeyboard();
    applyZoom();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

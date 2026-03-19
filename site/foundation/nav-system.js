/* ================================================================
   PERMANENCE OS -- Unified Navigation System v4

   Single source of truth for navigation across ALL 14 pages.
   Replaces ALL per-page dropdown HTML with one shared system.

   Provides:
   - File dropdown (14 pages, current highlighted)
   - View dropdown (theme color dots, zoom slider, Dark/Light/System)
   - Go dropdown (Tower Overview, Command Center, GitHub)
   - Inline theme toggle cycling Dark > Light > System
   - Keyboard shortcuts (Cmd+/- zoom)
   - Removes: old Go buttons, Quick Launch, Navigate, bottom nav, Powered by
   ================================================================ */

(function () {
  "use strict";

  // ── Page Registry ──────────────────────────────────────────────
  var PAGES = [
    { file: "index.html",            label: "Lobby" },
    { file: "local_hub.html",        label: "Control Room" },
    { file: "command_center.html",   label: "Command Center" },
    { file: "trading_room.html",     label: "Trading Room" },
    { file: "markets_terminal.html", label: "Markets Terminal" },
    { file: "night_capital.html",    label: "Night Capital" },
    { file: "daily_planner.html",    label: "Daily Planner" },
    { file: "ophtxn_shell.html",     label: "Terminal" },
    { file: "rooms.html",            label: "Tower" },
    { file: "ai_school.html",        label: "AI School" },
    { file: "official_app.html",     label: "App Studio" },
    { file: "agent_view.html",       label: "Agent View" },
    { file: "comms_hub.html",        label: "Comms Hub" },
    { file: "press_kit.html",        label: "Mind Map" }
  ];

  var currentFile = (location.pathname.split("/").pop() || "index.html").toLowerCase();

  // ── Zoom ───────────────────────────────────────────────────────
  var zoomKey = "ophtxn_zoom";
  var zoomLevel = 100;
  try {
    var s = parseInt(localStorage.getItem(zoomKey), 10);
    if (s >= 50 && s <= 200) zoomLevel = s;
  } catch (e) { /* */ }

  function applyZoom() {
    document.documentElement.style.fontSize = zoomLevel + "%";
    try { localStorage.setItem(zoomKey, String(zoomLevel)); } catch (e) { /* */ }
    var el = document.getElementById("nav-zoom-range");
    if (el) el.value = zoomLevel;
    var lbl = document.getElementById("nav-zoom-label");
    if (lbl) lbl.textContent = zoomLevel + "%";
  }

  // ── Theme (brightness) ────────────────────────────────────────
  var MODES = ["dark", "light", "system"];

  function getMode() {
    try { return localStorage.getItem("ophtxn_site_brightness") || "dark"; } catch (e) { return "dark"; }
  }

  function setMode(mode) {
    document.body.dataset.brightness = mode;
    try { localStorage.setItem("ophtxn_site_brightness", mode); } catch (e) { /* */ }
    updateModeLabel();
    updateViewModeButtons();
    // Also apply to old index.html pattern if present
    applyLegacyTheme(mode);
  }

  function applyLegacyTheme(mode) {
    // index.html uses CSS custom props for theme; keep that working
    var resolved = mode;
    if (mode === "system") {
      resolved = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    var root = document.documentElement.style;
    if (resolved === "dark") {
      root.setProperty("--bg-base", "#0a0a0a");
      root.setProperty("--bg-surface-1", "#1C1C1E");
      root.setProperty("--bg-surface-2", "#2C2C2E");
      root.setProperty("--text-primary", "#F5F5F7");
      root.setProperty("--text-secondary", "#86868B");
      root.setProperty("--text-tertiary", "rgba(255,255,255,0.30)");
      root.setProperty("--text-inverse", "#0a0a0a");
      root.setProperty("--sep", "rgba(255,255,255,0.08)");
      root.setProperty("--sep-bold", "rgba(255,255,255,0.15)");
    } else {
      root.setProperty("--bg-base", "#FFFFFF");
      root.setProperty("--bg-surface-1", "#F5F5F7");
      root.setProperty("--bg-surface-2", "#E8E8ED");
      root.setProperty("--text-primary", "#1D1D1F");
      root.setProperty("--text-secondary", "#6E6E73");
      root.setProperty("--text-tertiary", "rgba(0,0,0,0.25)");
      root.setProperty("--text-inverse", "#FFFFFF");
      root.setProperty("--sep", "rgba(0,0,0,0.08)");
      root.setProperty("--sep-bold", "rgba(0,0,0,0.15)");
    }
  }

  function cycleMode() {
    var cur = getMode();
    var idx = MODES.indexOf(cur);
    var next = MODES[(idx + 1) % MODES.length];
    setMode(next);
  }

  function updateModeLabel() {
    var btn = document.getElementById("navModeToggle");
    if (!btn) return;
    var m = getMode();
    btn.textContent = m.charAt(0).toUpperCase() + m.slice(1);
  }

  function updateViewModeButtons() {
    var cur = getMode();
    document.querySelectorAll(".nav-dd-mode-btn").forEach(function (b) {
      if (b.dataset.mode === cur) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }

  // ── Theme (color) ─────────────────────────────────────────────
  var COLORS = [
    { id: "aurora",  label: "Aurora",  bg: "linear-gradient(135deg,#00e5c4,#7b6fff)" },
    { id: "copper",  label: "Copper",  bg: "linear-gradient(135deg,#ffb347,#e8a87c)" },
    { id: "ocean",   label: "Ocean",   bg: "linear-gradient(135deg,#4a9eff,#00d4ff)" },
    { id: "rose",    label: "Rose",    bg: "linear-gradient(135deg,#ff5c8a,#ff8fab)" },
    { id: "violet",  label: "Violet",  bg: "linear-gradient(135deg,#9b6dff,#ff6fff)" },
    { id: "forest",  label: "Forest",  bg: "linear-gradient(135deg,#3ddc84,#00bfa5)" },
    { id: "solar",   label: "Solar",   bg: "linear-gradient(135deg,#ffd700,#ffb347)" },
    { id: "frost",   label: "Frost",   bg: "linear-gradient(135deg,#88d8f5,#b8e8ff)" },
    { id: "void",    label: "Void",    bg: "linear-gradient(135deg,#888,#555)" }
  ];

  function getThemeColor() {
    try { return localStorage.getItem("ophtxn_site_theme") || "aurora"; } catch (e) { return "aurora"; }
  }

  function setThemeColor(colorId) {
    document.body.dataset.theme = colorId;
    try { localStorage.setItem("ophtxn_site_theme", colorId); } catch (e) { /* */ }
    // Also set the accent CSS prop for index.html design-system pattern
    var flat = { aurora: "#00e5c4", copper: "#ffb347", ocean: "#4a9eff", rose: "#ff5c8a",
      violet: "#9b6dff", forest: "#3ddc84", solar: "#ffd700", frost: "#88d8f5", void: "#888" };
    if (flat[colorId]) {
      document.documentElement.style.setProperty("--accent", flat[colorId]);
      try { localStorage.setItem("theme-color", flat[colorId]); } catch (e) { /* */ }
    }
    updateColorDots();
  }

  function updateColorDots() {
    var cur = getThemeColor();
    document.querySelectorAll(".nav-dd-color-dot").forEach(function (d) {
      if (d.dataset.color === cur) {
        d.classList.add("active");
      } else {
        d.classList.remove("active");
      }
    });
  }

  // ── Nuke ALL old nav artifacts ────────────────────────────────
  function removeOldElements() {
    // Remove all old dropdown containers (both patterns)
    ["ddFile", "ddView", "ddGo", "dd-file", "dd-view", "dd-go"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });

    // Remove Go buttons (both patterns)
    var goBtn = document.getElementById("mbGo");
    if (goBtn) goBtn.remove();
    document.querySelectorAll('button[onclick*="openDD"]').forEach(function (b) {
      if (b.textContent.trim() === "Go") b.remove();
    });

    // Remove "Powered by" footer
    document.querySelectorAll(".mb-powered").forEach(function (el) { el.remove(); });

    // Remove site-footer (index.html)
    document.querySelectorAll(".site-footer").forEach(function (el) { el.remove(); });

    // Remove Navigate sections (ai_school sidebar)
    document.querySelectorAll('.sb-section-label').forEach(function (el) {
      if (el.textContent.trim() === "Navigate") {
        // Remove the label and subsequent nav links until next section
        var next = el.nextElementSibling;
        el.remove();
        while (next && !next.classList.contains("sb-section-label")) {
          var after = next.nextElementSibling;
          if (next.tagName === "A" || next.classList.contains("sb-nav-link")) {
            next.remove();
          }
          next = after;
        }
      }
    });
  }

  // ── Replace theme toggle in menubar ──────────────────────────
  function replaceThemeToggle() {
    // Find existing theme element (different IDs on different pages)
    var existing = document.getElementById("mbTheme") || document.getElementById("themeToggle");
    if (!existing) return;

    var toggle = document.createElement("button");
    toggle.id = "navModeToggle";
    toggle.className = "mb-mi nav-mode-toggle";
    toggle.style.cssText = "font-size:11px;padding:2px 8px;min-width:48px;text-align:center;";
    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      cycleMode();
    });
    existing.replaceWith(toggle);
    updateModeLabel();
  }

  // ── Build File dropdown HTML ──────────────────────────────────
  function buildFileDropdown() {
    var html = '<div class="dd-label">Pages</div>';
    PAGES.forEach(function (p) {
      var cls = p.file === currentFile ? ' class="dd-active"' : "";
      html += '<a href="' + p.file + '"' + cls + '>' + p.label + '</a>';
    });
    return html;
  }

  // ── Build View dropdown HTML ──────────────────────────────────
  function buildViewDropdown() {
    var activeColor = getThemeColor();
    var activeMode = getMode();

    var html = '<div class="dd-label">Theme Color</div>';
    html += '<div class="dd-row nav-dd-color-row">';
    COLORS.forEach(function (c) {
      var act = c.id === activeColor ? " active" : "";
      html += '<button class="nav-dd-color-dot' + act + '" data-color="' + c.id + '" title="' + c.label + '" style="background:' + c.bg + '"></button>';
    });
    html += '</div>';

    html += '<div class="dd-sep"></div>';
    html += '<div class="dd-label">Zoom</div>';
    html += '<div class="dd-row nav-dd-zoom-row">';
    html += '<input type="range" id="nav-zoom-range" min="50" max="200" step="5" value="' + zoomLevel + '" class="nav-dd-zoom-slider">';
    html += '<span id="nav-zoom-label" class="nav-dd-zoom-val">' + zoomLevel + '%</span>';
    html += '</div>';

    html += '<div class="dd-sep"></div>';
    html += '<div class="dd-label">Appearance</div>';
    html += '<div class="dd-row nav-dd-mode-row">';
    MODES.forEach(function (m) {
      var act = m === activeMode ? " active" : "";
      var label = m.charAt(0).toUpperCase() + m.slice(1);
      html += '<button class="nav-dd-mode-btn' + act + '" data-mode="' + m + '">' + label + '</button>';
    });
    html += '</div>';

    return html;
  }

  // ── Build Go dropdown HTML ────────────────────────────────────
  function buildGoDropdown() {
    var html = '<a href="rooms.html">Tower Overview</a>';
    html += '<a href="command_center.html">Command Center</a>';
    html += '<div class="dd-sep"></div>';
    html += '<a href="https://github.com/MaxProspero/permanence-os" target="_blank" rel="noopener">GitHub</a>';
    return html;
  }

  // ── Inject unified dropdowns ──────────────────────────────────
  function injectDropdowns() {
    // Determine which menubar pattern is in use
    var isOsMb = !!document.querySelector(".os-menubar");

    // Create File dropdown
    var ddFile = document.createElement("div");
    ddFile.className = isOsMb ? "mb-dropdown" : "dropdown";
    ddFile.id = "ddFile";
    ddFile.innerHTML = buildFileDropdown();

    // Create View dropdown
    var ddView = document.createElement("div");
    ddView.className = isOsMb ? "mb-dropdown" : "dropdown";
    ddView.id = "ddView";
    ddView.innerHTML = buildViewDropdown();

    // Create Go dropdown
    var ddGo = document.createElement("div");
    ddGo.className = isOsMb ? "mb-dropdown" : "dropdown";
    ddGo.id = "ddGo";
    ddGo.innerHTML = buildGoDropdown();

    document.body.appendChild(ddFile);
    document.body.appendChild(ddView);
    document.body.appendChild(ddGo);

    // ── Wire menu buttons ──
    var openDD = null;

    function closeAll() {
      document.querySelectorAll(".mb-dropdown.open, .dropdown.open").forEach(function (d) { d.classList.remove("open"); });
      document.querySelectorAll(".mb-mi.open, .nav-item.open").forEach(function (b) { b.classList.remove("open"); });
      openDD = null;
    }

    function positionDropdown(dd, btn) {
      var rect = btn.getBoundingClientRect();
      dd.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 240)) + "px";
    }

    function wireButton(btn, dd) {
      if (!btn || !dd) return;
      btn.removeAttribute("onclick");
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (openDD === dd) { closeAll(); return; }
        closeAll();
        positionDropdown(dd, btn);
        dd.classList.add("open");
        btn.classList.add("open");
        openDD = dd;
      });
      btn.addEventListener("mouseenter", function () {
        if (openDD && openDD !== dd) {
          closeAll();
          positionDropdown(dd, btn);
          dd.classList.add("open");
          btn.classList.add("open");
          openDD = dd;
        }
      });
    }

    // Wire File button -- find by id or by text content
    var fileBtn = document.getElementById("mbFile");
    if (!fileBtn) {
      document.querySelectorAll(".nav-item, button").forEach(function (b) {
        if (b.textContent.trim() === "File" && !fileBtn) fileBtn = b;
      });
    }
    wireButton(fileBtn, ddFile);

    // Wire View button
    var viewBtn = document.getElementById("mbView");
    if (!viewBtn) {
      document.querySelectorAll(".nav-item, button").forEach(function (b) {
        if (b.textContent.trim() === "View" && !viewBtn) viewBtn = b;
      });
    }
    wireButton(viewBtn, ddView);

    // Wire Go button -- add one if needed
    var goBtn = document.getElementById("mbGo");
    if (!goBtn) {
      // Find the View button and add Go after it
      var vb = viewBtn;
      if (vb) {
        goBtn = document.createElement("button");
        goBtn.className = vb.className;
        goBtn.id = "mbGo";
        goBtn.textContent = "Go";
        vb.parentNode.insertBefore(goBtn, vb.nextSibling);
      }
    }
    wireButton(goBtn, ddGo);

    // Close on outside click
    document.addEventListener("click", function () { closeAll(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAll();
    });

    // Hamburger (both patterns)
    var hb = document.getElementById("mbHamburger") || document.querySelector(".hamburger");
    if (hb) {
      hb.removeAttribute("onclick");
      hb.addEventListener("click", function (e) {
        e.stopPropagation();
        if (openDD === ddFile) { closeAll(); return; }
        closeAll();
        ddFile.style.left = "12px";
        ddFile.classList.add("open");
        openDD = ddFile;
      });
    }

    // ── Wire zoom slider ──
    var slider = document.getElementById("nav-zoom-range");
    if (slider) {
      slider.addEventListener("input", function (e) {
        e.stopPropagation();
        zoomLevel = parseInt(this.value, 10);
        applyZoom();
      });
      slider.addEventListener("click", function (e) { e.stopPropagation(); });
    }

    // ── Wire color dots ──
    ddView.querySelectorAll(".nav-dd-color-dot").forEach(function (dot) {
      dot.addEventListener("click", function (e) {
        e.stopPropagation();
        setThemeColor(dot.dataset.color);
      });
    });

    // ── Wire mode buttons ──
    ddView.querySelectorAll(".nav-dd-mode-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        setMode(btn.dataset.mode);
      });
    });
  }

  // ── Inject dropdown CSS ───────────────────────────────────────
  function injectStyles() {
    var style = document.createElement("style");
    style.id = "nav-system-v4-css";
    style.textContent = [
      /* Color dot row */
      ".nav-dd-color-row { display: flex; gap: 5px; padding: 6px 14px; flex-wrap: wrap; }",
      ".nav-dd-color-dot {",
      "  width: 18px; height: 18px; min-width: 18px; border-radius: 50%;",
      "  border: 2px solid transparent; cursor: pointer;",
      "  transition: all .15s; padding: 0; outline: none; background: none;",
      "}",
      ".nav-dd-color-dot:hover { transform: scale(1.2); border-color: rgba(255,255,255,.3); }",
      ".nav-dd-color-dot.active { border-color: #fff; box-shadow: 0 0 6px rgba(0,229,196,.4); }",

      /* Zoom row */
      ".nav-dd-zoom-row { display: flex; align-items: center; gap: 8px; padding: 4px 14px; }",
      ".nav-dd-zoom-slider {",
      "  flex: 1; height: 4px; -webkit-appearance: none; appearance: none;",
      "  background: rgba(255,255,255,.12); border-radius: 2px; outline: none;",
      "  cursor: pointer;",
      "}",
      ".nav-dd-zoom-slider::-webkit-slider-thumb {",
      "  -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%;",
      "  background: #00e5c4; cursor: pointer; border: none;",
      "}",
      ".nav-dd-zoom-val {",
      "  font-size: 11px; color: rgba(255,255,255,.5);",
      "  font-variant-numeric: tabular-nums; min-width: 36px; text-align: right;",
      "}",

      /* Mode buttons */
      ".nav-dd-mode-row { display: flex; gap: 4px; padding: 4px 14px 8px; }",
      ".nav-dd-mode-btn {",
      "  flex: 1; padding: 5px 0; font-size: 11px; text-align: center;",
      "  border-radius: 6px; background: none; border: 1px solid rgba(255,255,255,.1);",
      "  color: rgba(255,255,255,.5); cursor: pointer; transition: all .15s;",
      "}",
      ".nav-dd-mode-btn:hover { border-color: rgba(255,255,255,.2); color: rgba(255,255,255,.8); }",
      ".nav-dd-mode-btn.active {",
      "  border-color: #00e5c4; background: rgba(0,229,196,.1); color: #fff;",
      "}",

      /* Mode toggle in menubar */
      ".nav-mode-toggle {",
      "  color: rgba(255,255,255,.5); font-size: 11px !important;",
      "  transition: color .2s;",
      "}",
      ".nav-mode-toggle:hover { color: rgba(255,255,255,.9); }",

      /* Light mode adjustments */
      "[data-brightness='light'] .nav-dd-zoom-slider { background: rgba(0,0,0,.12); }",
      "[data-brightness='light'] .nav-dd-zoom-slider::-webkit-slider-thumb { background: #00a89a; }",
      "[data-brightness='light'] .nav-dd-zoom-val { color: rgba(0,0,0,.5); }",
      "[data-brightness='light'] .nav-dd-mode-btn { border-color: rgba(0,0,0,.12); color: rgba(0,0,0,.5); }",
      "[data-brightness='light'] .nav-dd-mode-btn:hover { border-color: rgba(0,0,0,.2); color: rgba(0,0,0,.8); }",
      "[data-brightness='light'] .nav-dd-mode-btn.active { border-color: #00a89a; background: rgba(0,169,154,.1); color: #111; }",
      "[data-brightness='light'] .nav-dd-color-dot:hover { border-color: rgba(0,0,0,.3); }",
      "[data-brightness='light'] .nav-dd-color-dot.active { border-color: #111; box-shadow: 0 0 6px rgba(0,0,0,.2); }",
      "[data-brightness='light'] .nav-mode-toggle { color: rgba(0,0,0,.5); }",
      "[data-brightness='light'] .nav-mode-toggle:hover { color: rgba(0,0,0,.9); }"
    ].join("\n");
    document.head.appendChild(style);
  }

  // ── Keyboard ───────────────────────────────────────────────────
  function initKeyboard() {
    document.addEventListener("keydown", function (e) {
      if (e.metaKey && e.key === "=") { e.preventDefault(); zoomLevel = Math.min(200, zoomLevel + 10); applyZoom(); }
      if (e.metaKey && e.key === "-") { e.preventDefault(); zoomLevel = Math.max(50, zoomLevel - 10); applyZoom(); }
      if (e.metaKey && e.key === "0") { e.preventDefault(); zoomLevel = 100; applyZoom(); }
    });
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    injectStyles();
    removeOldElements();
    replaceThemeToggle();
    injectDropdowns();
    initKeyboard();
    applyZoom();

    // Apply saved theme and brightness
    var savedTheme = getThemeColor();
    if (savedTheme) setThemeColor(savedTheme);
    var savedMode = getMode();
    if (savedMode) setMode(savedMode);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

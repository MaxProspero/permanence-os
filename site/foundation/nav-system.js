/* ================================================================
   PERMANENCE OS -- Unified Navigation System v5 (Surface Tabs)

   Single source of truth for navigation across ALL 14 pages.

   Provides:
   - 5 Surface tabs: Command, Flow, Markets, Intelligence, Network
   - View dropdown (theme color dots, zoom slider, Dark/Light/System)
   - System icons: Inbox, Terminal, Dark/Light toggle, Clock, Date
   - Logo click -> Permanence OS
   - Keyboard shortcuts (Cmd+/- zoom)
   - Removes old nav artifacts
   ================================================================ */

(function () {
  "use strict";

  // ── Surface Definitions ──────────────────────────────────────
  var SURFACES = [
    {
      id: "command",
      label: "Command",
      primary: "command_center.html",
      pages: [
        { file: "command_center.html", label: "Overview" },
        { file: "local_hub.html",      label: "Control Room" },
        { file: "agent_view.html",     label: "Agent View" },
        { file: "rooms.html",          label: "Tower" }
      ]
    },
    {
      id: "flow",
      label: "Flow",
      primary: "daily_planner.html",
      pages: [
        { file: "daily_planner.html", label: "Daily Planner" },
        { file: "official_app.html",  label: "App Studio" }
      ]
    },
    {
      id: "markets",
      label: "Markets",
      primary: "trading_room.html",
      pages: [
        { file: "trading_room.html",     label: "Trading Room" },
        { file: "markets_terminal.html", label: "Markets Terminal" },
        { file: "night_capital.html",    label: "Night Capital" }
      ]
    },
    {
      id: "intelligence",
      label: "Intelligence",
      primary: "ai_school.html",
      pages: [
        { file: "ai_school.html", label: "AI School" },
        { file: "press_kit.html", label: "Mind Map" }
      ]
    },
    {
      id: "network",
      label: "Network",
      primary: "comms_hub.html",
      pages: [
        { file: "comms_hub.html", label: "Comms Hub" }
      ]
    }
  ];

  // ── Port-aware routing (8787 static vs 8797 Flask /app/* routes) ──
  var isAppRoute = location.pathname.indexOf("/app/") === 0;
  var APP_ROUTES = {
    "index.html":            "/app/official",
    "ophtxn_shell.html":     "/app/ophtxn",
    "local_hub.html":        "/app/hub",
    "command_center.html":   "/app/command-center",
    "trading_room.html":     "/app/trading",
    "markets_terminal.html": "/app/markets",
    "night_capital.html":    "/app/night-capital",
    "daily_planner.html":    "/app/daily-planner",
    "rooms.html":            "/app/rooms",
    "ai_school.html":        "/app/ai-school",
    "official_app.html":     "/app/studio",
    "agent_view.html":       "/app/agent-view",
    "comms_hub.html":        "/app/comms",
    "press_kit.html":        "/app/press"
  };

  function pageHref(file) {
    if (isAppRoute && APP_ROUTES[file]) return APP_ROUTES[file];
    return file;
  }

  // ── Detect current page (works on both ports) ──
  var currentFile;
  if (isAppRoute) {
    var curPath = location.pathname;
    currentFile = "index.html";
    for (var f in APP_ROUTES) {
      if (APP_ROUTES[f] === curPath) { currentFile = f; break; }
    }
  } else {
    currentFile = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  }

  // ── Detect active surface ──
  function getActiveSurface() {
    for (var i = 0; i < SURFACES.length; i++) {
      var surf = SURFACES[i];
      for (var j = 0; j < surf.pages.length; j++) {
        if (surf.pages[j].file === currentFile) return surf.id;
      }
    }
    return null;
  }

  var activeSurface = getActiveSurface();

  // ── Zoom ───────────────────────────────────────────────────────
  var zoomKey = "ophtxn_zoom";
  var zoomLevel = 100;
  try {
    var s = parseInt(localStorage.getItem(zoomKey), 10);
    if (s >= 50 && s <= 200) zoomLevel = s;
  } catch (e) { /* */ }

  function applyZoom() {
    var scale = zoomLevel / 100;
    var main = document.querySelector("main") || document.querySelector(".page") || document.body;
    if (zoomLevel === 100) {
      main.style.transform = "";
      main.style.transformOrigin = "";
      main.style.width = "";
    } else {
      main.style.transform = "scale(" + scale + ")";
      main.style.transformOrigin = "top center";
      main.style.width = (100 / scale) + "%";
    }
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
    applyLegacyTheme(mode);
  }

  function applyLegacyTheme(mode) {
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
    ["ddFile", "ddView", "ddGo", "dd-file", "dd-view", "dd-go"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });

    var goBtn = document.getElementById("mbGo");
    if (goBtn) goBtn.remove();
    document.querySelectorAll('button[onclick*="openDD"]').forEach(function (b) {
      if (b.textContent.trim() === "Go") b.remove();
    });

    document.querySelectorAll(".mb-powered").forEach(function (el) { el.remove(); });
    document.querySelectorAll(".site-footer").forEach(function (el) { el.remove(); });

    document.querySelectorAll('.sb-section-label').forEach(function (el) {
      if (el.textContent.trim() === "Navigate") {
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

  // ── Build Surface dropdown HTML ───────────────────────────────
  function buildSurfaceDropdown(surface) {
    var html = '';
    surface.pages.forEach(function (p) {
      var cls = p.file === currentFile ? ' class="dd-active"' : "";
      html += '<a href="' + pageHref(p.file) + '"' + cls + '>' + p.label + '</a>';
    });
    return html;
  }

  // ── Rewrite the menubar ───────────────────────────────────────
  function rewriteMenubar() {
    var menubar = document.querySelector(".os-menubar");
    if (!menubar) return;

    // Preserve the logo element
    var logo = menubar.querySelector(".mb-logo");
    var logoHTML = logo ? logo.outerHTML : '';

    // Build the new menubar content
    var html = '';

    // Logo
    html += logoHTML;

    // Ophtxn label
    html += '<span class="mb-mi nav-brand-label">Ophtxn</span>';

    // Divider
    html += '<span class="nav-divider"></span>';

    // Surface tabs
    SURFACES.forEach(function (surf) {
      var isActive = surf.id === activeSurface;
      var activeClass = isActive ? " nav-surface-active" : "";
      html += '<button class="mb-mi nav-surface-tab' + activeClass + '" data-surface="' + surf.id + '">';
      html += surf.label;
      if (surf.pages.length > 1) {
        html += ' <span class="nav-tab-arrow">&#9662;</span>';
      }
      html += '</button>';
    });

    // Divider
    html += '<span class="nav-divider"></span>';

    // View button
    html += '<button class="mb-mi nav-view-btn" id="mbView">View</button>';

    // Spacer pushes right items to the right
    html += '<span class="nav-spacer"></span>';

    // System icons area (right side)
    // Inbox icon (SVG envelope)
    html += '<button class="mb-mi nav-sys-icon" id="navInbox" title="Inbox">';
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>';
    html += '</button>';

    // Terminal link
    html += '<a class="mb-mi nav-sys-icon" href="' + pageHref("ophtxn_shell.html") + '" title="Terminal">';
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>';
    html += '</a>';

    // Mode toggle
    html += '<button class="mb-mi nav-mode-toggle" id="navModeToggle" title="Toggle appearance"></button>';

    // Clock
    html += '<span class="mb-mi nav-clock" id="navClock"></span>';

    // Date
    html += '<span class="mb-mi nav-date" id="navDate"></span>';

    menubar.innerHTML = html;
  }

  // ── Clock and Date ────────────────────────────────────────────
  function updateClock() {
    var clock = document.getElementById("navClock");
    var dateEl = document.getElementById("navDate");
    if (!clock && !dateEl) return;
    var now = new Date();
    if (clock) {
      var h = now.getHours();
      var m = now.getMinutes();
      var ampm = h >= 12 ? "PM" : "AM";
      h = h % 12 || 12;
      clock.textContent = h + ":" + (m < 10 ? "0" : "") + m + " " + ampm;
    }
    if (dateEl) {
      var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      var days = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
      dateEl.textContent = days[now.getDay()] + " " + months[now.getMonth()] + " " + now.getDate();
    }
  }

  // ── Inject dropdowns and wire events ──────────────────────────
  function injectDropdowns() {
    var openDD = null;

    function closeAll() {
      document.querySelectorAll(".nav-dropdown.open").forEach(function (d) { d.classList.remove("open"); });
      document.querySelectorAll(".nav-surface-tab.open, .nav-view-btn.open").forEach(function (b) { b.classList.remove("open"); });
      openDD = null;
    }

    function positionDropdown(dd, btn) {
      var rect = btn.getBoundingClientRect();
      dd.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 240)) + "px";
    }

    // Create surface dropdowns
    SURFACES.forEach(function (surf) {
      if (surf.pages.length <= 1) return; // No dropdown for single-page surfaces

      var dd = document.createElement("div");
      dd.className = "nav-dropdown";
      dd.id = "ddSurface-" + surf.id;
      dd.innerHTML = buildSurfaceDropdown(surf);
      document.body.appendChild(dd);

      var btn = document.querySelector('.nav-surface-tab[data-surface="' + surf.id + '"]');
      if (!btn) return;

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
    });

    // For single-page surfaces, clicking navigates directly
    SURFACES.forEach(function (surf) {
      if (surf.pages.length > 1) return;
      var btn = document.querySelector('.nav-surface-tab[data-surface="' + surf.id + '"]');
      if (!btn) return;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        closeAll();
        window.location.href = pageHref(surf.primary);
      });
    });

    // Create View dropdown
    var ddView = document.createElement("div");
    ddView.className = "nav-dropdown";
    ddView.id = "ddView";
    ddView.innerHTML = buildViewDropdown();
    document.body.appendChild(ddView);

    var viewBtn = document.getElementById("mbView");
    if (viewBtn) {
      viewBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (openDD === ddView) { closeAll(); return; }
        closeAll();
        positionDropdown(ddView, viewBtn);
        ddView.classList.add("open");
        viewBtn.classList.add("open");
        openDD = ddView;
      });

      viewBtn.addEventListener("mouseenter", function () {
        if (openDD && openDD !== ddView) {
          closeAll();
          positionDropdown(ddView, viewBtn);
          ddView.classList.add("open");
          viewBtn.classList.add("open");
          openDD = ddView;
        }
      });
    }

    // Close on outside click and Escape
    document.addEventListener("click", function () { closeAll(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAll();
    });

    // Hamburger fallback
    var hb = document.getElementById("mbHamburger") || document.querySelector(".hamburger");
    if (hb) {
      hb.removeAttribute("onclick");
      hb.addEventListener("click", function (e) {
        e.stopPropagation();
        closeAll();
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

  // ── Inject CSS ────────────────────────────────────────────────
  function injectStyles() {
    var style = document.createElement("style");
    style.id = "nav-system-v5-css";
    style.textContent = [
      /* Surface tabs */
      ".nav-surface-tab {",
      "  font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase;",
      "  font-family: 'Sora', sans-serif; color: rgba(255,255,255,.5);",
      "  background: none; border: none; border-bottom: 2px solid transparent;",
      "  padding: 4px 10px; cursor: pointer; transition: all .15s;",
      "  display: inline-flex; align-items: center; gap: 3px;",
      "  height: 28px; box-sizing: border-box; line-height: 1;",
      "}",
      ".nav-surface-tab:hover { background: rgba(255,255,255,0.05); color: rgba(255,255,255,.8); }",
      ".nav-surface-tab.open { background: rgba(255,255,255,0.08); color: #fff; }",
      ".nav-surface-active { border-bottom-color: #00e5c4; color: #fff; }",
      ".nav-tab-arrow { font-size: 8px; opacity: 0.5; margin-left: 1px; }",

      /* Brand label */
      ".nav-brand-label {",
      "  font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase;",
      "  font-family: 'Orbitron', 'Sora', sans-serif; color: rgba(255,255,255,.7);",
      "  padding: 0 8px; cursor: default;",
      "}",

      /* View button */
      ".nav-view-btn {",
      "  font-size: 12px; letter-spacing: 0.05em;",
      "  font-family: 'Sora', sans-serif; color: rgba(255,255,255,.5);",
      "  background: none; border: none; padding: 4px 10px; cursor: pointer;",
      "  transition: all .15s; height: 28px; box-sizing: border-box;",
      "}",
      ".nav-view-btn:hover { color: rgba(255,255,255,.8); background: rgba(255,255,255,0.05); }",
      ".nav-view-btn.open { background: rgba(255,255,255,0.08); color: #fff; }",

      /* Divider */
      ".nav-divider {",
      "  width: 1px; height: 14px; background: rgba(255,255,255,.12);",
      "  margin: 0 4px; display: inline-block; vertical-align: middle;",
      "}",

      /* Spacer */
      ".nav-spacer { flex: 1; }",

      /* System icons */
      ".nav-sys-icon {",
      "  color: rgba(255,255,255,.45); padding: 2px 6px; cursor: pointer;",
      "  background: none; border: none; transition: color .15s;",
      "  display: inline-flex; align-items: center; text-decoration: none;",
      "}",
      ".nav-sys-icon:hover { color: rgba(255,255,255,.9); }",

      /* Mode toggle in menubar */
      ".nav-mode-toggle {",
      "  color: rgba(255,255,255,.45); font-size: 11px !important;",
      "  padding: 2px 8px; min-width: 40px; text-align: center;",
      "  background: none; border: none; cursor: pointer;",
      "  transition: color .2s;",
      "}",
      ".nav-mode-toggle:hover { color: rgba(255,255,255,.9); }",

      /* Clock and Date */
      ".nav-clock, .nav-date {",
      "  font-size: 11px; color: rgba(255,255,255,.45);",
      "  font-family: 'IBM Plex Mono', 'DM Mono', monospace;",
      "  font-variant-numeric: tabular-nums; padding: 0 4px; cursor: default;",
      "}",

      /* Unified dropdown (surfaces + view) */
      ".nav-dropdown {",
      "  position: fixed; top: 28px; left: 0; min-width: 200px;",
      "  background: rgba(28,28,30,.95); backdrop-filter: blur(20px);",
      "  -webkit-backdrop-filter: blur(20px);",
      "  border: 1px solid rgba(255,255,255,.1); border-radius: 8px;",
      "  box-shadow: 0 8px 32px rgba(0,0,0,.5); padding: 4px 0;",
      "  z-index: 10001; display: none;",
      "}",
      ".nav-dropdown.open { display: block; }",
      ".nav-dropdown a {",
      "  display: block; padding: 6px 14px; color: rgba(255,255,255,.7);",
      "  text-decoration: none; font-size: 12px; font-family: 'Sora', sans-serif;",
      "  transition: background .12s;",
      "}",
      ".nav-dropdown a:hover { background: rgba(255,255,255,.08); color: #fff; }",
      ".nav-dropdown a.dd-active { color: #00e5c4; }",
      ".nav-dropdown .dd-label {",
      "  font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;",
      "  color: rgba(255,255,255,.3); padding: 6px 14px 2px;",
      "  font-family: 'DM Mono', monospace;",
      "}",
      ".nav-dropdown .dd-sep { height: 1px; background: rgba(255,255,255,.08); margin: 4px 0; }",

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

      /* Light mode adjustments */
      "[data-brightness='light'] .nav-surface-tab { color: rgba(0,0,0,.45); }",
      "[data-brightness='light'] .nav-surface-tab:hover { background: rgba(0,0,0,.05); color: rgba(0,0,0,.8); }",
      "[data-brightness='light'] .nav-surface-tab.open { background: rgba(0,0,0,.08); color: #111; }",
      "[data-brightness='light'] .nav-surface-active { border-bottom-color: #00a89a; color: #111; }",
      "[data-brightness='light'] .nav-brand-label { color: rgba(0,0,0,.6); }",
      "[data-brightness='light'] .nav-view-btn { color: rgba(0,0,0,.45); }",
      "[data-brightness='light'] .nav-view-btn:hover { color: rgba(0,0,0,.8); background: rgba(0,0,0,.05); }",
      "[data-brightness='light'] .nav-view-btn.open { background: rgba(0,0,0,.08); color: #111; }",
      "[data-brightness='light'] .nav-divider { background: rgba(0,0,0,.12); }",
      "[data-brightness='light'] .nav-sys-icon { color: rgba(0,0,0,.4); }",
      "[data-brightness='light'] .nav-sys-icon:hover { color: rgba(0,0,0,.9); }",
      "[data-brightness='light'] .nav-clock, [data-brightness='light'] .nav-date { color: rgba(0,0,0,.4); }",
      "[data-brightness='light'] .nav-dropdown {",
      "  background: rgba(245,245,247,.95); border-color: rgba(0,0,0,.1);",
      "  box-shadow: 0 8px 32px rgba(0,0,0,.15);",
      "}",
      "[data-brightness='light'] .nav-dropdown a { color: rgba(0,0,0,.7); }",
      "[data-brightness='light'] .nav-dropdown a:hover { background: rgba(0,0,0,.05); color: #111; }",
      "[data-brightness='light'] .nav-dropdown a.dd-active { color: #00a89a; }",
      "[data-brightness='light'] .nav-dropdown .dd-label { color: rgba(0,0,0,.3); }",
      "[data-brightness='light'] .nav-dropdown .dd-sep { background: rgba(0,0,0,.08); }",
      "[data-brightness='light'] .nav-dd-zoom-slider { background: rgba(0,0,0,.12); }",
      "[data-brightness='light'] .nav-dd-zoom-slider::-webkit-slider-thumb { background: #00a89a; }",
      "[data-brightness='light'] .nav-dd-zoom-val { color: rgba(0,0,0,.5); }",
      "[data-brightness='light'] .nav-dd-mode-btn { border-color: rgba(0,0,0,.12); color: rgba(0,0,0,.5); }",
      "[data-brightness='light'] .nav-dd-mode-btn:hover { border-color: rgba(0,0,0,.2); color: rgba(0,0,0,.8); }",
      "[data-brightness='light'] .nav-dd-mode-btn.active { border-color: #00a89a; background: rgba(0,169,154,.1); color: #111; }",
      "[data-brightness='light'] .nav-dd-color-dot:hover { border-color: rgba(0,0,0,.3); }",
      "[data-brightness='light'] .nav-dd-color-dot.active { border-color: #111; box-shadow: 0 0 6px rgba(0,0,0,.2); }",
      "[data-brightness='light'] .nav-mode-toggle { color: rgba(0,0,0,.45); }",
      "[data-brightness='light'] .nav-mode-toggle:hover { color: rgba(0,0,0,.9); }",

      /* Ensure menubar is flex for spacer */
      ".os-menubar { display: flex; align-items: center; }"
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

  // ── Logo click -> Permanence OS ────────────────────────────────
  function wireLogoToggle() {
    var logo = document.querySelector(".mb-logo");
    if (!logo) return;
    var rt = window.__OPHTXN_RUNTIME || {};
    var ccUrl = rt.commandCenterUrl || rt.apiBase || "http://127.0.0.1:8000";
    logo.setAttribute("href", ccUrl);
    logo.setAttribute("target", "_blank");
    logo.setAttribute("rel", "noopener");
    logo.setAttribute("title", "Open Permanence OS");
  }

  // ── Wire mode toggle button ────────────────────────────────────
  function wireModeToggle() {
    var btn = document.getElementById("navModeToggle");
    if (!btn) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      cycleMode();
    });
    updateModeLabel();
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    injectStyles();
    removeOldElements();
    rewriteMenubar();
    wireLogoToggle();
    wireModeToggle();
    injectDropdowns();
    initKeyboard();
    applyZoom();

    // Apply saved theme and brightness
    var savedTheme = getThemeColor();
    if (savedTheme) setThemeColor(savedTheme);
    var savedMode = getMode();
    if (savedMode) setMode(savedMode);

    // Start clock
    updateClock();
    setInterval(updateClock, 30000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

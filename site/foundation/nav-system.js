/* ================================================================
   PERMANENCE OS -- Unified Navigation System
   Shared across all 14 Foundation Site pages.
   Provides: menu bar, dropdowns, back button, page slider,
   zoom controls, theme toggle, and keyboard shortcuts.
   ================================================================ */

(function () {
  "use strict";

  // ── Page Registry ──────────────────────────────────────────────
  var PAGES = [
    { id: "lobby",      file: "index.html",            label: "Lobby" },
    { id: "hub",        file: "local_hub.html",         label: "Control Room" },
    { id: "command",    file: "command_center.html",     label: "Command Center" },
    { id: "trading",    file: "trading_room.html",       label: "Trading Room" },
    { id: "markets",    file: "markets_terminal.html",   label: "Markets Terminal" },
    { id: "capital",    file: "night_capital.html",      label: "Night Capital" },
    { id: "planner",    file: "daily_planner.html",      label: "Daily Planner" },
    { id: "terminal",   file: "ophtxn_shell.html",       label: "Terminal" },
    { id: "tower",      file: "rooms.html",              label: "Tower" },
    { id: "school",     file: "ai_school.html",          label: "AI School" },
    { id: "studio",     file: "official_app.html",       label: "App Studio" },
    { id: "agent",      file: "agent_view.html",         label: "Agent View" },
    { id: "comms",      file: "comms_hub.html",          label: "Comms Hub" },
    { id: "mindmap",    file: "press_kit.html",          label: "Mind Map" },
  ];

  var currentFile = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  var currentIdx = PAGES.findIndex(function (p) { return p.file === currentFile; });
  if (currentIdx < 0) currentIdx = 0;

  // ── History Stack (for back button) ────────────────────────────
  var historyKey = "ophtxn_nav_history";
  function getHistory() {
    try { return JSON.parse(sessionStorage.getItem(historyKey) || "[]"); } catch (e) { return []; }
  }
  function pushHistory(file) {
    var h = getHistory();
    if (h[h.length - 1] !== file) h.push(file);
    if (h.length > 20) h = h.slice(-20);
    try { sessionStorage.setItem(historyKey, JSON.stringify(h)); } catch (e) { /* ignore */ }
  }
  function popHistory() {
    var h = getHistory();
    h.pop(); // remove current
    var prev = h.pop();
    try { sessionStorage.setItem(historyKey, JSON.stringify(h)); } catch (e) { /* ignore */ }
    return prev;
  }
  pushHistory(currentFile);

  // ── Zoom State ─────────────────────────────────────────────────
  var zoomKey = "ophtxn_zoom";
  var zoomLevels = [75, 80, 90, 100, 110, 125, 150];
  var zoomIdx = 3; // default 100%
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
    document.body.dataset.brightness = mode;
    try { localStorage.setItem("ophtxn_site_brightness", mode); } catch (e) { /* ignore */ }
    updateThemeLabel();
  }
  function updateThemeLabel() {
    var el = document.getElementById("nav-theme-label");
    if (el) {
      var m = getTheme();
      el.textContent = m.charAt(0).toUpperCase() + m.slice(1);
    }
  }

  // ── Inject Bottom Page Slider ──────────────────────────────────
  function createPageSlider() {
    var bar = document.createElement("div");
    bar.className = "page-slider";
    bar.setAttribute("role", "navigation");
    bar.setAttribute("aria-label", "Page navigation");

    // Back button
    var backBtn = document.createElement("button");
    backBtn.className = "ps-back";
    backBtn.title = "Go back";
    backBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>';
    backBtn.addEventListener("click", function () {
      var prev = popHistory();
      if (prev) { window.location.href = prev; }
      else if (window.history.length > 1) { window.history.back(); }
    });

    // Prev page
    var prevBtn = document.createElement("button");
    prevBtn.className = "ps-nav ps-prev";
    prevBtn.title = currentIdx > 0 ? PAGES[currentIdx - 1].label : "";
    prevBtn.disabled = currentIdx === 0;
    prevBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>';
    if (currentIdx > 0) {
      prevBtn.addEventListener("click", function () { window.location.href = PAGES[currentIdx - 1].file; });
    }

    // Page dots
    var dots = document.createElement("div");
    dots.className = "ps-dots";
    PAGES.forEach(function (p, i) {
      var dot = document.createElement("button");
      dot.className = "ps-dot" + (i === currentIdx ? " active" : "");
      dot.title = p.label;
      dot.setAttribute("aria-label", p.label);
      dot.addEventListener("click", function () { window.location.href = p.file; });
      dots.appendChild(dot);
    });

    // Current page label
    var label = document.createElement("span");
    label.className = "ps-label";
    label.textContent = PAGES[currentIdx].label;

    // Next page
    var nextBtn = document.createElement("button");
    nextBtn.className = "ps-nav ps-next";
    nextBtn.title = currentIdx < PAGES.length - 1 ? PAGES[currentIdx + 1].label : "";
    nextBtn.disabled = currentIdx === PAGES.length - 1;
    nextBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>';
    if (currentIdx < PAGES.length - 1) {
      nextBtn.addEventListener("click", function () { window.location.href = PAGES[currentIdx + 1].file; });
    }

    bar.appendChild(backBtn);
    bar.appendChild(prevBtn);
    bar.appendChild(dots);
    bar.appendChild(label);
    bar.appendChild(nextBtn);
    document.body.appendChild(bar);
  }

  // ── Inject Unified Dropdowns ───────────────────────────────────
  function createDropdowns() {
    // Remove existing dropdowns (old ddFile, ddView, ddGo, dd-file, dd-view, dd-go)
    ["ddFile", "ddView", "ddGo", "dd-file", "dd-view", "dd-go"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });

    // ── File Dropdown ──
    var ddFile = document.createElement("div");
    ddFile.className = "mb-dropdown";
    ddFile.id = "ddFile";
    ddFile.style.left = "72px";
    var fileHTML = '<div class="dd-label">Navigate</div>';
    PAGES.forEach(function (p, i) {
      var isCurrent = i === currentIdx;
      fileHTML += '<a href="' + p.file + '"' + (isCurrent ? ' class="dd-active"' : '') + '>' + p.label + '</a>';
      if (i === 8) fileHTML += '<div class="dd-sep"></div><div class="dd-label">Platform</div>';
    });
    ddFile.innerHTML = fileHTML;

    // ── View Dropdown ──
    var ddView = document.createElement("div");
    ddView.className = "mb-dropdown";
    ddView.id = "ddView";
    ddView.style.left = "112px";
    ddView.innerHTML =
      '<div class="dd-label">Appearance</div>' +
      '<div class="dd-row">' +
        '<button class="dd-mode-btn' + (getTheme() === "dark" ? " active" : "") + '" data-mode="dark">Dark</button>' +
        '<button class="dd-mode-btn' + (getTheme() === "light" ? " active" : "") + '" data-mode="light">Light</button>' +
        '<button class="dd-mode-btn' + (getTheme() === "system" ? " active" : "") + '" data-mode="system">System</button>' +
      '</div>' +
      '<div class="dd-sep"></div>' +
      '<div class="dd-label">Zoom</div>' +
      '<div class="dd-row dd-zoom-row">' +
        '<button class="dd-zoom-btn" id="nav-zoom-out" title="Zoom out">-</button>' +
        '<span class="dd-zoom-val" id="nav-zoom-label">' + zoomLevels[zoomIdx] + '%</span>' +
        '<button class="dd-zoom-btn" id="nav-zoom-in" title="Zoom in">+</button>' +
        '<button class="dd-zoom-btn dd-zoom-reset" id="nav-zoom-reset" title="Reset zoom">Reset</button>' +
      '</div>';

    // ── Go Dropdown ──
    var ddGo = document.createElement("div");
    ddGo.className = "mb-dropdown";
    ddGo.id = "ddGo";
    ddGo.style.left = "148px";
    ddGo.innerHTML =
      '<div class="dd-label">Quick Launch</div>' +
      '<a href="http://127.0.0.1:8000" target="_blank" rel="noopener">Command Center API</a>' +
      '<a href="http://127.0.0.1:8797/app/ophtxn" target="_blank" rel="noopener">Live Shell</a>' +
      '<div class="dd-sep"></div>' +
      '<div class="dd-label">External</div>' +
      '<a href="https://github.com/MaxProspero/permanence-os" target="_blank" rel="noopener">GitHub</a>';

    document.body.appendChild(ddFile);
    document.body.appendChild(ddView);
    document.body.appendChild(ddGo);

    // ── Wire dropdown toggles ──
    var menus = { mbFile: "ddFile", mbView: "ddView", mbGo: "ddGo" };
    var openDD = null;

    function closeAll() {
      document.querySelectorAll(".mb-dropdown.open").forEach(function (d) { d.classList.remove("open"); });
      document.querySelectorAll(".mb-mi.open").forEach(function (b) { b.classList.remove("open"); });
      openDD = null;
    }

    Object.keys(menus).forEach(function (btnId) {
      var btn = document.getElementById(btnId);
      var dd = document.getElementById(menus[btnId]);
      if (!btn || !dd) return;
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

    // Hamburger
    var hb = document.getElementById("mbHamburger");
    if (hb) {
      hb.addEventListener("click", function (e) {
        e.stopPropagation();
        var dd = document.getElementById("ddFile");
        if (!dd) return;
        if (openDD === dd) { closeAll(); }
        else { closeAll(); dd.classList.add("open"); dd.style.left = "12px"; openDD = dd; }
      });
    }

    // ── Wire theme buttons ──
    ddView.querySelectorAll(".dd-mode-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var mode = btn.dataset.mode;
        if (mode === "system") {
          mode = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
        }
        setTheme(mode);
        ddView.querySelectorAll(".dd-mode-btn").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
      });
    });

    // ── Wire zoom buttons ──
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
  }

  // ── Keyboard Shortcuts ─────────────────────────────────────────
  function initKeyboard() {
    document.addEventListener("keydown", function (e) {
      // Cmd+[ or Alt+Left = back
      if ((e.metaKey && e.key === "[") || (e.altKey && e.key === "ArrowLeft")) {
        e.preventDefault();
        var prev = popHistory();
        if (prev) window.location.href = prev;
        else if (window.history.length > 1) window.history.back();
      }
      // Cmd+] or Alt+Right = forward in page order
      if ((e.metaKey && e.key === "]") || (e.altKey && e.key === "ArrowRight")) {
        e.preventDefault();
        if (currentIdx < PAGES.length - 1) window.location.href = PAGES[currentIdx + 1].file;
      }
      // Cmd+= zoom in, Cmd+- zoom out, Cmd+0 reset
      if (e.metaKey && e.key === "=") { e.preventDefault(); if (zoomIdx < zoomLevels.length - 1) { zoomIdx++; applyZoom(); } }
      if (e.metaKey && e.key === "-") { e.preventDefault(); if (zoomIdx > 0) { zoomIdx--; applyZoom(); } }
      if (e.metaKey && e.key === "0") { e.preventDefault(); zoomIdx = 3; applyZoom(); }
    });
  }

  // ── Swipe Gesture (touch devices) ──────────────────────────────
  function initSwipe() {
    var startX = 0;
    var startY = 0;
    document.addEventListener("touchstart", function (e) {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });
    document.addEventListener("touchend", function (e) {
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      if (Math.abs(dx) > 80 && Math.abs(dy) < 50) {
        if (dx > 0 && currentIdx > 0) window.location.href = PAGES[currentIdx - 1].file;
        if (dx < 0 && currentIdx < PAGES.length - 1) window.location.href = PAGES[currentIdx + 1].file;
      }
    }, { passive: true });
  }

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    createDropdowns();
    createPageSlider();
    initKeyboard();
    initSwipe();
    applyZoom();
    updateThemeLabel();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

/* ================================================================
   PERMANENCE OS -- Terminal Overlay (Cmd+K)
   Global command palette overlay for all pages.

   Usage: Include <script src="terminal-overlay.js"></script> on any page.
   Opens with Cmd+K (Mac) or Ctrl+K (Windows/Linux).
   Closes with Escape or clicking outside.
   ================================================================ */

(function() {
  'use strict';

  var STORAGE_KEY = 'ophtxn_recent_commands';
  var MAX_RECENT = 8;

  // -- Quick actions definition --
  var QUICK_ACTIONS = [
    { label: 'Check Status', command: '/status' },
    { label: 'Approvals', command: '/approvals' },
    { label: 'Memory Search', command: '/memory search' }
  ];

  // -- Inject styles --
  var style = document.createElement('style');
  style.textContent = [
    '.term-overlay-scrim {',
    '  position: fixed; inset: 0; z-index: 10000;',
    '  background: rgba(10,10,15,0.85);',
    '  backdrop-filter: blur(20px);',
    '  -webkit-backdrop-filter: blur(20px);',
    '  display: none; align-items: flex-start; justify-content: center;',
    '  padding-top: min(20vh, 160px);',
    '}',
    '.term-overlay-scrim.open { display: flex; animation: term-fade-in 150ms ease-out; }',
    '@keyframes term-fade-in { from { opacity: 0; } to { opacity: 1; } }',

    '.term-overlay-card {',
    '  width: 100%; max-width: 640px;',
    '  background: rgba(18,18,26,0.95);',
    '  border: 1px solid rgba(255,255,255,0.10);',
    '  border-radius: 16px;',
    '  box-shadow: 0 16px 64px rgba(0,0,0,0.6), 0 0 1px rgba(255,255,255,0.08);',
    '  overflow: hidden;',
    '  animation: term-slide-in 200ms cubic-bezier(0.16,1,0.3,1);',
    '}',
    '@keyframes term-slide-in { from { opacity: 0; transform: translateY(-12px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }',

    '.term-overlay-header {',
    '  display: flex; align-items: center; gap: 10px;',
    '  padding: 16px 20px;',
    '  border-bottom: 1px solid rgba(255,255,255,0.06);',
    '}',
    '.term-overlay-icon {',
    '  width: 18px; height: 18px; flex-shrink: 0;',
    '  color: rgba(255,255,255,0.30);',
    '}',
    '.term-overlay-input {',
    '  flex: 1; background: none; border: none; outline: none;',
    '  font-family: "Sora", system-ui, sans-serif;',
    '  font-size: 18px; font-weight: 400;',
    '  color: #E0E0E0; caret-color: #00e5c4;',
    '}',
    '.term-overlay-input::placeholder { color: rgba(255,255,255,0.25); }',
    '.term-overlay-close {',
    '  background: rgba(255,255,255,0.06); border: none;',
    '  border-radius: 6px; padding: 4px 8px;',
    '  font-family: "DM Mono", monospace; font-size: 11px;',
    '  color: rgba(255,255,255,0.3); cursor: pointer;',
    '  transition: background 0.12s;',
    '}',
    '.term-overlay-close:hover { background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.5); }',

    '.term-overlay-body {',
    '  max-height: 60vh; overflow-y: auto;',
    '  padding: 12px 0;',
    '}',

    '.term-section-label {',
    '  padding: 8px 20px 4px;',
    '  font-family: "DM Mono", monospace; font-size: 10px;',
    '  font-weight: 500; letter-spacing: 0.12em;',
    '  text-transform: uppercase; color: rgba(255,255,255,0.20);',
    '}',

    '.term-result-item {',
    '  display: flex; align-items: center; gap: 10px;',
    '  padding: 8px 20px; cursor: pointer;',
    '  font-family: "Sora", system-ui, sans-serif; font-size: 14px;',
    '  color: #7B96AF;',
    '  transition: background 0.1s, color 0.1s;',
    '}',
    '.term-result-item:hover, .term-result-item.selected {',
    '  background: rgba(255,255,255,0.04); color: #E0E0E0;',
    '}',
    '.term-result-item .term-chevron {',
    '  color: rgba(255,255,255,0.15); font-size: 12px; margin-right: 2px;',
    '}',

    '.term-quick-actions {',
    '  display: flex; gap: 8px; padding: 12px 20px;',
    '  border-top: 1px solid rgba(255,255,255,0.04);',
    '}',
    '.term-quick-btn {',
    '  background: rgba(255,255,255,0.04);',
    '  border: 1px solid rgba(255,255,255,0.06);',
    '  border-radius: 8px; padding: 6px 14px;',
    '  font-family: "DM Mono", monospace; font-size: 11px;',
    '  color: #7B96AF; cursor: pointer;',
    '  transition: all 0.12s;',
    '}',
    '.term-quick-btn:hover {',
    '  background: rgba(0,229,196,0.08);',
    '  border-color: rgba(0,229,196,0.15);',
    '  color: #00e5c4;',
    '}',

    '.term-empty {',
    '  padding: 20px; text-align: center;',
    '  font-family: "DM Mono", monospace; font-size: 12px;',
    '  color: rgba(255,255,255,0.20);',
    '}'
  ].join('\n');
  document.head.appendChild(style);

  // -- Build DOM --
  var scrim = document.createElement('div');
  scrim.className = 'term-overlay-scrim';
  scrim.innerHTML = [
    '<div class="term-overlay-card">',
    '  <div class="term-overlay-header">',
    '    <svg class="term-overlay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">',
    '      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    '    </svg>',
    '    <input class="term-overlay-input" type="text" placeholder="Ask anything..." autocomplete="off" spellcheck="false">',
    '    <button class="term-overlay-close">Esc</button>',
    '  </div>',
    '  <div class="term-overlay-body"></div>',
    '  <div class="term-quick-actions"></div>',
    '</div>'
  ].join('');

  document.body.appendChild(scrim);

  var card = scrim.querySelector('.term-overlay-card');
  var input = scrim.querySelector('.term-overlay-input');
  var body = scrim.querySelector('.term-overlay-body');
  var actionsBar = scrim.querySelector('.term-quick-actions');
  var closeBtn = scrim.querySelector('.term-overlay-close');

  // -- Quick action buttons --
  QUICK_ACTIONS.forEach(function(action) {
    var btn = document.createElement('button');
    btn.className = 'term-quick-btn';
    btn.textContent = action.label;
    btn.addEventListener('click', function() {
      executeCommand(action.command);
    });
    actionsBar.appendChild(btn);
  });

  // -- Recent commands --
  function getRecent() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return [];
  }

  function addRecent(cmd) {
    var list = getRecent().filter(function(c) { return c !== cmd; });
    list.unshift(cmd);
    if (list.length > MAX_RECENT) list = list.slice(0, MAX_RECENT);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch (e) { /* ignore */ }
  }

  function renderRecent(filter) {
    body.innerHTML = '';
    var recent = getRecent();
    if (filter) {
      var lower = filter.toLowerCase();
      recent = recent.filter(function(c) { return c.toLowerCase().indexOf(lower) !== -1; });
    }

    if (recent.length === 0 && !filter) {
      body.innerHTML = '<div class="term-empty">No recent commands. Type something to get started.</div>';
      return;
    }

    if (recent.length === 0 && filter) {
      body.innerHTML = '<div class="term-empty">No results for "' + filter.replace(/</g, '&lt;') + '"</div>';
      return;
    }

    var label = document.createElement('div');
    label.className = 'term-section-label';
    label.textContent = 'RECENT';
    body.appendChild(label);

    recent.forEach(function(cmd) {
      var item = document.createElement('div');
      item.className = 'term-result-item';
      item.innerHTML = '<span class="term-chevron">></span> ' + cmd.replace(/</g, '&lt;');
      item.addEventListener('click', function() { executeCommand(cmd); });
      body.appendChild(item);
    });
  }

  function executeCommand(cmd) {
    addRecent(cmd);
    closeOverlay();
    // Dispatch a custom event so other scripts can listen
    var event = new CustomEvent('ophtxn:command', { detail: { command: cmd } });
    document.dispatchEvent(event);
  }

  // -- Open / Close --
  function openOverlay() {
    scrim.classList.add('open');
    input.value = '';
    renderRecent();
    // Delay focus slightly to allow animation to begin
    setTimeout(function() { input.focus(); }, 50);
  }

  function closeOverlay() {
    scrim.classList.remove('open');
    input.value = '';
  }

  function isOpen() {
    return scrim.classList.contains('open');
  }

  // -- Event listeners --
  document.addEventListener('keydown', function(e) {
    // Cmd+K or Ctrl+K to open
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (isOpen()) {
        closeOverlay();
      } else {
        openOverlay();
      }
      return;
    }

    // Escape to close
    if (e.key === 'Escape' && isOpen()) {
      e.preventDefault();
      closeOverlay();
    }
  });

  // Click outside card to close
  scrim.addEventListener('click', function(e) {
    if (e.target === scrim) {
      closeOverlay();
    }
  });

  closeBtn.addEventListener('click', function() { closeOverlay(); });

  // Input handling with debounce
  var debounceTimer = null;
  input.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
      renderRecent(input.value.trim());
    }, 120);
  });

  // Enter to execute
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      var val = input.value.trim();
      if (val) {
        executeCommand(val);
      }
    }
  });

})();

/* ================================================================
   PERMANENCE OS -- Inbox Overlay Panel
   Global right-side inbox panel for all pages.

   Usage: Include <script src="inbox-overlay.js"></script> on any page.
   Opens by clicking the inbox icon in the menubar.
   Closes with Escape, clicking outside, or the close button.
   ================================================================ */

(function() {
  'use strict';

  var STORAGE_KEY = 'ophtxn_inbox_items';

  // -- Inject styles --
  var style = document.createElement('style');
  style.textContent = [
    '.inbox-scrim {',
    '  position: fixed; inset: 0; z-index: 9000;',
    '  background: rgba(0,0,0,0.30);',
    '  display: none;',
    '}',
    '.inbox-scrim.open { display: block; animation: inbox-scrim-in 150ms ease-out; }',
    '@keyframes inbox-scrim-in { from { opacity: 0; } to { opacity: 1; } }',

    '.inbox-panel {',
    '  position: fixed; right: 0; top: 28px;',
    '  width: 320px; height: calc(100vh - 28px);',
    '  z-index: 9001;',
    '  background: rgba(18,18,26,0.95);',
    '  backdrop-filter: blur(20px);',
    '  -webkit-backdrop-filter: blur(20px);',
    '  border-left: 1px solid rgba(255,255,255,0.08);',
    '  display: flex; flex-direction: column;',
    '  transform: translateX(100%);',
    '  transition: transform 250ms cubic-bezier(0.16,1,0.3,1);',
    '}',
    '.inbox-panel.open { transform: translateX(0); }',

    '.inbox-header {',
    '  display: flex; align-items: center; justify-content: space-between;',
    '  padding: 16px 20px;',
    '  border-bottom: 1px solid rgba(255,255,255,0.06);',
    '  flex-shrink: 0;',
    '}',
    '.inbox-title {',
    '  font-family: "DM Mono", monospace; font-size: 11px;',
    '  font-weight: 500; letter-spacing: 0.12em;',
    '  text-transform: uppercase; color: rgba(255,255,255,0.50);',
    '}',
    '.inbox-close {',
    '  background: rgba(255,255,255,0.06); border: none;',
    '  border-radius: 6px; padding: 4px 8px;',
    '  font-family: "DM Mono", monospace; font-size: 11px;',
    '  color: rgba(255,255,255,0.3); cursor: pointer;',
    '  transition: background 0.12s;',
    '}',
    '.inbox-close:hover { background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.5); }',

    '.inbox-body {',
    '  flex: 1; overflow-y: auto; padding: 0;',
    '}',

    '.inbox-empty {',
    '  padding: 48px 20px; text-align: center;',
    '}',
    '.inbox-empty-title {',
    '  font-family: "Sora", system-ui, sans-serif; font-size: 14px;',
    '  color: rgba(255,255,255,0.35); margin-bottom: 8px;',
    '}',
    '.inbox-empty-hint {',
    '  font-family: "DM Mono", monospace; font-size: 11px;',
    '  color: rgba(255,255,255,0.18); line-height: 1.5;',
    '}',

    '.inbox-item {',
    '  padding: 14px 20px;',
    '  border-bottom: 1px solid rgba(255,255,255,0.04);',
    '  transition: background 0.1s;',
    '}',
    '.inbox-item:hover { background: rgba(255,255,255,0.03); }',
    '.inbox-item-header {',
    '  display: flex; align-items: center; gap: 8px; margin-bottom: 6px;',
    '}',
    '.inbox-item-badge {',
    '  display: inline-block; padding: 2px 8px;',
    '  background: rgba(0,229,196,0.08);',
    '  border: 1px solid rgba(0,229,196,0.15);',
    '  border-radius: 4px;',
    '  font-family: "DM Mono", monospace; font-size: 10px;',
    '  color: #00e5c4; text-transform: uppercase; letter-spacing: 0.06em;',
    '}',
    '.inbox-item-badge.alert {',
    '  background: rgba(255,69,58,0.08);',
    '  border-color: rgba(255,69,58,0.15);',
    '  color: #FF453A;',
    '}',
    '.inbox-item-badge.agent {',
    '  background: rgba(123,111,255,0.08);',
    '  border-color: rgba(123,111,255,0.15);',
    '  color: #7b6fff;',
    '}',
    '.inbox-item-time {',
    '  font-family: "DM Mono", monospace; font-size: 10px;',
    '  color: rgba(255,255,255,0.18); margin-left: auto;',
    '}',
    '.inbox-item-title {',
    '  font-family: "Sora", system-ui, sans-serif; font-size: 13px;',
    '  font-weight: 500; color: #E0E0E0; margin-bottom: 4px;',
    '}',
    '.inbox-item-body {',
    '  font-family: "Sora", system-ui, sans-serif; font-size: 12px;',
    '  color: #7B96AF; line-height: 1.45;',
    '}',
    '.inbox-item-actions {',
    '  display: flex; gap: 6px; margin-top: 10px;',
    '}',
    '.inbox-action-btn {',
    '  background: rgba(255,255,255,0.04);',
    '  border: 1px solid rgba(255,255,255,0.06);',
    '  border-radius: 6px; padding: 4px 12px;',
    '  font-family: "DM Mono", monospace; font-size: 10px;',
    '  color: #7B96AF; cursor: pointer;',
    '  transition: all 0.12s;',
    '}',
    '.inbox-action-btn:hover {',
    '  background: rgba(255,255,255,0.07);',
    '  color: #E0E0E0;',
    '}',
    '.inbox-action-btn.approve {',
    '  background: rgba(0,229,196,0.06);',
    '  border-color: rgba(0,229,196,0.12);',
    '  color: #00e5c4;',
    '}',
    '.inbox-action-btn.approve:hover {',
    '  background: rgba(0,229,196,0.12);',
    '}',

    '.inbox-footer {',
    '  flex-shrink: 0;',
    '  padding: 12px 20px;',
    '  border-top: 1px solid rgba(255,255,255,0.06);',
    '}',
    '.inbox-capture {',
    '  width: 100%; background: rgba(255,255,255,0.04);',
    '  border: 1px solid rgba(255,255,255,0.06);',
    '  border-radius: 8px; padding: 10px 14px;',
    '  font-family: "Sora", system-ui, sans-serif; font-size: 13px;',
    '  color: #E0E0E0; outline: none;',
    '  transition: border-color 0.2s;',
    '}',
    '.inbox-capture::placeholder { color: rgba(255,255,255,0.20); }',
    '.inbox-capture:focus { border-color: rgba(0,229,196,0.25); }',

    '@media (max-width: 400px) {',
    '  .inbox-panel { width: 100%; }',
    '}'
  ].join('\n');
  document.head.appendChild(style);

  // -- Build DOM --
  var scrim = document.createElement('div');
  scrim.className = 'inbox-scrim';
  document.body.appendChild(scrim);

  var panel = document.createElement('div');
  panel.className = 'inbox-panel';
  panel.innerHTML = [
    '<div class="inbox-header">',
    '  <span class="inbox-title">Inbox</span>',
    '  <button class="inbox-close">X</button>',
    '</div>',
    '<div class="inbox-body"></div>',
    '<div class="inbox-footer">',
    '  <input class="inbox-capture" type="text" placeholder="Capture something...">',
    '</div>'
  ].join('');
  document.body.appendChild(panel);

  var bodyEl = panel.querySelector('.inbox-body');
  var closeBtn = panel.querySelector('.inbox-close');
  var captureInput = panel.querySelector('.inbox-capture');

  // -- Storage helpers --
  function getItems() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return [];
  }

  function saveItems(items) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch (e) { /* ignore */ }
  }

  function addItem(title, type) {
    var items = getItems();
    items.unshift({
      id: Date.now().toString(36),
      title: title,
      type: type || 'note',
      time: new Date().toISOString(),
      body: ''
    });
    saveItems(items);
    renderItems();
  }

  function removeItem(id) {
    var items = getItems().filter(function(item) { return item.id !== id; });
    saveItems(items);
    renderItems();
  }

  // -- Render --
  function renderItems() {
    var items = getItems();
    bodyEl.innerHTML = '';

    if (items.length === 0) {
      bodyEl.innerHTML = [
        '<div class="inbox-empty">',
        '  <div class="inbox-empty-title">No items in inbox</div>',
        '  <div class="inbox-empty-hint">Items will appear here as agents process inputs and surface decisions.</div>',
        '</div>'
      ].join('');
      return;
    }

    items.forEach(function(item) {
      var el = document.createElement('div');
      el.className = 'inbox-item';

      var badgeClass = 'inbox-item-badge';
      if (item.type === 'alert') badgeClass += ' alert';
      if (item.type === 'agent') badgeClass += ' agent';

      var timeStr = '';
      try {
        var d = new Date(item.time);
        var h = d.getHours(), m = d.getMinutes();
        var ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12 || 12;
        timeStr = h + ':' + String(m).padStart(2, '0') + ' ' + ampm;
      } catch (e) { /* ignore */ }

      el.innerHTML = [
        '<div class="inbox-item-header">',
        '  <span class="' + badgeClass + '">' + (item.type || 'note') + '</span>',
        '  <span class="inbox-item-time">' + timeStr + '</span>',
        '</div>',
        '<div class="inbox-item-title">' + (item.title || '').replace(/</g, '&lt;') + '</div>',
        item.body ? '<div class="inbox-item-body">' + item.body.replace(/</g, '&lt;') + '</div>' : '',
        '<div class="inbox-item-actions">',
        '  <button class="inbox-action-btn approve" data-action="approve">Approve</button>',
        '  <button class="inbox-action-btn" data-action="task">To task</button>',
        '  <button class="inbox-action-btn" data-action="dismiss">Dismiss</button>',
        '</div>'
      ].join('');

      // Wire action buttons
      el.querySelectorAll('.inbox-action-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var action = btn.getAttribute('data-action');
          if (action === 'dismiss') {
            removeItem(item.id);
          } else if (action === 'approve') {
            removeItem(item.id);
            dispatchInboxEvent('approve', item);
          } else if (action === 'task') {
            removeItem(item.id);
            dispatchInboxEvent('task', item);
          }
        });
      });

      bodyEl.appendChild(el);
    });
  }

  function dispatchInboxEvent(action, item) {
    var event = new CustomEvent('ophtxn:inbox', { detail: { action: action, item: item } });
    document.dispatchEvent(event);
  }

  // -- Open / Close --
  function openPanel() {
    renderItems();
    scrim.classList.add('open');
    panel.classList.add('open');
  }

  function closePanel() {
    scrim.classList.remove('open');
    panel.classList.remove('open');
  }

  function isOpen() {
    return panel.classList.contains('open');
  }

  // -- Wire inbox icon in menubar --
  // The nav-system.js creates an inbox icon; we listen for clicks on it
  function wireInboxIcon() {
    var icon = document.getElementById('mbInbox') || document.querySelector('[data-inbox-trigger]');
    if (icon) {
      icon.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (isOpen()) { closePanel(); } else { openPanel(); }
      });
    }
  }

  // Try wiring immediately, and also after nav-system loads
  wireInboxIcon();
  document.addEventListener('DOMContentLoaded', wireInboxIcon);
  // Also try after a short delay for dynamically injected nav
  setTimeout(wireInboxIcon, 500);

  // -- Event listeners --
  scrim.addEventListener('click', closePanel);
  closeBtn.addEventListener('click', closePanel);

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isOpen()) {
      e.preventDefault();
      closePanel();
    }
  });

  // Capture input
  captureInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      var val = captureInput.value.trim();
      if (!val) return;
      addItem(val, 'note');
      captureInput.value = '';
    }
  });

  // Expose API for other scripts to push items
  window.ophtxnInbox = {
    open: openPanel,
    close: closePanel,
    add: addItem,
    remove: removeItem
  };

})();

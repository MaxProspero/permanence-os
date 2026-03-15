(() => {
  "use strict";

  const runtime = window.__OPHTXN_RUNTIME || {};
  const body = document.body;
  if (!body || body.dataset.surfaceSystem === "ready") return;
  body.dataset.surfaceSystem = "ready";

  const page = (() => {
    const path = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    if (path === "index.html" || path === "") return "foundation";
    if (path === "local_hub.html") return "hub";
    if (path === "command_center.html") return "command";
    if (path === "ophtxn_shell.html") return "shell";
    return "other";
  })();

  const services = [
    {
      id: "foundation",
      label: "Foundation",
      mode: "Front Door",
      href: "index.html",
      probe: (runtime.siteUrl || "http://127.0.0.1:8787").replace(/\/$/, "") + "/",
      active: page === "foundation",
    },
    {
      id: "hub",
      label: "Local Hub",
      mode: "Launch Cockpit",
      href: "local_hub.html",
      probe: (runtime.siteUrl || "http://127.0.0.1:8787").replace(/\/$/, "") + "/local_hub.html",
      active: page === "hub",
    },
    {
      id: "command",
      label: "Command Center",
      mode: "Execution Plane",
      href: runtime.commandCenterUrl || "http://127.0.0.1:8000",
      probe: (runtime.commandCenterUrl || "http://127.0.0.1:8000").replace(/\/$/, "") + "/api/status",
      active: page === "command",
    },
    {
      id: "shell",
      label: "Ophtxn Shell",
      mode: "Operator Console",
      href: runtime.shellUrl || "http://127.0.0.1:8797/app/ophtxn",
      probe: (runtime.appBase || "http://127.0.0.1:8797").replace(/\/$/, "") + "/health",
      active: page === "shell",
    },
  ];

  const current = services.find((svc) => svc.active) || services[0];
  const briefs = {
    foundation: {
      kicker: "Governed Personal Intelligence OS",
      title: "A front door for the runtime, not a marketing shell.",
      copy: "Permanence OS is designed as one local-first operating system with four modes: thesis, launch, execution, and operator context. The interface should explain that system clearly before it tries to impress anybody.",
      artifacts: ["\"INTEL\"", "\"OPS\"", "\"REVIEW\""],
      doctrine: [
        ["Operator", "Human remains final authority"],
        ["State", "Local-first governed runtime"],
        ["Shape", "Four surfaces, one OS family"],
      ],
      chips: [
        ["Mission", "Personal OS first"],
        ["Protocol", "Task tree orchestration"],
        ["Review", "No autonomy without audit"],
        ["Memory", "Context compounds across sessions"],
      ],
      actions: [
        { label: "Open Local Hub", href: "local_hub.html", kind: "primary" },
        { label: "Open Live Shell", href: runtime.shellUrl || "http://127.0.0.1:8797/app/ophtxn", kind: "secondary", external: true },
      ],
    },
    hub: {
      kicker: "Launch Cockpit",
      title: "The place where system state becomes operator action.",
      copy: "Local Hub should read like the live readiness layer for the whole stack: runtime health, approvals, agent posture, and the shortest path into command execution.",
      artifacts: ["\"OPS\"", "\"ARENA\"", "\"REVIEW\""],
      doctrine: [
        ["Readiness", "Verify runtimes before action"],
        ["Queue", "Approvals stay visible"],
        ["Flow", "Launch, verify, then route"],
      ],
      chips: [
        ["Readiness", "Three runtimes in one family"],
        ["Approvals", "Queue before irreversible action"],
        ["Fleet", "Active agents and constitution status"],
        ["Flow", "Launch → verify → operate"],
      ],
      actions: [
        { label: "Open Command Center", href: runtime.commandCenterUrl || "http://127.0.0.1:8000", kind: "primary", external: true },
        { label: "Open Shell", href: runtime.shellUrl || "http://127.0.0.1:8797/app/ophtxn", kind: "secondary", external: true },
      ],
    },
    command: {
      kicker: "Execution Plane",
      title: "Mission control for governed work, reviews, and live decisions.",
      copy: "Command Center is where orchestration, ledger logic, command flow, and review-gated change requests become legible. It should feel like an office for consequential decisions, not a novelty dashboard.",
      artifacts: ["\"COMMAND\"", "\"CAPITAL\"", "\"REVIEW\""],
      doctrine: [
        ["Authority", "Review before mutation"],
        ["Ledger", "Every write leaves provenance"],
        ["Focus", "One big data point per panel"],
      ],
      chips: [
        ["Command", "Intent decomposes into tasks"],
        ["Ledger", "Every write leaves an audit trail"],
        ["Review", "Diff preview before commit"],
        ["Telemetry", "Fleet health and fuel gauges"],
      ],
      actions: [
        { label: "Open Shell", href: runtime.shellUrl || "http://127.0.0.1:8797/app/ophtxn", kind: "primary", external: true },
        { label: "Back To Hub", href: "local_hub.html", kind: "secondary" },
      ],
    },
    shell: {
      kicker: "Operator Console",
      title: "A personal shell with memory, approvals, and system awareness.",
      copy: "Ophtxn Shell is the intimate mode of the OS. It should still feel connected to the wider system: approvals, mission state, command context, and local runtime posture should all stay visible.",
      artifacts: ["\"CONTEXT\"", "\"MEMORY\"", "\"REVIEW\""],
      doctrine: [
        ["Mode", "Conversation with operating context"],
        ["Memory", "Context compounds across sessions"],
        ["Boundary", "Ask before high-impact action"],
      ],
      chips: [
        ["Console", "Natural language with governed actions"],
        ["Context", "Session memory plus runtime state"],
        ["Queue", "Approvals stay close to the operator"],
        ["Bridge", "Chat mode connected to the system"],
      ],
      actions: [
        { label: "Open Command Center", href: runtime.commandCenterUrl || "http://127.0.0.1:8000", kind: "primary", external: true },
        { label: "Open Local Hub", href: "local_hub.html", kind: "secondary" },
      ],
    },
  };
  const brief = briefs[page] || briefs.foundation;

  const style = document.createElement("style");
  style.textContent = `
    .ops-system-brief {
      position: relative;
      z-index: 2;
      margin: 18px auto 22px;
      width: min(1200px, calc(100vw - 48px));
      padding: 22px 22px 18px;
      border-radius: 24px;
      border: 1px solid rgba(115,184,255,.14);
      background:
        linear-gradient(180deg, rgba(9, 14, 24, .86), rgba(6, 9, 15, .7)),
        radial-gradient(circle at top right, rgba(0,229,196,.12), transparent 30%),
        radial-gradient(circle at bottom left, rgba(123,111,255,.08), transparent 30%);
      box-shadow: 0 18px 60px rgba(0,0,0,.28);
      overflow: hidden;
    }
    .ops-system-brief::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, rgba(255,255,255,.04), transparent 18%, transparent 82%, rgba(255,255,255,.03)),
        linear-gradient(rgba(255,255,255,.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.02) 1px, transparent 1px);
      background-size: auto, 48px 48px, 48px 48px;
      opacity: .42;
      pointer-events: none;
    }
    .ops-system-grid {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    .ops-system-artifacts {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 14px;
    }
    .ops-system-artifact {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 0 12px;
      border-radius: 999px;
      border: 1px solid rgba(146,188,214,.12);
      background: rgba(255,255,255,.025);
      font: 700 11px/1 var(--mono, monospace);
      letter-spacing: .14em;
      text-transform: uppercase;
      color: var(--ink, #e7f4ff);
    }
    .ops-system-kicker {
      margin: 0 0 8px;
      font: 700 11px/1.2 var(--mono, monospace);
      letter-spacing: .18em;
      text-transform: uppercase;
      color: var(--muted, #7b96af);
    }
    .ops-system-title {
      margin: 0 0 10px;
      font: 800 clamp(24px, 4vw, 40px)/1.02 var(--sans, sans-serif);
      letter-spacing: -.04em;
      max-width: 14ch;
      color: var(--ink, #e7f4ff);
    }
    .ops-system-copy {
      max-width: 64ch;
      margin: 0;
      color: #b8cad8;
      font-size: 14px;
      line-height: 1.72;
    }
    .ops-system-doctrine {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0 0;
    }
    .ops-system-rule {
      min-width: 0;
      padding: 12px 12px 10px;
      border-radius: 14px;
      border: 1px solid rgba(146,188,214,.1);
      background: rgba(255,255,255,.025);
    }
    .ops-system-rule-label {
      display: block;
      margin-bottom: 5px;
      font: 700 10px/1.2 var(--mono, monospace);
      letter-spacing: .14em;
      text-transform: uppercase;
      color: #8ca8bf;
    }
    .ops-system-rule-value {
      display: block;
      color: var(--ink, #e7f4ff);
      font: 600 12px/1.45 var(--sans, sans-serif);
    }
    .ops-system-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 16px;
    }
    .ops-system-action {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 16px;
      border-radius: 999px;
      border: 1px solid rgba(146,188,214,.14);
      text-decoration: none;
      font: 700 11px/1 var(--mono, monospace);
      letter-spacing: .12em;
      text-transform: uppercase;
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }
    .ops-system-action:hover {
      transform: translateY(-1px);
      border-color: rgba(115,184,255,.22);
    }
    .ops-system-action.primary {
      color: #07121a;
      background: linear-gradient(135deg, rgba(242,237,232,.96), rgba(201,168,76,.92));
      border-color: rgba(201,168,76,.34);
      box-shadow: 0 10px 30px rgba(0,0,0,.18);
    }
    .ops-system-action.secondary {
      color: var(--ink, #e7f4ff);
      background: rgba(255,255,255,.03);
    }
    .ops-system-stack {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .ops-system-chip {
      min-width: 0;
      padding: 12px 13px;
      border-radius: 16px;
      border: 1px solid rgba(146,188,214,.12);
      background: rgba(255,255,255,.03);
    }
    .ops-system-chip-label {
      display: block;
      margin-bottom: 6px;
      font: 700 10px/1.2 var(--mono, monospace);
      letter-spacing: .14em;
      text-transform: uppercase;
      color: #8ca8bf;
    }
    .ops-system-chip-value {
      display: block;
      font: 700 13px/1.35 var(--sans, sans-serif);
      color: var(--ink, #e7f4ff);
    }
    .mb-mi,
    .mb-dropdown a,
    .mb-dropdown button,
    .page-title,
    .sidebar-title {
      font-family: var(--sans, sans-serif) !important;
      letter-spacing: .01em;
    }
    .page-subtitle,
    .tab,
    .shell-link,
    .metric-chip span:first-child,
    .chip {
      font-family: var(--mono, monospace) !important;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    .mb-tagline {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid rgba(170,205,227,.14);
      background: rgba(255,255,255,.05);
      color: #e5eef5 !important;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
    }
    .mb-dropdown {
      background:
        linear-gradient(180deg, rgba(11, 16, 24, .96), rgba(12, 19, 28, .93)) !important;
      border-color: rgba(170, 205, 227, .18) !important;
      box-shadow: 0 18px 48px rgba(0,0,0,.38), 0 0 0 1px rgba(255,255,255,.03) !important;
    }
    .mb-dropdown a,
    .mb-dropdown button {
      color: #f2f8fc !important;
    }
    .mb-dropdown a:hover,
    .mb-dropdown button:hover {
      background: rgba(255,255,255,.09) !important;
    }
    .mb-dropdown .dd-icon,
    .dd-icon {
      width: 24px !important;
      height: 24px !important;
      display: inline-flex !important;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      border: 1px solid rgba(170,205,227,.18);
      background: rgba(255,255,255,.045);
      color: rgba(244,249,252,.92);
      opacity: 1 !important;
      flex: 0 0 24px;
    }
    .mb-dropdown .dd-icon svg,
    .dd-icon svg {
      width: 13px;
      height: 13px;
      stroke: currentColor;
      fill: none;
      stroke-width: 1.7;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .tab {
      border-color: rgba(146,188,214,.12) !important;
    }
    .tab.on,
    .tab.active {
      border-color: rgba(201,168,76,.24) !important;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 10px 24px rgba(0,0,0,.18);
    }
    .sidebar,
    .metrics-bar,
    #footer,
    .status-bar {
      backdrop-filter: blur(18px) saturate(1.12);
      -webkit-backdrop-filter: blur(18px) saturate(1.12);
    }
    .ops-clock-trigger {
      cursor: pointer;
      padding: 3px 8px;
      border-radius: 7px;
      transition: background .14s ease, color .14s ease;
    }
    .ops-clock-trigger:hover,
    .ops-clock-trigger.open {
      background: rgba(255,255,255,.08);
      color: var(--ink, #e7f4ff);
    }
    .mb-date.ops-clock-trigger {
      color: #dbe7f0;
    }
    .ops-clock-dropdown {
      min-width: 260px;
      right: 12px;
      left: auto;
      top: 32px;
      padding: 8px;
    }
    .ops-clock-panel {
      border-radius: 14px;
      border: 1px solid rgba(170,205,227,.14);
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.025));
      padding: 12px;
    }
    .ops-clock-city {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(146,188,214,.08);
    }
    .ops-clock-city:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .ops-clock-city:first-child {
      padding-top: 0;
    }
    .ops-clock-label {
      display: flex;
      flex-direction: column;
      gap: 3px;
      min-width: 0;
    }
    .ops-clock-name {
      font: 700 11px/1.1 var(--sans, sans-serif);
      color: var(--ink, #e7f4ff);
    }
    .ops-clock-meta {
      font: 600 9px/1.1 var(--mono, monospace);
      letter-spacing: .12em;
      text-transform: uppercase;
      color: #9db4c7;
    }
    .ops-clock-time {
      font: 700 11px/1 var(--mono, monospace);
      letter-spacing: .08em;
      color: var(--ink, #e7f4ff);
      white-space: nowrap;
    }
    .ops-clock-footer {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid rgba(146,188,214,.08);
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .ops-clock-chip {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid rgba(146,188,214,.12);
      background: rgba(255,255,255,.025);
      font: 700 9px/1 var(--mono, monospace);
      letter-spacing: .12em;
      text-transform: uppercase;
      color: #a7bfd1;
    }
    .ops-surface-banner {
      position: fixed;
      right: 20px;
      bottom: 94px;
      z-index: 8800;
      width: min(320px, calc(100vw - 32px));
      padding: 14px 16px;
      border: 1px solid rgba(115,184,255,.16);
      border-radius: 18px;
      background:
        linear-gradient(180deg, rgba(11, 18, 28, .93), rgba(12, 18, 27, .84)),
        radial-gradient(circle at top right, rgba(0,229,196,.14), transparent 42%);
      box-shadow: 0 20px 60px rgba(0,0,0,.34);
      backdrop-filter: blur(18px) saturate(1.25);
      -webkit-backdrop-filter: blur(18px) saturate(1.25);
      color: var(--ink, #e7f4ff);
    }
    .ops-surface-banner::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      background:
        linear-gradient(120deg, rgba(0,229,196,.06), transparent 30%, rgba(123,111,255,.04) 70%, transparent);
      pointer-events: none;
    }
    .ops-surface-kicker {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
      font: 600 10px/1.2 var(--mono, monospace);
      letter-spacing: .16em;
      text-transform: uppercase;
      color: #a3bbcd;
    }
    .ops-surface-chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid rgba(0,229,196,.18);
      background: rgba(0,229,196,.08);
      color: var(--ink, #e7f4ff);
    }
    .ops-surface-chip-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #efbb5f;
      box-shadow: 0 0 0 4px rgba(239,187,95,.12);
    }
    .ops-surface-title {
      margin: 0 0 4px;
      font: 800 clamp(18px, 2vw, 24px)/1.05 var(--sans, sans-serif);
      letter-spacing: -.03em;
    }
    .ops-surface-copy {
      margin: 0;
      color: #b5c8d7;
      font-size: 13px;
      line-height: 1.6;
    }
    .ops-runtime-dock {
      position: fixed;
      left: 50%;
      bottom: 20px;
      transform: translateX(-50%);
      z-index: 8900;
      display: flex;
      align-items: stretch;
      gap: 10px;
      width: min(940px, calc(100vw - 24px));
      padding: 10px;
      border-radius: 22px;
      border: 1px solid rgba(146,188,214,.14);
      background:
        linear-gradient(180deg, rgba(11, 17, 26, .9), rgba(9, 13, 20, .84)),
        radial-gradient(circle at top center, rgba(115,184,255,.08), transparent 55%);
      box-shadow: 0 22px 60px rgba(0,0,0,.34);
      backdrop-filter: blur(18px) saturate(1.2);
      -webkit-backdrop-filter: blur(18px) saturate(1.2);
    }
    .ops-runtime-card {
      position: relative;
      flex: 1 1 0;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      text-decoration: none;
      color: inherit;
      border: 1px solid transparent;
      background: rgba(255,255,255,.02);
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }
    .ops-runtime-card:hover {
      transform: translateY(-2px);
      border-color: rgba(115,184,255,.16);
      background: rgba(255,255,255,.04);
    }
    .ops-runtime-card.is-active {
      border-color: rgba(0,229,196,.28);
      background:
        linear-gradient(180deg, rgba(0,229,196,.14), rgba(0,229,196,.03)),
        rgba(255,255,255,.03);
    }
    .ops-runtime-mark {
      width: 38px;
      height: 38px;
      flex: 0 0 38px;
      display: grid;
      place-items: center;
      border-radius: 12px;
      font: 700 11px/1 var(--mono, monospace);
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--ink, #e7f4ff);
      background: linear-gradient(135deg, rgba(115,184,255,.24), rgba(123,111,255,.14));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
    }
    .ops-runtime-meta {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .ops-runtime-label {
      font: 700 13px/1.15 var(--sans, sans-serif);
      color: var(--ink, #e7f4ff);
    }
    .ops-runtime-mode {
      font: 500 11px/1.25 var(--mono, monospace);
      letter-spacing: .08em;
      text-transform: uppercase;
      color: #abc0d1;
    }
    .ops-runtime-state {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding-left: 12px;
      font: 600 10px/1 var(--mono, monospace);
      letter-spacing: .08em;
      text-transform: uppercase;
      color: #abc0d1;
    }
    .ops-runtime-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: rgba(239,187,95,.95);
      box-shadow: 0 0 0 5px rgba(239,187,95,.08);
    }
    .ops-runtime-dot.live {
      background: rgba(0,229,196,.95);
      box-shadow: 0 0 0 5px rgba(0,229,196,.12);
    }
    .ops-runtime-dot.dead {
      background: rgba(255,92,138,.95);
      box-shadow: 0 0 0 5px rgba(255,92,138,.12);
    }
    @media (max-width: 980px) {
      .ops-system-grid {
        grid-template-columns: 1fr;
      }
      .ops-runtime-dock {
        flex-direction: column;
        width: min(480px, calc(100vw - 20px));
      }
      .ops-runtime-state {
        min-width: 72px;
      }
    }
    @media (max-width: 640px) {
      .ops-system-brief {
        width: min(100vw - 20px, 1200px);
        margin: 14px auto 16px;
        padding: 18px 16px 14px;
        border-radius: 20px;
      }
      .ops-system-stack {
        grid-template-columns: 1fr;
      }
      .ops-system-doctrine {
        grid-template-columns: 1fr;
      }
      .ops-system-title {
        max-width: none;
      }
      .ops-surface-banner {
        left: 12px;
        right: 12px;
        width: auto;
        bottom: auto;
        top: 44px;
      }
      .ops-runtime-dock {
        left: 12px;
        right: 12px;
        bottom: 12px;
        width: auto;
        transform: none;
      }
      .ops-runtime-card {
        align-items: flex-start;
        padding: 11px 12px;
      }
      .ops-runtime-state {
        margin-left: 0;
        padding-left: 0;
      }
    }
  `;
  document.head.appendChild(style);

  const buildBrief = () => {
    const section = document.createElement("section");
    section.className = "ops-system-brief";
    section.innerHTML = `
      <div class="ops-system-grid">
        <div>
          <div class="ops-system-artifacts">
            ${brief.artifacts
              .map((artifact) => `<span class="ops-system-artifact">${artifact}</span>`)
              .join("")}
          </div>
          <p class="ops-system-kicker">${brief.kicker}</p>
          <h2 class="ops-system-title">${brief.title}</h2>
          <p class="ops-system-copy">${brief.copy}</p>
          <div class="ops-system-doctrine">
            ${brief.doctrine
              .map(
                ([label, value]) => `
                  <div class="ops-system-rule">
                    <span class="ops-system-rule-label">${label}</span>
                    <span class="ops-system-rule-value">${value}</span>
                  </div>
                `,
              )
              .join("")}
          </div>
          <div class="ops-system-actions">
            ${brief.actions
              .map((action) => {
                const target = action.external ? ' target="_blank" rel="noopener"' : "";
                return `<a class="ops-system-action ${action.kind}" href="${action.href}"${target}>${action.label}</a>`;
              })
              .join("")}
          </div>
        </div>
        <div class="ops-system-stack">
          ${brief.chips
            .map(
              ([label, value]) => `
                <div class="ops-system-chip">
                  <span class="ops-system-chip-label">${label}</span>
                  <span class="ops-system-chip-value">${value}</span>
                </div>
              `,
            )
            .join("")}
        </div>
      </div>
    `;
    return section;
  };

  const insertBrief = () => {
    const section = buildBrief();
    if (page === "foundation") {
      const shell = document.querySelector("main.shell");
      if (shell) shell.insertBefore(section, shell.firstElementChild);
      return;
    }
    if (page === "hub") {
      const shell = document.querySelector(".shell");
      const header = shell && shell.querySelector(".page-header");
      if (shell && header && header.parentNode === shell) {
        shell.insertBefore(section, header.nextSibling);
      } else if (shell) {
        shell.insertBefore(section, shell.firstElementChild);
      }
      return;
    }
    if (page === "command") {
      const app = document.getElementById("app");
      if (app) app.insertBefore(section, app.firstElementChild);
      return;
    }
    if (page === "shell") {
      const main = document.querySelector(".chat-main");
      const metricsBar = main && document.getElementById("metricsBar");
      if (main && metricsBar && metricsBar.parentNode === main) {
        main.insertBefore(section, metricsBar.nextSibling);
      } else if (main) {
        main.insertBefore(section, main.firstElementChild);
      }
    }
  };

  insertBrief();

  const iconSvg = (kind) => {
    const icons = {
      lobby: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 7.5 8 3l5.5 4.5"/><path d="M4.5 6.5v6h7v-6"/><path d="M7 12.5V9h2v3.5"/></svg>`,
      hub: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3.5h10v9H3z"/><path d="M5.5 10V7"/><path d="M8 10V5.5"/><path d="M10.5 10V8"/></svg>`,
      command: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10"/><path d="M3 8h10"/><path d="M3 11.5h6"/><path d="M11.5 11.5h1"/></svg>`,
      trading: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 11.5 6.5 8l2.5 2 4-4"/><path d="M10.5 6h2.5v2.5"/></svg>`,
      terminal: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 4.5 6.5 7.5 3.5 10.5"/><path d="M8.5 11h4"/></svg>`,
      tower: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 13V3h6v10"/><path d="M3.5 13h9"/><path d="M6.5 6h3"/></svg>`,
      school: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 5.5 8 3l5.5 2.5L8 8 2.5 5.5Z"/><path d="M4 6.5v3.5c0 .8 1.8 2 4 2s4-1.2 4-2V6.5"/></svg>`,
      studio: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3.5h10v9H3z"/><path d="M6 6.5h4"/><path d="M6 9.5h4"/></svg>`,
      agent: `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="5.5" r="2.2"/><path d="M4.5 12c.7-1.7 2-2.5 3.5-2.5S10.8 10.3 11.5 12"/></svg>`,
      comms: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10v6H7l-3 2v-2H3z"/></svg>`,
      map: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4.5 6 3l4 1.5 3.5-1v8L10 13l-4-1.5-3.5 1z"/><path d="M6 3v8.5"/><path d="M10 4.5V13"/></svg>`,
      github: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.2 12.5c-3 .9-3-1.4-4.2-1.7"/><path d="M10.8 12.5v-2.3c0-.7.1-1.1-.3-1.5 1.4-.2 2.8-.7 2.8-3.2 0-.7-.2-1.3-.7-1.8.1-.2.3-.9-.1-1.8 0 0-.6-.2-1.9.7a6.7 6.7 0 0 0-3.4 0c-1.3-.9-1.9-.7-1.9-.7-.4.9-.2 1.6-.1 1.8-.4.5-.7 1.1-.7 1.8 0 2.5 1.4 3 2.8 3.2-.4.4-.4 1-.4 1.5v2.3"/></svg>`,
      generic: `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10"/><path d="M8 3v10"/></svg>`,
    };
    return icons[kind] || icons.generic;
  };

  const navIconKind = (label, href) => {
    const text = `${label} ${href}`.toLowerCase();
    if (text.includes("lobby") || text.includes("index")) return "lobby";
    if (text.includes("control room") || text.includes("local hub")) return "hub";
    if (text.includes("command center") || text.includes("go-cc")) return "command";
    if (text.includes("trading room") || text.includes("markets terminal") || text.includes("night capital")) return "trading";
    if (text.includes("terminal") || text.includes("shell")) return "terminal";
    if (text.includes("tower") || text.includes("rooms")) return "tower";
    if (text.includes("school")) return "school";
    if (text.includes("app studio") || text.includes("official_app")) return "studio";
    if (text.includes("agent view")) return "agent";
    if (text.includes("comms")) return "comms";
    if (text.includes("mind map") || text.includes("press kit")) return "map";
    if (text.includes("github")) return "github";
    return "generic";
  };

  const decorateNavIcons = () => {
    document.querySelectorAll(".mb-dropdown a, .mb-dropdown button").forEach((item) => {
      const iconSlot = item.querySelector(".dd-icon");
      if (!iconSlot) return;
      const label = (item.textContent || "").trim();
      const href = item.getAttribute("href") || item.id || "";
      iconSlot.innerHTML = iconSvg(navIconKind(label, href));
    });
  };

  decorateNavIcons();
  window.setTimeout(decorateNavIcons, 120);
  window.setTimeout(decorateNavIcons, 480);

  const navObserver = new MutationObserver(() => decorateNavIcons());
  navObserver.observe(document.body, { childList: true, subtree: true });

  const buildClockDropdown = () => {
    const clock = document.getElementById("mbClock");
    const date = document.getElementById("mbDate");
    const right = clock && clock.parentElement;
    if (!clock || !right || document.getElementById("opsClockDropdown")) return;

    clock.classList.add("ops-clock-trigger");
    if (date) date.classList.add("ops-clock-trigger");

    const host = document.createElement("div");
    host.id = "opsClockDropdown";
    host.className = "mb-dropdown ops-clock-dropdown";
    host.innerHTML = `
      <div class="ops-clock-panel">
        <div class="ops-clock-city">
          <div class="ops-clock-label">
            <span class="ops-clock-name">Local Runtime</span>
            <span class="ops-clock-meta">Operator Time</span>
          </div>
          <span class="ops-clock-time" data-clock-zone="local">--:--</span>
        </div>
        <div class="ops-clock-city">
          <div class="ops-clock-label">
            <span class="ops-clock-name">New York</span>
            <span class="ops-clock-meta">Market Session</span>
          </div>
          <span class="ops-clock-time" data-clock-zone="America/New_York">--:--</span>
        </div>
        <div class="ops-clock-city">
          <div class="ops-clock-label">
            <span class="ops-clock-name">UTC</span>
            <span class="ops-clock-meta">Audit Reference</span>
          </div>
          <span class="ops-clock-time" data-clock-zone="UTC">--:--</span>
        </div>
        <div class="ops-clock-footer">
          <span class="ops-clock-chip">"REVIEW" Aware</span>
          <span class="ops-clock-chip">Local-first</span>
          <span class="ops-clock-chip">Chronicle Time</span>
        </div>
      </div>
    `;
    right.appendChild(host);

    const close = () => {
      host.classList.remove("open");
      clock.classList.remove("open");
      if (date) date.classList.remove("open");
    };
    const open = () => {
      host.classList.add("open");
      clock.classList.add("open");
      if (date) date.classList.add("open");
      updateClockDropdown();
    };
    const toggle = (event) => {
      event.stopPropagation();
      if (host.classList.contains("open")) close();
      else open();
    };

    clock.addEventListener("click", toggle);
    if (date) date.addEventListener("click", toggle);
    clock.addEventListener("mouseenter", () => {
      if (document.querySelector(".mb-dropdown.open")) open();
    });
    host.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", close);

    const formatClock = (zone) => {
      const date = new Date();
      if (zone === "local") {
        return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      }
      return new Intl.DateTimeFormat("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZone: zone,
      }).format(date);
    };

    const updateClockDropdown = () => {
      host.querySelectorAll("[data-clock-zone]").forEach((node) => {
        node.textContent = formatClock(node.getAttribute("data-clock-zone"));
      });
    };

    updateClockDropdown();
    setInterval(updateClockDropdown, 1000);
  };

  buildClockDropdown();

  const banner = document.createElement("aside");
  banner.className = "ops-surface-banner";
  banner.innerHTML = `
    <div class="ops-surface-kicker">
      <span>Ophtxn Runtime Surface</span>
      <span class="ops-surface-chip"><span class="ops-surface-chip-dot"></span>${current.mode}</span>
    </div>
    <h2 class="ops-surface-title">${current.label}</h2>
    <p class="ops-surface-copy">One governed interface family across launch, execution, and live operator context. Each surface stays distinct, but none of them should feel disconnected.</p>
  `;
  document.body.appendChild(banner);

  const dock = document.createElement("nav");
  dock.className = "ops-runtime-dock";
  dock.setAttribute("aria-label", "Runtime navigation");
  dock.innerHTML = services
    .map((svc) => {
      const initials = svc.label.split(" ").map((word) => word[0]).join("").slice(0, 2);
      const target = /^https?:\/\//i.test(svc.href) ? ' target="_blank" rel="noopener"' : "";
      return `
        <a class="ops-runtime-card${svc.active ? " is-active" : ""}" href="${svc.href}" data-runtime-id="${svc.id}"${target}>
          <span class="ops-runtime-mark">${initials}</span>
          <span class="ops-runtime-meta">
            <span class="ops-runtime-label">${svc.label}</span>
            <span class="ops-runtime-mode">${svc.mode}</span>
          </span>
          <span class="ops-runtime-state">
            <span class="ops-runtime-dot" id="ops-dot-${svc.id}"></span>
            <span id="ops-state-${svc.id}">Probe</span>
          </span>
        </a>
      `;
    })
    .join("");
  document.body.appendChild(dock);

  const setState = (id, state, text) => {
    const dot = document.getElementById(`ops-dot-${id}`);
    const label = document.getElementById(`ops-state-${id}`);
    if (!dot || !label) return;
    dot.classList.remove("live", "dead");
    if (state === "live") dot.classList.add("live");
    if (state === "dead") dot.classList.add("dead");
    label.textContent = text;
  };

  const probe = (svc) => {
    fetch(svc.probe, { signal: AbortSignal.timeout(2600) })
      .then((response) => {
        setState(svc.id, response.ok ? "live" : "dead", response.ok ? "Live" : "Error");
      })
      .catch(() => {
        setState(svc.id, "dead", "Offline");
      });
  };

  services.forEach((svc) => probe(svc));
})();

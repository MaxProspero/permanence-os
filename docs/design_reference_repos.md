# Design Reference Repos -- Permanence OS Foundation Site Redesign

Last updated: 2026-03-19

## Tier 1: Primary References (study these first)

| Repo | Stars | Stack | Study For |
|------|-------|-------|-----------|
| glanceapp/glance | 32K | Go + HTML/CSS | Widget grid, minimal dark dashboard |
| lobehub/lobe-chat | 60K | Next.js, React | AI chat UI, model switching, agent system |
| netdata/netdata | 76K | C + React | Real-time charts on dark backgrounds |
| HeyPuter/puter | 35K | Vanilla JS | Web OS shell, taskbar, window management |
| maybe-finance/maybe | -- | Next.js, Tailwind | Finance dashboard, dark mode, net worth |
| ghostfolio/ghostfolio | -- | Angular, NestJS | Portfolio viz, allocation charts, Zen Mode |
| midday-ai/midday | -- | Next.js, shadcn/ui | Solo operator fintech, dark dashboard |
| danny-avila/LibreChat | 34K | React, Node | ChatGPT clone, artifacts, code interpreter |
| open-webui/open-webui | 55K | SvelteKit | Clean chat UI, model selector |
| OpenBB-finance/OpenBB | 25K | Python + React | Finance terminal, candlestick charts |

## Tier 2: Design Patterns

| Repo | Stars | Study For |
|------|-------|-----------|
| twentyhq/twenty | -- | Cmd+K command palette, keyboard-first |
| makeplane/plane | 46K | Multi-view layouts, Linear-style |
| calcom/cal.com | 36K | Time-based UI, form flows |
| dubinc/dub | 18K | Analytics dashboard, obsessive UX |
| louislam/uptime-kuma | 60K | Status indicators, real-time monitoring |
| documenso/documenso | 10K | Approval flow UX, shadcn/ui patterns |
| hcengineering (Huly) | -- | Everything-app combining chat+docs+projects |

## Tier 3: Component Libraries (copy-paste effects)

| Resource | What to steal |
|----------|--------------|
| ui.aceternity.com | Spotlight, aurora bg, moving borders, card tilt |
| magicui.design | Number tickers, text reveal, blur-fade, marquee |
| ibelick/motion-primitives | Smooth accordion, dialog, transition animations |
| horizon-ui/horizon-ui-chakra | Glassmorphism cards, gradient accents |
| BangerTech/Prism-Dashboard | Frosted glass blur CSS values |
| Yhooi2/shadcn-glass-ui | 48+ glass components |

## Tier 4: Layout Patterns

| Repo | Stars | Study For |
|------|-------|-----------|
| Lissy93/dashy | -- | Widget grid, 25+ themes, drag-and-drop |
| homarr-labs/homarr | -- | Drag-and-drop cards, service integration |
| gethomepage/homepage | -- | Service status cards, Docker integration |
| satnaing/shadcn-admin | 2.8K | Admin patterns, command palette |
| Kiranism/next-shadcn-dashboard-starter | 6K | Kanban, multi-theme, RBAC |

## Page-to-Repo Mapping

| Permanence OS Page | Primary Reference | Secondary |
|-------------------|------------------|-----------|
| Lobby (index.html) | Glance | Midday |
| Control Room (local_hub.html) | Uptime Kuma | Homarr |
| Command Center | Midday | shadcn-admin |
| Trading Room | Ghostfolio | OpenBB |
| Markets Terminal | Netdata | Maybe Finance |
| Night Capital | Maybe Finance | Ghostfolio |
| Daily Planner | Cal.com | Plane |
| Terminal (Ophtxn Shell) | Twenty CRM (Cmd+K) | Puter |
| Tower (rooms.html) | Dashy | Plane (multi-view) |
| AI School | LobeChat | LibreChat |
| App Studio | Documenso | Huly |
| Agent View | LobeChat | LibreChat |
| Comms Hub | Glance | Huly |
| Mind Map | Plane | -- |

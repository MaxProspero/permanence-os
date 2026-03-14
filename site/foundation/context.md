# Foundation Site Context

## Goal
14 HTML pages forming the visual surface of Permanence OS.

## Pages
| File | Purpose |
|------|---------|
| index.html | Landing page -- system overview, pillars, timeline, signup |
| command_center.html | Command Center -- operational dashboard, service status |
| agent_view.html | Agent View -- agent roster, department structure, status |
| comms_hub.html | Comms Hub -- communications dashboard, Telegram/Discord/email |
| rooms.html | Rooms -- collaborative workspace panels |
| ophtxn_shell.html | Ophtxn Shell -- terminal-style AI interaction interface |
| trading_room.html | Trading Room -- market data, backtests, trading signals |
| markets_terminal.html | Markets Terminal -- live market terminal, quotes, data feeds |
| daily_planner.html | Daily Planner -- task management, schedule, priorities |
| night_capital.html | Night Capital -- after-hours operations, overnight automation |
| local_hub.html | Local Hub -- local service health, system status dashboard |
| official_app.html | Official App -- app download, feature showcase |
| ai_school.html | AI School -- learning resources, training modules |
| press_kit.html | Press Kit -- brand assets, media resources, public info |

## Routing Table
| Task | Read These Files | Skip These Files |
|------|-----------------|-----------------|
| Edit Page | Target .html, /design/rules.md | All Python files |
| Add Nav Link | ALL .html files (update every page) | /scripts, /core |
| Fix Styles | Target .html, /design/rules.md | Other .html files |
| New Page | index.html (template), /design/rules.md, /workflows/new_page.md | /agents |

## Standards
- Every page must link to every other page via File dropdown
- Consistent menubar across all pages
- Same Google Fonts link on every page
- Same CSS custom property names (--c1, --c2, --c3, --rose, --violet)
- NO emojis

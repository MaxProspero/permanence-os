# Design Rules -- Permanence OS Foundation Site

## CSS Custom Properties (Tokens)

All pages must define these tokens in `:root`:

```css
:root {
  /* Backgrounds */
  --bg:      #060a10;
  --bg-card: rgba(10, 18, 30, 0.72);
  --glass:   rgba(12, 22, 38, 0.58);

  /* Lines and borders */
  --line:    rgba(146, 188, 214, 0.14);
  --line-hi: rgba(0, 229, 196, 0.25);

  /* Text */
  --ink:     #e7f4ff;
  --muted:   #7b96af;
  --dim:     #3a5068;

  /* Accent colors */
  --c1:      #00e5c4;   /* Teal -- primary accent */
  --c2:      #efbb5f;   /* Gold -- secondary accent */
  --c3:      #73b8ff;   /* Blue -- tertiary accent */
  --rose:    #ff5c8a;   /* Rose -- alerts, errors */
  --violet:  #7b6fff;   /* Violet -- highlight, special */

  /* Radius */
  --radius:  16px;

  /* Font stacks */
  --mono:    "DM Mono", "IBM Plex Mono", monospace;
  --sans:    "Sora", system-ui, sans-serif;
  --game:    "Orbitron", monospace;

  /* Film grain overlay */
  --f-rgb:   160,150,140;
  --f:       rgb(var(--f-rgb));
}
```

## Font Stack

| Usage | Font Family | Weights | CSS Variable |
|-------|------------|---------|-------------|
| Body text | Sora | 400, 600, 700, 800 | var(--sans) |
| Code / monospace | IBM Plex Mono | 400, 600 | var(--mono) |
| Display / headings | Orbitron | 700, 900 | var(--game) |
| Labels / small mono | DM Mono | 400, 500 | var(--mono) |

### Google Fonts Link (required on every page)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;600&family=Orbitron:wght@700;900&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Forbidden Fonts
Never use these as primary display fonts:
- Inter
- Roboto
- Arial
- Space Grotesk

## Color Palette Reference

| Name | Hex | CSS Variable | Usage |
|------|-----|-------------|-------|
| Teal | #00e5c4 | var(--c1) | Primary accent, live indicators, links |
| Gold | #efbb5f | var(--c2) | Secondary accent, status labels, highlights |
| Blue | #73b8ff | var(--c3) | Tertiary accent, informational |
| Rose | #ff5c8a | var(--rose) | Alerts, errors, destructive actions |
| Violet | #7b6fff | var(--violet) | Special highlights, progress bars |
| Ink | #e7f4ff | var(--ink) | Primary text |
| Muted | #7b96af | var(--muted) | Secondary text |
| Dim | #3a5068 | var(--dim) | Tertiary text, disabled states |
| Background | #060a10 | var(--bg) | Page background |
| Card BG | rgba(10,18,30,0.72) | var(--bg-card) | Card backgrounds |
| Glass | rgba(12,22,38,0.58) | var(--glass) | Glassmorphism panels |
| Line | rgba(146,188,214,0.14) | var(--line) | Default borders |
| Line Highlight | rgba(0,229,196,0.25) | var(--line-hi) | Active/hover borders |

## Component Patterns

### Glassmorphism Card
```css
.card {
  background: var(--bg-card);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
}
.card:hover {
  border-color: var(--line-hi);
}
```

### Corner Brackets (decorative)
```css
.bracket::before,
.bracket::after {
  content: "";
  position: absolute;
  width: 12px;
  height: 12px;
  border-color: var(--c1);
  border-style: solid;
}
.bracket::before {
  top: 0; left: 0;
  border-width: 2px 0 0 2px;
}
.bracket::after {
  bottom: 0; right: 0;
  border-width: 0 2px 2px 0;
}
```

### Menubar
The menubar appears at the top of every page. It contains:
- File dropdown with links to all 13 Foundation pages
- View dropdown
- Window dropdown
- Optional page-specific dropdowns
- Right-aligned status indicators

Key rules:
- Background: rgba(10,18,30,0.95) with backdrop-filter: blur(18px)
- Fixed position at top
- z-index: 1000
- Font: var(--mono) at 13px
- All 13 pages must be linked in the File dropdown on every page

### Navigation (File Dropdown)
Every page must include links to all Foundation pages in the File dropdown:
1. index.html -- Home / Landing
2. command_center.html -- Command Center
3. agent_view.html -- Agent View
4. comms_hub.html -- Comms Hub
5. rooms.html -- Rooms
6. ophtxn_shell.html -- Ophtxn Shell
7. trading_room.html -- Trading Room
8. daily_planner.html -- Daily Planner
9. night_capital.html -- Night Capital
10. local_hub.html -- Local Hub
11. official_app.html -- Official App
12. ai_school.html -- AI School
13. press_kit.html -- Press Kit

### Film Grain Overlay
```css
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  background: url("data:image/svg+xml,...") repeat;
  opacity: 0.03;
}
```

### Staggered Animations
```css
.animate { opacity: 0; transform: translateY(20px); animation: fadeUp 0.6s forwards; }
.animate:nth-child(1) { animation-delay: 0.1s; }
.animate:nth-child(2) { animation-delay: 0.2s; }
.animate:nth-child(3) { animation-delay: 0.3s; }
/* Continue pattern for additional children */

@keyframes fadeUp {
  to { opacity: 1; transform: translateY(0); }
}
```

## Responsive Breakpoints

| Breakpoint | Target |
|-----------|--------|
| Default | 1440px desktop |
| max-width: 900px | Tablet |
| max-width: 600px | Mobile (375px) |

Key responsive rules:
- Grid layouts collapse to single column below 900px
- Font sizes reduce by 1-2px on mobile
- Padding reduces from 24px to 16px on mobile
- Menubar remains fixed on all viewports
- Cards stack vertically on mobile

## General Rules
- NO emojis anywhere -- use text labels, CSS shapes, or SVG icons
- Always use CSS custom properties, never hardcoded hex in component styles
- backdrop-filter requires -webkit- prefix for Safari
- All images must have alt text
- Page title format: "PageName | Permanence OS"
- meta theme-color: #0a1118

# Design Workspace Context

## Goal
Manage visual layout, UI components, and aesthetic standards for all Foundation Site pages.

## Routing Table
| Task | Read These Files | Skip These Files | Skills |
|------|-----------------|-----------------|--------|
| Change Layout | /design/rules.md, /site/foundation/*.html | /scripts, /tests, /core | CSS, Glassmorphism |
| Update Colors | /design/rules.md, /canon/brand_identity.yaml | /agents, /memory | CSS Variables |
| New Page | /site/foundation/index.html (template), /design/rules.md | /scripts, /docs | HTML, CSS |
| Fix Responsive | Target page HTML | All other pages | CSS Media Queries |

## Visual Philosophy
- Tone: Dark, atmospheric, governance-grade intelligence aesthetic
- Style: Glassmorphism panels, grain overlay, scanlines, ambient gradients
- Density: High information density with clear hierarchy

## Design Rules
- Fonts: Sora (body), IBM Plex Mono (code), Orbitron (display), DM Mono (labels)
- Colors: --c1 teal, --c2 gold, --c3 blue, --rose, --violet (use CSS custom properties)
- Cards: backdrop-filter: blur(18px), rgba backgrounds, corner brackets
- Animations: Staggered via nth-child with animation-delay
- Responsive: Must work at 1440px and 375px
- NO emojis -- text labels and CSS shapes only
- NO Inter, Roboto, Arial, or Space Grotesk fonts

## Pipeline
1. Brief: Define the change in plain English
2. Spec: Generate technical spec before coding
3. Build: Execute in /site/foundation/
4. Verify: Screenshot at 1440px and 375px

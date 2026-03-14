# Workflow: Create a New Foundation Page

## Prerequisites
- Read /design/rules.md for CSS tokens, font stacks, and component patterns
- Read /site/foundation/index.html as the reference template
- Confirm the page name and purpose before starting

## Steps

### 1. Copy the Template
- Copy /site/foundation/index.html to /site/foundation/{new_page_name}.html
- This ensures you start with the correct meta tags, Google Fonts link, CSS tokens, menubar structure, and film grain overlay

### 2. Update Page Metadata
- Change the `<title>` tag to: `{Page Title} | Permanence OS`
- Update `<meta name="description">` with a page-specific description
- Update Open Graph and Twitter Card meta tags
- Update or remove JSON-LD structured data as appropriate

### 3. Update the Menubar
- The menubar must contain links to all Foundation pages in the File dropdown
- Verify all 13 pages are listed (see /design/rules.md for the full list)
- Set the current page link as active/highlighted

### 4. Replace Page Content
- Remove the index.html body content below the menubar
- Build the new page content using the design system components:
  - Glassmorphism cards for content panels
  - Corner brackets for decorative emphasis
  - Staggered animations for reveal effects
  - CSS custom properties for all colors (never hardcoded hex)

### 5. Ensure Responsive Layout
- Test at 1440px (desktop) and 375px (mobile)
- Grid layouts should collapse to single column below 900px
- Reduce padding from 24px to 16px on mobile
- Verify menubar works on all viewports

### 6. Update All Other Pages
- CRITICAL: Add the new page to the File dropdown on ALL existing Foundation pages
- This means editing all 13 (now 14) .html files in /site/foundation/
- The new link must appear in the same position in every File dropdown

### 7. Verify Font Stack
- Confirm the Google Fonts link includes: Sora, IBM Plex Mono, Orbitron, DM Mono
- Confirm no forbidden fonts are used (Inter, Roboto, Arial, Space Grotesk)

### 8. Check for Prohibited Patterns
- NO emojis -- use text labels and CSS shapes only
- NO setInterval with intervals less than 30000ms for health polling
- NO hardcoded colors -- use CSS custom properties
- All fetch calls must use AbortController

### 9. Final Checklist
- [ ] Page renders correctly at 1440px
- [ ] Page renders correctly at 375px
- [ ] Menubar has all Foundation page links
- [ ] All other pages updated with new page link
- [ ] CSS custom properties used throughout
- [ ] Google Fonts link present and correct
- [ ] No forbidden fonts
- [ ] No emojis
- [ ] Film grain overlay present
- [ ] Page title follows naming convention

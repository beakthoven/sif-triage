# Industrial Trust Blue — Complete Design System Specification
### Expanded edition: for designers, frontend developers, and AI coding agents

> **How to use this document:** This is written so that someone with little design experience — including an AI model generating code — can implement the "Industrial Trust" direction correctly without having to guess or invent conventions. Every number, color, and rule below is either a fixed standard (WCAG, and named industry motion/spacing systems) or a value computed and verified specifically for this palette. Nothing here is decorative — every rule exists to solve a real usability problem for an HSE (Health, Safety, Environment) platform. Where a rule is derived from an external standard, the source is named inline and listed again at the end.

---

## 1. Design Principles (read this first)

1. **One accent color, everywhere.** Orange (`#FF6B1A`) is the *only* color used for primary calls-to-action and interactive highlights. If you find yourself using orange for something that isn't clickable, or blue for something that is meant to grab attention, you've broken the system.
2. **Status colors carry meaning, not decoration.** Red/amber/green are reserved exclusively for compliance/safety status (overdue, warning, compliant). Never reuse them for branding, marketing banners, or unrelated UI.
3. **Color is never the only signal.** Every status must be paired with an icon and a text label. This is a hard accessibility requirement (WCAG 1.4.1), not a style preference — colorblind users (~8% of men) cannot rely on red vs. green alone.
4. **Numbers must never jitter.** Any place a number updates live (KPI tiles, counts) must use a monospace or tabular-figure font so digits don't shift width and cause layout jumps.
5. **Motion explains, it doesn't perform.** Every animation in this system exists to help the user understand a state change (something opened, something moved, something was confirmed). If an animation doesn't communicate a state change, remove it.

---

## 2. Color System

### 2.1 Base Palette

| Token name | Hex | Role |
|---|---|---|
| `color-primary` | `#0B2545` | Deep Industrial Blue — headers, nav, primary surfaces |
| `color-primary-hover` | `#123A6B` | Hover state for primary-colored elements |
| `color-secondary` | `#1B4B8A` | Steel Blue — secondary surfaces, links |
| `color-accent` | `#FF6B1A` | Safety Orange — CTAs, active states, focus highlights only |
| `color-accent-hover` | `#E55A0D` | Hover state for accent buttons |
| `color-bg` | `#F7F9FC` | Cool White — page background |
| `color-surface` | `#FFFFFF` | Card/panel background |
| `color-text` | `#1C2B36` | Graphite — default body text |
| `color-text-muted` | `#5A6B78` | Secondary/caption text |
| `color-border` | `#DCE3EA` | Cloud Gray — dividers, card borders, table lines |

### 2.2 Status Colors — Verified, Text-Safe Values

The obvious/saturated version of a status color (bright amber, bright green) usually **fails WCAG contrast when used as text on a light background**. The table below gives you two versions of each status color: a **fill** (for icon backgrounds, chip backgrounds, chart lines — doesn't need text contrast) and a **text-safe** shade (verified to pass AA for body-size text). Always use the text-safe shade when the color is applied to text or small icons; use the fill shade for larger blocks, chart lines, or dots ≥ 3:1 against the background (non-text UI components only need 3:1 per WCAG 1.4.11).

| Status | Fill (chips/dots/charts) | Text-safe shade (labels, small icons) | Verified contrast on `#F7F9FC` |
|---|---|---|---|
| 🔴 Critical / Overdue | `#D62828` | `#D62828` | **4.75:1** — passes AA for normal text |
| 🟡 Warning / Due soon | `#F2A900` (fill only — **do not use as text**, only 1.91:1) | `#8A5A00` | **5.62:1** — passes AA for normal text |
| 🟢 Compliant / Good | `#2E9E6B` (fill only — 3.20:1, borderline, use only for icons/large text/UI components) | `#17603F` | **7.16:1** — passes AAA for normal text |

**Chip/badge pattern** (colored text on a very light tint of the same hue — verified pairs, safe to copy directly):

| Status | Chip background | Chip text | Contrast |
|---|---|---|---|
| Critical | `#FBE7E5` | `#B3261E` | 5.5:1 ✅ |
| Warning | `#FBF0D9` | `#8A5A00` | 5.24:1 ✅ |
| Compliant | `#E4F3EC` | `#17603F` | 6.59:1 ✅ |

> ⚠️ **Do not use `#F2A900` (bright amber) or `#2E9E6B` (bright green) as text color on the light background.** They were part of the original moodboard palette but measured at 1.91:1 and 3.20:1 respectively — both fail WCAG AA for text (needs 4.5:1). Use them only as: chart line colors, icon fills at ≥24px, or dot indicators, always 3:1 or better against their immediate background, and always paired with the text-safe shade for any label next to them.

### 2.3 Verified Core Contrast Pairs
Computed using the official WCAG relative-luminance formula (not estimated):

| Foreground | Background | Ratio | Passes |
|---|---|---|---|
| `#1C2B36` (text) | `#F7F9FC` (bg) | 13.75:1 | AAA |
| `#FFFFFF` | `#0B2545` (primary) | 15.39:1 | AAA |
| `#FFFFFF` | `#1B4B8A` (secondary) | 8.68:1 | AAA |
| `#1C2B36` (text) | `#FF6B1A` (accent) | 5.09:1 | AA |
| `#1B4B8A` (link text) | `#F7F9FC` (bg) | 8.23:1 | AAA |

> ⚠️ **Critical rule for the orange accent button:** use **dark graphite text (`#1C2B36`) on the orange background, not white.** White text on `#FF6B1A` only reaches 2.85:1 and fails accessibility standards outright. This is a common mistake — orange buttons "look like" they want white text, but they don't pass contrast here. Always verify with the numbers above, not by eye.

### 2.4 Color Usage Rules
- Never use more than 3 colors (excluding neutrals and status colors) on a single screen.
- Primary blue is for structural chrome (header, nav, footer) — not for body copy backgrounds, which stay on `color-bg`.
- Orange is reserved for: primary buttons, active nav item indicator, focus rings, and the one most important interactive element per screen. If a screen has more than one orange element outside of buttons, that's a signal something is mis-prioritized.
- Status colors are never used decoratively (e.g., don't make a hero section green just because it "feels safe").

---

## 3. Typography

### 3.1 Font Stack
```css
--font-heading: 'Inter', 'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif;
--font-body: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'IBM Plex Mono', 'JetBrains Mono', 'SF Mono', Consolas, monospace;
```
Inter and IBM Plex Sans both ship **tabular figures** (fixed-width numerals) — required for this system. If you substitute a different font, verify it has a tabular-numeral OpenType feature (`font-feature-settings: "tnum"`) or KPI numbers will visually jitter as they update.

### 3.2 Type Scale
A fixed scale avoids arbitrary font sizes appearing throughout the codebase. Use only these values:

| Token | Size | Line-height | Weight | Use for |
|---|---|---|---|---|
| `text-xs` | 12px | 16px | 400/500 | Captions, table meta, timestamps |
| `text-sm` | 14px | 20px | 400/500 | Secondary body text, form labels, table cells |
| `text-base` | 16px | 24px | 400 | Default body text |
| `text-lg` | 18px | 28px | 500 | Emphasized body, card titles |
| `text-xl` | 20px | 28px | 600 | Section subheadings |
| `text-2xl` | 24px | 32px | 600 | Card/module headings |
| `text-3xl` | 28px | 36px | 700 | Page section titles |
| `text-4xl` | 36px | 44px | 700 | Hero sub-statements |
| `text-5xl` | 48px | 56px | 700 | Hero headline (desktop) |
| `text-kpi` | 32–40px | 1.1 | 700, **tabular-nums** | KPI tile numbers |

Rule: body text never drops below 14px anywhere in the product (16px minimum on mobile) — this matches general accessibility guidance for readable line length and matches the "large text" WCAG threshold boundary at 18.66px bold/24px regular, above which contrast requirements relax to 3:1.

### 3.3 Responsive Type
- Desktop hero (`text-5xl`) → scales down to `text-3xl` at viewport widths below 768px. Never scale body text (`text-base`) down on mobile — only scale display/heading sizes.
- Letter-spacing: `-0.02em` on anything `text-2xl` and above (tightens large type, standard practice); `0` (default) on body text.

---

## 4. Spacing & Layout Grid

### 4.1 Base Unit
All spacing in this system is a multiple of **8px** (the "8-point grid," a standard used across Material Design, IBM Carbon, and most professional design systems, because it divides evenly into common screen widths and keeps every developer using the same handful of values instead of arbitrary pixel counts).

| Token | Value |
|---|---|
| `space-1` | 4px *(half-step, use only for icon-to-label gaps)* |
| `space-2` | 8px |
| `space-3` | 16px |
| `space-4` | 24px |
| `space-6` | 32px |
| `space-8` | 48px |
| `space-12` | 64px |
| `space-16` | 96px |

- Card internal padding: `space-4` (24px) on mobile, `space-6` (32px) on desktop.
- Section vertical padding: `space-8` to `space-16` (48–96px) between major homepage sections.
- Gap between grid items (cards, KPI tiles): `space-3` (16px) on mobile, `space-4` (24px) on desktop.

### 4.2 Grid & Breakpoints
| Breakpoint | Min width | Columns | Container max-width |
|---|---|---|---|
| `mobile` | 0px | 4 | 100% (16px side padding) |
| `tablet` | 768px | 8 | 720px |
| `desktop` | 1024px | 12 | 1200px |
| `wide` | 1440px | 12 | 1320px |

Standard 12-column responsive grid (matches common corporate-site convention). Gutter: 24px at desktop, 16px at mobile.

### 4.3 Border Radius
| Token | Value | Use |
|---|---|---|
| `radius-sm` | 4px | Badges, chips, small buttons |
| `radius-md` | 8px | Cards, inputs, standard buttons |
| `radius-lg` | 12px | Modals, large panels |
| `radius-full` | 999px | Pills, avatars |

### 4.4 Elevation (Shadows)
Keep shadows subtle — this is a trust/enterprise direction, not a playful one.
```css
--shadow-sm: 0 1px 2px rgba(11, 37, 69, 0.06);
--shadow-md: 0 4px 8px rgba(11, 37, 69, 0.08);
--shadow-lg: 0 12px 24px rgba(11, 37, 69, 0.12);
```
Use `shadow-sm` on resting cards, `shadow-md` on hover, `shadow-lg` only on modals/dropdowns/popovers that float above the page.

---

## 5. Components

### 5.1 Buttons
| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| Primary | `#FF6B1A` | `#1C2B36` (see §2.3 warning) | none | One per screen — the main action |
| Secondary | transparent | `#1B4B8A` | 1px `#1B4B8A` | Secondary actions |
| Tertiary/text | transparent | `#1B4B8A` | none, underline on hover | Low-emphasis actions |
| Destructive | `#D62828` | `#FFFFFF` (5.01:1, passes) | none | Delete/deactivate actions only |
| Disabled | `#DCE3EA` | `#5A6B78` | none | — |

**States required for every button:** default, hover (`color-accent-hover` / 8% darken), active/pressed (additional 8% darken + `scale(0.98)` transform), focus-visible (2px `#FF6B1A` outline, 2px offset — never remove the browser focus ring without replacing it), disabled (reduced opacity 0.5, `cursor: not-allowed`).

Minimum tap target: **44×44px** (Apple/WCAG mobile accessibility guideline) even if the visible button is smaller — pad with invisible hit area if needed. Horizontal padding: `space-4` (24px) minimum on button text.

### 5.2 Forms & Inputs
- Label always above the field, never inside as a placeholder-only label (placeholder text disappears on input, causing users to forget what a field is — a well-documented usability failure).
- Field height: 44px minimum. Border: 1px `#DCE3EA`, radius `radius-md`.
- Focus state: border becomes `#1B4B8A`, plus a 2px `#FF6B1A` outer glow — never rely on border-color change alone for focus, since low-vision users may miss a subtle 1px change.
- Error state: border becomes `#D62828`, an error icon appears left-aligned inside the field, and error text appears directly below the field in `#B3261E` (the verified text-safe critical shade) at `text-sm` — never only a red border with no explanation.
- Validate on blur, not on every keystroke (keystroke-level validation feels punitive — a widely cited UX heuristic). Re-validate on submit.

### 5.3 Cards
- Background `#FFFFFF`, border 1px `#DCE3EA`, radius `radius-md`, shadow `shadow-sm` at rest → `shadow-md` on hover if the card is clickable (only apply hover elevation to clickable cards — a static card that lifts on hover is a common "false affordance" bug).
- Internal structure: icon or image top, `text-lg` title, `text-sm` muted description, optional link/button at bottom.

### 5.4 Status Badges / Pills
Always: `radius-full`, `space-2` horizontal padding × `space-1` vertical, `text-xs` or `text-sm` bold text, an icon (16px) to the left of the text, using the **chip pattern** from §2.2. Never a colored dot with no text next to it in a table row — dot-only is acceptable *only* inside a dense data table where a legend is always visible above the table.

### 5.5 Tables (for incident/audit/report lists)
- Sticky header row, background `#F7F9FC`, `text-sm` bold text, 1px bottom border `#DCE3EA`.
- Row height minimum 48px (touch-friendly, and gives room for a status badge).
- Zebra striping: alternate rows `#FFFFFF` / `#FBFCFE` (barely-there, ~1% lightness difference — enough to guide the eye across a wide row without looking "striped").
- Numeric columns right-aligned, monospace/tabular-nums font.
- Row hover: background shifts to `#F0F4F9`; entire row is clickable if it opens a detail view, with `cursor: pointer`.

### 5.6 KPI Tiles
- Fixed height, `space-4` padding, `radius-md`, `shadow-sm`.
- Structure top-to-bottom: `text-sm` muted label → `text-kpi` number (tabular-nums, bold) → small trend row (arrow icon + percentage in the text-safe status color + a 40×16px sparkline).
- Trend arrow: ▲ in text-safe green for improvement, ▼ in text-safe red for regression — but for safety metrics, confirm direction semantics per metric (e.g., a *decreasing* incident count is the "green" direction, not increasing) — never assume up=green.

### 5.7 Navigation
- Header height: 64px desktop / 56px mobile, background `#0B2545`, sticky on scroll.
- Active nav item: `#FF6B1A` 2px underline indicator, not a full background fill (keeps the header calm).
- Mobile: collapses to a hamburger menu below `tablet` breakpoint (768px); menu opens as a full-height slide-in panel from the right, not a dropdown (slide-in reads more clearly as "navigation" on small screens).

### 5.8 Alerts / Banners
- Full-width, `space-3` vertical padding, left-aligned icon + message + optional action link + dismiss (×) on the right.
- Background is the **chip tint** (e.g. `#FBE7E5` for critical), text is the text-safe shade, never the saturated fill color as a full-width background (too visually loud and can fail contrast for any white text placed on it).
- Critical banners are **not** dismissible until the underlying issue is acknowledged (e.g., an open critical incident) — this is a deliberate UX choice for a safety system: don't let users hide critical state.

### 5.9 Modals / Dialogs
- Max width 560px (forms) or 720px (content-heavy), centered, `radius-lg`, `shadow-lg`, scrim behind at `rgba(11,37,69,0.4)`.
- Always include a visible close (×) top-right AND allow `Esc` key to close, AND allow clicking the scrim to close — unless the modal represents an unsaved destructive action in progress, in which case clicking outside should prompt a confirmation rather than silently closing.
- Focus moves into the modal on open (to the first focusable element or the heading) and returns to the triggering element on close — required for keyboard/screen-reader users (WCAG 2.4.3).

### 5.10 Tooltips
- Appear on hover after a 300ms delay (prevents flickering on incidental mouse movement) and on keyboard focus with no delay.
- Dark background (`#0B2545`), white text, `text-xs`, `radius-sm`, max-width 240px, small arrow pointing to the trigger.

### 5.11 Toasts / Live Notifications
- Slide in from top-right, auto-dismiss after 5 seconds for informational toasts, **do not auto-dismiss** for anything reporting a new critical incident — require manual acknowledgment.
- Stack vertically with `space-2` gap if multiple appear; max 3 visible at once, others queue.

---

## 6. UI Language & Content Rules

### 6.1 Voice & Tone
Direct, plain-language, and calm even when the content is urgent. Never use exclamation points for alerts (they read as panicked, not authoritative — the opposite of what a safety system should convey). State facts and the next action clearly.

### 6.2 Button & Action Labels
- Use verbs, not nouns: "Report Incident," not "Incident Report" or "Submit."
- Never use vague labels like "OK," "Submit," or "Yes" on a destructive or important action — be specific: "Delete Report," "Close Incident," "Confirm Audit."
- Capitalization: Title Case for button labels ("Report Incident"), sentence case for everything else (body text, field labels, helper text).

### 6.3 Error Messages
Pattern: **what went wrong + what to do about it.** Never show a bare error code to an end user.
- ❌ "Error 400: Invalid input"
- ✅ "This report needs a location before it can be submitted. Select a site above."

### 6.4 Empty States
Every list/table needs a designed empty state, not a blank white box: an icon, one sentence explaining why it's empty, and (if applicable) a primary action to fill it. Example: "No open incidents at this site. Great work — here's how to report a new one if something comes up." → button.

### 6.5 Confirmation Dialogs
Only interrupt with a confirmation dialog for actions that are destructive or hard to reverse (deleting a report, closing an audit). Routine actions (saving a draft, adding a comment) should never be interrupted by a confirmation — this is a common over-use pattern that trains users to click through dialogs without reading them.

### 6.6 Numbers & Dates
- Dates: unambiguous format always — "24 Sep 2026," never "09/24/26" (locale ambiguity risk in a system that may be used internationally).
- Large numbers: use thousands separators (1,204 not 1204).
- Percentages to one decimal place max (98.7%, not 98.73218%).

---

## 7. Motion & Animation System

Motion tokens below follow the naming and duration conventions used by Material Design 3 and IBM Carbon's motion systems — both are widely adopted, well-tested references for how long an interface animation should take before it starts to feel slow or laggy.

### 7.1 Duration Tokens
| Token | Duration | Use |
|---|---|---|
| `motion-instant` | 50ms | Button press/ripple feedback, checkbox toggle |
| `motion-fast` | 150ms | Hover states, small icon transitions |
| `motion-standard` | 200–250ms | Default for most UI transitions (dropdown open, tab switch, tooltip) |
| `motion-medium` | 300–350ms | Card expand, modal open, panel slide-in |
| `motion-slow` | 400ms | Full-page/section transitions |

**Never exceed 400ms** for any single UI animation in this system — durations beyond that measurably feel like lag rather than motion, per established motion-design guidance. Full-screen or highly complex transitions may extend toward but not exceed the mobile convention ceiling of ~400–450ms.

### 7.2 Easing Curves
Define exactly these three — never use arbitrary easing values inline in code:
```css
--ease-standard: cubic-bezier(0.2, 0.0, 0, 1.0);   /* default for most transitions: fast start, smooth deceleration */
--ease-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1.0); /* elements entering the screen */
--ease-accelerate: cubic-bezier(0.4, 0.0, 1.0, 1.0); /* elements leaving the screen */
```

### 7.3 What Gets Animated (and What Doesn't)
Animate:
- Hover/focus/active state changes on interactive elements (`motion-fast`)
- Modal/panel/dropdown open-close (`motion-medium`, paired with `ease-decelerate` on open, `ease-accelerate` on close)
- Toast/notification enter (slide + fade, `motion-standard`)
- Accordion/expand-collapse content (`motion-standard`)
- Status badge color transitions when a status changes live on screen (e.g., an incident moves from "Open" to "Resolved") — fade the color over `motion-standard` so the change is noticeable but not alarming.

Never animate:
- Page-load content appearing (no fade-ins on initial render — content should just be there, especially for a tool people check urgently)
- Anything purely decorative (floating shapes, parallax backgrounds) — inconsistent with the "Industrial Trust" principle of restraint
- Numbers counting up/down on KPI tiles on every data refresh — this looks impressive once and becomes noise on a screen someone monitors all day. Update the number instantly; reserve a subtle highlight flash (background color pulse, 400ms, once) for the moment a number changes, not the value itself animating.

### 7.4 Stagger (for lists/grids appearing together)
When multiple cards/rows enter together (e.g., a dashboard loading its module grid), stagger their entrance by **40–80ms per item** so the eye can track each one appearing rather than seeing one flat flash — this is standard practice for multi-element entrances and prevents the "all at once" effect from feeling chaotic.

### 7.5 Reduced Motion
Always respect the OS-level setting:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
This is a WCAG 2.2 / vestibular-sensitivity requirement, not optional polish — some users experience genuine physical discomfort (dizziness, nausea) from motion effects.

---

## 8. UX & Frontend Requirements

### 8.1 Responsive Behavior
- Mobile-first build order: design/build the 375px-wide layout first, then expand up — this matches how most field workers will actually access the incident-reporting parts of this system (on a phone, possibly outdoors, possibly with gloves on, hence the 44px tap targets).
- Never hide critical actions (like "Report Incident") behind a secondary menu on mobile — it should remain a persistent, thumb-reachable button.

### 8.2 Loading States
- Use skeleton screens (gray placeholder blocks matching the eventual content's shape) for anything that takes over ~300ms to load — a bare spinner for content that takes longer than that increases perceived wait time versus a skeleton that previews structure.
- Buttons that trigger an async action (e.g., "Submit Report") switch to a loading spinner inside the button itself and become disabled — never let a user double-submit a safety report by clicking twice.

### 8.3 Keyboard & Focus
- Every interactive element must be reachable via `Tab` in a logical order matching the visual layout.
- Visible focus ring on every focusable element (2px `#FF6B1A`, 2px offset) — never `outline: none` without a replacement.
- Skip-to-content link for keyboard users at the very top of every page.

### 8.4 Accessibility Checklist (WCAG 2.1 AA baseline)
- [ ] All text meets 4.5:1 contrast (3:1 for text ≥18.66px bold/24px regular) — verified per §2.
- [ ] All non-text UI components (borders, icons, focus indicators) meet 3:1 contrast.
- [ ] No information conveyed by color alone — every status has an icon + text label.
- [ ] All images have alt text; all icons used as buttons have an accessible label (`aria-label`).
- [ ] All form fields have a visible, programmatically associated label.
- [ ] Focus order and visible focus state present on every page.
- [ ] `prefers-reduced-motion` respected everywhere.
- [ ] Minimum tap target 44×44px on all interactive elements.

### 8.5 Performance Budget
- Target largest contentful paint under 2.5s on a typical connection; total page weight under ~1.5MB for the marketing/informational pages.
- Lazy-load images below the fold; serve responsive image sizes (`srcset`) rather than one large asset scaled down in CSS.
- Charts/dashboards: paginate or virtualize any table/list beyond ~100 rows rather than rendering all rows at once.

---

## 9. Design Tokens (drop-in CSS)

```css
:root {
  /* Color */
  --color-primary: #0B2545;
  --color-primary-hover: #123A6B;
  --color-secondary: #1B4B8A;
  --color-accent: #FF6B1A;
  --color-accent-hover: #E55A0D;
  --color-bg: #F7F9FC;
  --color-surface: #FFFFFF;
  --color-text: #1C2B36;
  --color-text-muted: #5A6B78;
  --color-border: #DCE3EA;

  --color-critical: #D62828;
  --color-critical-text: #B3261E;
  --color-critical-chip: #FBE7E5;
  --color-warning-fill: #F2A900;
  --color-warning-text: #8A5A00;
  --color-warning-chip: #FBF0D9;
  --color-good-fill: #2E9E6B;
  --color-good-text: #17603F;
  --color-good-chip: #E4F3EC;

  /* Typography */
  --font-heading: 'Inter', 'IBM Plex Sans', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'IBM Plex Mono', 'JetBrains Mono', monospace;

  /* Spacing (8pt grid) */
  --space-1: 4px;  --space-2: 8px;  --space-3: 16px; --space-4: 24px;
  --space-6: 32px; --space-8: 48px; --space-12: 64px; --space-16: 96px;

  /* Radius */
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-full: 999px;

  /* Shadow */
  --shadow-sm: 0 1px 2px rgba(11, 37, 69, 0.06);
  --shadow-md: 0 4px 8px rgba(11, 37, 69, 0.08);
  --shadow-lg: 0 12px 24px rgba(11, 37, 69, 0.12);

  /* Motion */
  --motion-instant: 50ms;
  --motion-fast: 150ms;
  --motion-standard: 220ms;
  --motion-medium: 320ms;
  --motion-slow: 400ms;
  --ease-standard: cubic-bezier(0.2, 0.0, 0, 1.0);
  --ease-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1.0);
  --ease-accelerate: cubic-bezier(0.4, 0.0, 1.0, 1.0);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 10. Final Do's and Don'ts

| Do | Don't |
|---|---|
| Use dark graphite text on orange buttons | Use white text on orange buttons (fails contrast: 2.85:1) |
| Pair every status color with an icon + label | Rely on a colored dot alone in a table row |
| Use the text-safe status shades for labels/small text | Use the bright fill shades (`#F2A900`, `#2E9E6B`) as text color |
| Animate state changes (open/close/hover) in 150–400ms | Animate for decoration, or exceed 400ms on any single transition |
| Use one orange CTA per screen | Scatter orange across multiple competing elements |
| Show skeleton screens for loads over ~300ms | Show a spinner with no content preview for slow loads |
| Confirm only destructive/irreversible actions | Add a confirmation dialog to routine actions |
| Keep critical alerts persistent until acknowledged | Let users dismiss an active critical incident banner |

---

## Sources Referenced
- WCAG 2.1 Success Criteria 1.4.3 (Contrast Minimum), 1.4.11 (Non-text Contrast), 1.4.1 (Use of Color), 2.4.3 (Focus Order) — W3C Web Content Accessibility Guidelines.
- Material Design 3 motion duration/easing token scale (short/medium/long duration bands, standard/emphasized easing curves).
- IBM Carbon Design System motion guidance (duration calculated from distance/size; mechanical vs. natural motion modes).
- 8-point grid spacing convention, used across Material Design, IBM Carbon, and most professional design systems.
- General corporate web-design best practice for 2026 (12-column grid, 48–96px section padding, 2–3 primary color limit) per current corporate-website design guidance.
- All specific contrast ratios in §2.2–2.3 were computed directly from the WCAG relative-luminance formula for this exact palette, not estimated.

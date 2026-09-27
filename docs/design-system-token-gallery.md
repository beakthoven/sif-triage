# Design System Token Gallery

**Owner:** DESIGN-TOKENS. Source of truth: `docs/design-system-spec.md` §2 (binding).
**Implementation:** `dashboard/src/index.css` (tokens + utilities + base a11y), `dashboard/src/lib/devanagari.css` (Devanagari font wiring).

**Contrast method.** All ratios below were computed this session with the WCAG 2.x
relative-luminance formula (sRGB linearization, 0.2126/0.7152/0.0722 coefficients,
`(L1+0.05)/(L2+0.05)`), rounded to 2 dp. They are measured values, not vendor claims.
Surfaces referenced: canvas `#F5F4F0` · card `#FDFDFB` · raised `#FFFFFF` · sunken `#F0EEE8`.

Note on spec annotations: the spec's parentheticals are close but a few cite the wrong
surface — `--content-secondary` is **5.89 on card** (5.17 is its ratio on *sunken*),
`--verdict-high` is **4.93 on card** (5.02 is on raised white), `--verdict-clear` is
**5.38 on card** (5.48 raised). Colors are unchanged from the spec table; only the
surface attributions drift. Measured per-surface values are authoritative below.

---

## 1. Surface

| Token | Value | Use | Notes |
|---|---|---|---|
| `--surface-canvas` | `#F5F4F0` | page background (paper) | — |
| `--surface-card` | `#FDFDFB` | cards, panels | — |
| `--surface-raised` | `#FFFFFF` | popovers, dialogs, dropdowns | — |
| `--surface-sunken` | `#F0EEE8` | table zebra, code, insets | — |
| `--surface-overlay` | `rgba(28,30,33,0.45)` | modal scrim | — |

Utility: `bg-surface-*`. **`--surface-overlay` is for scrims only — never a text background.**

## 2. Content

| Token | Value | canvas | card | sunken | Use + rules |
|---|---|---|---|---|---|
| `--content-primary` | `#202226` | 14.47 | 15.64 | 13.73 | body text — safe everywhere |
| `--content-secondary` | `#5B6470` | 5.45 | 5.89 | 5.17 | labels, meta — **≥4.5:1 on every surface it may sit on** |
| `--content-muted` | `#7A828C` | 3.53 | 3.82 | 3.35 | placeholder, disabled — **≥3:1 only.** Never body copy; never the sole carrier of meaning |
| `--content-inverse` | `#FFFFFF` | — | — | — | on dark surfaces: 16.71:1 on `--action-primary` |

## 3. Border / Ring

| Token | Value | vs card | vs canvas | Role |
|---|---|---|---|---|
| `--border-subtle` | `#E4E2DA` | 1.27 | 1.18 | hairlines inside a card |
| `--border-default` | `#D6D3C9` | 1.47 | 1.36 | card edges, input borders |
| `--border-strong` | `#A8A49A` | 2.44 | 2.26 | emphasized separators |
| `--ring-focus` | `#1C1E21` | 16.40 | 15.18 | focus ring |

**Borders are decorative (all < 3:1).** State, selection, and severity must never be
carried by border hue alone — pair with word + weight + position (spec principle 2).

**Focus ring contract (un-removable).** `@layer base` in `index.css` sets
`:focus-visible { outline: 2px solid var(--ring-focus) !important; outline-offset: 2px; }`.
The `!important` beats every `outline-none`/`outline-hidden`/`focus-visible:outline-none`
in feature or primitive code (e.g. the tabpanel's `outline-none` in
`components/ui/tabs.tsx`, which was a WCAG 2.4.7 failure). Primitives must **not** add
their own focus rings; the token layer owns the ring. Focus-visible styling in primitives
(`focus-visible:outline-2 focus-visible:outline-ring-focus`) may remain — it agrees with
the base ring.

## 4. Action

| Token | Value | Contrast |
|---|---|---|
| `--action-primary` | `#1C1E21` | fill; with `--action-primary-fg` = 16.71:1 |
| `--action-primary-fg` | `#FFFFFF` | — |
| `--action-secondary` | `#F0EEE8` | fill; pair with `--content-primary` (13.73:1) |
| `--action-ghost-hover` | `#EDEAE2` | ghost hover fill only, never text |

## 5. Verdict — always paired with its label word (spec §2)

| Token | Value | Word | card | canvas | sunken |
|---|---|---|---|---|---|
| `--verdict-high` | `#B45309` | HIGH | 4.93 | 4.56 | 4.33 |
| `--verdict-moderate` | `#A16207` | MODERATE | 4.83 | **4.47** | 4.24 |
| `--verdict-low` | `#5B6470` | LOW | 5.89 | 5.45 | 5.17 |
| `--verdict-clear` | `#047857` | CLEAR | 5.38 | 4.98 | 4.73 |
| `--verdict-uncertain` | `#64748B` | REVIEW | 4.67 | **4.32** | 4.10 |

**Constraint (measured, honest):** `--verdict-moderate` and `--verdict-uncertain` as
normal-size text **fail AA (4.5:1) directly on canvas** (4.47 / 4.32). Render verdict
text on `--surface-card` or `--surface-raised` (or as large text ≥ 18.7px / 14px-bold,
where 3:1 suffices), never as small amber/slate text on the paper canvas. This is a
spec-value property, not a bug in the token file — flagged here so feature agents place
these tokens on card/raised surfaces.

## 6. Status

| Token | Value | card | canvas | Use |
|---|---|---|---|---|
| `--status-ok` | `#047857` | 5.38 | 4.98 | success, online |
| `--status-warn` | `#B45309` | 4.93 | 4.56 | attention |
| `--status-danger` | `#B42318` | 6.46 | 5.97 | destructive only |
| `--status-info` | `#1D4ED8` | 6.58 | 6.09 | informational |
| `--status-quiet` | `#64748B` | 4.67 | **4.32** | offline, inert — same canvas caveat as above |

## 7. Type scale (`index.css` `@theme` — utilities `text-display … text-mono`)

| Utility | Size / line | Weight (consumer applies) | Use |
|---|---|---|---|
| `text-display` | 32 / 38 | 600 (`font-semibold`) | page title |
| `text-title` | 22 / 28 | 600 | section head |
| `text-subtitle` | 17 / 24 | 600 | card head |
| `text-body` | 15 / 22 | 400 (`font-normal`) | default |
| `text-label` | 13 / 18 | 500 (`font-medium`) | controls, table header |
| `text-caption` | 12 / 16 | 400 | meta, timestamps |
| `text-mono` | 13 / 18 | 500 | scores, ids, counts |

Fonts: `--font-sans` IBM Plex Sans · `--font-mono` IBM Plex Mono ·
`--font-devanagari` IBM Plex Sans Devanagari (see §11). Sizes are exact px per spec
(independent of the 18px root; browser zoom still scales them). Legacy utilities
(`text-sm`, `text-2xl`, …) remain Tailwind rem defaults and render larger at the 18px
root — transitional; new code should use the token steps above.

## 8. Spacing — 4 px base (`--spacing: 4px`)

`space-N = 4px × N`. Canonical steps per spec: `space-1..6` = 4/8/12/16/20/24,
`space-8/10/12/16` = 32/40/48/64. Utilities `p-*, m-*, gap-*, w-*, h-*, inset-*` all
follow (`p-4` = 16px, `p-16` = 64px). Intermediate steps (7, 9, 11, …) exist dynamically
(28, 36, 44 …) but are non-canonical — do not use in new layouts. Note the base is px,
so spacing does not scale with the 18px root (type does) — deliberate per spec.

## 9. Radius

`rounded-xs` 3 · `rounded-sm` 5 · `rounded-md` 8 · `rounded-lg` 12 · `rounded-xl` 16 ·
`rounded-full` 999. Compat: `--radius-4xl` aliases to `--radius-xl` while
`components/ui/badge.tsx` still emits `rounded-4xl`; `rounded-2xl/3xl` remain Tailwind
defaults and are unused — do not adopt them.

## 10. Motion

| Token | Value | Use |
|---|---|---|
| `--motion-fast` | 120ms | hover/press feedback |
| `--motion-base` | 200ms | default — `--default-transition-duration` is wired to it, so every `transition-*` utility defaults to 200ms |
| `--motion-slow` | 320ms | panel/entrance transitions |

Easing (Astryx): `ease-out` = `cubic-bezier(0.16, 1, 0.3, 1)` ·
`ease-in-out` = `cubic-bezier(0.65, 0, 0.35, 1)` (both override Tailwind's built-ins).
JS motion consumes `var(--motion-*)` and must live under
`<MotionConfig reducedMotion="user">`; the CSS `prefers-reduced-motion` kill-switch in
`index.css` is the safety net for pure-CSS motion. Never animate for decoration.

## 11. Devanagari (EN/हिं toggle)

`dashboard/src/lib/devanagari.css` (imported from `index.css`) loads
`@fontsource/ibm-plex-sans-devanagari` **Devanagari subsets** at 400/500/600 — the exact
weights the type scale uses — and defines `--font-devanagari-stack`. `index.css` composes
it into `--font-sans`, `--font-mono`, `--font-heading` (so every UI string resolves
Devanagari glyphs in a brand face instead of an OS fallback) and exposes it as the
`--font-devanagari` token (utility `font-devanagari`) for explicitly Hindi-typed
elements. There is **no** IBM Plex Mono Devanagari (verified E404 at stack selection),
so mono keeps Plex Mono first and falls through to the Sans Devanagari face. Latin glyphs
in mixed strings come from Plex Sans, which sits earlier in the chain. Latin-only strings
download nothing extra (subsets are `unicode-range`-scoped).

## 12. Dark mode — DECIDED: not implemented

**No dark theme ships.** The "reading room" palette, verdict semantics, and measured
contrast are tuned for light surfaces only; a dark variant would need a full second token
table (new, unapproved colors) to be anything other than an a11y liability.

`@custom-variant dark (&:is(.dark *))` is **kept as an inert shim**, deliberately not
deleted: `components/ui/*` (shadcn-derived) carry `dark:` guards; Tailwind's default
`dark` variant is a `prefers-color-scheme` media query, so deleting the custom variant
would half-activate those guards for OS-dark users on a light instrument. Pinned to a
`.dark` ancestor that nothing ever sets (verified: no code sets the class), the guards
compile but never match. `html { color-scheme: light }` additionally blocks UA dark form
skins. Do not add a `.dark` toggle without the full token table.

## 13. Compatibility aliases (transient — delete when components/ui is fully migrated)

Legacy token/utility names map onto spec tokens; **no new colors**. Kept because live
views and shadcn primitives still consume them (and `button.tsx` references
`var(--foreground)` / `var(--secondary)` / `var(--radius-md)` as raw vars).

| Legacy | → Spec token | | Legacy | → Spec token |
|---|---|---|---|---|
| `--background` / `bg-background` | `--surface-canvas` | | `--accent` | `--action-ghost-hover` |
| `--foreground` / `text-foreground` | `--content-primary` | | `--destructive` | `--status-danger` |
| `--card` | `--surface-card` | | `--border` | `--border-default` |
| `--popover` | `--surface-raised` | | `--input` | `--border-default` |
| `--primary` | `--action-primary` | | `--ring` | `--ring-focus` |
| `--secondary` | `--action-secondary` | | `--verdict` / `text-verdict` | `--verdict-high` |
| `--muted` | `--surface-sunken` | | `--ok` / `text-ok` | `--verdict-clear` |
| `--muted-foreground` | `--content-secondary` | | `--quiet` / `text-quiet` | `--verdict-uncertain` |
| `--chart-1…5` (raw `var()` in analytics charts) | high → secondary → uncertain → strong → default border | | | |

Removed (verified zero consumers): `--paper`, all `--sidebar-*`, the `--radius` calc
chain, and the `* { outline-ring/50 }` base rule. (The `--chart-*` vars were initially
deleted on a zero-consumer check; `features/analytics/charts.tsx` landed mid-flight
using raw `var(--chart-N)` and they are restored here as compat aliases above.)

## 14. Token inventory (spec-match verification)

Defined in `dashboard/src/index.css` `:root` and consumed via the `@theme inline` /
`@theme` mappings — names match `docs/design-system-spec.md` §2 exactly:

- **Surface (5):** `--surface-canvas`, `--surface-card`, `--surface-raised`,
  `--surface-sunken`, `--surface-overlay`
- **Content (4):** `--content-primary`, `--content-secondary`, `--content-muted`,
  `--content-inverse`
- **Border/Ring (4):** `--border-subtle`, `--border-default`, `--border-strong`,
  `--ring-focus`
- **Action (4):** `--action-primary`, `--action-primary-fg`, `--action-secondary`,
  `--action-ghost-hover`
- **Verdict (5):** `--verdict-high`, `--verdict-moderate`, `--verdict-low`,
  `--verdict-clear`, `--verdict-uncertain`
- **Status (5):** `--status-ok`, `--status-warn`, `--status-danger`, `--status-info`,
  `--status-quiet`
- **Fonts (3):** `--font-sans`, `--font-mono`, `--font-devanagari`
- **Type (7 steps + line-heights):** `--text-display/title/subtitle/body/label/caption/mono`
  with `--text-<step>--line-height` pairs
- **Spacing:** `--spacing: 4px` (dynamic `space-N` = 4px × N; canonical 1–6, 8, 10, 12, 16)
- **Radius (6):** `--radius-xs`, `-sm`, `-md`, `-lg`, `-xl`, `-full`
- **Motion (3):** `--motion-fast`, `--motion-base`, `--motion-slow`
- **Easing (2):** `--ease-out` = `cubic-bezier(0.16,1,0.3,1)`,
  `--ease-in-out` = `cubic-bezier(0.65,0,0.35,1)`

Supporting internals (not product tokens): `--font-stack-sans`, `--font-stack-mono`,
`--font-devanagari-stack` (in `lib/devanagari.css`), `--default-transition-duration`,
`--radius-4xl` (compat), and the §13 alias block.

## 15. How feature files consume this

- Colors: only `bg-surface-*`, `text-content-*`, `border-border-*`, `bg-action-*`,
  `text-verdict-*`, `text-status-*` (or the §13 legacy names until migration completes).
  **No raw hex, no new colors** (spec rule, §2).
- Type: `text-display|title|subtitle|body|label|caption|mono` + weight utilities.
- Spacing/radius: `p-4`, `gap-2`, `rounded-md`, etc.
- Motion: `transition-*` (defaults to 200ms), `ease-out`/`ease-in-out` (Astryx curves),
  `duration-*` for overrides; JS motion via `var(--motion-*)` under
  `<MotionConfig reducedMotion="user">`.
- Focus: nothing to do — the token layer owns the ring. Do not add
  `outline-none`-adjacent focus styling; you cannot remove the base ring, and you
  shouldn't try.

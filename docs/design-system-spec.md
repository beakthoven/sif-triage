# Design System Contract (binding)

**Source of truth for every UI agent.** Adapted from **Astryx** (Meta design system — semantic
tokens, component vocabulary, visual language) + **motion-primitives** (interaction layer).
Token model is mapped onto Tailwind 4 CSS-first `@theme`; we do **not** adopt StyleX.

Every UI agent MUST compile against this contract. Do not invent token names or component props.

---

## 1. Principles (from Astryx's posture)

1. **Semantic over raw.** Never reference a hex value in a feature file. Use the token.
2. **Verdict is a first-class semantic.** This is a safety instrument: severity is expressed by
   words + position + token, never hue alone. No red/green pairing without a label.
3. **Motion clarifies state change, never decorates.** Every animated component lives under
   `<MotionConfig reducedMotion="user">`.
4. **Density where it earns trust, air where it helps reading.** Two densities only: `compact`
   (queue, tables) and `comfortable` (detail, explanations).
5. **Accessible by default.** Focus ring is always visible. All interactive elements reachable by
   keyboard. Contrast ≥ 4.5:1 body / ≥ 3:1 large & UI.

---

## 2. Tokens

Defined once in `dashboard/src/index.css` inside `@theme inline`, consumed as Tailwind utilities.
Astryx semantics preserved; names normalised to kebab CSS vars.

### Surface
| Token | Value | Use |
|---|---|---|
| `--surface-canvas` | `#F5F4F0` | page background (paper) |
| `--surface-card` | `#FDFDFB` | cards, panels |
| `--surface-raised` | `#FFFFFF` | popovers, dialogs, dropdowns |
| `--surface-sunken` | `#F0EEE8` | table zebra, code, insets |
| `--surface-overlay` | `rgba(28,30,33,0.45)` | modal scrim |

### Content
| Token | Value | Use |
|---|---|---|
| `--content-primary` | `#202226` | body text |
| `--content-secondary` | `#5B6470` | labels, meta (5.17:1 on card) |
| `--content-muted` | `#7A828C` | placeholder, disabled (≥3:1 only) |
| `--content-inverse` | `#FFFFFF` | on dark surfaces |

### Border / Ring
| Token | Value |
|---|---|
| `--border-subtle` | `#E4E2DA` |
| `--border-default` | `#D6D3C9` |
| `--border-strong` | `#A8A49A` |
| `--ring-focus` | `#1C1E21` | always 2px solid with 2px offset |

### Action
| Token | Value |
|---|---|
| `--action-primary` | `#1C1E21` |
| `--action-primary-fg` | `#FFFFFF` |
| `--action-secondary` | `#F0EEE8` |
| `--action-ghost-hover` | `#EDEAE2` |

### Verdict (the product's core semantic — always paired with a word)
| Token | Value | Label word |
|---|---|---|
| `--verdict-high` | `#B45309` (5.02:1 on card) | `HIGH` |
| `--verdict-moderate` | `#A16207` | `MODERATE` |
| `--verdict-low` | `#5B6470` | `LOW` |
| `--verdict-clear` | `#047857` (5.42:1) | `CLEAR` |
| `--verdict-uncertain` | `#64748B` | `REVIEW` |

### Status
| Token | Value | Use |
|---|---|---|
| `--status-ok` | `#047857` | success, online |
| `--status-warn` | `#B45309` | attention |
| `--status-danger` | `#B42318` | destructive only |
| `--status-info` | `#1D4ED8` | informational |
| `--status-quiet` | `#64748B` | offline, inert |

### Type scale (`--font-sans` IBM Plex Sans; `--font-mono` IBM Plex Mono; `--font-devanagari` IBM Plex Sans Devanagari)
| Step | Size / line | Weight | Use |
|---|---|---|---|
| `display` | 32/38 | 600 | page title |
| `title` | 22/28 | 600 | section head |
| `subtitle` | 17/24 | 600 | card head |
| `body` | 15/22 | 400 | default |
| `label` | 13/18 | 500 | controls, table header |
| `caption` | 12/16 | 400 | meta, timestamps |
| `mono` | 13/18 | 500 | scores, ids, counts |

### Spacing (4 px base) `space-1…16` = 4,8,12,16,20,24,32,40,48,64
### Radius `radius-xs 3 · sm 5 · md 8 · lg 12 · xl 16 · full 999`
### Motion (motion-primitives) `motion-fast 120ms · motion-base 200ms · motion-slow 320ms`
### Easing `ease-out cubic-bezier(0.16,1,0.3,1) · ease-in-out cubic-bezier(0.65,0,0.35,1)`

**Rule:** feature files may use spacing/radius/type utilities freely. They may **not** introduce
colors outside this table.

---

## 3. Primitives — exact import + props

All from `@/components/ui`. Implemented in `dashboard/src/components/ui/`. Tailwind classes only.

```tsx
Button({ variant: "primary"|"secondary"|"ghost"|"destructive",
         size: "sm"|"md"|"lg", loading?: boolean, icon?: ReactNode, ...props })

Chip({ tone: "high"|"moderate"|"low"|"clear"|"uncertain"|"neutral"|"danger"|"info",
       children, size: "sm"|"md" })          // ALWAYS renders a word, never hue alone

Card({ density?: "compact"|"comfortable", interactive?: boolean, children })
CardHeader({ title, meta?: ReactNode, actions?: ReactNode })
CardGrid({ children })

Field({ label, hint?, error?, required?, children })
Input({ size?: "sm"|"md", invalid?: boolean, ...props })
Textarea({ rows?, invalid?: boolean, ...props })
Select({ options: {value,label}[], value, onChange })

Table<Row>({ columns: ColumnDef<Row>[], data: Row[], sort?, onSortChange?,
             density?: "compact"|"comfortable", stickyHeader?: boolean })
  // ColumnDef = { id, header, cell(row), align?, width?, sortable? }

Tabs({ items: {value,label,icon?,badge?}[], value, onChange })
  // MUST implement roving tabindex + arrow keys + aria-selected

Dialog({ open, onOpenChange, title, description?, footer?, children })
Sheet({ open, onOpenChange, side: "right"|"bottom", title, children })
Command({ open, onOpenChange, placeholder, groups: CommandGroup[] })
Toast via `sonner` — helper `notify.success|error|info(message, {description})`

Progress({ value, max, label?, detail?, indeterminate?: boolean })
Tooltip({ content, children })
Skeleton({ className })
EmptyState({ title, description, action? })
ErrorState({ title, description, onRetry? })
DateRangePicker({ value, onChange })   // wraps react-day-picker range
```

## 4. Domain components — `@/components/domain`

```tsx
VerdictCard({ report, score, band, stability, rules, spans, gates, explanation,
              onConfirm, onReject, decided?: "confirm"|"reject" })
  // ONE card per report. Score + evidence ALWAYS visible regardless of band.
  // Never render two stacked cards for one report.

ScoreReadout({ score, band, threshold, stability, modelVersion })
  // Shows numeric score, review-priority word, the tuned threshold,
  // and the stability indicator. Never a bare number.

StabilityIndicator({ spread, nVariants, verdictFlips })
  // Motion-clarified. High spread → "unstable wording" chip, routes to REVIEW.

EvidenceText({ text, spans })        // spans underlined + tinted, exact-substring only
RuleBars({ rules: {code,name,prob,inScope}[] })   // 7 in-scope + 2 declared out-of-scope
GateList({ gates: GateState[] })     // badge vs gray visually distinct
ExplanationBlock({ template, source, cached })
BarrierList({ barriers: {gate,label,detail}[] })  // NEW — barrier-failure gates (A2)

DensityTable({ rows, by, dateRange, minN })       // min-n guard + Wilson CI required
PatternCard({ pattern })                          // CI labelled as RATE's, not lift's
IngestProgress({ done, total, status, etaSeconds, onCancel })
DecisionRow({ decision })                         // who / when / was / now / RATIONALE
LimitationsPanel({ items })                       // honest limitations, always reachable
```

## 5. File ownership (no agent may write outside its slice)

```
dashboard/src/index.css                    → DESIGN (tokens, a11y, motion)
dashboard/src/components/ui/**             → DESIGN (primitives)
dashboard/src/components/domain/**         → DOMAIN
dashboard/src/features/queue/**            → QUEUE
dashboard/src/features/report/**           → REPORT
dashboard/src/features/analytics/**        → ANALYTICS
dashboard/src/features/ingest/**           → INGEST
dashboard/src/features/decisions/**        → DECISIONS
dashboard/src/features/settings/**         → SETTINGS
dashboard/src/lib/**                       → SHELL (api client, types, i18n, utils)
dashboard/src/routes.tsx  src/App.tsx      → SHELL
dashboard/package.json  vite.config.*      → DESIGN
```

Backend ownership is per-file: `app/gates.py`→GATES, `app/classifier.py`→CLASSIFIER,
`app/storage.py`+`config.py`+`main.py`→STORE, `tests/**`→TESTS, `packaging/**`→PACK.

## 6. Non-negotiables for every UI agent

1. Import only from `@/components/ui`, `@/components/domain`, `@/lib/*`. No ad-hoc colors.
2. Every AI verdict renders with reasoning + threshold + stability. Never a bare score.
3. Empty, loading, and error states required for every data surface. No fabricated fallback data.
4. Reduced-motion respected. Focus ring visible on every interactive element.
5. EN/हिं both complete in `@/lib/phrasebook.ts`. No hardcoded user-facing strings in features.
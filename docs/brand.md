# Superstar brand guidelines

> Superstar is a piece of infrastructure that has to feel personal.
> Operators run it; org admins configure it; everyday people submit
> tickets and read decisions. The brand has to carry warmth without
> sacrificing competence.

This document is the single source of truth for what Superstar looks
like and how it talks. Implementers should never invent a token, a
component, or a tone of voice — if it's not in here, ask before adding
it.

The visual references this draws from are mobile task-management apps
(Todoist, Microsoft To Do, indie task apps like the references in our
shared design folder). The intent: Superstar should feel as friendly
on a phone as those apps do, and as serious on a desktop dashboard
as Stripe or Linear.

---

## Personality

Three words, in order:

**Warm. Confident. Honest.**

- **Warm** — we greet people by name. We use generous whitespace, rounded
  corners, and color blocks when they earn it. We don't fight the user
  with grey-on-grey "professional" minimalism.
- **Confident** — single-colour-block heroes, big numerals, big bold
  primary actions. Don't apologise with thin grey buttons; commit to
  the action and put it front-and-center.
- **Honest** — every decision the LLM makes cites the rule that drove
  it. The brand reflects that: never hide an error behind a smile, never
  put a feature behind a coming-soon banner that won't ship.

**Voice cues** — short sentences. "Hello, Mithun." not "Welcome back,
user." Active verbs. No exclamation marks. No emoji in chrome (✓ /
arrows in glyphs are fine).

---

## The mark

![logo](../frontend/public/logo.svg)

A ticket (rounded square with two semicircular notches at the left and
right midpoints) framing a 5-point gold star. The shape encodes the
product (ticketing) and the name (star) in one silhouette.

- **Primary asset:** [`frontend/public/logo.svg`](../frontend/public/logo.svg) — 256×256, two flat fills, no gradients.
- **Favicon:** [`frontend/public/favicon.svg`](../frontend/public/favicon.svg) — same mark with the star scaled up ~18 % for tiny-render legibility.
- **Clear space:** keep one notch-radius (~10 % of the mark's height) on all sides.
- **Minimum size:** 16 px favicon. Below 24 px, drop any wordmark beside the mark.

### Reductions

- **Mono on light** — render both shapes in `--ink-900` (#111).
- **Mono on dark** — both shapes in white.
- **Star only** — drop the ticket when you need a tiny accent (chip icons, in-text). Always gold.

### Don't

- Don't outline either shape — both are filled flat.
- Don't add a drop shadow on the mark itself.
- Don't recolour the star to anything other than `--gold-500` or one of the mono treatments.
- Don't put the mark on a busy photo background.

---

## Colour

The palette is **two brand colours + a 9-step neutral ramp + four
semantic state pairs**. That is everything. Anything else is a smell.

### Brand

| Token | Hex | Use |
|---|---|---|
| `--red-600` | `#D7242B` | Primary CTAs, the mark's body, hero blocks, selected pill backgrounds. **The "do this" colour.** |
| `--red-700` | `#B81C22` | Pressed / hover state on red. Borders on filled-red surfaces. |
| `--red-100` | `#FCE6E7` | Soft red wash — selected chip background when filled-red would be too loud, error block backgrounds. |
| `--gold-500` | `#F5C518` | The mark's star. Sticker badges. Completion / "well done" glyphs. **The "you did it" colour.** Never used as body text. |
| `--gold-100` | `#FFF6D6` | Subtle gold wash for sticker badges' edge glow, "new" tag backgrounds. |

**Two-accent system:** red is the action colour ("do this"), gold is
the achievement colour ("you did it"). They don't compete. Red on
buttons, gold on score badges and completion ticks. Never the reverse.

### Neutrals — the 9-step ink ramp

| Token | Hex | Use |
|---|---|---|
| `--ink-950` | `#0F0F11` | Display headings only |
| `--ink-900` | `#18181B` | Body text |
| `--ink-700` | `#3F3F46` | Secondary text |
| `--ink-500` | `#71717A` | Muted text, placeholders, helper copy |
| `--ink-400` | `#A1A1AA` | Soft labels, the watermark heading colour |
| `--ink-300` | `#D4D4D8` | Borders on interactive controls |
| `--ink-200` | `#E4E4E7` | Borders on static cards |
| `--ink-100` | `#F4F4F5` | Subtle row backgrounds, code blocks |
| `--ink-50`  | `#FAFAFA` | Inner surfaces inside a card |
| `--ink-0`   | `#FFFFFF` | Card surfaces |
| `--bg-page` | `#F2F3F5` | The tinted page background the outer frame sits on |

### Semantic states

Status pills and decisioning outcomes ride these — never use brand red
for an "unhealthy" state.

| Token | Background | Foreground | Used for |
|---|---|---|---|
| `--ok-bg` / `--ok-fg` | `#E3F5E9` / `#1B7A3A` | Approve, decided, healthy |
| `--warn-bg` / `--warn-fg` | `#FFF4D6` / `#8A6100` | Escalate, shadow mode, attention |
| `--err-bg` / `--err-fg` | `#FCE6E7` / `#B81C22` | Reject, error, destructive |
| `--info-bg` / `--info-fg` | `#E6F0FA` / `#1A56C0` | Open, pending, informational |

---

## Typography

**Inter Variable** is the typeface. One family, three weights.

```
font-family: "Inter Variable", "Inter", "Helvetica Neue", Helvetica, sans-serif;
font-family-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
```

We picked Inter deliberately:
- It's the standard "modern SaaS" sans — what GitHub, Figma, Notion, Linear all use. Readers don't have to think about the typeface; they just read.
- Variable-font means one file covers every weight from 100–900 plus italics. No multi-file weight juggling, ~150 kB total over the wire.
- Self-hosted via `@fontsource-variable/inter` — no Google Fonts CDN request, no privacy / EU-cookie concerns.
- Pixel-grid optimised down to 11 px. The reason it reads so cleanly at small sizes in dashboards.
- Helvetica stays in the fallback chain so the font doesn't go missing if the CSS shim doesn't load (slow network, blocked extension, etc.).

### Body tweaks

Inter reads a hair wide at body size, and its default `a` and `l` shapes
have a touch of personality that doesn't match our "honest / restrained"
voice. Two micro-adjustments on `body`:

```css
letter-spacing: -0.005em;                    /* tighten body */
font-feature-settings: "cv11", "ss03";       /* calmer a + l */
```

### Weights

- **400 — regular** — body copy, helpers
- **500 — medium** — labels, navigation, secondary CTAs
- **700 — bold** — display headings, primary CTAs, names ("Hello, **Mithun**")

Inter does have a real semibold (600), but we still avoid it: the
500 → 700 jump is intentional. Three weights are enough to express
every hierarchy we need.

### Scale

A 7-step modular scale. Use the token, not the px value.

| Token | px | Line-height | Weight | Use |
|---|---|---|---|---|
| `--text-display-xl` | clamp(48px, 8vw, 80px) | 0.95 | 700 | The huge greeting / hero title ("**Hello, Mithun.**") |
| `--text-display` | clamp(36px, 6vw, 56px) | 1.0 | 700 | Page H1 ("**Tickets**") or display-heading variant |
| `--text-h1` | 28 px | 1.15 | 700 | Sub-page heading ("**Pick a workspace**") |
| `--text-h2` | 20 px | 1.25 | 500 | Section heads inside a card ("Create a task") |
| `--text-h3` | 16 px | 1.4 | 500 | List item titles, card titles |
| `--text-body` | 14 px | 1.5 | 400 | Default body copy |
| `--text-small` | 12.5 px | 1.45 | 400 | Helper text, status pills, metadata |
| `--text-mono` | 13 px | 1.5 | 400 | Identifiers, payload JSON, rule_ids |

Letter spacing is **negative** on display sizes (`-0.02em` to
`-0.025em`) and **slightly positive** on small uppercase labels
(`0.06em` to `0.08em`).

---

## Spacing & radius

The base unit is **4 px**. Every spacing decision is a multiple.

| Token | px |
|---|---|
| `--space-1` | 4 |
| `--space-2` | 8 |
| `--space-3` | 12 |
| `--space-4` | 16 |
| `--space-6` | 24 |
| `--space-8` | 32 |
| `--space-12` | 48 |
| `--space-16` | 64 |

### Radii — softer than you'd think

The references this draws from go **big** with radii. Same here:

| Token | px | Use |
|---|---|---|
| `--radius-sm` | 6 | Chips, status pills, code tags |
| `--radius-md` | 10 | Buttons, inputs, list rows |
| `--radius-lg` | 16 | Card surfaces |
| `--radius-xl` | 24 | Outer frame, hero cards |
| `--radius-2xl` | 32 | Accent / illustration cards, FABs |
| `999px` | — | Full pill chips |

**Rule of thumb:** when in doubt, go up one step. Pills should feel
pill-y. Cards should look like they could be slid into a pocket.

### Shadows

Three tiers. The frame uses heavy; surfaces light; accent CTAs glow.

```
--shadow-frame:
  0 1px 2px rgba(15, 15, 17, 0.04),
  0 8px 24px -8px rgba(15, 15, 17, 0.08),
  0 32px 64px -24px rgba(15, 15, 17, 0.06);

--shadow-surface:
  0 1px 2px rgba(15, 15, 17, 0.03),
  0 4px 12px -4px rgba(15, 15, 17, 0.04);

--shadow-pop:
  0 6px 24px -8px rgba(215, 36, 43, 0.20);  /* red glow */

--shadow-gold-pop:
  0 6px 24px -8px rgba(245, 197, 24, 0.30); /* gold glow */
```

---

## Components

The catalog. Implementers must use these — do not invent variants.

### Buttons

Three roles, that's it.

- **`btn-primary`** — filled red, white text, `--radius-md`. The one thing the user should do on this screen. Never more than one per page.
- **`btn-secondary`** — outline on white, ink-900 text. For "Cancel" and other non-destructive secondaries.
- **`btn-quiet`** — text-only, no border, no fill, ink-700. For in-row actions inside a card.
- **`btn-danger`** — quiet variant in `--err-fg` text on `--err-bg` hover. For Delete.

**Sizing:** mobile primary buttons are **min 48 px tall** (touch target);
desktop primaries are 40 px. Don't go below 36 px for a primary action.

**Full-width on mobile, content-width on desktop.** A primary CTA that
spans the column on a phone goes back to content-width on tablet+
breakpoints.

### Pill chips

The reference design's calendar dot picker and tab pills are the
template here.

- Padding: 6 px / 14 px
- Radius: `999px`
- Font: 14 px, 500 weight
- **Unselected:** `--ink-50` bg, `--ink-700` text
- **Selected (soft):** `--red-100` bg, `--red-700` text
- **Selected (loud):** `--red-600` bg, white text
- **Gold variant (completion):** `--gold-500` bg, `--ink-950` text

Use **soft selected** for filters / tabs (multiple selectable). Use
**loud selected** for the active item in a single-select control (date
strip, segmented control).

### Cards

Three levels of card emphasis.

1. **Surface card** — `--ink-0` bg, 1 px `--ink-200` border, `--radius-lg`, `--shadow-surface`. The default. Used for list rows, form sections.
2. **Hero card** — filled `--red-600` bg, white type inside, `--radius-xl`, no border. Used for the top-of-screen accent panel (e.g. "Back End Development · Progress 56 %"). At most one per screen.
3. **Sticker card** — filled `--gold-500`, ink-950 type, `--radius-2xl`. Reserved for "completion" or "score" moments. Rare.

Card padding: `--space-4` (16 px) on mobile, `--space-6` (24 px) on tablet+.

### Greeting header

A signature pattern: bold name, soft helper line below.

```
Hello, [Name]
Have a nice day.
```

- Name in `--text-display` (large, 700 weight, slightly negative tracking)
- Helper line in `--text-body`, `--ink-500`, no bold

Render this only at the top of authenticated home screens (Dashboard,
workspace picker). Don't repeat on subpages.

### Page heading

For interior pages, use **display-heading** — `--text-display`, `--ink-400`, light weight. The watermark style: it tells you where you are without competing with the content below it.

```
Tickets          (← display-heading, ink-400)
[+ New ticket]   (← primary CTA, opposite end of the row)
```

### Avatar

40 × 40 px on mobile, 32 × 32 px in chrome. Round (`999px`). Always with a 2 px white "ring" outline when on a coloured background. If no photo, render a monogram (first letter of name) in `--ink-900` on `--ink-100` bg, weight 700.

### Tab / segmented control

Pill chips inside a single row, evenly spaced, with the selected pill in **loud red**. Use this for "My tasks / Projects / Notes"-style mode switching, NOT for filters (filters use soft selected).

### List item / Task row

```
┌─────────────────────────────────────────┐
│ [icon] Title                        ▸   │
│        Sub-meta · created [date]        │
└─────────────────────────────────────────┘
```

- Surface card with `--radius-md`
- Icon 32 × 32 px, ink-900 on ink-100 bg, `--radius-md`
- Title: `--text-h3`, 500 weight
- Sub-meta: `--text-small`, `--ink-500`
- Chevron / completion circle on the right
- Whole row is clickable (link or button), with a subtle hover (`--ink-50` bg)

### Form fields

Each form question is a **tinted question card** — Google-Forms-style.

- Wrap each field in a card with `--ink-50` bg, `--ink-100` border, `--radius-lg`
- Label first (15 px, 500 weight, `--ink-900`), helper below (13 px, `--ink-500`), input last
- Input has a white background and turns to a `--ink-900` border on focus, with a 3 px ink-tinted ring
- Gap between cards: `--space-6` (24 px)

### Toggle switch

For boolean settings. 44 × 24 px track, 20 × 20 px thumb. Off = `--ink-300` bg, on = `--red-600` bg, thumb always white. Animates on toggle.

### Date strip

A horizontal scroll of pill chips, one per date. Each pill shows a date number (large, 700) and a weekday letter (small, 400, ink-500). Selected pill uses **loud red**.

### Bottom nav (mobile)

4 icons + labels (or icons alone if labels won't fit). 64 px tall. Active item: red glyph + thin red top-border. Inactive: ink-500 glyph.

### FAB / "+ Add" button

Floating action button at the bottom-right on mobile. 56 × 56 px circle, `--red-600` filled, `+` glyph in white, `--shadow-pop`. Alternative inline form: pill button "+ Add task" with rounded corners — same red, smaller padding.

### Hero metric

For dashboard summary cards.

- Big number (`--text-display`, tabular-nums, ink-950)
- Decimals stepped down (60 % size, ink-500)
- A `delta-pill` next to it: `▲1.9%` green or `▼0.5%` red
- Small label below: `--text-small`, ink-500

### Score badge (sticker)

For "auto-decide rate", "eval precision", or similar "you did it" moments. Wavy-edged disc, gold filled, big monogram + score inside. Pair with a small label beside it: "B · 69/100 · Good".

---

## Patterns

### Card-on-card

The reference designs lean hard on this: a coloured hero card with a
white form sheet floating on top of it (the "Create New Task" screen).
Pattern:

1. Top half of the viewport is the hero (filled red, ink-0 type, `--radius-xl`).
2. Bottom half is a white card (`--ink-0`, `--radius-xl 0 0 24 24` if it docks to the screen edge) overlapping the bottom of the hero.
3. The white card has the form inside it, scrolling independently.

Use only for action screens where the context (the data being acted
on) lives in the hero and the action (the form) lives in the sheet.

### Friendly greetings

Always greet the user by name on the dashboard / workspace picker:

```
Hello, Mithun.
Have a nice day.
```

Avoid "Welcome back", "Greetings", or "Hi there" — generic. Use the
user's first name (or full name if first isn't available). Lowercase
"hello"; capital on the name. End with a soft helper that's specific
to the context if you can ("Three tickets need a decision today.").

### Empty states

When a list is empty, show:

1. A small illustration or large monogram (gold or red, soft)
2. A one-sentence title ("No tickets match this filter.")
3. A one-sentence next step ("Try a different filter, or submit a new ticket.")
4. The CTA, if there's one ("+ New ticket")

Don't apologise. Don't use exclamation marks. The empty state is just
information.

### Mobile-first responsive tiers

Every layout has three states. Test all three.

| Tier | Viewport | What changes |
|---|---|---|
| Phone | ≤ 640 px | Frame loses radius and fills the screen. Header wraps with nav on a second row. Every multi-col grid stacks to 1. Tables overflow-scroll horizontally. Inputs use 16 px font (iOS no-zoom-on-focus). Tap targets ≥ 44 px. |
| Tablet | ≤ 1024 px | Outer frame keeps a smaller radius. Bento grids collapse from 3 cols to 2. Multi-column form rows stack. Header stays single-row. |
| Desktop | > 1024 px | Full layout with `--max-frame: 1280 px` outer frame. Bento grids run 3-col. Sidebars (if any) are visible. |

**Design mobile first.** Compose the screen for a 375 × 812 phone,
then verify it scales up gracefully. The references this draws from
were mobile apps — desktop is the bonus layer, not the source of truth.

---

## Voice

We write the UI the way we'd brief a careful colleague. Short. Direct.
No exclamation marks, no emoji in chrome.

| Good | Not OK |
|---|---|
| Eval complete. | Yay! 🎉 You did it! |
| 1 of 3 voters approved. Waiting for the rest. | Oh no, only one person voted… |
| Sign in to continue. | Hey there, sign in to access the app! |
| Hello, Mithun. | Welcome back, user! |

Error messages should explain **what** happened and **what to do**, in
one sentence. Surface the underlying API error after that, in
monospace.

### About the product

When describing Superstar in writing (README, marketing copy, slides):

- Lead with the outcome, not the feature: *"Auto-decide most requests, cite the rules, escalate the rest."* Not *"AI-powered ticketing platform with RAG."*
- Be specific about the safety contract — citation + applies_when + threshold is the whole pitch.
- Don't oversell the LLM. The interesting part is the guards, not the model.

---

## Implementation

All tokens land in `frontend/src/index.css` as `:root` custom
properties. Components reference tokens, never hex literals. Add a new
shade only when an existing one provably doesn't fit — every extra
colour costs more than it pays back.

CSS file ordering:

1. `:root` token definitions
2. Element resets (`body`, `a`, `code`, `pre`, `input/select/textarea`)
3. Layout primitives (`.app-shell`, `.app-main`, `.page-header`)
4. Components, alphabetical-ish
5. Responsive overrides at the bottom, ordered phone-first

**When in doubt: fewer rules, larger whitespace, more radius, brighter
red on the one thing you want the user to do next.**

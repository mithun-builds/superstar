# SuperStar brand guidelines

A minimal identity for a piece of OSS infrastructure. The goal is **calm and
legible** — not "design-led startup". Most pixels are content (tickets,
decisions, rules); the brand recedes into the chrome until it needs to act
as a signal (status colour, primary action, error).

## The mark

- **Form** — a ticket shape (rounded square with two semicircular notches at the left and right midpoints) framing a 5-point star. Encodes the product (ticketing) and the name (star) in one silhouette.
- **Primary asset:** [`frontend/public/logo.svg`](../frontend/public/logo.svg) (256×256, two flat fills, no gradients).
- **Favicon:** [`frontend/public/favicon.svg`](../frontend/public/favicon.svg) — same mark with the star scaled up ~18% for tiny-render legibility.
- **Clear space:** keep a margin equal to one notch-radius (~10% of the mark's height) on all sides.
- **Minimum size:** 16 px favicon. Below 24 px, drop any wordmark beside the mark.

### Reductions

- **Mono on light** — render the ticket in `--ink-900` (#111), the star in the same colour. Use when the surface is already coloured.
- **Mono on dark** — both shapes in white.
- **Star only** — drop the ticket frame when you need a tiny accent (chip icons, in-text). Use the gold.

### Don't

- Don't outline the star or the ticket separately — both are filled flat.
- Don't add a drop shadow.
- Don't put the mark on a busy photo background.
- Don't recolour the star to anything other than `--gold-500` or one of the mono treatments above.

## Colour

The palette is **two brand colours + a neutral ramp + four semantic states**.
That's it — anything else is a smell.

### Brand

| Token | Hex | Use |
|---|---|---|
| `--red-600` | `#D7242B` | The mark's body. Primary CTA. Selected-state fill. |
| `--red-700` | `#B81C22` | CTA hover/pressed. Borders on red surfaces. |
| `--red-100` | `#FCE6E7` | Red-tinted backgrounds (errors, destructive confirmations). |
| `--gold-500` | `#F5C518` | The mark's star. Accent only — never as a body colour or text. |
| `--gold-100` | `#FFF6D6` | Highlight / "new" tag background. |

Why these specifically:
- **`#D7242B`** — a warm vivid red that reads clearly on white without vibrating. Lighter would feel "candy"; darker would feel corporate. Same family as the reference mark.
- **`#F5C518`** — the gold that says "rating / approval" without going amber. Same hue as IMDb's familiar star; works against both red and white.

### Neutrals

A 9-step warm-grey ramp. Use these for 95% of the UI.

| Token | Hex | Use |
|---|---|---|
| `--ink-950` | `#0F0F11` | Display text (page headings only) |
| `--ink-900` | `#18181B` | Body text |
| `--ink-700` | `#3F3F46` | Secondary text |
| `--ink-500` | `#71717A` | Muted text, placeholders, helper copy |
| `--ink-300` | `#D4D4D8` | Borders on interactive controls |
| `--ink-200` | `#E4E4E7` | Borders on static cards |
| `--ink-100` | `#F4F4F5` | Subtle row backgrounds, code blocks |
| `--ink-50`  | `#FAFAFA` | App background |
| `--ink-0`   | `#FFFFFF` | Card surfaces |

### Semantic states

Status pills and the four decisioning outcomes ride this scale, not the brand reds. Brand red is for *actions*, not for *bad-outcome* states.

| Token | Background | Foreground | Used for |
|---|---|---|---|
| `--ok-bg` / `--ok-fg` | `#E3F5E9` / `#1B7A3A` | Approve, decided, healthy |
| `--warn-bg` / `--warn-fg` | `#FFF4D6` / `#8A6100` | Escalate, shadow mode, attention |
| `--err-bg` / `--err-fg` | `#FCE6E7` / `#B81C22` | Reject, error, destructive |
| `--info-bg` / `--info-fg` | `#E6F0FA` / `#1A56C0` | Open, pending, informational |

## Typography

System fonts. Two weights. Two scales — display and body. That's it.

```
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, system-ui, sans-serif;
font-family-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
```

| Token | Size | Weight | Use |
|---|---|---|---|
| `--text-display` | 28 px / 1.2 | 700 | Page H1 |
| `--text-h2` | 18 px / 1.3 | 600 | Section heads |
| `--text-h3` | 15 px / 1.4 | 600 | Card heads, field labels |
| `--text-body` | 14 px / 1.5 | 400 | Default |
| `--text-small` | 12.5 px / 1.4 | 400 | Helper text, status pills, metadata |
| `--text-mono` | 13 px / 1.5 | 400 | Identifiers, IDs, rule_ids, payloads |

Avoid heavier than 700. Avoid italics in chrome (reserve for quoted user content like stage notes).

## Spacing & radius

A single 4 px base.

| Token | Value |
|---|---|
| `--space-1` | 4 px |
| `--space-2` | 8 px |
| `--space-3` | 12 px |
| `--space-4` | 16 px |
| `--space-6` | 24 px |
| `--space-8` | 32 px |
| `--radius-sm` | 4 px (chips, pills) |
| `--radius-md` | 8 px (buttons, cards, inputs) |
| `--radius-lg` | 12 px (modals — when we get them) |

## Buttons — three roles, that's it

```
.btn            → secondary; subtle border, transparent bg, full-weight text
.btn-primary    → red filled. One per page. The thing you want them to do.
.btn-quiet      → link-style; no border, no fill. For "Save", "Delete" inside
                  a row that's already enclosed by a card.
.btn-danger     → red text on a red-100 hover; for destructive actions
                  (Delete) that can ruin the user's day.
```

If a row of three buttons makes sense, exactly one of them is `btn-primary`. If a card has fewer than three actions, prefer `btn-quiet` for all of them — let the card itself be the visual frame.

## Status pills

Used everywhere — ticket status, stage status, vote tally, decision outcome.

- Padding: `2px 8px`
- Radius: `--radius-sm` (the chip variant of pill — flatter at small sizes)
- Font: `--text-small`, weight 600, uppercase, letter-spacing 0.02em
- Colour: from the **Semantic states** table only. Never use brand red for an unhealthy status.

## Voice

We write the UI the way you'd brief a careful colleague. Short. Direct. No exclamation marks, no emoji.

- **OK**: "Eval complete." / "1 of 3 voters approved. Waiting for the rest."
- **Not OK**: "Yay! 🎉 You did it!" / "Oh no, something went wrong!"

Error messages should explain what happened and what the user can do, in one sentence. Surface the original API error after that, in monospace.

## Voice — about the product

When describing SuperStar in writing (README, marketing copy, slide decks):

- Lead with the outcome, not the feature: "Auto-decide most requests, cite the rules, escalate the rest." Not: "AI-powered ticketing platform with RAG."
- Be specific about the safety contract — citation + applies_when + threshold is the whole pitch.
- Don't oversell the LLM. The interesting part is the guards, not the model.

## Implementation

All tokens above land in `frontend/src/index.css` as `:root` custom properties. Components reference tokens, never hex literals. Add a new shade only when an existing one provably doesn't fit — every extra colour costs more than it pays back.

CSS file ordering:
1. `:root` token definitions
2. Element resets (`body`, `a`, `code`, `pre`)
3. Layout primitives (`.app-shell`, `.app-main`, `.page-header`)
4. Components, alphabetical
5. Responsive overrides at the bottom

When in doubt: **fewer rules, larger whitespace.** The product is content-heavy; the chrome's job is to disappear.

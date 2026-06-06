// Brand-catalog presentational components. Stateless, dumb, take props.
//
// Pair with the matching CSS classes in index.css. The components are
// documented in docs/brand.md; this file is the React-shaped expression
// of that catalog. If you find yourself adding a new component here,
// add it to the brand doc first.

import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// GreetingHeader — "Hello, [Name]." with a soft subtitle.
// Render only on top-level authenticated screens (Dashboard, workspace
// picker). Don't repeat on subpages.
// ---------------------------------------------------------------------------
export function GreetingHeader({
  name,
  subtitle,
}: {
  name: string;
  subtitle?: ReactNode;
}) {
  return (
    <header className="greeting">
      <h1 className="greeting-line">
        Hello, <span className="name">{name}</span>.
      </h1>
      {subtitle && <p className="greeting-sub">{subtitle}</p>}
    </header>
  );
}

// ---------------------------------------------------------------------------
// HeroCard — filled red top-of-screen panel. At most one per screen.
// Carries the action context — title, sub, optional CTA row.
// Inside a hero, .btn-primary auto-switches to gold so it doesn't melt.
// ---------------------------------------------------------------------------
export function HeroCard({
  eyebrow,
  title,
  sub,
  children,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="hero-card">
      {eyebrow && <div className="hero-card-eyebrow">{eyebrow}</div>}
      <h2 className="hero-card-title">{title}</h2>
      {sub && <p className="hero-card-sub">{sub}</p>}
      {children}
      {actions && <div className="hero-card-actions">{actions}</div>}
    </section>
  );
}

// ---------------------------------------------------------------------------
// StickerCard — filled gold "you did it" moment. Rare.
// Use for completion / approval / score celebrations.
// ---------------------------------------------------------------------------
export function StickerCard({
  eyebrow,
  children,
}: {
  eyebrow?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="sticker-card">
      {eyebrow && <div className="sticker-card-eyebrow">{eyebrow}</div>}
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Toggle — red switch when on, neutral when off. Stateless: pass `on`
// and `onChange`.
// ---------------------------------------------------------------------------
export function Toggle({
  on,
  onChange,
  label,
  disabled,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      className="toggle"
      onClick={() => onChange(!on)}
    />
  );
}

// ---------------------------------------------------------------------------
// SegmentedControl — pill row with one loud-red selected.
// `options` is [{value, label}]. Single-select only.
// ---------------------------------------------------------------------------
export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (next: T) => void;
  options: Array<{ value: T; label: ReactNode }>;
}) {
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DateStrip — horizontal scroll of date pills. Pure presentation;
// caller passes `dates` (Date objects) and the selected one.
// ---------------------------------------------------------------------------
export function DateStrip({
  dates,
  selected,
  onSelect,
}: {
  dates: Date[];
  selected: Date;
  onSelect: (d: Date) => void;
}) {
  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  return (
    <div className="date-strip" role="listbox">
      {dates.map((d) => (
        <button
          key={d.toISOString()}
          type="button"
          role="option"
          aria-pressed={isSameDay(d, selected)}
          aria-selected={isSameDay(d, selected)}
          className="date-pill"
          onClick={() => onSelect(d)}
        >
          <span className="date-pill-num">{d.getDate()}</span>
          <span className="date-pill-day">
            {d.toLocaleDateString(undefined, { weekday: "short" })}
          </span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Avatar — round monogram. Falls back to initials when no `src`.
// `size` defaults to "md" (40 px). Use "sm" in chrome, "lg" in heroes.
// ---------------------------------------------------------------------------
export function Avatar({
  src,
  name,
  size = "md",
}: {
  src?: string | null;
  name: string;
  size?: "sm" | "md" | "lg";
}) {
  const letter = (name?.trim().charAt(0) || "?").toUpperCase();
  const cls = size === "sm" ? "avatar avatar-sm" : size === "lg" ? "avatar avatar-lg" : "avatar";
  if (src) {
    return (
      <img
        className={cls}
        src={src}
        alt={name}
        style={{ objectFit: "cover" }}
      />
    );
  }
  return <span className={cls} aria-label={name}>{letter}</span>;
}

// ---------------------------------------------------------------------------
// FAB — floating + button, bottom-right. Use when the screen has one
// clear "create new" action and the page chrome wouldn't fit another CTA.
// ---------------------------------------------------------------------------
export function FAB({
  onClick,
  label = "Add",
  glyph = "+",
}: {
  onClick: () => void;
  label?: string;
  glyph?: string;
}) {
  return (
    <button
      type="button"
      className="fab"
      onClick={onClick}
      aria-label={label}
    >
      {glyph}
    </button>
  );
}

// ---------------------------------------------------------------------------
// BottomNav — mobile-only 4-icon nav. Pass `items` with a current `to`.
// The component handles its own visibility (display: none above 640 px).
// ---------------------------------------------------------------------------
export function BottomNav({
  items,
  activeHref,
}: {
  items: Array<{ to: string; label: string; glyph: ReactNode }>;
  activeHref: string;
}) {
  return (
    <nav className="bottom-nav" aria-label="Primary">
      {items.map((it) => (
        <a
          key={it.to}
          href={it.to}
          className={activeHref === it.to || activeHref.startsWith(it.to + "/") ? "active" : ""}
        >
          <span className="icon" aria-hidden="true">{it.glyph}</span>
          <span>{it.label}</span>
        </a>
      ))}
    </nav>
  );
}

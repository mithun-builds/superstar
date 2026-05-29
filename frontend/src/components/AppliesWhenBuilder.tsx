// Visual editor for the applies_when DSL.
//
// Renders one row per top-level condition, with three controls:
//   field name  |  operator  |  value (shape depends on operator)
//
// Operators mirror the DSL evaluator (superstar/applies_when.py):
//   equals    bare scalar             { field: scalar }
//   in        bare list               { field: [...] }
//   not_in    {not_in: [...]}         { field: {not_in: [...]} }
//   not       {not: scalar}           { field: {not: scalar} }
//   gte/gt/lte/lt   {op: N}           { field: {op: N} }
//   between   {between: [a, b]}       { field: {between: [a, b]} }
//   has_any   {has_any: [...]}        { field: {has_any: [...]} }
//
// Round-trips: the parser handles any valid DSL document the backend
// would accept, and the serializer emits the same shape it parsed.
// Editing an existing rule never loses fields the UI doesn't recognize
// — those flow through via the `_unknown` bucket and are merged back on
// serialize.

import { useEffect, useState } from "react";

export type Operator =
  | "equals"
  | "in"
  | "not_in"
  | "not"
  | "gte"
  | "gt"
  | "lte"
  | "lt"
  | "between"
  | "has_any";

const NUMERIC_OPS = new Set<Operator>(["gte", "gt", "lte", "lt", "between"]);
const LIST_OPS = new Set<Operator>(["in", "not_in", "has_any"]);

interface Condition {
  field: string;
  operator: Operator;
  scalar?: string;
  list?: string;
  between?: [string, string];
}

interface Props {
  value: Record<string, unknown> | null;
  onChange: (next: Record<string, unknown>) => void;
  knownFieldNames?: string[];
}

// ---------------------------------------------------------------------------
// Parse / serialize
// ---------------------------------------------------------------------------
function parse(obj: Record<string, unknown> | null): {
  rows: Condition[];
  unknown: Record<string, unknown>;
} {
  const rows: Condition[] = [];
  const unknown: Record<string, unknown> = {};
  if (!obj || typeof obj !== "object") return { rows, unknown };

  for (const [field, predicate] of Object.entries(obj)) {
    const cond = parsePredicate(field, predicate);
    if (cond) rows.push(cond);
    else unknown[field] = predicate;
  }
  return { rows, unknown };
}

function parsePredicate(field: string, predicate: unknown): Condition | null {
  if (predicate === null || predicate === undefined) return null;

  // bare scalar → equals
  if (typeof predicate === "string" || typeof predicate === "number" || typeof predicate === "boolean") {
    return { field, operator: "equals", scalar: String(predicate) };
  }
  // bare list → in
  if (Array.isArray(predicate)) {
    return { field, operator: "in", list: predicate.map(String).join(", ") };
  }
  // dict → operator predicate
  if (typeof predicate === "object") {
    const entries = Object.entries(predicate as Record<string, unknown>);
    if (entries.length !== 1) return null;
    const [op, arg] = entries[0];
    switch (op) {
      case "not":
        return { field, operator: "not", scalar: String(arg) };
      case "gte":
      case "gt":
      case "lte":
      case "lt":
        return { field, operator: op as Operator, scalar: String(arg) };
      case "between":
        if (Array.isArray(arg) && arg.length === 2) {
          return { field, operator: "between", between: [String(arg[0]), String(arg[1])] };
        }
        return null;
      case "not_in":
      case "has_any":
        if (Array.isArray(arg)) {
          return { field, operator: op as Operator, list: arg.map(String).join(", ") };
        }
        return null;
      default:
        return null;
    }
  }
  return null;
}

function coerce(s: string): string | number | boolean {
  const trimmed = s.trim();
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  if (trimmed !== "" && !Number.isNaN(Number(trimmed))) return Number(trimmed);
  return trimmed;
}

function serialize(rows: Condition[], unknown: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...unknown };
  for (const r of rows) {
    if (!r.field.trim()) continue;
    switch (r.operator) {
      case "equals":
        out[r.field] = coerce(r.scalar ?? "");
        break;
      case "in":
        out[r.field] = (r.list ?? "").split(",").map((s) => coerce(s)).filter((v) => v !== "");
        break;
      case "not":
        out[r.field] = { not: coerce(r.scalar ?? "") };
        break;
      case "gte":
      case "gt":
      case "lte":
      case "lt":
        out[r.field] = { [r.operator]: Number(r.scalar ?? "0") };
        break;
      case "between":
        out[r.field] = { between: [Number(r.between?.[0] ?? 0), Number(r.between?.[1] ?? 0)] };
        break;
      case "not_in":
      case "has_any":
        out[r.field] = {
          [r.operator]: (r.list ?? "").split(",").map((s) => coerce(s)).filter((v) => v !== ""),
        };
        break;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AppliesWhenBuilder({ value, onChange, knownFieldNames }: Props) {
  const [rows, setRows] = useState<Condition[]>([]);
  const [unknown, setUnknown] = useState<Record<string, unknown>>({});

  // Hydrate from incoming value on first render and whenever the parent
  // hands us a fresh object (e.g. after API reload).
  useEffect(() => {
    const parsed = parse(value);
    setRows(parsed.rows);
    setUnknown(parsed.unknown);
  }, [value]);

  const update = (next: Condition[]) => {
    setRows(next);
    onChange(serialize(next, unknown));
  };

  const setRow = (i: number, patch: Partial<Condition>) =>
    update(rows.map((r, j) => (i === j ? { ...r, ...patch } : r)));

  const addRow = () => {
    // Default to the first known field that ISN'T already used as a top-level
    // condition key — two rows with the same field name would collide on
    // serialize (each entry overwrites the prior one).
    const inUse = new Set(rows.map((r) => r.field));
    const firstFree = knownFieldNames?.find((n) => !inUse.has(n));
    update([
      ...rows,
      { field: firstFree ?? "", operator: "equals", scalar: "" },
    ]);
  };

  const removeRow = (i: number) => update(rows.filter((_, j) => i !== j));

  return (
    <div className="applies-when-builder">
      {rows.length === 0 && (
        <p className="muted">
          No conditions — this rule will be considered applicable to every
          request of this type. Click <strong>+ Add condition</strong> to
          constrain it.
        </p>
      )}

      {rows.map((r, i) => (
        <div key={i} className="cond-row">
          {knownFieldNames && knownFieldNames.length > 0 ? (
            <select
              value={r.field}
              onChange={(e) => setRow(i, { field: e.target.value })}
              className="cond-field"
            >
              {!knownFieldNames.includes(r.field) && r.field !== "" && (
                <option value={r.field}>{r.field} (custom)</option>
              )}
              <option value="">— pick a field —</option>
              {knownFieldNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              className="cond-field"
              placeholder="field name"
              value={r.field}
              onChange={(e) => setRow(i, { field: e.target.value })}
            />
          )}

          <select
            value={r.operator}
            onChange={(e) =>
              setRow(i, { operator: e.target.value as Operator, scalar: "", list: "", between: ["", ""] })
            }
            className="cond-op"
          >
            <option value="equals">equals</option>
            <option value="not">not equal</option>
            <option value="in">in (list)</option>
            <option value="not_in">not in</option>
            <option value="gte">≥</option>
            <option value="gt">&gt;</option>
            <option value="lte">≤</option>
            <option value="lt">&lt;</option>
            <option value="between">between</option>
            <option value="has_any">has any of</option>
          </select>

          {LIST_OPS.has(r.operator) ? (
            <input
              type="text"
              className="cond-value"
              placeholder="comma-separated values"
              value={r.list ?? ""}
              onChange={(e) => setRow(i, { list: e.target.value })}
            />
          ) : r.operator === "between" ? (
            <>
              <input
                type="number"
                className="cond-value cond-value-half"
                placeholder="min"
                value={r.between?.[0] ?? ""}
                onChange={(e) =>
                  setRow(i, { between: [e.target.value, r.between?.[1] ?? ""] })
                }
              />
              <input
                type="number"
                className="cond-value cond-value-half"
                placeholder="max"
                value={r.between?.[1] ?? ""}
                onChange={(e) =>
                  setRow(i, { between: [r.between?.[0] ?? "", e.target.value] })
                }
              />
            </>
          ) : (
            <input
              type={NUMERIC_OPS.has(r.operator) ? "number" : "text"}
              className="cond-value"
              placeholder="value"
              value={r.scalar ?? ""}
              onChange={(e) => setRow(i, { scalar: e.target.value })}
            />
          )}

          <button type="button" className="btn-icon" onClick={() => removeRow(i)} title="Remove">
            ✕
          </button>
        </div>
      ))}

      <button type="button" className="btn" onClick={addRow}>
        + Add condition
      </button>

      {Object.keys(unknown).length > 0 && (
        <p className="muted small">
          (Editor preserved {Object.keys(unknown).length} unrecognized condition
          {Object.keys(unknown).length === 1 ? "" : "s"} as-is.)
        </p>
      )}
    </div>
  );
}

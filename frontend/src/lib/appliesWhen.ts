/**
 * Client-side twin of superstar/applies_when.py.
 *
 * Same DSL, same operators, same semantics. Used by DynamicForm to evaluate
 * show_if / choices_if conditions in real time as the user types.
 *
 * Operators:
 *   bare scalar              equality
 *   list                     membership
 *   { gte | gt | lte | lt }  numeric comparisons
 *   { between: [a, b] }      inclusive numeric range
 *   { not_in: [...] }        not in list
 *   { not: x }               inequality
 *   { has_any: [...] }       array intersection
 *
 * Empty/null conditions → applies = true (no constraints).
 */

export type Predicate = unknown;
export type ConditionsMap = Record<string, Predicate> | null | undefined;

const KNOWN_OPS = new Set([
  "gte", "gt", "lte", "lt", "between", "not_in", "not", "has_any",
]);

export function appliesTo(
  conditions: ConditionsMap,
  payload: Record<string, unknown>,
): { applies: boolean; reasons: string[] } {
  if (!conditions || typeof conditions !== "object" || Object.keys(conditions).length === 0) {
    return { applies: true, reasons: [] };
  }
  const failures: string[] = [];
  for (const [field, predicate] of Object.entries(conditions)) {
    const ok = checkField(field, payload[field], predicate, failures);
    if (!ok) {
      // checkField pushes a reason; loop continues so reasons are exhaustive.
    }
  }
  return { applies: failures.length === 0, reasons: failures };
}

function checkField(
  field: string,
  value: unknown,
  predicate: Predicate,
  failures: string[],
): boolean {
  // Bare scalar → equality
  if (
    typeof predicate === "string" ||
    typeof predicate === "number" ||
    typeof predicate === "boolean"
  ) {
    if (value === predicate) return true;
    failures.push(`${field} = ${JSON.stringify(value)}, expected ${JSON.stringify(predicate)}`);
    return false;
  }

  // List → membership
  if (Array.isArray(predicate)) {
    if (predicate.some((p) => p === value)) return true;
    failures.push(`${field} = ${JSON.stringify(value)}, expected one of ${JSON.stringify(predicate)}`);
    return false;
  }

  // Dict → operator
  if (predicate && typeof predicate === "object") {
    const entries = Object.entries(predicate as Record<string, unknown>);
    if (entries.length !== 1) {
      failures.push(`${field}: predicate must have exactly one operator, got ${entries.length}`);
      return false;
    }
    const [op, arg] = entries[0];
    if (!KNOWN_OPS.has(op)) {
      failures.push(`${field}: unknown operator ${JSON.stringify(op)}`);
      return false;
    }
    return applyOp(field, value, op, arg, failures);
  }

  failures.push(`${field}: unsupported predicate ${JSON.stringify(predicate)}`);
  return false;
}

function applyOp(
  field: string,
  value: unknown,
  op: string,
  arg: unknown,
  failures: string[],
): boolean {
  if (op === "not") {
    if (value !== arg) return true;
    failures.push(`${field}: not = ${JSON.stringify(arg)} but value matched`);
    return false;
  }

  if (op === "not_in") {
    if (!Array.isArray(arg)) {
      failures.push(`${field}: not_in requires a list`);
      return false;
    }
    if (!arg.some((a) => a === value)) return true;
    failures.push(`${field} = ${JSON.stringify(value)} but is in ${JSON.stringify(arg)}`);
    return false;
  }

  if (op === "has_any") {
    if (!Array.isArray(arg)) {
      failures.push(`${field}: has_any requires a list`);
      return false;
    }
    if (Array.isArray(value) && value.some((v) => arg.includes(v))) return true;
    failures.push(`${field} has none of ${JSON.stringify(arg)}`);
    return false;
  }

  // Numeric ops
  const numericOps = ["gte", "gt", "lte", "lt"];
  if (numericOps.includes(op)) {
    if (value === null || value === undefined || value === "") {
      failures.push(`${field}: cannot compare ${op} ${JSON.stringify(arg)} — missing value`);
      return false;
    }
    const v = Number(value);
    const a = Number(arg);
    if (Number.isNaN(v) || Number.isNaN(a)) {
      failures.push(`${field}: non-numeric comparison`);
      return false;
    }
    const pass =
      op === "gte" ? v >= a :
      op === "gt"  ? v >  a :
      op === "lte" ? v <= a :
                     v <  a;
    if (pass) return true;
    failures.push(`${field} = ${v}, expected ${op} ${a}`);
    return false;
  }

  if (op === "between") {
    if (!Array.isArray(arg) || arg.length !== 2) {
      failures.push(`${field}: between requires [low, high]`);
      return false;
    }
    if (value === null || value === undefined || value === "") {
      failures.push(`${field}: missing value for between`);
      return false;
    }
    const v = Number(value);
    const lo = Number(arg[0]);
    const hi = Number(arg[1]);
    if (Number.isNaN(v) || Number.isNaN(lo) || Number.isNaN(hi)) {
      failures.push(`${field}: non-numeric between`);
      return false;
    }
    if (v >= lo && v <= hi) return true;
    failures.push(`${field} = ${v}, expected between ${lo} and ${hi}`);
    return false;
  }

  failures.push(`${field}: unhandled operator ${op}`);
  return false;
}


/**
 * Resolve the active choices for an enum field given the current payload.
 * Mirrors backend _active_choices: first matching rule wins, fall back to
 * the field's static `choices`.
 */
export function activeChoices(
  field: { choices?: string[]; choices_if?: Array<{ conditions: ConditionsMap; choices: string[] }> },
  payload: Record<string, unknown>,
): string[] {
  for (const rule of field.choices_if ?? []) {
    if (appliesTo(rule.conditions, payload).applies) {
      return rule.choices ?? [];
    }
  }
  return field.choices ?? [];
}

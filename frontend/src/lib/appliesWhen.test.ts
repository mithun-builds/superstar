// Tests for the TypeScript port of applies_when.
//
// Mirrors superstar/tests/test_applies_when.py one-for-one. When you add
// an operator or change semantics in either port, update both test files
// — that mirroring is the only thing keeping the form's client-side
// behavior in sync with backend validation.
//
// Pure logic only — no React, no DOM, no testing-library.
import { describe, expect, it } from "vitest";
import { activeChoices, appliesTo } from "./appliesWhen";

describe("appliesTo — equality + membership", () => {
  it("scalar equality passes", () => {
    expect(appliesTo({ role: "engineer" }, { role: "engineer" })).toEqual({
      applies: true,
      reasons: [],
    });
  });

  it("scalar equality fails with a useful reason", () => {
    const { applies, reasons } = appliesTo({ role: "engineer" }, { role: "finance" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("role");
    expect(reasons[0]).toContain("engineer");
  });

  it("number scalar equality", () => {
    expect(appliesTo({ qty: 5 }, { qty: 5 }).applies).toBe(true);
    expect(appliesTo({ qty: 5 }, { qty: 6 }).applies).toBe(false);
  });

  it("boolean scalar equality", () => {
    expect(appliesTo({ urgent: true }, { urgent: true }).applies).toBe(true);
    expect(appliesTo({ urgent: true }, { urgent: false }).applies).toBe(false);
  });

  it("list-as-predicate is membership", () => {
    expect(appliesTo({ role: ["engineer", "ops"] }, { role: "engineer" }).applies).toBe(true);
    expect(appliesTo({ role: ["engineer", "ops"] }, { role: "finance" }).applies).toBe(false);
  });

  it("list-membership failure mentions the allowed set", () => {
    const { reasons } = appliesTo({ role: ["engineer", "ops"] }, { role: "finance" });
    expect(reasons[0]).toContain("expected one of");
  });
});

describe("appliesTo — numeric operators", () => {
  const cases: Array<[string, number, number | string, boolean]> = [
    ["gte", 350, 350, true],
    ["gte", 350, 349, false],
    ["gt", 350, 351, true],
    ["gt", 350, 350, false],
    ["lte", 350, 350, true],
    ["lte", 350, 351, false],
    ["lt", 350, 349, true],
    ["lt", 350, 350, false],
  ];
  it.each(cases)("op=%s threshold=%s value=%s → applies=%s", (op, threshold, value, expected) => {
    expect(appliesTo({ w: { [op]: threshold } }, { w: value }).applies).toBe(expected);
  });

  it("string-of-a-number is coerced (the frontend reads form values as strings)", () => {
    // Critical parity case: DOM `<input type=number>` writes strings into
    // payload. The DSL must not silently fail on those.
    expect(appliesTo({ w: { gte: 350 } }, { w: "351" }).applies).toBe(true);
    expect(appliesTo({ w: { lt: 10 } }, { w: "5" }).applies).toBe(true);
  });

  it("missing value fails with a 'missing' reason", () => {
    const { applies, reasons } = appliesTo({ w: { gte: 350 } }, {});
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("missing");
  });

  it("empty-string value treated as missing (matches form initial state)", () => {
    const { applies, reasons } = appliesTo({ w: { gte: 350 } }, { w: "" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("missing");
  });

  it("non-numeric value fails with a 'non-numeric' reason", () => {
    const { applies, reasons } = appliesTo({ w: { gte: 350 } }, { w: "tall" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("non-numeric");
  });
});

describe("appliesTo — between (inclusive)", () => {
  const cond = { w: { between: [300, 600] } };
  it("hits lower bound", () => expect(appliesTo(cond, { w: 300 }).applies).toBe(true));
  it("hits upper bound", () => expect(appliesTo(cond, { w: 600 }).applies).toBe(true));
  it("midpoint", () => expect(appliesTo(cond, { w: 450 }).applies).toBe(true));
  it("below low", () => expect(appliesTo(cond, { w: 299 }).applies).toBe(false));
  it("above high", () => expect(appliesTo(cond, { w: 601 }).applies).toBe(false));

  it("malformed between (not a 2-list)", () => {
    const { applies, reasons } = appliesTo({ w: { between: [300] } }, { w: 400 });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("between");
  });

  it("missing value fails", () => {
    const { applies, reasons } = appliesTo(cond, {});
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("missing");
  });
});

describe("appliesTo — not / not_in", () => {
  it("not (inequality) passes when value differs", () => {
    expect(appliesTo({ role: { not: "intern" } }, { role: "engineer" }).applies).toBe(true);
  });

  it("not fails when value matches", () => {
    const { applies, reasons } = appliesTo({ role: { not: "intern" } }, { role: "intern" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("not");
  });

  it("not_in passes when value isn't in the list", () => {
    expect(
      appliesTo({ finish: { not_in: ["PU", "Membrane"] } }, { finish: "Laminate" }).applies,
    ).toBe(true);
  });

  it("not_in fails when value IS in the list", () => {
    const { applies, reasons } = appliesTo(
      { finish: { not_in: ["PU", "Membrane"] } },
      { finish: "PU" },
    );
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("is in");
  });

  it("not_in malformed (non-list arg) fails clearly", () => {
    const { applies, reasons } = appliesTo({ x: { not_in: "PU" } }, { x: "PU" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("list");
  });
});

describe("appliesTo — has_any (array intersection)", () => {
  it("matches when any tag overlaps", () => {
    expect(
      appliesTo({ tags: { has_any: ["urgent", "vip"] } }, { tags: ["normal", "vip"] }).applies,
    ).toBe(true);
  });

  it("fails when no tags overlap", () => {
    expect(
      appliesTo({ tags: { has_any: ["urgent", "vip"] } }, { tags: ["normal"] }).applies,
    ).toBe(false);
  });

  it("non-array payload value fails (not silently true)", () => {
    expect(
      appliesTo({ tags: { has_any: ["urgent"] } }, { tags: "urgent" }).applies,
    ).toBe(false);
  });

  it("malformed has_any (non-list arg) fails", () => {
    const { applies, reasons } = appliesTo({ tags: { has_any: "urgent" } }, { tags: ["urgent"] });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("list");
  });
});

describe("appliesTo — empty / null / multi-field semantics", () => {
  it("null conditions → universally true", () => {
    expect(appliesTo(null, { anything: 1 }).applies).toBe(true);
  });

  it("undefined conditions → universally true", () => {
    expect(appliesTo(undefined, {}).applies).toBe(true);
  });

  it("empty object conditions → universally true", () => {
    expect(appliesTo({}, {}).applies).toBe(true);
  });

  it("multiple conditions are AND-ed (all must match)", () => {
    const cond = { role: "engineer", quantity: { gte: 1 } };
    expect(appliesTo(cond, { role: "engineer", quantity: 5 }).applies).toBe(true);
    expect(appliesTo(cond, { role: "engineer", quantity: 0 }).applies).toBe(false);
    expect(appliesTo(cond, { role: "intern", quantity: 5 }).applies).toBe(false);
  });

  it("multiple failures accumulate (exhaustive reasons, not short-circuit)", () => {
    const cond = { role: "engineer", quantity: { gte: 1 } };
    const { applies, reasons } = appliesTo(cond, { role: "intern", quantity: 0 });
    expect(applies).toBe(false);
    expect(reasons).toHaveLength(2);
  });
});

describe("appliesTo — malformed input", () => {
  it("dict predicate with two operators is rejected", () => {
    const { applies, reasons } = appliesTo({ w: { gte: 1, lte: 10 } }, { w: 5 });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("exactly one operator");
  });

  it("unknown operator is rejected", () => {
    const { applies, reasons } = appliesTo({ w: { matches: "x" } }, { w: "x" });
    expect(applies).toBe(false);
    expect(reasons[0]).toContain("unknown operator");
  });
});

// ---------------------------------------------------------------------------
// activeChoices — used by enum form fields with cascading choices
// ---------------------------------------------------------------------------
describe("activeChoices", () => {
  const field = {
    choices: ["fallback_only"],
    choices_if: [
      { conditions: { room: "kitchen" }, choices: ["base", "wall", "sink"] },
      { conditions: { room: "wardrobe" }, choices: ["base", "dresser"] },
    ],
  };

  it("returns first-matching rule's choices", () => {
    expect(activeChoices(field, { room: "kitchen" })).toEqual(["base", "wall", "sink"]);
  });

  it("returns the second rule's choices on miss-then-hit", () => {
    expect(activeChoices(field, { room: "wardrobe" })).toEqual(["base", "dresser"]);
  });

  it("falls back to static choices when no rule matches", () => {
    expect(activeChoices(field, { room: "bathroom" })).toEqual(["fallback_only"]);
  });

  it("falls back to static choices when payload lacks the trigger field", () => {
    expect(activeChoices(field, {})).toEqual(["fallback_only"]);
  });

  it("first match wins (doesn't iterate further)", () => {
    const f = {
      choices_if: [
        { conditions: { x: 1 }, choices: ["A"] },
        { conditions: { x: 1 }, choices: ["B"] }, // never reached
      ],
    };
    expect(activeChoices(f, { x: 1 })).toEqual(["A"]);
  });

  it("missing choices_if returns plain choices", () => {
    expect(activeChoices({ choices: ["a", "b"] }, {})).toEqual(["a", "b"]);
  });

  it("missing both returns empty array", () => {
    expect(activeChoices({}, {})).toEqual([]);
  });
});

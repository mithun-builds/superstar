# `applies_when` — the condition DSL

One small predicate language used in three places:

1. **Rule frontmatter** — when does this KB rule apply to a request payload?
2. **`show_if` on a form field** — when is this field visible to the requester?
3. **`choices_if` on an enum field** — which choices are valid given the rest of the form state?

Same syntax, same evaluation semantics. Admins learn it once.

## Shape

A mapping of `field -> predicate`. All conditions must match (implicit AND)
for the block to be considered true. Empty / null block = always true.

```yaml
applies_when:
  request_type: additional_lock
  type_of_shutter: 1-shutter
  quantity: {gte: 1}
```

## Predicate forms

| Form | Meaning |
|---|---|
| `field: <scalar>` | equality (string / number / bool) |
| `field: [v1, v2]` | membership: `payload[field]` ∈ list |
| `field: {gte: N}` | `payload[field] >= N` |
| `field: {gt: N}` | `payload[field] > N` |
| `field: {lte: N}` | `payload[field] <= N` |
| `field: {lt: N}` | `payload[field] < N` |
| `field: {between: [a, b]}` | `a <= payload[field] <= b` (inclusive on both ends) |
| `field: {not: <scalar>}` | inequality |
| `field: {not_in: [...]}` | `payload[field]` ∉ list |
| `field: {has_any: [...]}` | array-valued field intersects list (at least one match) |

Dict predicates must have **exactly one** operator key — `{gte: 1, lte: 5}`
is a parse error, use `between` for ranges.

## Missing payload values

A missing key counts as a condition failure for every operator except where
the predicate is explicitly designed for absence. Numeric ops (`gte`, `gt`,
`lte`, `lt`, `between`) fail with a clear "value is missing" reason. There
is deliberately no `{optional: true}` modifier — if you need "either A or
not present", split it into two rules.

## Return value

```python
applies_to(conditions: dict | None, payload: dict) -> (bool, list[str])
```

When the second element is non-empty, each string explains exactly which
condition didn't match — usable in audit logs and admin debugging.

```python
>>> applies_to({"role": "engineer", "quantity": {"gte": 1}}, {"role": "intern", "quantity": 0})
(False, ["role = 'intern', expected 'engineer'", "quantity = 0, expected gte 1"])
```

## Backend ↔ frontend parity

Two implementations:

- [`superstar/applies_when.py`](../superstar/applies_when.py) — Python, used by the decisioning service for citation verification and by the serializer for payload validation
- [`frontend/src/lib/appliesWhen.ts`](../frontend/src/lib/appliesWhen.ts) — TypeScript port, used by the requester form to compute `show_if` / `choices_if` live

These **must stay in sync.** The Python port has 26 unit tests in `superstar/tests/test_applies_when.py`. The TypeScript port has no test coverage yet — a known gap. When you add an operator, update both ports + the Python tests, and ideally add a Vitest counterpart while you're there.

## Where it's evaluated

| Use site | When | Source |
|---|---|---|
| Rule citation verification | After the LLM responds; guard 3 of the four-guard pipeline | `apps/decisioning/services.py` |
| Form validation on `show_if` | At POST time | `apps/tickets/serializers.py` |
| Form validation on `choices_if` | At POST time, to compute the *active* choice list | `apps/tickets/serializers.py` |
| Form rendering on `show_if` | Live, as the requester types | `frontend/src/components/DynamicForm.tsx` |
| Form rendering on `choices_if` | Live, recomputes the active choices on every change | `frontend/src/components/DynamicForm.tsx` |

## Worked examples

**Range with a guard rail:**
```yaml
# Approve only if 1-5 modules of standard width
applies_when:
  request_type: standard_unit
  quantity: {between: [1, 5]}
  width_mm: 600
```

**Negative — "anything but the named values":**
```yaml
# Escalate for any finish that isn't laminate or membrane
applies_when:
  shutter_finish: {not_in: [Laminate, Membrane]}
```

**Conditional form field (`show_if`):**
```yaml
# Show the "module width" field only on air-vent requests
show_if:
  request_type: air_vent
```

**Cascading dropdown (`choices_if`):**
```yaml
choices_if:
  - conditions: {room_type: kitchen}
    choices: [base_unit, wall_unit, sink_unit, hob_unit]
  - conditions: {room_type: wardrobe}
    choices: [base_unit, wall_unit, dresser]
```

## Why a custom DSL (not Python expressions / JSONLogic)

- **Python expressions** — admins shouldn't be allowed to write arbitrary Python in a SaaS. Eval risk.
- **JSONLogic** — capable but ceremonial for the 80% case of "field equals x". This DSL keeps that case to one line.
- **JMESPath / JSONPath** — query languages, not predicate languages. Wrong fit.

The current DSL covers every rule shape we've needed for NSD.AI and the IT
access demo. When a real use case needs an operator we don't have, add it
to both ports + both test files.

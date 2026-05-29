"""applies_when — pure-logic predicate evaluator for rule frontmatter.

Lives in the framework-agnostic `superstar/` package because it's reused
by the Django decisioning service AND the standalone smoke scripts. No
Django imports.

## Why this exists

The LLM citation guard catches structurally-invented `rule_id` values
(model cited an ID that wasn't retrieved). But the model can still cite
a *real* rule_id whose `applies_when` conditions don't actually match
the request payload — e.g. citing NSD-LOCK-003 (PU/Membrane only) for a
Laminate request. This verifier closes that gap mechanically.

If any cited rule's conditions fail, the decisioning service forces
escalate. Same shape as the existing guards.

## DSL

A frontmatter `applies_when` block is a mapping of `field -> predicate`.
All conditions must match (implicit AND) for the rule to apply.

Predicates:

| Form                                        | Meaning                                |
|---------------------------------------------|----------------------------------------|
| `field: <scalar>`                           | equality                               |
| `field: [v1, v2]`                           | membership: payload[field] in list     |
| `field: {gte: N}`                           | payload[field] >= N                    |
| `field: {gt: N}`                            | payload[field] > N                     |
| `field: {lte: N}`                           | payload[field] <= N                    |
| `field: {lt: N}`                            | payload[field] < N                     |
| `field: {between: [a, b]}`                  | a <= payload[field] <= b               |
| `field: {not_in: [...]}`                    | payload[field] not in list             |
| `field: {not: <scalar>}`                    | inequality                             |
| `field: {has_any: [...]}`                   | array-valued field intersects list     |

A missing payload field counts as a condition failure unless the
predicate is `{optional: true}` (not currently supported — extend if a
real use case appears).

## Return value

`applies_to(conditions, payload) -> (bool, list[str])`

Returns `(applies, reasons_failed)`. When `applies` is `False`, the list
explains exactly which condition didn't match — usable in audit logs.
"""
from __future__ import annotations

from typing import Any

# Operator names recognized in dict predicates. Anything else is a parse error.
_KNOWN_OPS = frozenset({"gte", "gt", "lte", "lt", "between", "not_in", "not", "has_any"})


def applies_to(conditions: dict | None, payload: dict) -> tuple[bool, list[str]]:
    """Evaluate a rule's `applies_when` block against a request payload.

    If `conditions` is None or empty, the rule is considered to apply
    universally (no constraints declared). Callers can opt to treat that
    differently if they prefer strict matching.
    """
    if not conditions:
        return True, []

    if not isinstance(conditions, dict):
        return False, [f"applies_when must be a mapping, got {type(conditions).__name__}"]

    failures: list[str] = []
    for field, predicate in conditions.items():
        ok, reason = _check(field, payload.get(field), predicate)
        if not ok:
            failures.append(reason)

    return (not failures, failures)


def _check(field: str, value: Any, predicate: Any) -> tuple[bool, str]:
    # Bare scalar → equality.
    if isinstance(predicate, (str, int, float, bool)) and not isinstance(predicate, bool):
        # bool is a subclass of int in Python; handle separately to keep semantics tight
        if value == predicate:
            return True, ""
        return False, f"{field} = {value!r}, expected {predicate!r}"

    # Bare bool predicate (explicit branch — order matters).
    if isinstance(predicate, bool):
        if value == predicate:
            return True, ""
        return False, f"{field} = {value!r}, expected {predicate!r}"

    # List → membership.
    if isinstance(predicate, list):
        if value in predicate:
            return True, ""
        return False, f"{field} = {value!r}, expected one of {predicate}"

    # Dict → operator predicate.
    if isinstance(predicate, dict):
        if len(predicate) != 1:
            return False, f"{field}: predicate dict must have exactly one operator, got {list(predicate)}"
        op, arg = next(iter(predicate.items()))
        if op not in _KNOWN_OPS:
            return False, f"{field}: unknown operator {op!r} (known: {sorted(_KNOWN_OPS)})"
        return _apply_op(field, value, op, arg)

    return False, f"{field}: unsupported predicate type {type(predicate).__name__}: {predicate!r}"


def _apply_op(field: str, value: Any, op: str, arg: Any) -> tuple[bool, str]:
    if op in ("gte", "gt", "lte", "lt"):
        if value is None:
            return False, f"{field}: cannot compare {op} {arg!r} — payload value is missing"
        try:
            v = float(value)
            a = float(arg)
        except (TypeError, ValueError):
            return False, f"{field}: cannot compare non-numeric {value!r} {op} {arg!r}"
        cmp = {"gte": v >= a, "gt": v > a, "lte": v <= a, "lt": v < a}[op]
        if cmp:
            return True, ""
        return False, f"{field} = {value!r}, expected {op} {arg!r}"

    if op == "between":
        if not (isinstance(arg, list) and len(arg) == 2):
            return False, f"{field}: between expects [low, high], got {arg!r}"
        if value is None:
            return False, f"{field}: cannot range-check — payload value is missing"
        try:
            v = float(value)
            lo, hi = float(arg[0]), float(arg[1])
        except (TypeError, ValueError):
            return False, f"{field}: non-numeric values in between check"
        if lo <= v <= hi:
            return True, ""
        return False, f"{field} = {value!r}, expected between {arg[0]} and {arg[1]}"

    if op == "not_in":
        if not isinstance(arg, list):
            return False, f"{field}: not_in expects a list, got {arg!r}"
        if value not in arg:
            return True, ""
        return False, f"{field} = {value!r}, expected NOT one of {arg}"

    if op == "not":
        if value != arg:
            return True, ""
        return False, f"{field} = {value!r}, expected != {arg!r}"

    if op == "has_any":
        if not isinstance(arg, list):
            return False, f"{field}: has_any expects a list, got {arg!r}"
        if isinstance(value, list) and any(v in arg for v in value):
            return True, ""
        return False, f"{field} = {value!r}, expected at least one of {arg}"

    # Unreachable because _check already filtered.
    return False, f"{field}: unhandled operator {op}"

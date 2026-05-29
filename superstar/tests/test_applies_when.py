"""Tests for the applies_when DSL evaluator.

Pure logic — no Django, no DB.
"""
from __future__ import annotations

import pytest

from superstar.applies_when import applies_to


# ---------------------------------------------------------------------------
# Equality + membership
# ---------------------------------------------------------------------------
def test_equality_passes() -> None:
    ok, why = applies_to({"role": "engineer"}, {"role": "engineer"})
    assert ok and why == []


def test_equality_fails_with_reason() -> None:
    ok, why = applies_to({"role": "engineer"}, {"role": "finance"})
    assert not ok
    assert "role" in why[0] and "engineer" in why[0]


def test_list_membership_passes() -> None:
    ok, _ = applies_to({"role": ["engineer", "ops"]}, {"role": "engineer"})
    assert ok


def test_list_membership_fails() -> None:
    ok, why = applies_to({"role": ["engineer", "ops"]}, {"role": "finance"})
    assert not ok
    assert "expected one of" in why[0]


# ---------------------------------------------------------------------------
# Numeric comparisons
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "op, threshold, value, expected",
    [
        ("gte", 350, 350, True),
        ("gte", 350, 349, False),
        ("gt", 350, 351, True),
        ("gt", 350, 350, False),
        ("lte", 350, 350, True),
        ("lte", 350, 351, False),
        ("lt", 350, 349, True),
        ("lt", 350, 350, False),
    ],
)
def test_numeric_operators(op, threshold, value, expected) -> None:
    ok, _ = applies_to({"width_mm": {op: threshold}}, {"width_mm": value})
    assert ok is expected


def test_numeric_op_with_missing_value_fails() -> None:
    ok, why = applies_to({"width_mm": {"gte": 350}}, {})
    assert not ok
    assert "missing" in why[0]


def test_numeric_op_with_non_numeric_value_fails() -> None:
    ok, why = applies_to({"width_mm": {"gte": 350}}, {"width_mm": "tall"})
    assert not ok
    assert "non-numeric" in why[0]


# ---------------------------------------------------------------------------
# between
# ---------------------------------------------------------------------------
def test_between_inclusive() -> None:
    cond = {"width_mm": {"between": [300, 600]}}
    assert applies_to(cond, {"width_mm": 300})[0]
    assert applies_to(cond, {"width_mm": 450})[0]
    assert applies_to(cond, {"width_mm": 600})[0]
    assert not applies_to(cond, {"width_mm": 299})[0]
    assert not applies_to(cond, {"width_mm": 601})[0]


def test_between_malformed_args() -> None:
    ok, why = applies_to({"width_mm": {"between": [300]}}, {"width_mm": 400})
    assert not ok
    assert "between expects [low, high]" in why[0]


# ---------------------------------------------------------------------------
# not_in / not / has_any
# ---------------------------------------------------------------------------
def test_not_in() -> None:
    cond = {"finish": {"not_in": ["PU", "Membrane"]}}
    assert applies_to(cond, {"finish": "Laminate"})[0]
    assert not applies_to(cond, {"finish": "PU"})[0]


def test_not_equal() -> None:
    cond = {"status": {"not": "closed"}}
    assert applies_to(cond, {"status": "open"})[0]
    assert not applies_to(cond, {"status": "closed"})[0]


def test_has_any() -> None:
    cond = {"reasons": {"has_any": ["civil_obstruction", "config_change"]}}
    assert applies_to(cond, {"reasons": ["civil_obstruction"]})[0]
    assert applies_to(cond, {"reasons": ["config_change", "other"]})[0]
    assert not applies_to(cond, {"reasons": ["other"]})[0]
    assert not applies_to(cond, {"reasons": []})[0]


# ---------------------------------------------------------------------------
# Multi-condition AND semantics
# ---------------------------------------------------------------------------
def test_multiple_conditions_all_must_pass() -> None:
    cond = {
        "request_type": "additional_lock",
        "type_of_shutter": "2-shutter",
        "shutter_finish": {"not_in": ["PU", "Membrane"]},
    }
    payload_pass = {
        "request_type": "additional_lock",
        "type_of_shutter": "2-shutter",
        "shutter_finish": "Laminate",
    }
    payload_fail = {**payload_pass, "shutter_finish": "PU"}

    assert applies_to(cond, payload_pass) == (True, [])

    ok, why = applies_to(cond, payload_fail)
    assert not ok
    assert len(why) == 1  # only the finish check failed


def test_multiple_failures_all_reported() -> None:
    cond = {"a": "x", "b": "y", "c": {"gte": 10}}
    ok, why = applies_to(cond, {"a": "wrong", "b": "y", "c": 5})
    assert not ok
    assert len(why) == 2  # a and c failed; b passed


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_empty_conditions_apply_universally() -> None:
    assert applies_to({}, {"anything": "here"}) == (True, [])
    assert applies_to(None, {}) == (True, [])


def test_unknown_operator_fails_with_reason() -> None:
    ok, why = applies_to({"x": {"matches": "regex"}}, {"x": "y"})
    assert not ok
    assert "unknown operator" in why[0]


def test_predicate_dict_with_multiple_ops_is_error() -> None:
    ok, why = applies_to({"x": {"gte": 1, "lte": 10}}, {"x": 5})
    assert not ok
    assert "exactly one operator" in why[0]


def test_real_nsd_rule_lock_004() -> None:
    """Sanity check against an actual NSD rule shape."""
    cond = {
        "request_type": "additional_lock",
        "type_of_shutter": "2-shutter",
        "shutter_finish": {"not_in": ["PU", "Membrane", "Flutted", "Glazzensa"]},
    }
    # Should apply for 2-shutter Laminate (the case Gemma kept missing).
    ok, _ = applies_to(cond, {
        "request_type": "additional_lock",
        "type_of_shutter": "2-shutter",
        "shutter_finish": "Laminate",
    })
    assert ok

    # Should NOT apply for 2-shutter PU (LOCK-003's territory).
    ok, why = applies_to(cond, {
        "request_type": "additional_lock",
        "type_of_shutter": "2-shutter",
        "shutter_finish": "PU",
    })
    assert not ok
    assert "shutter_finish" in why[0]


def test_real_nsd_rule_airvent_001() -> None:
    """Air vent rejection on small modules."""
    cond = {
        "request_type": "air_vent",
        "module_width_mm": {"lt": 350},
        "module_height_mm": {"lt": 350},
    }
    # Should apply: 250x250 module.
    assert applies_to(cond, {
        "request_type": "air_vent",
        "module_width_mm": 250,
        "module_height_mm": 250,
    })[0]

    # Should NOT apply: 500x600 module.
    ok, _ = applies_to(cond, {
        "request_type": "air_vent",
        "module_width_mm": 500,
        "module_height_mm": 600,
    })
    assert not ok

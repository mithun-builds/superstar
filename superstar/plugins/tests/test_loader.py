"""Tests for the plugin loader — pure parsing, no Django DB required.

Run with: `pytest superstar/plugins/tests/`
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from superstar.plugins import base as plugins_base
from superstar.plugins.loader import PluginSpecError, load_plugins


@pytest.fixture(autouse=True)
def clear_registry():
    """Tests should not see each other's registrations."""
    plugins_base._REGISTRY.clear()
    yield
    plugins_base._REGISTRY.clear()


def _write_yaml(dir_: Path, name: str, body: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text(textwrap.dedent(body).lstrip())
    return p


def test_load_single_plugin_config(tmp_path: Path) -> None:
    """Layout (a): config_dir/plugins/<x>.yaml (the demo layout)."""
    _write_yaml(
        tmp_path / "plugins",
        "demo.access.yaml",
        """
        identifier: demo.access
        display_name: Demo Access
        schema:
          fields:
            - name: role
              type: enum
              label: Role
              required: true
              choices: [engineer, sales]
        workflow:
          stages:
            - name: Review
              approvers: [security]
              mode: any_member
        """,
    )
    loaded = load_plugins(tmp_path)
    assert len(loaded) == 1
    contract = loaded[0]
    assert contract.identifier == "demo.access"
    assert contract.display_name == "Demo Access"
    assert contract.schema.fields[0].name == "role"
    assert contract.schema.fields[0].choices == ("engineer", "sales")
    assert contract.workflow.stages[0].name == "Review"
    # AI policy defaults preserved when not specified.
    assert contract.ai_policy.shadow_mode is True
    assert contract.ai_policy.confidence_threshold == 0.85


def test_load_multi_plugin_config(tmp_path: Path) -> None:
    """Layout (b): config_dir/<subfolder>/plugins/<x>.yaml."""
    _write_yaml(
        tmp_path / "nsd-ai" / "plugins",
        "homelane.nonstandard.yaml",
        """
        identifier: homelane.nonstandard
        display_name: Non-Standard Furniture
        schema:
          fields:
            - name: request_type
              type: enum
              choices: [lock, vent]
        workflow:
          stages:
            - name: Design
              approvers: [design-head]
              mode: any_member
        """,
    )
    _write_yaml(
        tmp_path / "engineering" / "plugins",
        "homelane.engineering.yaml",
        """
        identifier: homelane.engineering
        display_name: Engineering Tickets
        schema:
          fields:
            - name: severity
              type: enum
              choices: [low, high]
        workflow:
          stages:
            - name: Triage
              approvers: [eng-leads]
              mode: any_member
        """,
    )
    loaded = load_plugins(tmp_path)
    ids = sorted(c.identifier for c in loaded)
    assert ids == ["homelane.engineering", "homelane.nonstandard"]


def test_missing_required_key_raises(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "plugins",
        "broken.yaml",
        """
        identifier: broken.thing
        display_name: Broken
        # missing schema and workflow
        """,
    )
    with pytest.raises(PluginSpecError):
        load_plugins(tmp_path)


def test_duplicate_identifier_raises(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "plugins",
        "a.yaml",
        """
        identifier: dup.id
        display_name: A
        schema: { fields: [{ name: x, type: string }] }
        workflow: { stages: [{ name: S, approvers: [r], mode: any_member }] }
        """,
    )
    _write_yaml(
        tmp_path / "plugins",
        "b.yaml",
        """
        identifier: dup.id
        display_name: B
        schema: { fields: [{ name: y, type: string }] }
        workflow: { stages: [{ name: S, approvers: [r], mode: any_member }] }
        """,
    )
    with pytest.raises(ValueError):  # register_plugin raises on dup
        load_plugins(tmp_path)


def test_nonexistent_config_dir_is_warning_not_error(tmp_path: Path) -> None:
    """Missing config dir should warn and return empty, not crash startup."""
    loaded = load_plugins(tmp_path / "does-not-exist")
    assert loaded == []

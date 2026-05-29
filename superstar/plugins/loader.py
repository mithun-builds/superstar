"""Plugin discovery + registration.

At Django startup, walks `SUPERSTAR_CONFIG_DIR/<plugin>/plugins/*.yaml`,
parses each into a PluginContract dataclass, and registers it in the
in-memory registry (`superstar.plugins.base._REGISTRY`).

Discovery is deliberately filesystem-driven, not database-driven. Plugin
specs are config artifacts — they live with the tenant config, not in
SuperStar's database. Changing a plugin means editing the YAML and
restarting (or hitting a reload endpoint, not implemented in v0).

Failures are loud: a malformed YAML, a missing required field, or a
duplicate identifier raises at startup, not at first request.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .base import (
    AIPolicy,
    FieldSpec,
    NotificationSpec,
    PluginContract,
    SchemaSpec,
    StageSpec,
    WorkflowSpec,
    all_plugins,
    register_plugin,
)

logger = logging.getLogger(__name__)


class PluginSpecError(ValueError):
    """Raised when a plugin YAML is malformed or incomplete."""


def load_plugins(config_dir: Path) -> list[PluginContract]:
    """Discover and register every plugin under `config_dir`.

    Layout expected:
        config_dir/
            <plugin-folder>/
                plugins/
                    <plugin>.yaml
                kb/...
                prompts/...

    Returns the list of contracts loaded in this call (the registry is the
    source of truth for the full set across calls).
    """
    config_dir = Path(config_dir)
    if not config_dir.is_dir():
        logger.warning("SUPERSTAR_CONFIG_DIR not found or not a directory: %s", config_dir)
        return []

    loaded: list[PluginContract] = []
    # Two layouts accepted:
    #   (a) config_dir/plugins/*.yaml          (single-plugin config, e.g. the demo)
    #   (b) config_dir/<plugin>/plugins/*.yaml (multi-plugin tenant config)
    yaml_paths = list(config_dir.glob("plugins/*.yaml")) + list(
        config_dir.glob("*/plugins/*.yaml")
    )

    for path in sorted(yaml_paths):
        try:
            contract = _load_yaml(path)
        except PluginSpecError as exc:
            logger.error("Plugin spec invalid at %s: %s", path, exc)
            raise
        register_plugin(contract)
        loaded.append(contract)
        logger.info("Plugin registered: %s (from %s)", contract.identifier, path)

    return loaded


def _load_yaml(path: Path) -> PluginContract:
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise PluginSpecError(f"Top level must be a mapping, got {type(raw).__name__}")

    required = ["identifier", "display_name", "schema", "workflow"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise PluginSpecError(f"Missing required keys: {missing}")

    return PluginContract(
        identifier=str(raw["identifier"]),
        display_name=str(raw["display_name"]),
        schema=_parse_schema(raw["schema"]),
        workflow=_parse_workflow(raw["workflow"]),
        ai_policy=_parse_ai_policy(raw.get("ai_policy", {})),
        notifications=_parse_notifications(raw.get("notifications", {})),
    )


def _parse_schema(raw: Any) -> SchemaSpec:
    if not isinstance(raw, dict) or "fields" not in raw:
        raise PluginSpecError("schema.fields is required")
    fields = []
    for f in raw["fields"]:
        if not isinstance(f, dict) or "name" not in f or "type" not in f:
            raise PluginSpecError(f"schema field missing name/type: {f!r}")
        fields.append(
            FieldSpec(
                name=str(f["name"]),
                type=str(f["type"]),
                label=str(f.get("label", f["name"])),
                required=bool(f.get("required", True)),
                choices=tuple(str(c) for c in f.get("choices", [])),
                help_text=str(f.get("help_text", "")),
            )
        )
    return SchemaSpec(fields=tuple(fields))


def _parse_workflow(raw: Any) -> WorkflowSpec:
    if not isinstance(raw, dict) or "stages" not in raw:
        raise PluginSpecError("workflow.stages is required")
    stages = []
    for s in raw["stages"]:
        if not isinstance(s, dict):
            raise PluginSpecError(f"workflow stage must be a mapping: {s!r}")
        stages.append(
            StageSpec(
                name=str(s["name"]),
                approvers=tuple(str(a) for a in s.get("approvers", [])),
                mode=str(s.get("mode", "any_member")),
                sla_hours=s.get("sla_hours"),
            )
        )
    return WorkflowSpec(
        stages=tuple(stages),
        sequential=bool(raw.get("sequential", True)),
    )


def _parse_ai_policy(raw: dict) -> AIPolicy:
    return AIPolicy(
        enabled=bool(raw.get("enabled", True)),
        kb_path=str(raw.get("kb_path", "kb/")),
        system_prompt_path=str(raw.get("system_prompt_path", "prompts/decisioning.md")),
        confidence_threshold=float(raw.get("confidence_threshold", 0.85)),
        require_citation=bool(raw.get("require_citation", True)),
        shadow_mode=bool(raw.get("shadow_mode", True)),
    )


def _parse_notifications(raw: dict) -> NotificationSpec:
    def t(key: str) -> tuple[str, ...]:
        return tuple(str(x) for x in raw.get(key, []))

    return NotificationSpec(
        on_create_notify=t("on_create_notify"),
        on_decision_notify=t("on_decision_notify"),
        on_escalation_notify=t("on_escalation_notify"),
        on_close_notify=t("on_close_notify"),
    )


def get_all_loaded() -> dict:
    """Convenience accessor for diagnostics / admin views."""
    return all_plugins()

"""Plugin contract for ticket types.

A ticket type plugin declares:
- `schema`         — form fields the requester fills in (typed, validated)
- `workflow`       — stages and approval modes
- `ai_policy`      — KB pointer, prompt, confidence threshold, citation rules
- `notifications`  — what to send, to whom, when
- (optional) Python hooks for imperative logic

Plugins are addressed by a dotted identifier scoped to the tenant:
  `<tenant>.<usecase>` — e.g. `homelane.nonstandard` for NSD.AI.

Declarative plugins live as YAML files in `SUPERSTAR_CONFIG_DIR/plugins/`.
Imperative plugins register at startup via setuptools entry points:

    [project.entry-points."superstar.plugins"]
    homelane.nonstandard = "my_pkg.plugin:NonStandardPlugin"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Spec types — what a plugin declares
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "string" | "int" | "enum" | "bool" | "text"
    label: str
    required: bool = True
    choices: tuple[str, ...] = ()
    help_text: str = ""


@dataclass(frozen=True)
class SchemaSpec:
    """The form requesters fill in for this ticket type."""
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class StageSpec:
    name: str
    approvers: tuple[str, ...]  # role names or group identifiers
    mode: str  # "any_member" | "unanimous_team" | "majority" | "specific_user"
    sla_hours: int | None = None


@dataclass(frozen=True)
class WorkflowSpec:
    stages: tuple[StageSpec, ...]
    sequential: bool = True


@dataclass(frozen=True)
class AIPolicy:
    """How decisioning treats this ticket type."""
    enabled: bool = True
    kb_path: str = "kb/"  # relative to tenant config dir
    system_prompt_path: str = "prompts/decisioning.md"
    confidence_threshold: float = 0.85
    require_citation: bool = True
    shadow_mode: bool = True


@dataclass(frozen=True)
class NotificationSpec:
    on_create_notify: tuple[str, ...] = ()
    on_decision_notify: tuple[str, ...] = ()
    on_escalation_notify: tuple[str, ...] = ()
    on_close_notify: tuple[str, ...] = ()


@dataclass(frozen=True)
class PluginContract:
    """The full declarative spec for a ticket type."""
    identifier: str          # e.g. "homelane.nonstandard"
    display_name: str
    schema: SchemaSpec
    workflow: WorkflowSpec
    ai_policy: AIPolicy = field(default_factory=AIPolicy)
    notifications: NotificationSpec = field(default_factory=NotificationSpec)


# ---------------------------------------------------------------------------
# Imperative plugin protocol — optional hooks
# ---------------------------------------------------------------------------
class TicketTypePlugin(Protocol):
    """Optional Python hooks. Implement only those you need.

    The contract (declarative spec) is required; hooks are bonus."""

    contract: PluginContract

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Return validation errors (empty list = valid). Optional."""
        ...

    def post_decide(self, *, ticket_id: int, decision: Any) -> None:
        """Called after the decisioning service emits a decision.
        Use for custom downstream integrations. Optional."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, PluginContract | TicketTypePlugin] = {}


def register_plugin(plugin: PluginContract | TicketTypePlugin) -> None:
    """Register a plugin. Called at startup by the contract loader and by
    setuptools entry-point discovery."""
    identifier = plugin.contract.identifier if hasattr(plugin, "contract") else plugin.identifier
    if identifier in _REGISTRY:
        raise ValueError(f"Plugin already registered: {identifier}")
    _REGISTRY[identifier] = plugin


def get_plugin(identifier: str) -> PluginContract | TicketTypePlugin:
    if identifier not in _REGISTRY:
        raise KeyError(f"No plugin registered for ticket type: {identifier}")
    return _REGISTRY[identifier]


def all_plugins() -> dict[str, PluginContract | TicketTypePlugin]:
    return dict(_REGISTRY)

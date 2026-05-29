"""Plugin system — ticket types as plugins.

Two ways to register:

1. **Declarative (JSONB spec)** — preferred for most cases. A YAML/JSON file
   in the tenant's config dir declares the schema, workflow, AI policy, and
   notification rules. No code. Admin-editable.

2. **Imperative (Python entry point)** — for ticket types that need custom
   logic (custom validation, custom decision post-processing, integrations
   with internal systems). Register via the `superstar.plugins` entry point
   group.

Most ticket types should be declarative. Use imperative only when you can
articulate the specific code that can't be expressed as config.
"""
from .base import (
    AIPolicy,
    NotificationSpec,
    PluginContract,
    SchemaSpec,
    TicketTypePlugin,
    WorkflowSpec,
    get_plugin,
    register_plugin,
)

__all__ = [
    "TicketTypePlugin",
    "PluginContract",
    "SchemaSpec",
    "WorkflowSpec",
    "AIPolicy",
    "NotificationSpec",
    "register_plugin",
    "get_plugin",
]

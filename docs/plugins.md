# Plugins — ticket types

A plugin defines one ticket type. SuperStar's core ships with no built-in
ticket types; every type a deployment uses is a plugin loaded from the
tenant config directory.

Two registration paths:

| Style       | Where it lives                                       | When to use                                          |
|-------------|------------------------------------------------------|------------------------------------------------------|
| Declarative | YAML in `SUPERSTAR_CONFIG_DIR/<plugin>/plugins/*.yaml` | Schema + workflow + AI policy + notifications        |
| Imperative  | Python package, registered via entry point            | Custom validation, downstream integrations, post-decide hooks |

Most plugins are declarative-only. Use imperative when you have specific
Python logic that can't be expressed as config.

## Declarative spec

See `superstar/plugins/base.py` for the dataclass definitions. A plugin YAML
maps 1:1 to `PluginContract`:

```yaml
identifier: <tenant>.<usecase>           # e.g. homelane.nonstandard
display_name: "Human-readable name"

schema:
  fields:
    - name: <field>
      type: string | int | enum | bool | text
      label: "Form label"
      required: true | false
      choices: [...]                     # only for enum
      help_text: "Optional helper text"

workflow:
  sequential: true | false
  stages:
    - name: "Stage 1"
      approvers: [<role-or-group>]
      mode: any_member | unanimous_team | majority | specific_user
      sla_hours: 24

ai_policy:
  enabled: true
  kb_path: kb/
  system_prompt_path: prompts/decisioning.md
  confidence_threshold: 0.85
  require_citation: true
  shadow_mode: true

notifications:
  on_create_notify: [...]
  on_decision_notify: [...]
  on_escalation_notify: [...]
  on_close_notify: [...]
```

## Imperative hooks

For Python-side logic, register via setuptools entry point:

```toml
[project.entry-points."superstar.plugins"]
homelane.nonstandard = "homelane_plugins.nsd:NSDPlugin"
```

```python
# homelane_plugins/nsd.py
from superstar.plugins import PluginContract, TicketTypePlugin

class NSDPlugin(TicketTypePlugin):
    contract = PluginContract(...)

    def validate(self, payload):
        errors = []
        if payload["module_width_mm"] > 1200:
            errors.append("Module width above 1200mm needs custom carcass approval first.")
        return errors

    def post_decide(self, *, ticket_id, decision):
        # e.g. push the decision into Sc-Pro via its API.
        ...
```

## Loading order

At Django startup:

1. Discover declarative plugins by walking `SUPERSTAR_CONFIG_DIR/*/plugins/*.yaml`.
2. Discover imperative plugins via the `superstar.plugins` entry point group.
3. Register both into the in-memory registry (`superstar.plugins.register_plugin`).
4. Validate every contract — duplicate identifiers, missing prompt files, or
   missing KB paths fail loudly at startup, not at first request.

## Naming convention

Plugin identifiers use a dotted `<tenant>.<usecase>` form. Tenant is usually
the organization the plugin originated with; usecase is short and stable.

Examples:
- `homelane.nonstandard` — HomeLane's non-standard furniture (NSD.AI)
- `homelane.engineering` — future internal engineering tickets
- `itaccess.access-request` — the OSS demo

Identifiers are global within a SuperStar deployment. Tenants don't get to
collide on identifier — they get isolated databases instead.

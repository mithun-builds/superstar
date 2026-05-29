# Ticket types — runtime configuration

Each tenant org defines its own ticket types through the SuperStar admin UI.
There are no ticket types in code — the platform itself is generic, and every
ticket type is a row in `apps_tickets_tickettype` scoped to a single org.

If you're looking for "how do I add a ticket type for HomeLane's
non-standard furniture flow", you don't write code. You sign in to a
running SuperStar deployment as a HomeLane org admin and create one via
**Admin → Ticket types → New**.

## The data model

| Table | What it holds |
|---|---|
| `tickets_tickettype` | Display name, identifier, AI policy (enabled / threshold / shadow / system prompt), sequential workflow flag, notifications config |
| `tickets_tickettypefield` | One row per form field — name, type, required, choices, help text, order |
| `tickets_workflowstage` | One row per approval stage — name, approvers (string list), mode, SLA |
| `kb_rulechunk` | The KB rules for AI decisioning — body, frontmatter (`applies_when`, decision, price, post-actions), embedding |

All four tables are org-scoped via RLS policies.

## Lifecycle

```
Org admin signs in
    │
    ▼
Admin → Ticket types → New
    │
    ▼
Set display name + identifier (e.g. "homelane.nonstandard")
Define schema fields  (form for the requester)
Define workflow stages (approval chain on escalation)
Configure AI policy   (enable + threshold + shadow + prompt)
Add KB rules          (each with applies_when conditions)
    │
    ▼
Org's requesters can now submit tickets of this type via /o/<slug>/new
```

## Field types

Configured per-field on a TicketType:

| `field_type` | Frontend rendering |
|---|---|
| `string` | `<input type="text">` |
| `int` | `<input type="number">` |
| `bool` | `<input type="checkbox">` |
| `text` | `<textarea>` |
| `enum` | `<select>` populated from `choices` |

## Workflow stage modes

| `mode` | Behavior |
|---|---|
| `any_member` | First approver in `approvers` to act decides the stage (v0 default) |
| `unanimous_team` | All members must approve (Phase 2 — needs Team model) |
| `majority` | More than half must approve (Phase 2) |
| `specific_user` | Only the named user can decide (Phase 2) |

In a sequential workflow (`TicketType.sequential = True`), stages must be
decided in `order`. The decisioning service materializes them on escalation
and the API enforces "current stage only" via `decide_stage()`.

## Rule shape (per `kb_rulechunk` row)

The frontmatter editor in the admin UI lets you set:

```yaml
rule_id: ABC-001                # stable, unique within ticket_type
title: Human-readable title
body: |
  Markdown body explaining the rule, its conditions, the decision
  it produces. This is what gets embedded with BGE-M3 and shown
  to the LLM at decision time.
applies_when:                   # the DSL — see docs/applies_when.md
  request_type: foo
  quantity: {gte: 10}
  finish: {not_in: [PU, Membrane]}
decision: approve | reject | escalate
price_delta: 0
post_actions:
  - "Manual selection in Sc-Pro"
```

`applies_when` is enforced at decision time by the **applies_when verifier**
— see `superstar/applies_when.py`. The model can cite a rule, but if the
cited rule's conditions don't match the request payload, the decisioning
service forces escalation.

## Why not YAML files

Earlier iterations of SuperStar loaded ticket types from
`SUPERSTAR_CONFIG_DIR/plugins/*.yaml` at startup. That was wrong for a
SaaS-shaped product:

- Tenants couldn't iterate without filesystem access to the server
- Configuration drifted between environments
- Customer data lived in a separate Git repo, which created the "is it
  in superstar or superstar-config-X" confusion every time
- No audit trail for who changed what

DB-native config solves all four. The CLI command
`python manage.py create_tenant` only creates the empty Org — everything
else happens in-product.

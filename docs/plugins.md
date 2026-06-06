# Ticket types — runtime configuration

Each tenant org defines its own ticket types through the Superstar admin UI.
There are no ticket types in code — the platform itself is generic, and every
ticket type is a row in `apps_tickets_tickettype` scoped to a single org.

If you're looking for "how do I add a ticket type for HomeLane's
non-standard furniture flow", you don't write code. You sign in to a
running Superstar deployment as a HomeLane org admin and create one via
**Admin → Ticket types → New**.

## The data model

| Table | What it holds |
|---|---|
| `tickets_tickettype` | Display name, identifier, AI policy (enabled / threshold / shadow / system prompt), sequential workflow flag, notifications config |
| `tickets_tickettypefield` | One row per form field — name, type, required, choices, help text, order, plus `show_if` / `choices_if` for conditional rendering |
| `tickets_workflowstage` | One row per approval stage — name, approvers (list of team slugs), mode, SLA |
| `tickets_approvalstage` | Per-ticket materialization of a workflow stage — status, decided_by, note, snapshot of approvers at materialization time |
| `tickets_stagevote` | One row per individual approver vote — vote, note, voter, timestamp |
| `tenants_team` + `tenants_teammembership` | Approver teams + their members |
| `kb_rulechunk` | The KB rules for AI decisioning — body, frontmatter (`applies_when`, decision, price, post-actions), embedding |

All tables are org-scoped via RLS policies.

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

A stage's `approvers` field is a list of **team slugs**. Each team has a set
of members. The stage's `mode` determines how votes from those members combine
into a stage decision.

| `mode` | Behavior |
|---|---|
| `any_member` | First member of any approver team to vote decides the stage. Tally hidden in the UI (a tally that maxes at 1 isn't informative). |
| `unanimous_team` | Every member of every approver team must approve. One reject collapses the stage. |
| `majority` | More than half of all members must approve. `floor(N/2) + 1` is the threshold; ditto for rejects. |
| `specific_user` | The first listed team must have exactly one member; only that user can vote. |

In a sequential workflow (`TicketType.sequential = True`), stages must be
decided in `order`. The decisioning service materializes them on escalation
and the API enforces "current stage only" via `decide_stage()`.

### How votes are recorded

Every approver decision writes a `StageVote` row (vote=`approved`/`rejected`,
note, voter, timestamp). The vote tally on the API response derives from
these rows — no separate state. This makes it cheap to add new vote modes
(or audit "who voted what when") later without schema churn.

### Authorization

The backend gate (`apps.tickets.approval.can_decide_stage`) decides who can
vote on a stage:

- Org `owner`, `admin`, or platform `superuser` → bypass (escape hatch)
- Otherwise: user must be a member of one of the stage's approver teams,
  or (for `specific_user`) be the named user

The frontend doesn't try to gate the buttons up-front — it surfaces the
backend's 403 if the user lacks permission. This keeps the source of truth
single.

## Approver teams

Teams are org-scoped (RLS-isolated) and have:

- `slug` — referenced from `WorkflowStage.approvers`
- `name`, `description`
- `memberships` — many-to-many to users via `TeamMembership` rows

Managed in the admin UI under **Admin → Teams**. A team can be empty (no
members) — useful for staging up a workflow before the people exist.

## Conditional form fields — show_if + choices_if

Two optional fields on `TicketTypeField` let the requester form react to
other selections without server round-trips.

### `show_if`

Same shape as a rule's `applies_when`: a condition map evaluated against
the current form state. When the conditions don't match, the field is
hidden in the UI **and** dropped from the saved payload (so stale values
don't leak through).

```yaml
# `shutter_finish` is only required when request_type is one of lock/vent
show_if:
  request_type: [additional_lock, air_vent]
```

Validation honors this — a hidden required field doesn't 400 the request.

### `choices_if`

Cascading dropdowns: the choices an enum offers depend on other field
values. A list of `{conditions, choices}` rules evaluated top-to-bottom;
the first matching rule's choices win. No match → fall back to the static
`choices` list.

```yaml
choices_if:
  - conditions: {room_type: kitchen}
    choices: [base_unit, wall_unit, sink_unit, hob_unit]
  - conditions: {room_type: wardrobe}
    choices: [base_unit, wall_unit, dresser]
```

Backend payload validation honors `choices_if` too — submitting a kitchen-
only choice on a wardrobe request 400s.

### Why reuse `applies_when` for both

Admins already learn one condition syntax for rules. Reusing the same DSL
for form behavior means they only learn it once. The frontend ships a
TypeScript port (`frontend/src/lib/appliesWhen.ts`) of the Python evaluator
so form behavior matches server validation exactly.

See [docs/applies_when.md](applies_when.md) for the full DSL.

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

Earlier iterations of Superstar loaded ticket types from
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

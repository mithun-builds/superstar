// Admin → Ticket type edit screen.
//
// Three editor sections on one page:
//   1. Identity + AI policy + system prompt (PATCH /api/admin/ticket-types/<id>/)
//   2. Schema fields (CRUD on /fields/)
//   3. Workflow stages (CRUD on /stages/)
//
// Each section saves independently. Keeping them split avoids a giant
// transactional update + lets the admin iterate on one piece without
// risking the others.

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import AppliesWhenBuilder from "../../components/AppliesWhenBuilder";
import type {
  AdminTeam,
  AdminTicketType,
  AdminTicketTypeField,
  AdminWorkflowStage,
  Paginated,
} from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function TicketTypeEdit() {
  const orgSlug = useOrgRequired();
  const { ticketTypeId } = useParams<{ ticketTypeId: string }>();
  const path = `/api/admin/ticket-types/${ticketTypeId}/`;
  const ttState = useApi<AdminTicketType>(path, { orgSlug });

  if (ttState.loading) return <p>Loading…</p>;
  if (ttState.error) return <p className="error">{ttState.error.message}</p>;
  if (!ttState.data) return null;

  return (
    <section className="page-admin-edit">
      <header className="page-header">
        <div>
          <h1>{ttState.data.display_name}</h1>
          <p className="muted">
            <code>{ttState.data.identifier}</code> · {ttState.data.is_active ? "active" : "inactive"}
          </p>
        </div>
        <Link to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`} className="btn">
          KB rules →
        </Link>
      </header>

      <IdentityAndAiPolicy
        ticketType={ttState.data}
        orgSlug={orgSlug}
        onSaved={() => ttState.reload()}
      />
      <FieldsEditor
        ticketTypeId={ticketTypeId!}
        orgSlug={orgSlug}
        fields={ttState.data.fields}
        onChanged={() => ttState.reload()}
      />
      <StagesEditor
        ticketTypeId={ticketTypeId!}
        orgSlug={orgSlug}
        stages={ttState.data.workflow_stages}
        onChanged={() => ttState.reload()}
      />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 1: identity + AI policy + system prompt
// ---------------------------------------------------------------------------
function IdentityAndAiPolicy({
  ticketType,
  orgSlug,
  onSaved,
}: {
  ticketType: AdminTicketType;
  orgSlug: string;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    display_name: ticketType.display_name,
    description: ticketType.description,
    is_active: ticketType.is_active,
    sequential: ticketType.sequential,
    ai_enabled: ticketType.ai_enabled,
    confidence_threshold: ticketType.confidence_threshold,
    require_citation: ticketType.require_citation,
    shadow_mode: ticketType.shadow_mode,
    system_prompt: ticketType.system_prompt,
  });

  const save = useMutation(async () => {
    await api(`/api/admin/ticket-types/${ticketType.id}/`, {
      method: "PATCH",
      orgSlug,
      body: form,
    });
    onSaved();
  });

  return (
    <section className="card">
      <h3>Identity &amp; AI policy</h3>

      <div className="form-field">
        <label>Display name</label>
        <input
          type="text"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
      </div>
      <div className="form-field">
        <label>Description</label>
        <textarea
          value={form.description}
          rows={2}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>

      <div className="checkbox-row">
        <label>
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />{" "}
          Active
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.sequential}
            onChange={(e) => setForm({ ...form, sequential: e.target.checked })}
          />{" "}
          Sequential workflow
        </label>
      </div>

      <hr />
      <h4>AI decisioning</h4>

      <div className="checkbox-row">
        <label>
          <input
            type="checkbox"
            checked={form.ai_enabled}
            onChange={(e) => setForm({ ...form, ai_enabled: e.target.checked })}
          />{" "}
          AI enabled
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.require_citation}
            onChange={(e) => setForm({ ...form, require_citation: e.target.checked })}
          />{" "}
          Require citation
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.shadow_mode}
            onChange={(e) => setForm({ ...form, shadow_mode: e.target.checked })}
          />{" "}
          Shadow mode <small className="muted">(log only, don't apply)</small>
        </label>
      </div>

      <div className="form-field">
        <label>Confidence threshold (0 – 1)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={form.confidence_threshold}
          onChange={(e) =>
            setForm({ ...form, confidence_threshold: Number(e.target.value) })
          }
        />
      </div>
      <div className="form-field">
        <label>System prompt</label>
        <textarea
          rows={12}
          value={form.system_prompt}
          onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          placeholder="You are SuperStar's decisioning engine for ..."
        />
        <small className="help">
          Prepended to every LLM call. Define the output JSON schema and the
          grounding rules here.
        </small>
      </div>

      <div className="btn-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "Saving…" : "Save identity & AI policy"}
        </button>
        {save.error && <span className="error">{save.error.message}</span>}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 2: schema fields editor
// ---------------------------------------------------------------------------
function FieldsEditor({
  ticketTypeId,
  orgSlug,
  fields,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  fields: AdminTicketTypeField[];
  onChanged: () => void;
}) {
  return (
    <section className="card">
      <h3>Schema fields</h3>
      <p className="muted">
        Each row is a form input requesters fill in when submitting a ticket of
        this type. Field names become JSON keys on the ticket payload.
      </p>

      {fields.length === 0 && <p className="muted">No fields yet.</p>}

      {(() => {
        const siblingNames = fields.map((f) => f.name).filter(Boolean);
        return (
          <>
            {fields.map((f) => (
              <FieldRow
                key={f.id}
                ticketTypeId={ticketTypeId}
                orgSlug={orgSlug}
                field={f}
                siblingNames={siblingNames.filter((n) => n !== f.name)}
                onChanged={onChanged}
              />
            ))}
            <FieldRow
              ticketTypeId={ticketTypeId}
              orgSlug={orgSlug}
              field={null}
              siblingNames={siblingNames}
              onChanged={onChanged}
            />
          </>
        );
      })()}
    </section>
  );
}

function FieldRow({
  ticketTypeId,
  orgSlug,
  field,
  siblingNames,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  field: AdminTicketTypeField | null;
  siblingNames: string[];
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Partial<AdminTicketTypeField>>(
    field ?? {
      order: 0,
      name: "",
      field_type: "string",
      label: "",
      required: true,
      choices: [],
      help_text: "",
      show_if: null,
      choices_if: [],
    },
  );
  const [showConditions, setShowConditions] = useState(
    !!(field && ((field.show_if && Object.keys(field.show_if).length > 0) || (field.choices_if && field.choices_if.length > 0))),
  );

  const isNew = field === null;

  const save = useMutation(async () => {
    if (isNew) {
      await api(`/api/admin/ticket-types/${ticketTypeId}/fields/`, {
        method: "POST",
        orgSlug,
        body: draft,
      });
      setDraft({
        order: 0,
        name: "",
        field_type: "string",
        label: "",
        required: true,
        choices: [],
        help_text: "",
        show_if: null,
        choices_if: [],
      });
    } else {
      await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
        method: "PATCH",
        orgSlug,
        body: draft,
      });
    }
    onChanged();
  });

  const del = useMutation(async () => {
    if (!field) return;
    await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
      method: "DELETE",
      orgSlug,
    });
    onChanged();
  });

  return (
    <div className={`row-edit ${isNew ? "row-new" : ""}`}>
      <div className="row-inputs">
        <input
          type="number"
          className="input-tiny"
          value={draft.order ?? 0}
          onChange={(e) => setDraft({ ...draft, order: Number(e.target.value) })}
          placeholder="order"
        />
        <input
          type="text"
          className="input-narrow"
          value={draft.name ?? ""}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="field name (e.g. role)"
        />
        <select
          value={draft.field_type ?? "string"}
          onChange={(e) =>
            setDraft({ ...draft, field_type: e.target.value as AdminTicketTypeField["field_type"] })
          }
        >
          <option value="string">string</option>
          <option value="int">int</option>
          <option value="bool">bool</option>
          <option value="text">text</option>
          <option value="enum">enum</option>
        </select>
        <input
          type="text"
          value={draft.label ?? ""}
          onChange={(e) => setDraft({ ...draft, label: e.target.value })}
          placeholder="display label"
        />
        <label className="checkbox-inline">
          <input
            type="checkbox"
            checked={draft.required ?? true}
            onChange={(e) => setDraft({ ...draft, required: e.target.checked })}
          />{" "}
          required
        </label>
      </div>

      {draft.field_type === "enum" && (
        <input
          type="text"
          value={(draft.choices ?? []).join(", ")}
          onChange={(e) =>
            setDraft({
              ...draft,
              choices: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
            })
          }
          placeholder="default choices, comma-separated"
        />
      )}

      <div className="conditions-row">
        <button
          type="button"
          className="link-btn"
          onClick={() => setShowConditions((v) => !v)}
        >
          {showConditions ? "▾" : "▸"} Conditions
          {(draft.show_if && Object.keys(draft.show_if).length > 0) || (draft.choices_if && draft.choices_if.length > 0)
            ? <span className="chip chip-active inline-chip">active</span>
            : null}
        </button>
      </div>

      {showConditions && (
        <div className="conditions-panel">
          <div className="form-field">
            <label>Show only when…</label>
            <AppliesWhenBuilder
              value={(draft.show_if as Record<string, unknown>) || {}}
              onChange={(v) =>
                setDraft({ ...draft, show_if: Object.keys(v).length === 0 ? null : v })
              }
              knownFieldNames={siblingNames}
            />
            <small className="help">
              Empty = always show. Otherwise this field renders only when ALL
              conditions match the request payload.
            </small>
          </div>

          {draft.field_type === "enum" && (
            <ChoicesIfEditor
              value={draft.choices_if ?? []}
              onChange={(v) => setDraft({ ...draft, choices_if: v })}
              siblingNames={siblingNames}
            />
          )}
        </div>
      )}

      <div className="btn-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading || !draft.name || !draft.label}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "…" : isNew ? "Add field" : "Save"}
        </button>
        {!isNew && (
          <button
            type="button"
            className="btn btn-reject"
            disabled={del.loading}
            onClick={() => del.call(undefined)}
          >
            Delete
          </button>
        )}
      </div>
      {save.error && <p className="error">{save.error.message}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 3: workflow stages editor
// ---------------------------------------------------------------------------
function StagesEditor({
  ticketTypeId,
  orgSlug,
  stages,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  stages: AdminWorkflowStage[];
  onChanged: () => void;
}) {
  // Fetch the org's teams so each StageRow can render a multi-select of
  // existing team slugs instead of asking admins to type comma-separated
  // strings that have to exactly match team slugs to actually authorize anyone.
  const teamsState = useApi<Paginated<AdminTeam> | AdminTeam[]>(
    "/api/admin/teams/",
    { orgSlug },
  );
  const teamSlugs = (() => {
    if (!teamsState.data) return [];
    const arr = Array.isArray(teamsState.data) ? teamsState.data : teamsState.data.results;
    return arr.map((t) => t.slug);
  })();

  return (
    <section className="card">
      <h3>Workflow stages</h3>
      <p className="muted">
        On escalation, SuperStar materializes a stage per row, in order. The
        ticket advances when the active stage is approved by a member of one of
        its approver teams.
      </p>

      {stages.length === 0 && <p className="muted">No stages yet.</p>}

      {stages.map((s) => (
        <StageRow
          key={s.id}
          ticketTypeId={ticketTypeId}
          orgSlug={orgSlug}
          stage={s}
          knownTeamSlugs={teamSlugs}
          onChanged={onChanged}
        />
      ))}

      <StageRow
        ticketTypeId={ticketTypeId}
        orgSlug={orgSlug}
        stage={null}
        knownTeamSlugs={teamSlugs}
        onChanged={onChanged}
      />

      {teamSlugs.length === 0 && (
        <p className="muted small">
          No teams configured yet. <a href={`/o/${orgSlug}/admin/teams`}>Create one</a> first,
          then come back to add it as an approver group.
        </p>
      )}
    </section>
  );
}

function StageRow({
  ticketTypeId,
  orgSlug,
  stage,
  knownTeamSlugs,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  stage: AdminWorkflowStage | null;
  knownTeamSlugs: string[];
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Partial<AdminWorkflowStage>>(
    stage ?? {
      order: 0,
      name: "",
      approvers: [],
      mode: "any_member",
      sla_hours: null,
    },
  );
  const isNew = stage === null;

  const save = useMutation(async () => {
    if (isNew) {
      await api(`/api/admin/ticket-types/${ticketTypeId}/stages/`, {
        method: "POST",
        orgSlug,
        body: draft,
      });
      setDraft({
        order: 0,
        name: "",
        approvers: [],
        mode: "any_member",
        sla_hours: null,
      });
    } else {
      await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
        method: "PATCH",
        orgSlug,
        body: draft,
      });
    }
    onChanged();
  });

  const del = useMutation(async () => {
    if (!stage) return;
    await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
      method: "DELETE",
      orgSlug,
    });
    onChanged();
  });

  return (
    <div className={`row-edit ${isNew ? "row-new" : ""}`}>
      <div className="row-inputs">
        <input
          type="number"
          className="input-tiny"
          value={draft.order ?? 0}
          onChange={(e) => setDraft({ ...draft, order: Number(e.target.value) })}
          placeholder="order"
        />
        <input
          type="text"
          value={draft.name ?? ""}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="stage name (e.g. Security review)"
        />
        <select
          value={draft.mode ?? "any_member"}
          onChange={(e) =>
            setDraft({ ...draft, mode: e.target.value as AdminWorkflowStage["mode"] })
          }
        >
          <option value="any_member">any member</option>
          <option value="unanimous_team">unanimous team</option>
          <option value="majority">majority</option>
          <option value="specific_user">specific user</option>
        </select>
        <input
          type="number"
          className="input-tiny"
          value={draft.sla_hours ?? ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              sla_hours: e.target.value === "" ? null : Number(e.target.value),
            })
          }
          placeholder="SLA hrs"
        />
      </div>

      <ApproverTeamSelector
        selected={draft.approvers ?? []}
        knownTeamSlugs={knownTeamSlugs}
        onChange={(approvers) => setDraft({ ...draft, approvers })}
      />

      <div className="btn-row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading || !draft.name}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "…" : isNew ? "Add stage" : "Save"}
        </button>
        {!isNew && (
          <button
            type="button"
            className="btn btn-reject"
            disabled={del.loading}
            onClick={() => del.call(undefined)}
          >
            Delete
          </button>
        )}
      </div>
      {save.error && <p className="error">{save.error.message}</p>}
    </div>
  );
}


/** Multi-select of team slugs in this org + a fallback for stages that
 *  reference team slugs no longer present (preserved as "(stale)" chips so
 *  we don't silently erase them on save). */
function ApproverTeamSelector({
  selected,
  knownTeamSlugs,
  onChange,
}: {
  selected: string[];
  knownTeamSlugs: string[];
  onChange: (next: string[]) => void;
}) {
  const stale = selected.filter((s) => !knownTeamSlugs.includes(s));

  const toggle = (slug: string) => {
    if (selected.includes(slug)) {
      onChange(selected.filter((s) => s !== slug));
    } else {
      onChange([...selected, slug]);
    }
  };

  return (
    <div className="approver-team-selector">
      <div className="chip-row">
        {knownTeamSlugs.map((slug) => {
          const on = selected.includes(slug);
          return (
            <button
              type="button"
              key={slug}
              className={`chip ${on ? "chip-active" : ""}`}
              onClick={() => toggle(slug)}
            >
              {on ? "✓ " : ""}{slug}
            </button>
          );
        })}
        {stale.map((slug) => (
          <button
            type="button"
            key={`stale-${slug}`}
            className="chip chip-stale"
            title="No team with this slug exists in this org. Click to remove."
            onClick={() => onChange(selected.filter((s) => s !== slug))}
          >
            {slug} <span className="muted">(stale)</span>
          </button>
        ))}
      </div>
      {knownTeamSlugs.length === 0 && (
        <small className="muted">
          No teams in this org yet. Create one in Admin → Teams.
        </small>
      )}
    </div>
  );
}


/** Editor for the choices_if rule list — cascading dropdowns.
 *  Each rule has a conditions block (uses AppliesWhenBuilder) + a list of
 *  choices that should be active when those conditions match. First rule
 *  that matches wins; if none, the field's static `choices` is used. */
function ChoicesIfEditor({
  value,
  onChange,
  siblingNames,
}: {
  value: Array<{ conditions: Record<string, unknown>; choices: string[] }>;
  onChange: (v: Array<{ conditions: Record<string, unknown>; choices: string[] }>) => void;
  siblingNames: string[];
}) {
  const setRule = (i: number, patch: Partial<{ conditions: Record<string, unknown>; choices: string[] }>) =>
    onChange(value.map((r, j) => (i === j ? { ...r, ...patch } : r)));
  const addRule = () => onChange([...value, { conditions: {}, choices: [] }]);
  const removeRule = (i: number) => onChange(value.filter((_, j) => i !== j));

  return (
    <div className="form-field">
      <label>Choices change when…</label>
      <small className="help">
        Each rule overrides the default <code>choices</code> when its conditions match.
        First match wins. If no rule matches, default choices are used.
      </small>
      {value.length === 0 && (
        <p className="muted small">
          No rules — default choices apply to all requests.
        </p>
      )}
      {value.map((rule, i) => (
        <div key={i} className="choices-if-rule">
          <div className="cir-header">
            <strong>Rule {i + 1}</strong>
            <button
              type="button"
              className="btn-icon"
              onClick={() => removeRule(i)}
              title="Remove rule"
            >
              ✕
            </button>
          </div>
          <small className="help">When…</small>
          <AppliesWhenBuilder
            value={rule.conditions}
            onChange={(conditions) => setRule(i, { conditions })}
            knownFieldNames={siblingNames}
          />
          <div style={{ marginTop: "0.5rem" }}>
            <label className="cir-label">…then choices are:</label>
            <input
              type="text"
              value={rule.choices.join(", ")}
              onChange={(e) =>
                setRule(i, {
                  choices: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                })
              }
              placeholder="comma-separated values"
              style={{ width: "100%" }}
            />
          </div>
        </div>
      ))}
      <button type="button" className="btn" onClick={addRule}>
        + Add rule
      </button>
    </div>
  );
}

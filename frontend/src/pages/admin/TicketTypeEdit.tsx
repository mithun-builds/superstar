// Admin → Ticket type edit screen.
//
// Layout choices (the "minimal design" pass):
//   - Identity is a one-line editable header. Identifier shown as immutable
//     mono text beside the name.
//   - Active + AI-enabled live as pill toggles in the header — no big
//     "AI policy" card up front.
//   - Sensitive / power-user AI controls (system prompt, confidence threshold,
//     require_citation, shadow_mode) live behind a single "Advanced" disclosure.
//   - Fields + Stages are each rendered as a collapsible list. Each row is a
//     one-line summary; click to expand into the full editor. Only one row is
//     expanded at a time so the page never balloons.
//   - Add-row affordance is a quiet dashed "+ Add field" / "+ Add stage" at the
//     bottom of each list, not another always-mounted form template.

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

  if (ttState.loading) return <p className="muted">Loading…</p>;
  if (ttState.error) return <p className="error">{ttState.error.message}</p>;
  if (!ttState.data) return null;

  const tt = ttState.data;
  return (
    <>
      <IdentityHeader
        ticketType={tt}
        orgSlug={orgSlug}
        onSaved={() => ttState.reload()}
        rulesHref={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`}
      />

      <section className="section">
        <div className="section-head">
          <h3>Fields</h3>
        </div>
        <FieldsList
          ticketTypeId={ticketTypeId!}
          orgSlug={orgSlug}
          fields={tt.fields}
          onChanged={() => ttState.reload()}
        />
      </section>

      <section className="section">
        <div className="section-head">
          <h3>Workflow</h3>
        </div>
        <StagesList
          ticketTypeId={ticketTypeId!}
          orgSlug={orgSlug}
          stages={tt.workflow_stages}
          onChanged={() => ttState.reload()}
        />
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// Identity header — inline-editable display name + status pills + Advanced
// ---------------------------------------------------------------------------
function IdentityHeader({
  ticketType,
  orgSlug,
  onSaved,
  rulesHref,
}: {
  ticketType: AdminTicketType;
  orgSlug: string;
  onSaved: () => void;
  rulesHref: string;
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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const dirty =
    form.display_name !== ticketType.display_name ||
    form.description !== ticketType.description ||
    form.is_active !== ticketType.is_active ||
    form.sequential !== ticketType.sequential ||
    form.ai_enabled !== ticketType.ai_enabled ||
    form.confidence_threshold !== ticketType.confidence_threshold ||
    form.require_citation !== ticketType.require_citation ||
    form.shadow_mode !== ticketType.shadow_mode ||
    form.system_prompt !== ticketType.system_prompt;

  const save = useMutation(async () => {
    await api(`/api/admin/ticket-types/${ticketType.id}/`, {
      method: "PATCH",
      orgSlug,
      body: form,
    });
    onSaved();
  });

  return (
    <header className="page-header">
      <div style={{ display: "grid", gap: "var(--space-2)", flex: 1, minWidth: 0 }}>
        <input
          type="text"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          style={{
            fontSize: "30px",
            fontWeight: 500,
            padding: "2px 4px",
            margin: "-2px -4px",
            border: "1px solid transparent",
            borderRadius: "var(--radius-md)",
            letterSpacing: "-0.015em",
            background: "transparent",
            lineHeight: 1.2,
          }}
        />
        <div className="ticket-meta">
          <code>{ticketType.identifier}</code>
          <span className="sep-dot">·</span>
          <StatusToggle
            label="Active"
            on={form.is_active}
            onChange={(v) => setForm({ ...form, is_active: v })}
          />
          <span className="sep-dot">·</span>
          <StatusToggle
            label="AI on"
            offLabel="AI off"
            on={form.ai_enabled}
            onChange={(v) => setForm({ ...form, ai_enabled: v })}
          />
          {form.shadow_mode && (
            <>
              <span className="sep-dot">·</span>
              <span className="status status-escalate">Shadow mode</span>
            </>
          )}
        </div>

        <button
          type="button"
          className="disclosure"
          onClick={() => setShowAdvanced((v) => !v)}
          style={{ marginTop: "var(--space-2)" }}
        >
          {showAdvanced ? "▾" : "▸"} {showAdvanced ? "Hide" : "Show"} advanced settings
        </button>
        {showAdvanced && (
          <div className="disclosure-panel">
            <div className="form-field">
              <label>Description</label>
              <textarea
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional — shown on the requester form."
              />
            </div>
            <label className="checkbox-inline">
              <input
                type="checkbox"
                checked={form.sequential}
                onChange={(e) => setForm({ ...form, sequential: e.target.checked })}
              />
              Sequential workflow
            </label>
            <label className="checkbox-inline">
              <input
                type="checkbox"
                checked={form.require_citation}
                onChange={(e) => setForm({ ...form, require_citation: e.target.checked })}
              />
              Require citation (guard 1)
            </label>
            <label className="checkbox-inline">
              <input
                type="checkbox"
                checked={form.shadow_mode}
                onChange={(e) => setForm({ ...form, shadow_mode: e.target.checked })}
              />
              Shadow mode — log decisions but don't apply them
            </label>
            <div className="form-field">
              <label>Confidence threshold (0 – 1)</label>
              <input
                type="number" step="0.01" min="0" max="1"
                value={form.confidence_threshold}
                onChange={(e) =>
                  setForm({ ...form, confidence_threshold: Number(e.target.value) })
                }
                style={{ width: "120px" }}
              />
            </div>
            <div className="form-field">
              <label>System prompt</label>
              <textarea
                rows={10}
                value={form.system_prompt}
                onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                placeholder="You are Superstar's decisioning engine for ..."
                style={{ fontFamily: "var(--font-mono)", fontSize: "12.5px" }}
              />
              <small className="help">
                Prepended to every LLM call. Define the JSON schema and the grounding rules here.
              </small>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-start" }}>
        <Link to={rulesHref} className="btn">KB rules</Link>
        {dirty && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={save.loading}
            onClick={() => save.call(undefined)}
          >
            {save.loading ? "Saving…" : "Save"}
          </button>
        )}
      </div>
    </header>
  );
}

/** A small toggle that reads as a status pill but flips on click. */
function StatusToggle({
  label, offLabel, on, onChange,
}: {
  label: string;
  offLabel?: string;
  on: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      className={`status ${on ? "status-decided" : "status-closed"}`}
      style={{ cursor: "pointer", border: "none", padding: "2px 8px" }}
      onClick={() => onChange(!on)}
      aria-pressed={on}
    >
      {on ? label : (offLabel ?? `${label} off`)}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Fields — collapsible list
// ---------------------------------------------------------------------------
function FieldsList({
  ticketTypeId, orgSlug, fields, onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  fields: AdminTicketTypeField[];
  onChanged: () => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const siblingNames = fields.map((f) => f.name).filter(Boolean);

  return (
    <div className="list">
      {fields.length === 0 && !adding && (
        <p className="muted">No fields yet.</p>
      )}
      {fields.map((f) =>
        openId === f.id ? (
          <FieldEdit
            key={f.id}
            ticketTypeId={ticketTypeId}
            orgSlug={orgSlug}
            field={f}
            siblingNames={siblingNames.filter((n) => n !== f.name)}
            onClose={() => setOpenId(null)}
            onChanged={() => { onChanged(); setOpenId(null); }}
          />
        ) : (
          <button
            key={f.id}
            type="button"
            className="list-row"
            onClick={() => setOpenId(f.id)}
            style={{ textAlign: "left", width: "100%", background: "transparent", font: "inherit", cursor: "pointer" }}
          >
            <FieldSummary field={f} />
            <span className="muted small">Edit →</span>
          </button>
        ),
      )}

      {adding ? (
        <FieldEdit
          ticketTypeId={ticketTypeId}
          orgSlug={orgSlug}
          field={null}
          siblingNames={siblingNames}
          onClose={() => setAdding(false)}
          onChanged={() => { onChanged(); setAdding(false); }}
        />
      ) : (
        <button type="button" className="list-add" onClick={() => setAdding(true)}>
          + Add field
        </button>
      )}
    </div>
  );
}

function FieldSummary({ field }: { field: AdminTicketTypeField }) {
  const hasConditions =
    (field.show_if && Object.keys(field.show_if).length > 0) ||
    (field.choices_if && field.choices_if.length > 0);
  const choicesNote =
    field.field_type === "enum"
      ? ` · ${field.choices.length} option${field.choices.length === 1 ? "" : "s"}`
      : "";

  return (
    <span className="list-row-summary">
      <span className="mono">{field.name}</span>
      <span className="sep-dot">·</span>
      <span>{field.field_type}{choicesNote}</span>
      {field.required && (
        <>
          <span className="sep-dot">·</span>
          <span className="list-row-meta">Required</span>
        </>
      )}
      {hasConditions && (
        <>
          <span className="sep-dot">·</span>
          <span className="status status-open" style={{ fontSize: "10px" }}>Conditions</span>
        </>
      )}
    </span>
  );
}

function FieldEdit({
  ticketTypeId, orgSlug, field, siblingNames, onClose, onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  field: AdminTicketTypeField | null;
  siblingNames: string[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Partial<AdminTicketTypeField>>(
    field ?? {
      order: 0, name: "", field_type: "string", label: "",
      required: true, choices: [], help_text: "",
      show_if: null, choices_if: [],
    },
  );
  const [showConditions, setShowConditions] = useState(
    !!(field && ((field.show_if && Object.keys(field.show_if).length > 0) || (field.choices_if && field.choices_if.length > 0))),
  );

  const isNew = field === null;

  const save = useMutation(async () => {
    if (isNew) {
      await api(`/api/admin/ticket-types/${ticketTypeId}/fields/`, {
        method: "POST", orgSlug, body: draft,
      });
    } else {
      await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
        method: "PATCH", orgSlug, body: draft,
      });
    }
    onChanged();
  });
  const del = useMutation(async () => {
    if (!field) return;
    await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
      method: "DELETE", orgSlug,
    });
    onChanged();
  });

  return (
    <div className="list-row-expanded">
      <div className="grid-two">
        <div className="form-field">
          <label>Name (JSON key)</label>
          <input
            type="text"
            value={draft.name ?? ""}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="e.g. role"
          />
        </div>
        <div className="form-field">
          <label>Type</label>
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
        </div>
      </div>

      <div className="form-field">
        <label>Display label</label>
        <input
          type="text"
          value={draft.label ?? ""}
          onChange={(e) => setDraft({ ...draft, label: e.target.value })}
          placeholder="What requesters see"
        />
      </div>

      {draft.field_type === "enum" && (
        <div className="form-field">
          <label>Choices (comma-separated)</label>
          <input
            type="text"
            value={(draft.choices ?? []).join(", ")}
            onChange={(e) =>
              setDraft({
                ...draft,
                choices: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            placeholder="engineer, ops, finance"
          />
        </div>
      )}

      <label className="checkbox-inline">
        <input
          type="checkbox"
          checked={draft.required ?? true}
          onChange={(e) => setDraft({ ...draft, required: e.target.checked })}
        />
        Required
      </label>

      <button
        type="button"
        className="disclosure"
        onClick={() => setShowConditions((v) => !v)}
      >
        {showConditions ? "▾" : "▸"} Conditions
        {((draft.show_if && Object.keys(draft.show_if).length > 0) || (draft.choices_if && draft.choices_if.length > 0)) && (
          <span className="status status-open" style={{ fontSize: "10px", marginLeft: 6 }}>active</span>
        )}
      </button>

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
              Empty = always show. Otherwise this field renders only when ALL conditions match.
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

      <div className="row-actions">
        {!isNew && (
          <button
            type="button"
            className="btn-danger"
            disabled={del.loading}
            onClick={() => del.call(undefined)}
          >
            Delete
          </button>
        )}
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading || !draft.name || !draft.label}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "…" : isNew ? "Add field" : "Save"}
        </button>
      </div>
      {save.error && <p className="error">{save.error.message}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stages — collapsible list
// ---------------------------------------------------------------------------
function StagesList({
  ticketTypeId, orgSlug, stages, onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  stages: AdminWorkflowStage[];
  onChanged: () => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

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
    <div className="list">
      {stages.length === 0 && !adding && <p className="muted">No stages yet.</p>}
      {stages.map((s) =>
        openId === s.id ? (
          <StageEdit
            key={s.id}
            ticketTypeId={ticketTypeId}
            orgSlug={orgSlug}
            stage={s}
            knownTeamSlugs={teamSlugs}
            onClose={() => setOpenId(null)}
            onChanged={() => { onChanged(); setOpenId(null); }}
          />
        ) : (
          <button
            key={s.id}
            type="button"
            className="list-row"
            onClick={() => setOpenId(s.id)}
            style={{ textAlign: "left", width: "100%", background: "transparent", font: "inherit", cursor: "pointer" }}
          >
            <StageSummary stage={s} knownTeamSlugs={teamSlugs} />
            <span className="muted small">Edit →</span>
          </button>
        ),
      )}

      {adding ? (
        <StageEdit
          ticketTypeId={ticketTypeId}
          orgSlug={orgSlug}
          stage={null}
          knownTeamSlugs={teamSlugs}
          onClose={() => setAdding(false)}
          onChanged={() => { onChanged(); setAdding(false); }}
        />
      ) : (
        <button type="button" className="list-add" onClick={() => setAdding(true)}>
          + Add stage
        </button>
      )}

      {teamSlugs.length === 0 && (
        <p className="muted small">
          No teams yet. <a href={`/o/${orgSlug}/admin/teams`}>Create one</a> first.
        </p>
      )}
    </div>
  );
}

function StageSummary({
  stage, knownTeamSlugs,
}: {
  stage: AdminWorkflowStage;
  knownTeamSlugs: string[];
}) {
  const modeLabel: Record<string, string> = {
    any_member: "any member",
    unanimous_team: "unanimous",
    majority: "majority",
    specific_user: "specific user",
  };
  const stale = stage.approvers.filter((s) => !knownTeamSlugs.includes(s));
  return (
    <span className="list-row-summary">
      <span style={{ color: "var(--ink-500)" }}>{stage.order}</span>
      <span style={{ fontWeight: 500 }}>{stage.name || "(unnamed)"}</span>
      <span className="sep-dot">·</span>
      <span className="list-row-meta">{modeLabel[stage.mode] ?? stage.mode}</span>
      {stage.approvers.length > 0 && (
        <>
          <span className="sep-dot">·</span>
          <span className="list-row-meta">{stage.approvers.join(", ")}</span>
        </>
      )}
      {stale.length > 0 && (
        <span className="status status-rejected" style={{ fontSize: "10px" }}>stale teams</span>
      )}
    </span>
  );
}

function StageEdit({
  ticketTypeId, orgSlug, stage, knownTeamSlugs, onClose, onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  stage: AdminWorkflowStage | null;
  knownTeamSlugs: string[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Partial<AdminWorkflowStage>>(
    stage ?? {
      order: 0, name: "", approvers: [], mode: "any_member", sla_hours: null,
    },
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const isNew = stage === null;

  const save = useMutation(async () => {
    if (isNew) {
      await api(`/api/admin/ticket-types/${ticketTypeId}/stages/`, {
        method: "POST", orgSlug, body: draft,
      });
    } else {
      await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
        method: "PATCH", orgSlug, body: draft,
      });
    }
    onChanged();
  });
  const del = useMutation(async () => {
    if (!stage) return;
    await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
      method: "DELETE", orgSlug,
    });
    onChanged();
  });

  return (
    <div className="list-row-expanded">
      <div className="form-field">
        <label>Stage name</label>
        <input
          type="text"
          value={draft.name ?? ""}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="e.g. Security review"
        />
      </div>

      <div className="grid-two">
        <div className="form-field">
          <label>Order</label>
          <input
            type="number"
            value={draft.order ?? 0}
            onChange={(e) => setDraft({ ...draft, order: Number(e.target.value) })}
          />
        </div>
        <div className="form-field">
          <label>Mode</label>
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
        </div>
      </div>

      <ApproverTeamSelector
        selected={draft.approvers ?? []}
        knownTeamSlugs={knownTeamSlugs}
        onChange={(approvers) => setDraft({ ...draft, approvers })}
      />

      <button
        type="button"
        className="disclosure"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? "▾" : "▸"} {showAdvanced ? "Hide" : "Show"} SLA
      </button>
      {showAdvanced && (
        <div className="disclosure-panel">
          <div className="form-field">
            <label>SLA (hours)</label>
            <input
              type="number"
              value={draft.sla_hours ?? ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  sla_hours: e.target.value === "" ? null : Number(e.target.value),
                })
              }
              placeholder="e.g. 24"
              style={{ width: "120px" }}
            />
          </div>
        </div>
      )}

      <div className="row-actions">
        {!isNew && (
          <button
            type="button"
            className="btn-danger"
            disabled={del.loading}
            onClick={() => del.call(undefined)}
          >
            Delete
          </button>
        )}
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.loading || !draft.name}
          onClick={() => save.call(undefined)}
        >
          {save.loading ? "…" : isNew ? "Add stage" : "Save"}
        </button>
      </div>
      {save.error && <p className="error">{save.error.message}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers — preserved from the prior version
// ---------------------------------------------------------------------------

/** Multi-select of team slugs in this org + a fallback for stages that
 *  reference team slugs no longer present (preserved as "(stale)" chips so
 *  we don't silently erase them on save). */
function ApproverTeamSelector({
  selected, knownTeamSlugs, onChange,
}: {
  selected: string[];
  knownTeamSlugs: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (slug: string) => {
    onChange(selected.includes(slug) ? selected.filter((s) => s !== slug) : [...selected, slug]);
  };
  return (
    <div className="approver-team-selector">
      <label style={{ fontSize: "13px", fontWeight: 500, color: "var(--ink-700)" }}>Approver teams</label>
      <div className="chip-row">
        {knownTeamSlugs.map((slug) => {
          const on = selected.includes(slug);
          return (
            <button
              key={slug}
              type="button"
              className={`chip ${on ? "chip-active" : ""}`}
              onClick={() => toggle(slug)}
            >
              {on ? "✓ " : ""}{slug}
            </button>
          );
        })}
        {selected.filter((s) => !knownTeamSlugs.includes(s)).map((slug) => (
          <button
            key={slug}
            type="button"
            className="chip chip-stale"
            onClick={() => toggle(slug)}
            title="This team no longer exists. Click to remove."
          >
            {slug} (stale)
          </button>
        ))}
      </div>
    </div>
  );
}

function ChoicesIfEditor({
  value, onChange, siblingNames,
}: {
  value: NonNullable<AdminTicketTypeField["choices_if"]>;
  onChange: (next: NonNullable<AdminTicketTypeField["choices_if"]>) => void;
  siblingNames: string[];
}) {
  const rules = value ?? [];
  const setRule = (
    i: number,
    next: { conditions: Record<string, unknown>; choices: string[] },
  ) => onChange(rules.map((r, idx) => (idx === i ? next : r)));
  const remove = (i: number) => onChange(rules.filter((_, idx) => idx !== i));
  const addRule = () =>
    onChange([...rules, { conditions: {}, choices: [] }]);

  return (
    <div className="form-field">
      <label>Cascading choices (choices_if)</label>
      <small className="help">
        First matching rule wins. If no rule matches, the field's static
        choices are used as a fallback.
      </small>
      {rules.length === 0 && <p className="muted small">No rules — falls back to static choices.</p>}
      {rules.map((rule, i) => (
        <div key={i} className="choices-if-rule">
          <div className="cir-header">
            <span className="cir-label">Rule {i + 1}</span>
            <button type="button" className="btn-icon" onClick={() => remove(i)}>×</button>
          </div>
          <div className="form-field">
            <label className="small">When…</label>
            <AppliesWhenBuilder
              value={rule.conditions}
              onChange={(v) => setRule(i, { ...rule, conditions: v })}
              knownFieldNames={siblingNames}
            />
          </div>
          <div className="form-field">
            <label className="small">Show these choices</label>
            <input
              type="text"
              value={rule.choices.join(", ")}
              onChange={(e) =>
                setRule(i, {
                  ...rule,
                  choices: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                })
              }
              placeholder="base_unit, wall_unit, sink_unit"
            />
          </div>
        </div>
      ))}
      <button type="button" className="link-btn" onClick={addRule}>+ Add rule</button>
    </div>
  );
}

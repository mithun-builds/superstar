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
import type {
  AdminTicketType,
  AdminTicketTypeField,
  AdminWorkflowStage,
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

      {fields.map((f) => (
        <FieldRow
          key={f.id}
          ticketTypeId={ticketTypeId}
          orgSlug={orgSlug}
          field={f}
          onChanged={onChanged}
        />
      ))}

      <FieldRow
        ticketTypeId={ticketTypeId}
        orgSlug={orgSlug}
        field={null}
        onChanged={onChanged}
      />
    </section>
  );
}

function FieldRow({
  ticketTypeId,
  orgSlug,
  field,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  field: AdminTicketTypeField | null;
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
    },
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
          placeholder="choices, comma-separated"
        />
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
  return (
    <section className="card">
      <h3>Workflow stages</h3>
      <p className="muted">
        On escalation, SuperStar materializes a stage per row, in order. The
        ticket advances when the active stage is approved.
      </p>

      {stages.length === 0 && <p className="muted">No stages yet.</p>}

      {stages.map((s) => (
        <StageRow
          key={s.id}
          ticketTypeId={ticketTypeId}
          orgSlug={orgSlug}
          stage={s}
          onChanged={onChanged}
        />
      ))}

      <StageRow
        ticketTypeId={ticketTypeId}
        orgSlug={orgSlug}
        stage={null}
        onChanged={onChanged}
      />
    </section>
  );
}

function StageRow({
  ticketTypeId,
  orgSlug,
  stage,
  onChanged,
}: {
  ticketTypeId: string;
  orgSlug: string;
  stage: AdminWorkflowStage | null;
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

      <input
        type="text"
        value={(draft.approvers ?? []).join(", ")}
        onChange={(e) =>
          setDraft({
            ...draft,
            approvers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
          })
        }
        placeholder="approver groups, comma-separated (e.g. security, design-head)"
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

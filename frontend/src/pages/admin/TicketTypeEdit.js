import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
import { useOrgRequired } from "../../contexts/OrgContext";
export default function TicketTypeEdit() {
    const orgSlug = useOrgRequired();
    const { ticketTypeId } = useParams();
    const path = `/api/admin/ticket-types/${ticketTypeId}/`;
    const ttState = useApi(path, { orgSlug });
    if (ttState.loading)
        return _jsx("p", { children: "Loading\u2026" });
    if (ttState.error)
        return _jsx("p", { className: "error", children: ttState.error.message });
    if (!ttState.data)
        return null;
    return (_jsxs("section", { className: "page-admin-edit", children: [_jsxs("header", { className: "page-header", children: [_jsxs("div", { children: [_jsx("h1", { children: ttState.data.display_name }), _jsxs("p", { className: "muted", children: [_jsx("code", { children: ttState.data.identifier }), " \u00B7 ", ttState.data.is_active ? "active" : "inactive"] })] }), _jsx(Link, { to: `/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`, className: "btn", children: "KB rules \u2192" })] }), _jsx(IdentityAndAiPolicy, { ticketType: ttState.data, orgSlug: orgSlug, onSaved: () => ttState.reload() }), _jsx(FieldsEditor, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, fields: ttState.data.fields, onChanged: () => ttState.reload() }), _jsx(StagesEditor, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, stages: ttState.data.workflow_stages, onChanged: () => ttState.reload() })] }));
}
// ---------------------------------------------------------------------------
// Section 1: identity + AI policy + system prompt
// ---------------------------------------------------------------------------
function IdentityAndAiPolicy({ ticketType, orgSlug, onSaved, }) {
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
    return (_jsxs("section", { className: "card", children: [_jsx("h3", { children: "Identity & AI policy" }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Display name" }), _jsx("input", { type: "text", value: form.display_name, onChange: (e) => setForm({ ...form, display_name: e.target.value }) })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Description" }), _jsx("textarea", { value: form.description, rows: 2, onChange: (e) => setForm({ ...form, description: e.target.value }) })] }), _jsxs("div", { className: "checkbox-row", children: [_jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: form.is_active, onChange: (e) => setForm({ ...form, is_active: e.target.checked }) }), " ", "Active"] }), _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: form.sequential, onChange: (e) => setForm({ ...form, sequential: e.target.checked }) }), " ", "Sequential workflow"] })] }), _jsx("hr", {}), _jsx("h4", { children: "AI decisioning" }), _jsxs("div", { className: "checkbox-row", children: [_jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: form.ai_enabled, onChange: (e) => setForm({ ...form, ai_enabled: e.target.checked }) }), " ", "AI enabled"] }), _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: form.require_citation, onChange: (e) => setForm({ ...form, require_citation: e.target.checked }) }), " ", "Require citation"] }), _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: form.shadow_mode, onChange: (e) => setForm({ ...form, shadow_mode: e.target.checked }) }), " ", "Shadow mode ", _jsx("small", { className: "muted", children: "(log only, don't apply)" })] })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Confidence threshold (0 \u2013 1)" }), _jsx("input", { type: "number", step: "0.01", min: "0", max: "1", value: form.confidence_threshold, onChange: (e) => setForm({ ...form, confidence_threshold: Number(e.target.value) }) })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "System prompt" }), _jsx("textarea", { rows: 12, value: form.system_prompt, onChange: (e) => setForm({ ...form, system_prompt: e.target.value }), placeholder: "You are SuperStar's decisioning engine for ..." }), _jsx("small", { className: "help", children: "Prepended to every LLM call. Define the output JSON schema and the grounding rules here." })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: save.loading, onClick: () => save.call(undefined), children: save.loading ? "Saving…" : "Save identity & AI policy" }), save.error && _jsx("span", { className: "error", children: save.error.message })] })] }));
}
// ---------------------------------------------------------------------------
// Section 2: schema fields editor
// ---------------------------------------------------------------------------
function FieldsEditor({ ticketTypeId, orgSlug, fields, onChanged, }) {
    return (_jsxs("section", { className: "card", children: [_jsx("h3", { children: "Schema fields" }), _jsx("p", { className: "muted", children: "Each row is a form input requesters fill in when submitting a ticket of this type. Field names become JSON keys on the ticket payload." }), fields.length === 0 && _jsx("p", { className: "muted", children: "No fields yet." }), fields.map((f) => (_jsx(FieldRow, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, field: f, onChanged: onChanged }, f.id))), _jsx(FieldRow, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, field: null, onChanged: onChanged })] }));
}
function FieldRow({ ticketTypeId, orgSlug, field, onChanged, }) {
    const [draft, setDraft] = useState(field ?? {
        order: 0,
        name: "",
        field_type: "string",
        label: "",
        required: true,
        choices: [],
        help_text: "",
    });
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
        }
        else {
            await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
                method: "PATCH",
                orgSlug,
                body: draft,
            });
        }
        onChanged();
    });
    const del = useMutation(async () => {
        if (!field)
            return;
        await api(`/api/admin/ticket-types/${ticketTypeId}/fields/${field.id}/`, {
            method: "DELETE",
            orgSlug,
        });
        onChanged();
    });
    return (_jsxs("div", { className: `row-edit ${isNew ? "row-new" : ""}`, children: [_jsxs("div", { className: "row-inputs", children: [_jsx("input", { type: "number", className: "input-tiny", value: draft.order ?? 0, onChange: (e) => setDraft({ ...draft, order: Number(e.target.value) }), placeholder: "order" }), _jsx("input", { type: "text", className: "input-narrow", value: draft.name ?? "", onChange: (e) => setDraft({ ...draft, name: e.target.value }), placeholder: "field name (e.g. role)" }), _jsxs("select", { value: draft.field_type ?? "string", onChange: (e) => setDraft({ ...draft, field_type: e.target.value }), children: [_jsx("option", { value: "string", children: "string" }), _jsx("option", { value: "int", children: "int" }), _jsx("option", { value: "bool", children: "bool" }), _jsx("option", { value: "text", children: "text" }), _jsx("option", { value: "enum", children: "enum" })] }), _jsx("input", { type: "text", value: draft.label ?? "", onChange: (e) => setDraft({ ...draft, label: e.target.value }), placeholder: "display label" }), _jsxs("label", { className: "checkbox-inline", children: [_jsx("input", { type: "checkbox", checked: draft.required ?? true, onChange: (e) => setDraft({ ...draft, required: e.target.checked }) }), " ", "required"] })] }), draft.field_type === "enum" && (_jsx("input", { type: "text", value: (draft.choices ?? []).join(", "), onChange: (e) => setDraft({
                    ...draft,
                    choices: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                }), placeholder: "choices, comma-separated" })), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: save.loading || !draft.name || !draft.label, onClick: () => save.call(undefined), children: save.loading ? "…" : isNew ? "Add field" : "Save" }), !isNew && (_jsx("button", { type: "button", className: "btn btn-reject", disabled: del.loading, onClick: () => del.call(undefined), children: "Delete" }))] }), save.error && _jsx("p", { className: "error", children: save.error.message })] }));
}
// ---------------------------------------------------------------------------
// Section 3: workflow stages editor
// ---------------------------------------------------------------------------
function StagesEditor({ ticketTypeId, orgSlug, stages, onChanged, }) {
    return (_jsxs("section", { className: "card", children: [_jsx("h3", { children: "Workflow stages" }), _jsx("p", { className: "muted", children: "On escalation, SuperStar materializes a stage per row, in order. The ticket advances when the active stage is approved." }), stages.length === 0 && _jsx("p", { className: "muted", children: "No stages yet." }), stages.map((s) => (_jsx(StageRow, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, stage: s, onChanged: onChanged }, s.id))), _jsx(StageRow, { ticketTypeId: ticketTypeId, orgSlug: orgSlug, stage: null, onChanged: onChanged })] }));
}
function StageRow({ ticketTypeId, orgSlug, stage, onChanged, }) {
    const [draft, setDraft] = useState(stage ?? {
        order: 0,
        name: "",
        approvers: [],
        mode: "any_member",
        sla_hours: null,
    });
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
        }
        else {
            await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
                method: "PATCH",
                orgSlug,
                body: draft,
            });
        }
        onChanged();
    });
    const del = useMutation(async () => {
        if (!stage)
            return;
        await api(`/api/admin/ticket-types/${ticketTypeId}/stages/${stage.id}/`, {
            method: "DELETE",
            orgSlug,
        });
        onChanged();
    });
    return (_jsxs("div", { className: `row-edit ${isNew ? "row-new" : ""}`, children: [_jsxs("div", { className: "row-inputs", children: [_jsx("input", { type: "number", className: "input-tiny", value: draft.order ?? 0, onChange: (e) => setDraft({ ...draft, order: Number(e.target.value) }), placeholder: "order" }), _jsx("input", { type: "text", value: draft.name ?? "", onChange: (e) => setDraft({ ...draft, name: e.target.value }), placeholder: "stage name (e.g. Security review)" }), _jsxs("select", { value: draft.mode ?? "any_member", onChange: (e) => setDraft({ ...draft, mode: e.target.value }), children: [_jsx("option", { value: "any_member", children: "any member" }), _jsx("option", { value: "unanimous_team", children: "unanimous team" }), _jsx("option", { value: "majority", children: "majority" }), _jsx("option", { value: "specific_user", children: "specific user" })] }), _jsx("input", { type: "number", className: "input-tiny", value: draft.sla_hours ?? "", onChange: (e) => setDraft({
                            ...draft,
                            sla_hours: e.target.value === "" ? null : Number(e.target.value),
                        }), placeholder: "SLA hrs" })] }), _jsx("input", { type: "text", value: (draft.approvers ?? []).join(", "), onChange: (e) => setDraft({
                    ...draft,
                    approvers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                }), placeholder: "approver groups, comma-separated (e.g. security, design-head)" }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: save.loading || !draft.name, onClick: () => save.call(undefined), children: save.loading ? "…" : isNew ? "Add stage" : "Save" }), !isNew && (_jsx("button", { type: "button", className: "btn btn-reject", disabled: del.loading, onClick: () => del.call(undefined), children: "Delete" }))] }), save.error && _jsx("p", { className: "error", children: save.error.message })] }));
}

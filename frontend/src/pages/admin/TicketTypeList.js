import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// Admin → Ticket types list.
// Shows every ticket type the org owns, lets admin create new ones or
// drill into an existing one.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import { useOrgRequired } from "../../contexts/OrgContext";
export default function TicketTypeList() {
    const orgSlug = useOrgRequired();
    const navigate = useNavigate();
    const list = useApi("/api/admin/ticket-types/", { orgSlug });
    const [draft, setDraft] = useState(null);
    const create = useMutation(async (input) => {
        const t = await api("/api/admin/ticket-types/", {
            method: "POST",
            orgSlug,
            body: { ...input, is_active: true },
        });
        setDraft(null);
        navigate(`/o/${orgSlug}/admin/ticket-types/${t.id}`);
        return t;
    });
    const items = unwrap(list.data);
    return (_jsxs("section", { className: "page-admin-list", children: [_jsxs("header", { className: "page-header", children: [_jsx("h1", { children: "Ticket types" }), _jsx("button", { type: "button", className: "btn btn-primary", onClick: () => setDraft({ identifier: "", display_name: "" }), children: "+ New ticket type" })] }), list.loading && _jsx("p", { children: "Loading\u2026" }), list.error && (_jsxs("p", { className: "error", children: ["Couldn't load: ", list.error.message] })), draft && (_jsxs("div", { className: "card", children: [_jsx("h3", { children: "New ticket type" }), _jsxs("p", { className: "muted", children: ["Identifier is the stable key cited in tickets and audit logs. Conventional shape: ", _jsx("code", { children: "<tenant>.<usecase>" }), " \u2014 e.g.", " ", _jsx("code", { children: "homelane.nonstandard" }), ". Cannot contain spaces or uppercase."] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Identifier" }), _jsx("input", { type: "text", value: draft.identifier, onChange: (e) => setDraft({ ...draft, identifier: e.target.value }), placeholder: "acme.access-request" })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Display name" }), _jsx("input", { type: "text", value: draft.display_name, onChange: (e) => setDraft({ ...draft, display_name: e.target.value }), placeholder: "Access request" })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: !draft.identifier || !draft.display_name || create.loading, onClick: () => create.call(draft), children: create.loading ? "Creating…" : "Create" }), _jsx("button", { type: "button", className: "btn", onClick: () => setDraft(null), children: "Cancel" })] }), create.error && (_jsxs("pre", { className: "error-block", children: [create.error.message, "body" in create.error &&
                                "\n" + JSON.stringify(create.error.body, null, 2)] }))] })), items && items.length === 0 && !draft && (_jsxs("p", { className: "muted", children: ["No ticket types yet. Click ", _jsx("strong", { children: "+ New ticket type" }), " to create the first one. Configure schema fields, approval workflow, AI policy, and KB rules from the edit screen."] })), items && items.length > 0 && (_jsxs("table", { className: "ticket-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Identifier" }), _jsx("th", { children: "Display name" }), _jsx("th", { children: "Fields / Stages" }), _jsx("th", { children: "AI" }), _jsx("th", { children: "Active" })] }) }), _jsx("tbody", { children: items.map((t) => (_jsxs("tr", { children: [_jsx("td", { children: _jsx(Link, { to: `/o/${orgSlug}/admin/ticket-types/${t.id}`, children: _jsx("code", { children: t.identifier }) }) }), _jsx("td", { children: t.display_name }), _jsxs("td", { children: [t.fields.length, " fields / ", t.workflow_stages.length, " stages"] }), _jsx("td", { children: t.ai_enabled ? (_jsx("span", { className: `status status-${t.shadow_mode ? "escalated" : "approved"}`, children: t.shadow_mode ? "shadow" : "live" })) : (_jsx("span", { className: "status status-closed", children: "off" })) }), _jsx("td", { children: t.is_active ? "✓" : "—" })] }, t.id))) })] }))] }));
}
function unwrap(v) {
    if (v === null)
        return null;
    if (Array.isArray(v))
        return v;
    return v.results;
}

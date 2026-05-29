import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
// Admin → Ticket type → KB rules list.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import { useOrgRequired } from "../../contexts/OrgContext";
export default function RuleList() {
    const orgSlug = useOrgRequired();
    const { ticketTypeId } = useParams();
    const tt = useApi(`/api/admin/ticket-types/${ticketTypeId}/`, { orgSlug });
    const rules = useApi(`/api/admin/ticket-types/${ticketTypeId}/rules/`, { orgSlug });
    const [creating, setCreating] = useState(false);
    const [draftRuleId, setDraftRuleId] = useState("");
    const create = useMutation(async () => {
        if (!draftRuleId.trim())
            return null;
        const r = await api(`/api/admin/ticket-types/${ticketTypeId}/rules/`, {
            method: "POST",
            orgSlug,
            body: {
                rule_id: draftRuleId.trim(),
                title: "",
                body: "Edit me — describe the rule, its conditions, and the decision it produces.",
                decision_hint: "escalate",
                price_delta: "0",
                post_actions: [],
                applies_when: {},
            },
        });
        setCreating(false);
        setDraftRuleId("");
        rules.reload();
        return r;
    });
    const items = unwrap(rules.data);
    return (_jsxs("section", { className: "page-admin-rules", children: [_jsxs("header", { className: "page-header", children: [_jsxs("div", { children: [_jsx("h1", { children: "KB rules" }), _jsx("p", { className: "muted", children: tt.data ? (_jsxs(_Fragment, { children: ["For ", _jsx(Link, { to: `/o/${orgSlug}/admin/ticket-types/${ticketTypeId}`, children: _jsx("code", { children: tt.data.identifier }) })] })) : ("Loading…") })] }), _jsx("button", { type: "button", className: "btn btn-primary", onClick: () => setCreating(true), children: "+ New rule" })] }), creating && (_jsxs("div", { className: "card", children: [_jsx("h3", { children: "New rule" }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Rule ID (stable, unique within ticket type)" }), _jsx("input", { type: "text", value: draftRuleId, onChange: (e) => setDraftRuleId(e.target.value), placeholder: "e.g. NSD-LOCK-001" })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: !draftRuleId.trim() || create.loading, onClick: () => create.call(undefined), children: create.loading ? "Creating…" : "Create + edit" }), _jsx("button", { type: "button", className: "btn", onClick: () => setCreating(false), children: "Cancel" })] }), create.error && _jsx("p", { className: "error", children: create.error.message })] })), rules.loading && _jsx("p", { children: "Loading rules\u2026" }), rules.error && _jsx("p", { className: "error", children: rules.error.message }), items && items.length === 0 && !creating && (_jsxs("p", { className: "muted", children: ["No rules yet. The decisioning loop has nothing to retrieve until at least one rule is added \u2014 click ", _jsx("strong", { children: "+ New rule" }), " to start."] })), items && items.length > 0 && (_jsxs("table", { className: "ticket-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Rule ID" }), _jsx("th", { children: "Title" }), _jsx("th", { children: "Decision" }), _jsx("th", { children: "Price \u0394" })] }) }), _jsx("tbody", { children: items.map((r) => (_jsxs("tr", { children: [_jsx("td", { children: _jsx(Link, { to: `/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules/${r.id}`, children: _jsx("code", { children: r.rule_id }) }) }), _jsx("td", { children: r.title || _jsx("span", { className: "muted", children: "\u2014" }) }), _jsx("td", { children: _jsx("span", { className: `status status-${r.decision_hint || "open"}`, children: r.decision_hint || "—" }) }), _jsx("td", { children: r.price_delta })] }, r.id))) })] }))] }));
}
function unwrap(v) {
    if (v === null)
        return null;
    if (Array.isArray(v))
        return v;
    return v.results;
}

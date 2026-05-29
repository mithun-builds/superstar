import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// Admin → Ticket type → Rule edit.
//
// Body editor is a plain <textarea> for v0 — markdown-aware editor (Lexical,
// CodeMirror) is a polish pass. `applies_when` is a JSON textarea — works,
// not pretty. A visual rule-builder is the long-tail UX win.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import { useOrgRequired } from "../../contexts/OrgContext";
export default function RuleEdit() {
    const orgSlug = useOrgRequired();
    const navigate = useNavigate();
    const { ticketTypeId, ruleId } = useParams();
    const path = `/api/admin/ticket-types/${ticketTypeId}/rules/${ruleId}/`;
    const ruleState = useApi(path, { orgSlug });
    const [form, setForm] = useState(null);
    const [appliesError, setAppliesError] = useState(null);
    // Hydrate the form when the rule loads.
    useEffect(() => {
        if (!ruleState.data || form !== null)
            return;
        setForm({
            title: ruleState.data.title,
            body: ruleState.data.body,
            decision_hint: ruleState.data.decision_hint,
            price_delta: ruleState.data.price_delta,
            post_actions_text: ruleState.data.post_actions.join("\n"),
            applies_when_text: JSON.stringify(ruleState.data.applies_when ?? {}, null, 2),
            category: ruleState.data.category,
            subcategory: ruleState.data.subcategory,
        });
    }, [ruleState.data, form]);
    const save = useMutation(async () => {
        if (!form)
            return null;
        let applies_when = {};
        try {
            applies_when = form.applies_when_text.trim()
                ? JSON.parse(form.applies_when_text)
                : {};
            setAppliesError(null);
        }
        catch (e) {
            setAppliesError("applies_when must be valid JSON: " + (e instanceof Error ? e.message : String(e)));
            throw new Error("Invalid applies_when JSON");
        }
        const out = await api(path, {
            method: "PATCH",
            orgSlug,
            body: {
                title: form.title,
                body: form.body,
                decision_hint: form.decision_hint,
                price_delta: form.price_delta,
                post_actions: form.post_actions_text
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean),
                applies_when,
                category: form.category,
                subcategory: form.subcategory,
            },
        });
        ruleState.reload();
        return out;
    });
    const del = useMutation(async () => {
        await api(path, { method: "DELETE", orgSlug });
        navigate(`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`);
    });
    if (ruleState.loading)
        return _jsx("p", { children: "Loading rule\u2026" });
    if (ruleState.error)
        return _jsx("p", { className: "error", children: ruleState.error.message });
    if (!ruleState.data || !form)
        return null;
    return (_jsxs("section", { className: "page-admin-rule-edit", children: [_jsxs("header", { className: "page-header", children: [_jsxs("div", { children: [_jsxs("h1", { children: ["Rule ", _jsx("code", { children: ruleState.data.rule_id })] }), _jsx("p", { className: "muted", children: _jsx(Link, { to: `/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`, children: "\u2190 Back to rules" }) })] }), _jsx("button", { type: "button", className: "btn btn-reject", disabled: del.loading, onClick: () => {
                            if (window.confirm(`Delete rule ${ruleState.data.rule_id}?`)) {
                                del.call(undefined);
                            }
                        }, children: "Delete rule" })] }), _jsxs("div", { className: "card", children: [_jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Title" }), _jsx("input", { type: "text", value: form.title, onChange: (e) => setForm({ ...form, title: e.target.value }), placeholder: "Short human-readable title" })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Body (markdown \u2014 what the LLM sees)" }), _jsx("textarea", { rows: 12, value: form.body, onChange: (e) => setForm({ ...form, body: e.target.value }), placeholder: "## Rule\n\nDescribe the rule and its conditions in plain language.\n\n## Decision\n\n..." }), _jsxs("small", { className: "help", children: ["This is the text the LLM reads when retrieving this rule. Be specific about conditions and outcomes. The decisioning service also enforces the structured ", _jsx("code", { children: "applies_when" }), " block below \u2014 both must agree."] })] }), _jsxs("div", { className: "grid-two", children: [_jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Decision" }), _jsxs("select", { value: form.decision_hint, onChange: (e) => setForm({ ...form, decision_hint: e.target.value }), children: [_jsx("option", { value: "", children: "\u2014" }), _jsx("option", { value: "approve", children: "approve" }), _jsx("option", { value: "reject", children: "reject" }), _jsx("option", { value: "escalate", children: "escalate" })] })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Price delta" }), _jsx("input", { type: "text", value: form.price_delta, onChange: (e) => setForm({ ...form, price_delta: e.target.value }), placeholder: "0" })] })] }), _jsxs("div", { className: "grid-two", children: [_jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Category" }), _jsx("input", { type: "text", value: form.category, onChange: (e) => setForm({ ...form, category: e.target.value }) })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Subcategory" }), _jsx("input", { type: "text", value: form.subcategory, onChange: (e) => setForm({ ...form, subcategory: e.target.value }) })] })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "Post-actions (one per line)" }), _jsx("textarea", { rows: 3, value: form.post_actions_text, onChange: (e) => setForm({ ...form, post_actions_text: e.target.value }), placeholder: "Manual selection in Sc-Pro" })] }), _jsxs("div", { className: "form-field", children: [_jsx("label", { children: "applies_when \u2014 structured conditions (JSON)" }), _jsx("textarea", { rows: 10, value: form.applies_when_text, onChange: (e) => setForm({ ...form, applies_when_text: e.target.value }), spellCheck: false, style: { fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }, placeholder: `{\n  "request_type": "lock",\n  "shutter_finish": {"not_in": ["PU", "Membrane"]}\n}` }), _jsxs("small", { className: "help", children: ["DSL operators: bare scalar = equality, list = membership,", " ", _jsx("code", { children: `{gte/gt/lte/lt: N}` }), ",", " ", _jsx("code", { children: `{between: [a, b]}` }), ",", " ", _jsx("code", { children: `{not_in: [...]}` }), ",", " ", _jsx("code", { children: `{not: x}` }), ",", " ", _jsx("code", { children: `{has_any: [...]}` }), ". See ", _jsx("code", { children: "docs/plugins.md" }), "."] }), appliesError && _jsx("p", { className: "error", children: appliesError })] }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-primary", disabled: save.loading, onClick: () => save.call(undefined).catch(() => {
                                    /* errors surface via save.error + appliesError */
                                }), children: save.loading ? "Saving…" : "Save rule" }), save.error && _jsx("span", { className: "error", children: save.error.message })] })] })] }));
}

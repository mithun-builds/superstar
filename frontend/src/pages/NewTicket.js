import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
// Create-a-ticket flow:
//   1. Fetch /api/tickets/plugins/ — list of supported ticket types
//   2. User picks a plugin from the list (skip step if only one)
//   3. Render DynamicForm from the picked plugin's fields
//   4. POST /api/tickets/ + navigate to detail page
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi, useMutation } from "../api/hooks";
import DynamicForm from "../components/DynamicForm";
import { useOrgRequired } from "../contexts/OrgContext";
export default function NewTicket() {
    const orgSlug = useOrgRequired();
    const navigate = useNavigate();
    const { data: plugins, loading, error } = useApi("/api/tickets/plugins/", { orgSlug });
    const [pickedId, setPickedId] = useState(null);
    const [title, setTitle] = useState("");
    // Auto-pick when there's exactly one plugin.
    const picked = useMemo(() => {
        if (!plugins)
            return null;
        const id = pickedId ?? (plugins.length === 1 ? plugins[0].identifier : null);
        return plugins.find((p) => p.identifier === id) ?? null;
    }, [plugins, pickedId]);
    const submit = useMutation(async ({ payload }) => {
        if (!picked)
            throw new Error("Pick a ticket type first.");
        const finalTitle = title.trim() || `${picked.display_name} request`;
        const t = await api("/api/tickets/", {
            method: "POST",
            orgSlug,
            body: {
                ticket_type: picked.identifier,
                title: finalTitle,
                payload,
            },
        });
        navigate(`/o/${orgSlug}/tickets/${t.id}`);
        return t;
    });
    if (loading)
        return _jsx("p", { children: "Loading ticket types\u2026" });
    if (error)
        return _jsxs("p", { className: "error", children: ["Couldn't fetch ticket types: ", error.message] });
    if (!plugins || plugins.length === 0) {
        return (_jsxs("p", { children: ["No ticket types are configured. Add a plugin YAML under", " ", _jsx("code", { children: "SUPERSTAR_CONFIG_DIR/plugins/" }), " and restart the server."] }));
    }
    return (_jsxs("section", { className: "page-new-ticket", children: [_jsx("h1", { children: "New ticket" }), plugins.length > 1 && (_jsxs("div", { className: "form-field", children: [_jsx("label", { htmlFor: "picker", children: "Ticket type" }), _jsxs("select", { id: "picker", value: pickedId ?? "", onChange: (e) => setPickedId(e.target.value || null), children: [_jsx("option", { value: "", children: "\u2014 pick one \u2014" }), plugins.map((p) => (_jsxs("option", { value: p.identifier, children: [p.display_name, " (", p.identifier, ")"] }, p.identifier)))] })] })), picked && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "form-field", children: [_jsx("label", { htmlFor: "title", children: "Title" }), _jsx("input", { id: "title", type: "text", value: title, onChange: (e) => setTitle(e.target.value), placeholder: `${picked.display_name} request` }), _jsxs("small", { className: "help", children: ["Optional \u2014 defaults to \"", picked.display_name, " request\"."] })] }), _jsx("hr", {}), _jsx("h2", { children: picked.display_name }), picked.ai_enabled && (_jsxs("p", { className: "muted", children: ["This ticket type runs AI decisioning", picked.shadow_mode ? " (shadow mode — decisions logged, not applied)" : "", "."] })), _jsx(DynamicForm, { fields: picked.fields, onSubmit: async (payload) => {
                            // Drop the return so the type matches DynamicForm's void contract.
                            // Errors are surfaced via submit.error below.
                            await submit.call({ payload }).catch(() => undefined);
                        }, submitting: submit.loading, submitLabel: "Submit ticket" }), submit.error && (_jsxs("pre", { className: "error-block", children: [submit.error instanceof Error ? submit.error.message : String(submit.error), "body" in submit.error &&
                                "\n" + JSON.stringify(submit.error.body, null, 2)] }))] }))] }));
}

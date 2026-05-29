import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// Approval-chain widget: shows every stage in order, highlights the active
// one, and renders an approve/reject form for the active stage when the user
// is allowed to act (v0: anyone authenticated can decide — role-based gating
// is a Phase 1.5 concern).
import { useState } from "react";
import { api } from "../api/client";
export default function StagesPanel({ ticketId, orgSlug, stages, onChange }) {
    return (_jsxs("div", { className: "stages-panel", children: [_jsx("h3", { children: "Approval chain" }), _jsx("ol", { className: "stages-list", children: stages.stages.map((s) => (_jsxs("li", { className: `stage stage-${s.status} ${s.id === stages.active_stage_id ? "stage-active" : ""}`, children: [_jsxs("div", { className: "stage-row", children: [_jsxs("span", { className: "stage-name", children: [s.order, ". ", s.name] }), _jsx("span", { className: `status status-${s.status}`, children: s.status })] }), s.note && _jsxs("p", { className: "stage-note", children: ["\"", s.note, "\""] }), s.decided_at && (_jsxs("p", { className: "stage-meta", children: ["decided ", new Date(s.decided_at).toLocaleString()] })), s.id === stages.active_stage_id && (_jsx(StageDecideForm, { ticketId: ticketId, stage: s, orgSlug: orgSlug, onChange: onChange }))] }, s.id))) })] }));
}
function StageDecideForm({ ticketId, stage, orgSlug, onChange, }) {
    const [note, setNote] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const decide = async (decision) => {
        setBusy(true);
        setError(null);
        try {
            await api(`/api/tickets/${ticketId}/stages/${stage.id}/decide/`, {
                method: "POST",
                orgSlug,
                body: { decision, note: note.trim() },
            });
            setNote("");
            onChange();
        }
        catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        }
        finally {
            setBusy(false);
        }
    };
    return (_jsxs("div", { className: "stage-actions", children: [_jsx("textarea", { placeholder: "Optional note for the requester / approver trail", value: note, onChange: (e) => setNote(e.target.value), rows: 2 }), _jsxs("div", { className: "btn-row", children: [_jsx("button", { type: "button", className: "btn btn-approve", disabled: busy, onClick: () => decide("approved"), children: "Approve" }), _jsx("button", { type: "button", className: "btn btn-reject", disabled: busy, onClick: () => decide("rejected"), children: "Reject" })] }), error && _jsx("p", { className: "error", children: error })] }));
}

import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
// Single-ticket view:
//   - Header: title + status badge + ticket type
//   - Payload pretty-printed
//   - "Run decisioning" action (when no decision exists or to re-run)
//   - Decision card (most recent) — outcome, citations, confidence, reason
//   - Approval chain (when ticket is escalated/in-flight)
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi, useMutation } from "../api/hooks";
import StagesPanel from "../components/StagesPanel";
import { useOrgRequired } from "../contexts/OrgContext";
export default function TicketDetail() {
    const orgSlug = useOrgRequired();
    const { ticketId } = useParams();
    const ticketState = useApi(ticketId ? `/api/tickets/${ticketId}/` : null, { orgSlug });
    const stagesState = useApi(ticketId ? `/api/tickets/${ticketId}/stages/` : null, { orgSlug });
    const decide = useMutation(async () => {
        const out = await api(`/api/tickets/${ticketId}/decide/`, { method: "POST", orgSlug });
        ticketState.reload();
        stagesState.reload();
        return out;
    });
    if (ticketState.loading)
        return _jsx("p", { children: "Loading ticket\u2026" });
    if (ticketState.error) {
        return _jsxs("p", { className: "error", children: ["Couldn't load ticket: ", ticketState.error.message] });
    }
    const ticket = ticketState.data;
    if (!ticket)
        return null;
    const stages = stagesState.data;
    const hasStages = stages && stages.stages.length > 0;
    return (_jsxs("section", { className: "page-ticket-detail", children: [_jsxs("header", { className: "page-header", children: [_jsxs("div", { children: [_jsx("h1", { children: ticket.title }), _jsxs("div", { className: "ticket-meta", children: [_jsx("code", { children: ticket.ticket_type }), _jsx("span", { className: `status status-${ticket.status}`, children: ticket.status }), _jsxs("span", { className: "muted", children: ["created ", new Date(ticket.created_at).toLocaleString()] })] })] }), _jsx("button", { type: "button", className: "btn", onClick: () => decide.call(undefined), disabled: decide.loading, children: decide.loading ? "Running…" : "Run decisioning" })] }), _jsxs("div", { className: "ticket-grid", children: [_jsxs("section", { className: "card", children: [_jsx("h3", { children: "Request payload" }), _jsx("pre", { className: "payload-pre", children: JSON.stringify(ticket.payload, null, 2) }), ticket.decision_summary && (_jsxs(_Fragment, { children: [_jsx("h3", { children: "Decision summary" }), _jsx("p", { children: ticket.decision_summary })] }))] }), _jsxs("section", { className: "card", children: [_jsx("h3", { children: "Latest decision" }), decide.data ? (_jsx(DecisionPanel, { decision: decide.data })) : (_jsx("p", { className: "muted", children: "No decisioning run yet in this page session. Click \"Run decisioning\" to invoke the LLM." })), decide.error && (_jsxs("pre", { className: "error-block", children: [decide.error.message, "body" in decide.error &&
                                        "\n" +
                                            JSON.stringify(decide.error.body, null, 2)] }))] }), hasStages && (_jsx("section", { className: "card card-wide", children: _jsx(StagesPanel, { ticketId: ticket.id, orgSlug: orgSlug, stages: stages, onChange: () => {
                                ticketState.reload();
                                stagesState.reload();
                            } }) }))] })] }));
}
function DecisionPanel({ decision }) {
    return (_jsxs("div", { className: "decision-panel", children: [_jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Outcome:" }), " ", _jsx("span", { className: `status status-${decision.outcome}`, children: decision.outcome }), decision.shadow_mode && (_jsx("span", { className: "badge shadow", children: "shadow mode \u2014 not applied" }))] }), _jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Confidence:" }), " ", decision.confidence] }), _jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Cited rules:" }), " ", decision.cited_rule_ids.length ? (decision.cited_rule_ids.map((r) => (_jsx("code", { className: "rule-tag", children: r }, r)))) : (_jsx("span", { className: "muted", children: "(none)" }))] }), _jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Reason:" }), _jsx("p", { children: decision.reason_text })] }), Number(decision.price_delta) !== 0 && (_jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Price delta:" }), " ", decision.price_delta] })), decision.post_actions.length > 0 && (_jsxs("div", { className: "decision-row", children: [_jsx("strong", { children: "Post-actions:" }), _jsx("ul", { children: decision.post_actions.map((a, i) => (_jsx("li", { children: a }, i))) })] }))] }));
}

import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// Tenant dashboard — list of tickets in this org, with filters by status.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
import { useOrgRequired } from "../contexts/OrgContext";
const STATUS_OPTIONS = [
    { value: "all", label: "All" },
    { value: "open", label: "Open" },
    { value: "escalated", label: "Escalated" },
    { value: "decided", label: "Decided (auto)" },
    { value: "approved", label: "Approved" },
    { value: "rejected", label: "Rejected" },
    { value: "closed", label: "Closed" },
];
export default function Dashboard() {
    const orgSlug = useOrgRequired();
    const [filter, setFilter] = useState("all");
    const { data, loading, error } = useApi("/api/tickets/", { orgSlug });
    const visible = data?.results.filter((t) => filter === "all" || t.status === filter) ?? [];
    return (_jsxs("section", { className: "page-dashboard", children: [_jsxs("header", { className: "page-header", children: [_jsx("h1", { children: "Tickets" }), _jsx(Link, { to: `/o/${orgSlug}/new`, className: "btn btn-primary", children: "+ New ticket" })] }), _jsx("div", { className: "filter-row", children: STATUS_OPTIONS.map((opt) => (_jsx("button", { type: "button", className: `chip ${filter === opt.value ? "chip-active" : ""}`, onClick: () => setFilter(opt.value), children: opt.label }, opt.value))) }), loading && _jsx("p", { children: "Loading tickets\u2026" }), error && _jsxs("p", { className: "error", children: ["Couldn't load tickets: ", error.message] }), data && visible.length === 0 && (_jsx("p", { className: "muted", children: "No tickets match this filter." })), visible.length > 0 && (_jsxs("table", { className: "ticket-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Title" }), _jsx("th", { children: "Type" }), _jsx("th", { children: "Status" }), _jsx("th", { children: "Created" })] }) }), _jsx("tbody", { children: visible.map((t) => (_jsxs("tr", { children: [_jsx("td", { children: _jsx(Link, { to: `/o/${orgSlug}/tickets/${t.id}`, children: t.title }) }), _jsx("td", { children: _jsx("code", { children: t.ticket_type }) }), _jsx("td", { children: _jsx("span", { className: `status status-${t.status}`, children: t.status }) }), _jsx("td", { children: new Date(t.created_at).toLocaleString() })] }, t.id))) })] }))] }));
}

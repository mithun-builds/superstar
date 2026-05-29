// Tenant dashboard — list of tickets in this org, with filters by status.

import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Paginated, Ticket, TicketStatus } from "../api/types";
import { useOrgRequired } from "../contexts/OrgContext";

const STATUS_OPTIONS: ({ value: TicketStatus | "all"; label: string })[] = [
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
  const [filter, setFilter] = useState<TicketStatus | "all">("all");
  const { data, loading, error } = useApi<Paginated<Ticket>>(
    "/api/tickets/",
    { orgSlug },
  );

  const visible = data?.results.filter(
    (t) => filter === "all" || t.status === filter,
  ) ?? [];

  return (
    <section className="page-dashboard">
      <header className="page-header">
        <h1>Tickets</h1>
        <Link to={`/o/${orgSlug}/new`} className="btn btn-primary">+ New ticket</Link>
      </header>

      <div className="filter-row">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`chip ${filter === opt.value ? "chip-active" : ""}`}
            onClick={() => setFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading && <p>Loading tickets…</p>}
      {error && <p className="error">Couldn't load tickets: {error.message}</p>}

      {data && visible.length === 0 && (
        <p className="muted">No tickets match this filter.</p>
      )}

      {visible.length > 0 && (
        <table className="ticket-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Type</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link to={`/o/${orgSlug}/tickets/${t.id}`}>{t.title}</Link>
                </td>
                <td><code>{t.ticket_type}</code></td>
                <td>
                  <span className={`status status-${t.status}`}>{t.status}</span>
                </td>
                <td>{new Date(t.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

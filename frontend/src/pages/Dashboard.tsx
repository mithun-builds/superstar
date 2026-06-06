// Tenant dashboard — friendly greeting, decision-stats hero (when there's
// data to summarise), get-started checklist (when there isn't), and the
// status-filtered ticket list at the bottom.

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me, Paginated, Ticket, TicketStatus } from "../api/types";
import { useOrgRequired } from "../contexts/OrgContext";
import { GreetingHeader, HeroCard } from "../components/brand";
import GetStarted from "../components/GetStarted";

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
  const { data: me } = useApi<Me>("/api/me/");
  const { data, loading, error } = useApi<Paginated<Ticket>>(
    "/api/tickets/",
    { orgSlug },
  );

  // Pick a first name out of the full name when we have one; fall back to
  // the email's local part if not. Keeps the greeting feeling personal even
  // when full_name is blank.
  const greetingName = useMemo(() => {
    const fn = me?.full_name?.trim();
    if (fn) return fn.split(/\s+/)[0];
    if (me?.email) return me.email.split("@")[0];
    return "there";
  }, [me]);

  const stats = useMemo(() => {
    const all = data?.results ?? [];
    const decided = all.filter((t) =>
      ["decided", "approved", "rejected"].includes(t.status),
    ).length;
    const escalated = all.filter((t) => t.status === "escalated").length;
    return { total: all.length, decided, escalated };
  }, [data]);

  const visible = data?.results.filter(
    (t) => filter === "all" || t.status === filter,
  ) ?? [];

  return (
    <section className="page-dashboard">
      <GreetingHeader
        name={greetingName}
        subtitle={
          stats.total === 0
            ? "Let's get your tenant set up."
            : `${stats.total} ticket${stats.total === 1 ? "" : "s"} so far — ` +
              `${stats.decided} decided automatically.`
        }
      />

      {/* If the tenant still has setup to do, show the checklist instead of
          the stats hero. Once everything's configured the checklist hides
          itself, and the hero takes its place. */}
      {stats.total > 0 ? (
        <HeroCard
          eyebrow="Decisions"
          title={
            <>
              {stats.decided}
              <span style={{ fontWeight: 500, opacity: 0.75 }}> / {stats.total}</span>
              {" "}auto-decided
            </>
          }
          sub={
            stats.escalated > 0
              ? `${stats.escalated} escalated to humans — they're waiting in the list below.`
              : "Every ticket so far has cleared the four-guard pipeline."
          }
          actions={
            <Link to={`/o/${orgSlug}/new`} className="btn btn-primary">
              + New ticket
            </Link>
          }
        />
      ) : (
        <GetStarted orgSlug={orgSlug} />
      )}

      <header className="page-header" style={{ marginTop: "var(--space-8)" }}>
        <h2 className="display-heading">Tickets</h2>
        {stats.total > 0 && (
          <Link to={`/o/${orgSlug}/new`} className="btn">+ New ticket</Link>
        )}
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

      {loading && <p className="muted">Loading tickets…</p>}
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

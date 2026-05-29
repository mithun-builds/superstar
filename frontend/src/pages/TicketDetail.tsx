// Single-ticket view:
//   - Header: title + status badge + ticket type
//   - Payload pretty-printed
//   - "Run decisioning" action (when no decision exists or to re-run)
//   - Decision card (most recent) — outcome, citations, confidence, reason
//   - Approval chain (when ticket is escalated/in-flight)

import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi, useMutation } from "../api/hooks";
import type { DecideResult, StagesResponse, Ticket } from "../api/types";
import StagesPanel from "../components/StagesPanel";
import { useOrgRequired } from "../contexts/OrgContext";

export default function TicketDetail() {
  const orgSlug = useOrgRequired();
  const { ticketId } = useParams<{ ticketId: string }>();

  const ticketState = useApi<Ticket>(
    ticketId ? `/api/tickets/${ticketId}/` : null,
    { orgSlug },
  );
  const stagesState = useApi<StagesResponse>(
    ticketId ? `/api/tickets/${ticketId}/stages/` : null,
    { orgSlug },
  );

  const decide = useMutation(async () => {
    const out = await api<DecideResult>(
      `/api/tickets/${ticketId}/decide/`,
      { method: "POST", orgSlug },
    );
    ticketState.reload();
    stagesState.reload();
    return out;
  });

  if (ticketState.loading) return <p>Loading ticket…</p>;
  if (ticketState.error) {
    return <p className="error">Couldn't load ticket: {ticketState.error.message}</p>;
  }
  const ticket = ticketState.data;
  if (!ticket) return null;
  const stages = stagesState.data;

  const hasStages = stages && stages.stages.length > 0;

  return (
    <section className="page-ticket-detail">
      <header className="page-header">
        <div>
          <h1>{ticket.title}</h1>
          <div className="ticket-meta">
            <code>{ticket.ticket_type}</code>
            <span className={`status status-${ticket.status}`}>{ticket.status}</span>
            <span className="muted">
              created {new Date(ticket.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => decide.call(undefined)}
          disabled={decide.loading}
        >
          {decide.loading ? "Running…" : "Run decisioning"}
        </button>
      </header>

      <div className="ticket-grid">
        <section className="card">
          <h3>Request payload</h3>
          <pre className="payload-pre">
            {JSON.stringify(ticket.payload, null, 2)}
          </pre>
          {ticket.decision_summary && (
            <>
              <h3>Decision summary</h3>
              <p>{ticket.decision_summary}</p>
            </>
          )}
        </section>

        <section className="card">
          <h3>Latest decision</h3>
          {decide.data ? (
            <DecisionPanel decision={decide.data} />
          ) : (
            <p className="muted">
              No decisioning run yet in this page session. Click "Run decisioning"
              to invoke the LLM.
            </p>
          )}
          {decide.error && (
            <pre className="error-block">
              {decide.error.message}
              {"body" in (decide.error as object) &&
                "\n" +
                  JSON.stringify((decide.error as { body: unknown }).body, null, 2)}
            </pre>
          )}
        </section>

        {hasStages && (
          <section className="card card-wide">
            <StagesPanel
              ticketId={ticket.id}
              orgSlug={orgSlug}
              stages={stages!}
              onChange={() => {
                ticketState.reload();
                stagesState.reload();
              }}
            />
          </section>
        )}
      </div>
    </section>
  );
}

function DecisionPanel({ decision }: { decision: DecideResult }) {
  return (
    <div className="decision-panel">
      <div className="decision-row">
        <strong>Outcome:</strong>{" "}
        <span className={`status status-${decision.outcome}`}>{decision.outcome}</span>
        {decision.shadow_mode && (
          <span className="badge shadow">shadow mode — not applied</span>
        )}
      </div>
      <div className="decision-row">
        <strong>Confidence:</strong> {decision.confidence}
      </div>
      <div className="decision-row">
        <strong>Cited rules:</strong>{" "}
        {decision.cited_rule_ids.length ? (
          decision.cited_rule_ids.map((r) => (
            <code key={r} className="rule-tag">{r}</code>
          ))
        ) : (
          <span className="muted">(none)</span>
        )}
      </div>
      <div className="decision-row">
        <strong>Reason:</strong>
        <p>{decision.reason_text}</p>
      </div>
      {Number(decision.price_delta) !== 0 && (
        <div className="decision-row">
          <strong>Price delta:</strong> {decision.price_delta}
        </div>
      )}
      {decision.post_actions.length > 0 && (
        <div className="decision-row">
          <strong>Post-actions:</strong>
          <ul>
            {decision.post_actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

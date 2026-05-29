// Admin → Ticket type → KB rules list.

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminRule, AdminTicketType, Paginated } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function RuleList() {
  const orgSlug = useOrgRequired();
  const { ticketTypeId } = useParams<{ ticketTypeId: string }>();
  const tt = useApi<AdminTicketType>(`/api/admin/ticket-types/${ticketTypeId}/`, { orgSlug });
  const rules = useApi<Paginated<AdminRule> | AdminRule[]>(
    `/api/admin/ticket-types/${ticketTypeId}/rules/`,
    { orgSlug },
  );

  const [creating, setCreating] = useState(false);
  const [draftRuleId, setDraftRuleId] = useState("");

  const create = useMutation(async () => {
    if (!draftRuleId.trim()) return null;
    const r = await api<AdminRule>(
      `/api/admin/ticket-types/${ticketTypeId}/rules/`,
      {
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
      },
    );
    setCreating(false);
    setDraftRuleId("");
    rules.reload();
    return r;
  });

  const items = unwrap(rules.data);

  return (
    <section className="page-admin-rules">
      <header className="page-header">
        <div>
          <h1>KB rules</h1>
          <p className="muted">
            {tt.data ? (
              <>For <Link to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}`}><code>{tt.data.identifier}</code></Link></>
            ) : (
              "Loading…"
            )}
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          + New rule
        </button>
      </header>

      {creating && (
        <div className="card">
          <h3>New rule</h3>
          <div className="form-field">
            <label>Rule ID (stable, unique within ticket type)</label>
            <input
              type="text"
              value={draftRuleId}
              onChange={(e) => setDraftRuleId(e.target.value)}
              placeholder="e.g. NSD-LOCK-001"
            />
          </div>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={!draftRuleId.trim() || create.loading}
              onClick={() => create.call(undefined)}
            >
              {create.loading ? "Creating…" : "Create + edit"}
            </button>
            <button type="button" className="btn" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
          {create.error && <p className="error">{create.error.message}</p>}
        </div>
      )}

      {rules.loading && <p>Loading rules…</p>}
      {rules.error && <p className="error">{rules.error.message}</p>}
      {items && items.length === 0 && !creating && (
        <p className="muted">
          No rules yet. The decisioning loop has nothing to retrieve until at
          least one rule is added — click <strong>+ New rule</strong> to start.
        </p>
      )}

      {items && items.length > 0 && (
        <table className="ticket-table">
          <thead>
            <tr>
              <th>Rule ID</th>
              <th>Title</th>
              <th>Decision</th>
              <th>Price Δ</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules/${r.id}`}>
                    <code>{r.rule_id}</code>
                  </Link>
                </td>
                <td>{r.title || <span className="muted">—</span>}</td>
                <td>
                  <span className={`status status-${r.decision_hint || "open"}`}>
                    {r.decision_hint || "—"}
                  </span>
                </td>
                <td>{r.price_delta}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function unwrap<T>(v: Paginated<T> | T[] | null): T[] | null {
  if (v === null) return null;
  if (Array.isArray(v)) return v;
  return v.results;
}

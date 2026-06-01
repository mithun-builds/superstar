// Admin → Ticket type → KB rules list.
//
// Same shape as TeamList / FieldsList: each rule is a one-line list-row
// (rule_id · title · decision pill). Click → opens RuleEdit. "New rule"
// opens an inline expander at the top of the list — the only thing
// required to create a stub is the rule_id; everything else is filled
// in on the edit page.

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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
  const [adding, setAdding] = useState(false);
  const items = unwrap(rules.data);

  return (
    <>
      <header className="page-header">
        <div style={{ display: "grid", gap: "var(--space-2)", flex: 1, minWidth: 0 }}>
          <h1>KB rules</h1>
          <p className="ticket-meta" style={{ margin: 0 }}>
            {tt.data ? (
              <>
                For{" "}
                <Link to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}`}>
                  <code>{tt.data.identifier}</code>
                </Link>
              </>
            ) : (
              "Loading…"
            )}
          </p>
        </div>
        {!adding && (
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            New rule
          </button>
        )}
      </header>

      {rules.loading && <p className="muted">Loading rules…</p>}
      {rules.error && <p className="error">{rules.error.message}</p>}

      <div className="list">
        {adding && (
          <NewRuleRow
            orgSlug={orgSlug}
            ticketTypeId={ticketTypeId!}
            onClose={() => setAdding(false)}
            onCreated={() => { rules.reload(); setAdding(false); }}
          />
        )}

        {items && items.length === 0 && !adding && (
          <p className="muted">
            No rules yet. The decisioning loop has nothing to retrieve until at
            least one rule exists.
          </p>
        )}

        {items?.map((r) => (
          <Link
            key={r.id}
            to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules/${r.id}`}
            className="list-row"
          >
            <span className="list-row-summary">
              <span className="mono">{r.rule_id}</span>
              <span className="sep-dot">·</span>
              <span style={{ fontWeight: 500 }}>
                {r.title || <span className="muted">(no title)</span>}
              </span>
              {r.decision_hint && (
                <>
                  <span className="sep-dot">·</span>
                  <span className={`status status-${r.decision_hint}`}>{r.decision_hint}</span>
                </>
              )}
              {r.price_delta && r.price_delta !== "0" && r.price_delta !== "0.00" && (
                <>
                  <span className="sep-dot">·</span>
                  <span className="list-row-meta">Δ {r.price_delta}</span>
                </>
              )}
            </span>
            <span className="muted small">Edit →</span>
          </Link>
        ))}
      </div>
    </>
  );
}

function NewRuleRow({
  orgSlug, ticketTypeId, onClose, onCreated,
}: {
  orgSlug: string;
  ticketTypeId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const navigate = useNavigate();
  const [ruleId, setRuleId] = useState("");

  const create = useMutation(async () => {
    const r = await api<AdminRule>(
      `/api/admin/ticket-types/${ticketTypeId}/rules/`,
      {
        method: "POST",
        orgSlug,
        body: {
          rule_id: ruleId.trim(),
          title: "",
          body: "Describe the rule, its conditions, and the decision it produces.",
          decision_hint: "escalate",
          price_delta: "0",
          post_actions: [],
          applies_when: {},
        },
      },
    );
    onCreated();
    navigate(`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules/${r.id}`);
    return r;
  });

  return (
    <div className="list-row-expanded">
      <div className="form-field">
        <label>Rule ID</label>
        <input
          type="text"
          value={ruleId}
          onChange={(e) => setRuleId(e.target.value)}
          placeholder="e.g. NSD-LOCK-001"
          autoFocus
          style={{ fontFamily: "var(--font-mono)" }}
        />
        <small className="help">
          Stable, unique within this ticket type. Cited by the LLM at decision time.
        </small>
      </div>

      <div className="row-actions">
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!ruleId.trim() || create.loading}
          onClick={() => create.call(undefined)}
        >
          {create.loading ? "Creating…" : "Create & edit"}
        </button>
      </div>
      {create.error && <p className="error">{create.error.message}</p>}
    </div>
  );
}

function unwrap<T>(v: Paginated<T> | T[] | null): T[] | null {
  if (v === null) return null;
  if (Array.isArray(v)) return v;
  return v.results;
}

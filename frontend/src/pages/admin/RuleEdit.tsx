// Admin → Ticket type → Rule edit.
//
// What the user actually changes when they open this page:
//   - The rule's body (the markdown the LLM reads on retrieval)
//   - The applies_when conditions (the structured gate)
//   - The decision the rule produces
// Everything else is rarely edited and lives behind "Show advanced".
//
// Layout:
//   - Title is an inline-editable H1; rule_id sits below as mono identifier.
//   - Decision is a clickable status pill (cycles approve → reject → escalate).
//   - Body markdown + applies_when builder are the two core sections.
//   - Advanced (category, subcategory, price delta, post-actions) is a
//     single disclosure at the bottom of the form.
//   - Save appears only when dirty; Delete sits top-right with confirm().

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminRule, AdminTicketType } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";
import AppliesWhenBuilder from "../../components/AppliesWhenBuilder";
import MarkdownPreview from "../../components/MarkdownPreview";

type Form = {
  title: string;
  body: string;
  decision_hint: AdminRule["decision_hint"];
  price_delta: string;
  post_actions_text: string;
  applies_when: Record<string, unknown>;
  category: string;
  subcategory: string;
};

function toForm(r: AdminRule): Form {
  return {
    title: r.title,
    body: r.body,
    decision_hint: r.decision_hint,
    price_delta: r.price_delta,
    post_actions_text: r.post_actions.join("\n"),
    applies_when: (r.applies_when as Record<string, unknown>) ?? {},
    category: r.category,
    subcategory: r.subcategory,
  };
}

function formsEqual(a: Form, b: Form): boolean {
  return (
    a.title === b.title &&
    a.body === b.body &&
    a.decision_hint === b.decision_hint &&
    a.price_delta === b.price_delta &&
    a.post_actions_text === b.post_actions_text &&
    a.category === b.category &&
    a.subcategory === b.subcategory &&
    JSON.stringify(a.applies_when) === JSON.stringify(b.applies_when)
  );
}

export default function RuleEdit() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const { ticketTypeId, ruleId } = useParams<{ ticketTypeId: string; ruleId: string }>();
  const path = `/api/admin/ticket-types/${ticketTypeId}/rules/${ruleId}/`;
  const ruleState = useApi<AdminRule>(path, { orgSlug });

  // Parent ticket type → field names for AppliesWhenBuilder autocomplete.
  const ttState = useApi<AdminTicketType>(
    `/api/admin/ticket-types/${ticketTypeId}/`,
    { orgSlug },
  );

  const [form, setForm] = useState<Form | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Hydrate form when rule loads.
  useEffect(() => {
    if (!ruleState.data || form !== null) return;
    setForm(toForm(ruleState.data));
  }, [ruleState.data, form]);

  const dirty = ruleState.data && form ? !formsEqual(form, toForm(ruleState.data)) : false;

  const save = useMutation(async () => {
    if (!form) return null;
    const out = await api<AdminRule>(path, {
      method: "PATCH",
      orgSlug,
      body: {
        title: form.title,
        body: form.body,
        decision_hint: form.decision_hint,
        price_delta: form.price_delta,
        post_actions: form.post_actions_text
          .split("\n").map((s) => s.trim()).filter(Boolean),
        applies_when: form.applies_when,
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

  if (ruleState.loading) return <p className="muted">Loading rule…</p>;
  if (ruleState.error) return <p className="error">{ruleState.error.message}</p>;
  if (!ruleState.data || !form) return null;
  const rule = ruleState.data;

  return (
    <>
      <header className="page-header">
        <div style={{ display: "grid", gap: "var(--space-2)", flex: 1, minWidth: 0 }}>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Rule title"
            style={{
              fontSize: "30px",
              fontWeight: 500,
              padding: "2px 4px",
              margin: "-2px -4px",
              border: "1px solid transparent",
              borderRadius: "var(--radius-md)",
              letterSpacing: "-0.015em",
              background: "transparent",
              lineHeight: 1.2,
            }}
          />
          <div className="ticket-meta">
            <code>{rule.rule_id}</code>
            <span className="sep-dot">·</span>
            <DecisionToggle
              value={form.decision_hint}
              onChange={(v) => setForm({ ...form, decision_hint: v })}
            />
          </div>
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-start" }}>
          <button
            type="button"
            className="btn-danger"
            disabled={del.loading}
            onClick={() => {
              if (window.confirm(`Delete rule ${rule.rule_id}?`)) del.call(undefined);
            }}
          >
            Delete
          </button>
          {dirty && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={save.loading}
              onClick={() => save.call(undefined).catch(() => undefined)}
            >
              {save.loading ? "Saving…" : "Save"}
            </button>
          )}
        </div>
      </header>

      <section className="section">
        <div className="section-head">
          <h3>Body</h3>
          <span className="muted small">Markdown — what the LLM reads when this rule is retrieved.</span>
        </div>
        <div className="md-split">
          <textarea
            rows={14}
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            placeholder="## Rule&#10;&#10;Describe the rule and its conditions in plain language.&#10;&#10;## Decision&#10;&#10;..."
          />
          <div className="md-preview-pane">
            <MarkdownPreview source={form.body} />
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h3>Conditions</h3>
          <span className="muted small">All rows must match the request payload for this rule to apply.</span>
        </div>
        <AppliesWhenBuilder
          value={form.applies_when}
          onChange={(applies_when) => setForm({ ...form, applies_when })}
          knownFieldNames={ttState.data?.fields.map((f) => f.name) ?? []}
        />
      </section>

      <section className="section">
        <button
          type="button"
          className="disclosure"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? "▾" : "▸"} {showAdvanced ? "Hide" : "Show"} advanced
        </button>
        {showAdvanced && (
          <div className="disclosure-panel">
            <div className="grid-two">
              <div className="form-field">
                <label>Price delta</label>
                <input
                  type="text"
                  value={form.price_delta}
                  onChange={(e) => setForm({ ...form, price_delta: e.target.value })}
                  placeholder="0"
                />
              </div>
              <div className="form-field">
                <label>Category</label>
                <input
                  type="text"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </div>
            </div>
            <div className="form-field">
              <label>Subcategory</label>
              <input
                type="text"
                value={form.subcategory}
                onChange={(e) => setForm({ ...form, subcategory: e.target.value })}
              />
            </div>
            <div className="form-field">
              <label>Post-actions (one per line)</label>
              <textarea
                rows={3}
                value={form.post_actions_text}
                onChange={(e) => setForm({ ...form, post_actions_text: e.target.value })}
                placeholder="e.g. Notify #sales-ops"
              />
            </div>
          </div>
        )}
      </section>

      {save.error && <p className="error">{save.error.message}</p>}
    </>
  );
}

/** Cycles approve → reject → escalate when clicked. Renders as a status pill
 *  matching the decision colour. */
function DecisionToggle({
  value, onChange,
}: {
  value: AdminRule["decision_hint"];
  onChange: (v: AdminRule["decision_hint"]) => void;
}) {
  const order: AdminRule["decision_hint"][] = ["approve", "reject", "escalate"];
  const next = () => {
    const i = order.indexOf(value);
    onChange(order[(i + 1) % order.length] ?? "escalate");
  };
  return (
    <button
      type="button"
      className={`status status-${value || "open"}`}
      style={{ cursor: "pointer", border: "none", padding: "2px 8px" }}
      onClick={next}
      title="Click to cycle decision"
    >
      {value || "—"}
    </button>
  );
}

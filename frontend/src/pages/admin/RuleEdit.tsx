// Admin → Ticket type → Rule edit.
//
// Body editor is a plain <textarea> for v0 — markdown-aware editor (Lexical,
// CodeMirror) is a polish pass. `applies_when` is a JSON textarea — works,
// not pretty. A visual rule-builder is the long-tail UX win.

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminRule, AdminTicketType } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";
import AppliesWhenBuilder from "../../components/AppliesWhenBuilder";
import MarkdownPreview from "../../components/MarkdownPreview";

export default function RuleEdit() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const { ticketTypeId, ruleId } = useParams<{ ticketTypeId: string; ruleId: string }>();
  const path = `/api/admin/ticket-types/${ticketTypeId}/rules/${ruleId}/`;
  const ruleState = useApi<AdminRule>(path, { orgSlug });

  // Fetch the parent ticket type so the AppliesWhenBuilder can offer
  // its actual field names as autocomplete (admins don't have to type the
  // payload key names from memory, and they can't typo them silently).
  const ttState = useApi<AdminTicketType>(
    `/api/admin/ticket-types/${ticketTypeId}/`,
    { orgSlug },
  );

  const [form, setForm] = useState<{
    title: string;
    body: string;
    decision_hint: AdminRule["decision_hint"];
    price_delta: string;
    post_actions_text: string;
    applies_when: Record<string, unknown>;
    category: string;
    subcategory: string;
  } | null>(null);

  // Hydrate the form when the rule loads.
  useEffect(() => {
    if (!ruleState.data || form !== null) return;
    setForm({
      title: ruleState.data.title,
      body: ruleState.data.body,
      decision_hint: ruleState.data.decision_hint,
      price_delta: ruleState.data.price_delta,
      post_actions_text: ruleState.data.post_actions.join("\n"),
      applies_when: (ruleState.data.applies_when as Record<string, unknown>) ?? {},
      category: ruleState.data.category,
      subcategory: ruleState.data.subcategory,
    });
  }, [ruleState.data, form]);

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
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
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

  if (ruleState.loading) return <p>Loading rule…</p>;
  if (ruleState.error) return <p className="error">{ruleState.error.message}</p>;
  if (!ruleState.data || !form) return null;

  return (
    <section className="page-admin-rule-edit">
      <header className="page-header">
        <div>
          <h1>Rule <code>{ruleState.data.rule_id}</code></h1>
          <p className="muted">
            <Link to={`/o/${orgSlug}/admin/ticket-types/${ticketTypeId}/rules`}>
              ← Back to rules
            </Link>
          </p>
        </div>
        <button
          type="button"
          className="btn btn-reject"
          disabled={del.loading}
          onClick={() => {
            if (window.confirm(`Delete rule ${ruleState.data!.rule_id}?`)) {
              del.call(undefined);
            }
          }}
        >
          Delete rule
        </button>
      </header>

      <div className="card">
        <div className="form-field">
          <label>Title</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Short human-readable title"
          />
        </div>

        <div className="form-field">
          <label>Body (markdown — what the LLM sees)</label>
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
          <small className="help">
            Left: source. Right: rendered preview. This is the text the LLM
            reads when retrieving this rule. The decisioning service also
            enforces the structured <code>applies_when</code> block below —
            both must agree.
          </small>
        </div>

        <div className="grid-two">
          <div className="form-field">
            <label>Decision</label>
            <select
              value={form.decision_hint}
              onChange={(e) =>
                setForm({ ...form, decision_hint: e.target.value as AdminRule["decision_hint"] })
              }
            >
              <option value="">—</option>
              <option value="approve">approve</option>
              <option value="reject">reject</option>
              <option value="escalate">escalate</option>
            </select>
          </div>
          <div className="form-field">
            <label>Price delta</label>
            <input
              type="text"
              value={form.price_delta}
              onChange={(e) => setForm({ ...form, price_delta: e.target.value })}
              placeholder="0"
            />
          </div>
        </div>

        <div className="grid-two">
          <div className="form-field">
            <label>Category</label>
            <input
              type="text"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
          </div>
          <div className="form-field">
            <label>Subcategory</label>
            <input
              type="text"
              value={form.subcategory}
              onChange={(e) => setForm({ ...form, subcategory: e.target.value })}
            />
          </div>
        </div>

        <div className="form-field">
          <label>Post-actions (one per line)</label>
          <textarea
            rows={3}
            value={form.post_actions_text}
            onChange={(e) => setForm({ ...form, post_actions_text: e.target.value })}
            placeholder="Manual selection in Sc-Pro"
          />
        </div>

        <div className="form-field">
          <label>applies_when — structured conditions</label>
          <AppliesWhenBuilder
            value={form.applies_when}
            onChange={(applies_when) => setForm({ ...form, applies_when })}
            knownFieldNames={ttState.data?.fields.map((f) => f.name) ?? []}
          />
          <small className="help">
            Each row is checked at decision time. ALL rows must match the
            request payload for this rule to apply. Field dropdown is
            populated from this ticket type's schema fields.
          </small>
        </div>

        <div className="btn-row">
          <button
            type="button"
            className="btn btn-primary"
            disabled={save.loading}
            onClick={() => save.call(undefined).catch(() => undefined)}
          >
            {save.loading ? "Saving…" : "Save rule"}
          </button>
          {save.error && <span className="error">{save.error.message}</span>}
        </div>
      </div>
    </section>
  );
}

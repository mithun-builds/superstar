// Admin → Ticket types list.
// Shows every ticket type the org owns, lets admin create new ones or
// drill into an existing one.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminTicketType, Paginated } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function TicketTypeList() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const list = useApi<Paginated<AdminTicketType> | AdminTicketType[]>(
    "/api/admin/ticket-types/",
    { orgSlug },
  );

  const [draft, setDraft] = useState<{ identifier: string; display_name: string } | null>(null);

  const create = useMutation(async (input: { identifier: string; display_name: string }) => {
    const t = await api<AdminTicketType>("/api/admin/ticket-types/", {
      method: "POST",
      orgSlug,
      body: { ...input, is_active: true },
    });
    setDraft(null);
    navigate(`/o/${orgSlug}/admin/ticket-types/${t.id}`);
    return t;
  });

  const items = unwrap(list.data);

  return (
    <section className="page-admin-list">
      <header className="page-header">
        <h1 className="display-heading">Ticket types</h1>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setDraft({ identifier: "", display_name: "" })}
        >
          + New ticket type
        </button>
      </header>

      {list.loading && <p>Loading…</p>}
      {list.error && (
        <p className="error">Couldn't load: {list.error.message}</p>
      )}

      {draft && (
        <div className="card">
          <h3>New ticket type</h3>
          <p className="muted">
            Identifier is the stable key cited in tickets and audit logs.
            Conventional shape: <code>&lt;tenant&gt;.&lt;usecase&gt;</code> — e.g.{" "}
            <code>homelane.nonstandard</code>. Cannot contain spaces or uppercase.
          </p>
          <div className="form-field">
            <label>Identifier</label>
            <input
              type="text"
              value={draft.identifier}
              onChange={(e) => setDraft({ ...draft, identifier: e.target.value })}
              placeholder="acme.access-request"
            />
          </div>
          <div className="form-field">
            <label>Display name</label>
            <input
              type="text"
              value={draft.display_name}
              onChange={(e) => setDraft({ ...draft, display_name: e.target.value })}
              placeholder="Access request"
            />
          </div>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={!draft.identifier || !draft.display_name || create.loading}
              onClick={() => create.call(draft)}
            >
              {create.loading ? "Creating…" : "Create"}
            </button>
            <button type="button" className="btn" onClick={() => setDraft(null)}>
              Cancel
            </button>
          </div>
          {create.error && (
            <pre className="error-block">
              {create.error.message}
              {"body" in (create.error as object) &&
                "\n" + JSON.stringify((create.error as { body: unknown }).body, null, 2)}
            </pre>
          )}
        </div>
      )}

      {items && items.length === 0 && !draft && (
        <p className="muted">
          No ticket types yet. Click <strong>+ New ticket type</strong> to
          create the first one. Configure schema fields, approval workflow,
          AI policy, and KB rules from the edit screen.
        </p>
      )}

      {items && items.length > 0 && (
        <table className="ticket-table">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Display name</th>
              <th>Fields / Stages</th>
              <th>AI</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link to={`/o/${orgSlug}/admin/ticket-types/${t.id}`}>
                    <code>{t.identifier}</code>
                  </Link>
                </td>
                <td>{t.display_name}</td>
                <td>
                  {t.fields.length} fields / {t.workflow_stages.length} stages
                </td>
                <td>
                  {t.ai_enabled ? (
                    <span className={`status status-${t.shadow_mode ? "escalated" : "approved"}`}>
                      {t.shadow_mode ? "shadow" : "live"}
                    </span>
                  ) : (
                    <span className="status status-closed">off</span>
                  )}
                </td>
                <td>{t.is_active ? "✓" : "—"}</td>
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

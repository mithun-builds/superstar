// Admin → Teams list.
// Lists this org's approver teams + inline-creates new ones. Team slug is
// what WorkflowStage.approvers references, so slug stability matters.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminTeam, Paginated } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function TeamList() {
  const orgSlug = useOrgRequired();
  const navigate = useNavigate();
  const list = useApi<Paginated<AdminTeam> | AdminTeam[]>(
    "/api/admin/teams/",
    { orgSlug },
  );

  const [draft, setDraft] = useState<{ slug: string; name: string } | null>(null);

  const create = useMutation(async () => {
    if (!draft) throw new Error("no draft");
    const t = await api<AdminTeam>("/api/admin/teams/", {
      method: "POST",
      orgSlug,
      body: { slug: draft.slug.trim(), name: draft.name.trim(), description: "" },
    });
    setDraft(null);
    navigate(`/o/${orgSlug}/admin/teams/${t.id}`);
    return t;
  });

  const items = unwrap(list.data);

  return (
    <section className="page-admin-list">
      <header className="page-header">
        <h1>Teams</h1>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setDraft({ slug: "", name: "" })}
        >
          + New team
        </button>
      </header>

      {list.loading && <p>Loading…</p>}
      {list.error && <p className="error">{list.error.message}</p>}

      {draft && (
        <div className="card">
          <h3>New team</h3>
          <p className="muted">
            The <strong>slug</strong> is what workflow stages reference. It must be
            unique within this org and contain only lowercase letters, digits,
            and dashes (e.g. <code>security-review</code>, <code>design-head</code>).
          </p>
          <div className="form-field">
            <label>Slug</label>
            <input
              type="text"
              value={draft.slug}
              onChange={(e) => setDraft({ ...draft, slug: e.target.value })}
              placeholder="security-review"
            />
          </div>
          <div className="form-field">
            <label>Display name</label>
            <input
              type="text"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="Security Review Team"
            />
          </div>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={!draft.slug || !draft.name || create.loading}
              onClick={() => create.call(undefined)}
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
          No teams yet. Workflow stages reference teams by slug — without any
          teams configured, only org owners and admins can decide stages.
          Click <strong>+ New team</strong> to set up your first one.
        </p>
      )}

      {items && items.length > 0 && (
        <table className="ticket-table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Name</th>
              <th>Members</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link to={`/o/${orgSlug}/admin/teams/${t.id}`}>
                    <code>{t.slug}</code>
                  </Link>
                </td>
                <td>{t.name}</td>
                <td>{t.member_count}</td>
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

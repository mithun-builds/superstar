// Admin → Teams list.
//
// Lists this org's approver teams + inline-creates new ones. Team slug is
// what WorkflowStage.approvers references, so slug stability matters.
//
// Layout follows the TicketTypeEdit pattern:
//   - Teams render as one-line list rows (slug · name · member count).
//   - "New team" expands an inline create form at the top of the list
//     instead of opening a modal or jumping to a separate page.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { AdminTeam, Paginated } from "../../api/types";
import { useOrgRequired } from "../../contexts/OrgContext";

export default function TeamList() {
  const orgSlug = useOrgRequired();
  const list = useApi<Paginated<AdminTeam> | AdminTeam[]>(
    "/api/admin/teams/",
    { orgSlug },
  );
  const [adding, setAdding] = useState(false);
  const items = unwrap(list.data);

  return (
    <>
      <header className="page-header">
        <h1 className="display-heading">Teams</h1>
        {!adding && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setAdding(true)}
          >
            New team
          </button>
        )}
      </header>

      {list.loading && <p className="muted">Loading…</p>}
      {list.error && <p className="error">{list.error.message}</p>}

      <div className="list">
        {adding && (
          <NewTeamRow
            orgSlug={orgSlug}
            onClose={() => setAdding(false)}
            onCreated={() => { list.reload(); setAdding(false); }}
          />
        )}

        {items && items.length === 0 && !adding && (
          <p className="muted">
            No teams yet. Stages reference teams by slug — without any teams,
            only org owners and admins can decide stages.
          </p>
        )}

        {items?.map((t) => (
          <Link
            key={t.id}
            to={`/o/${orgSlug}/admin/teams/${t.id}`}
            className="list-row"
            style={{ borderBottom: undefined }}
          >
            <span className="list-row-summary">
              <span className="mono">{t.slug}</span>
              <span className="sep-dot">·</span>
              <span style={{ fontWeight: 500 }}>{t.name}</span>
              <span className="sep-dot">·</span>
              <span className="list-row-meta">
                {t.member_count} member{t.member_count === 1 ? "" : "s"}
              </span>
            </span>
            <span className="muted small">Edit →</span>
          </Link>
        ))}
      </div>
    </>
  );
}

function NewTeamRow({
  orgSlug, onClose, onCreated,
}: {
  orgSlug: string;
  onClose: () => void;
  onCreated: (t: AdminTeam) => void;
}) {
  const navigate = useNavigate();
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");

  const create = useMutation(async () => {
    const t = await api<AdminTeam>("/api/admin/teams/", {
      method: "POST",
      orgSlug,
      body: { slug: slug.trim(), name: name.trim(), description: "" },
    });
    onCreated(t);
    navigate(`/o/${orgSlug}/admin/teams/${t.id}`);
    return t;
  });

  return (
    <div className="list-row-expanded">
      <div className="grid-two">
        <div className="form-field">
          <label>Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="security-review"
            autoFocus
          />
          <small className="help">
            Lowercase, digits, dashes. Workflow stages reference this — pick carefully.
          </small>
        </div>
        <div className="form-field">
          <label>Display name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Security Review"
          />
        </div>
      </div>

      <div className="row-actions">
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!slug.trim() || !name.trim() || create.loading}
          onClick={() => create.call(undefined)}
        >
          {create.loading ? "Creating…" : "Create team"}
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
  );
}

function unwrap<T>(v: Paginated<T> | T[] | null): T[] | null {
  if (v === null) return null;
  if (Array.isArray(v)) return v;
  return v.results;
}

// Admin → Workspaces (cross-tenant).
//
// Superuser-only — lists every workspace on the deployment, with a
// "New workspace" inline expander (mirrors the CLI `python manage.py
// create_tenant` flow) and inline Edit for renaming a workspace's
// display name.
//
// Lives at the top-level route `/admin/workspaces` because managing
// the list of tenants is conceptually above any one tenant. The slug
// is intentionally NOT editable: it appears in every URL the workspace
// users have bookmarked and in historical audit-log entries; changing
// it would silently break both.
//
// Naming note: the data model calls this an Org and the API keeps that
// name (/api/platform/orgs/). Everything customer-facing uses the word
// "workspace" — see docs/brand.md.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { useApi, useMutation } from "../../api/hooks";
import type { Me, PlatformOrg } from "../../api/types";

export default function PlatformOrgList() {
  const me = useApi<Me>("/api/me/");
  const list = useApi<PlatformOrg[]>("/api/platform/orgs/");
  const [adding, setAdding] = useState(false);

  // Friendly client-side gate; the API enforces it server-side too.
  if (me.loading) return <p className="muted">Loading…</p>;
  if (me.data && !me.data.is_superuser) {
    return (
      <>
        <header className="page-header">
          <h1>Workspaces</h1>
        </header>
        <p className="muted">
          Managing the list of workspaces is limited to Superstar superusers.
          Ask whoever runs your deployment if you need a new one.
        </p>
      </>
    );
  }

  return (
    <>
      <header className="page-header">
        <h1 className="display-heading">Workspaces</h1>
        {!adding && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setAdding(true)}
          >
            New workspace
          </button>
        )}
      </header>

      {list.loading && <p className="muted">Loading…</p>}
      {list.error && <p className="error">{list.error.message}</p>}

      <div className="list">
        {adding && (
          <NewWorkspaceRow
            onClose={() => setAdding(false)}
            onCreated={() => { list.reload(); setAdding(false); }}
          />
        )}

        {list.data && list.data.length === 0 && !adding && (
          <p className="muted">
            No workspaces on this deployment yet. Click{" "}
            <strong>New workspace</strong> to create the first one.
          </p>
        )}

        {list.data?.map((org) => (
          <WorkspaceRow
            key={org.id}
            org={org}
            onChanged={() => list.reload()}
          />
        ))}
      </div>
    </>
  );
}

function WorkspaceRow({
  org, onChanged,
}: {
  org: PlatformOrg;
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);

  const del = useMutation(async () => {
    await api(`/api/platform/orgs/${org.id}/`, { method: "DELETE" });
    onChanged();
  });

  if (editing) {
    return (
      <EditWorkspaceRow
        org={org}
        onClose={() => setEditing(false)}
        onSaved={() => { onChanged(); setEditing(false); }}
      />
    );
  }

  return (
    <div className="list-row" style={{ cursor: "default" }}>
      <span className="list-row-summary">
        <span className="mono">{org.slug}</span>
        <span className="sep-dot">·</span>
        <span style={{ fontWeight: 500 }}>{org.name}</span>
        <span className="sep-dot">·</span>
        <span className="list-row-meta">
          {org.member_count} member{org.member_count === 1 ? "" : "s"}
        </span>
        {org.owner_emails.length > 0 && (
          <>
            <span className="sep-dot">·</span>
            <span className="list-row-meta">{org.owner_emails.join(", ")}</span>
          </>
        )}
      </span>
      <span style={{ display: "flex", gap: "var(--space-2)" }}>
        <button
          type="button"
          className="btn-quiet"
          onClick={() => navigate(`/o/${org.slug}`)}
        >
          Open →
        </button>
        <button
          type="button"
          className="btn-quiet"
          onClick={() => setEditing(true)}
        >
          Rename
        </button>
        <button
          type="button"
          className="btn-danger"
          disabled={del.loading}
          onClick={() => {
            if (window.confirm(
              `Delete workspace "${org.slug}"? This permanently removes its ticket types, rules, tickets, teams, and decisions. The action can't be undone.`,
            )) {
              del.call(undefined);
            }
          }}
        >
          Delete
        </button>
      </span>
    </div>
  );
}

function EditWorkspaceRow({
  org, onClose, onSaved,
}: {
  org: PlatformOrg;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(org.name);

  const save = useMutation(async () => {
    await api<PlatformOrg>(`/api/platform/orgs/${org.id}/`, {
      method: "PATCH",
      body: { name: name.trim() },
    });
    onSaved();
  });

  const fieldErrors: Record<string, string> = (() => {
    const e = save.error;
    if (!(e instanceof ApiError) || typeof e.body !== "object" || e.body === null) return {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(e.body as Record<string, unknown>)) {
      out[k] = Array.isArray(v) ? String(v[0]) : String(v);
    }
    return out;
  })();

  return (
    <div className="list-row-expanded">
      <div className="grid-two">
        <div className="form-field">
          <label>Slug</label>
          <input
            type="text"
            value={org.slug}
            disabled
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <small className="help">
            Slug is immutable — it's in every URL the workspace's users have
            bookmarked. Create a new workspace if you need a different slug.
          </small>
        </div>
        <div className="form-field">
          <label>Display name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          {fieldErrors.name && <small className="error">{fieldErrors.name}</small>}
        </div>
      </div>

      <div className="row-actions">
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!name.trim() || name.trim() === org.name || save.loading}
          onClick={() => save.call(undefined).catch(() => undefined)}
        >
          {save.loading ? "Saving…" : "Save"}
        </button>
      </div>
      {save.error && !Object.keys(fieldErrors).length && (
        <p className="error">{save.error.message}</p>
      )}
    </div>
  );
}

function NewWorkspaceRow({
  onClose, onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");

  const create = useMutation(async () => {
    await api<PlatformOrg>("/api/platform/orgs/", {
      method: "POST",
      body: {
        slug: slug.trim(),
        name: name.trim(),
        owner_email: ownerEmail.trim() || undefined,
        owner_password: ownerPassword || undefined,
      },
    });
    onCreated();
  });

  // Pretty-print the validation errors the backend returns. With ApiError
  // we get a structured body like { slug: ["…"], owner_password: ["…"] }.
  const fieldErrors: Record<string, string> = (() => {
    const e = create.error;
    if (!(e instanceof ApiError) || typeof e.body !== "object" || e.body === null) return {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(e.body as Record<string, unknown>)) {
      out[k] = Array.isArray(v) ? String(v[0]) : String(v);
    }
    return out;
  })();

  return (
    <div className="list-row-expanded">
      <div className="grid-two">
        <div className="form-field">
          <label>Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="acme"
            autoFocus
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <small className="help">
            Lowercase, digits, dashes. URL-safe — appears in /o/&lt;slug&gt;/
            and can't be changed later.
          </small>
          {fieldErrors.slug && <small className="error">{fieldErrors.slug}</small>}
        </div>
        <div className="form-field">
          <label>Display name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Acme Inc."
          />
          {fieldErrors.name && <small className="error">{fieldErrors.name}</small>}
        </div>
      </div>

      <div className="grid-two">
        <div className="form-field">
          <label>Owner email<span className="optional-mark"> (optional)</span></label>
          <input
            type="email"
            value={ownerEmail}
            onChange={(e) => setOwnerEmail(e.target.value)}
            placeholder="founder@acme.test"
          />
          <small className="help">
            If empty, the workspace starts with no members and you'll add
            memberships manually. If set and the email already has an
            account, that user becomes the owner.
          </small>
          {fieldErrors.owner_email && <small className="error">{fieldErrors.owner_email}</small>}
        </div>
        <div className="form-field">
          <label>
            Owner password
            <span className="optional-mark"> (new users only)</span>
          </label>
          <input
            type="password"
            value={ownerPassword}
            onChange={(e) => setOwnerPassword(e.target.value)}
            placeholder="•••••••"
            autoComplete="new-password"
          />
          <small className="help">
            Required only if the email isn't an existing user.
          </small>
          {fieldErrors.owner_password && (
            <small className="error">{fieldErrors.owner_password}</small>
          )}
        </div>
      </div>

      <div className="row-actions">
        <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!slug.trim() || !name.trim() || create.loading}
          onClick={() => create.call(undefined).catch(() => undefined)}
        >
          {create.loading ? "Creating…" : "Create workspace"}
        </button>
      </div>
      {create.error && !Object.keys(fieldErrors).length && (
        <p className="error">{create.error.message}</p>
      )}
    </div>
  );
}

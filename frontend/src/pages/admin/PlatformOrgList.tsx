// Admin → Platform → Orgs.
//
// Superuser-only — lists every tenant on the deployment, with a "New org"
// inline expander that mirrors the CLI `python manage.py create_tenant`
// flow: slug + display name, plus optional owner email + password.
//
// Layout matches TeamList + RuleList: each org renders as a one-line
// list-row (slug · name · N members · owner@email), and the create form
// expands at the top instead of opening a modal.

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
          <h1>Platform</h1>
        </header>
        <p className="muted">
          Platform-level actions (create / delete tenants) are limited to
          superusers. Ask the Superstar operator if you need a new org.
        </p>
      </>
    );
  }

  return (
    <>
      <header className="page-header">
        <h1 className="display-heading">Orgs</h1>
        {!adding && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setAdding(true)}
          >
            New org
          </button>
        )}
      </header>

      {list.loading && <p className="muted">Loading…</p>}
      {list.error && <p className="error">{list.error.message}</p>}

      <div className="list">
        {adding && (
          <NewOrgRow
            onClose={() => setAdding(false)}
            onCreated={() => { list.reload(); setAdding(false); }}
          />
        )}

        {list.data && list.data.length === 0 && !adding && (
          <p className="muted">
            No orgs on this deployment yet. Click <strong>New org</strong>{" "}
            to create the first one.
          </p>
        )}

        {list.data?.map((org) => (
          <OrgRow
            key={org.id}
            org={org}
            onDeleted={() => list.reload()}
          />
        ))}
      </div>
    </>
  );
}

function OrgRow({
  org, onDeleted,
}: {
  org: PlatformOrg;
  onDeleted: () => void;
}) {
  const navigate = useNavigate();
  const del = useMutation(async () => {
    await api(`/api/platform/orgs/${org.id}/`, { method: "DELETE" });
    onDeleted();
  });

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
          className="btn-danger"
          disabled={del.loading}
          onClick={() => {
            if (window.confirm(
              `Delete org "${org.slug}"? This permanently removes its ticket types, rules, tickets, teams, and decisions. The action can't be undone.`,
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

function NewOrgRow({
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
            Lowercase, digits, dashes. URL-safe — appears in /o/&lt;slug&gt;/.
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
            If empty, the org has no members and you'll need to add memberships
            manually. If set and the email matches an existing user, that user
            becomes the owner.
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
          {create.loading ? "Creating…" : "Create org"}
        </button>
      </div>
      {create.error && !Object.keys(fieldErrors).length && (
        <p className="error">{create.error.message}</p>
      )}
    </div>
  );
}

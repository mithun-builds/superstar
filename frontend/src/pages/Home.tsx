// Org picker — the first thing a user sees after signing in.
//
// Most users belong to exactly one org and will single-click straight
// through. Multi-org users (consultants / platform admins) actually use
// the picker. The layout is built for the click-through case but stays
// readable when there are 5+ tiles.
//
// The "not signed in" branch lands here when /api/me/ returns 403. We
// don't try to render an error — we just point at Django's login.

import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me, OrgMembership } from "../api/types";

export default function Home() {
  const { data: me, loading, error } = useApi<Me>("/api/me/");

  if (loading) return <p className="muted">Loading…</p>;
  if (error) return <SignInPrompt />;
  if (!me) return null;

  return (
    <>
      <header className="page-header">
        <div style={{ display: "grid", gap: "var(--space-2)" }}>
          <h1>Pick a workspace</h1>
          <p className="muted" style={{ margin: 0 }}>
            Signed in as <strong style={{ color: "var(--ink-900)", fontWeight: 500 }}>
              {me.full_name || me.email}
            </strong>
            . <a href="/admin/logout/?next=/" style={{ borderBottom: "1px solid var(--ink-300)" }}>Sign out</a>
          </p>
        </div>
      </header>

      {me.memberships.length === 0 ? (
        <EmptyState email={me.email} />
      ) : (
        <ul className="org-list">
          {me.memberships.map((m) => (
            <li key={m.id}>
              <OrgTile membership={m} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function OrgTile({ membership: m }: { membership: OrgMembership }) {
  const letter = (m.org_name || m.org_slug || "?").charAt(0).toUpperCase();
  return (
    <Link to={`/o/${m.org_slug}`} className="org-tile">
      <span className="org-tile-avatar" aria-hidden="true">{letter}</span>
      <span className="org-tile-body">
        <span className="org-tile-name">{m.org_name}</span>
        <span className="org-tile-meta">
          <code>{m.org_slug}</code>
          <span className="sep-dot">·</span>
          <span>{m.role}</span>
        </span>
      </span>
      <span className="org-tile-arrow" aria-hidden="true">→</span>
    </Link>
  );
}

function EmptyState({ email }: { email: string }) {
  return (
    <section className="empty-state">
      <p className="muted">
        You're signed in, but you're not a member of any org yet. Ask a
        platform admin to add you, or bootstrap an org from the command line:
      </p>
      <pre>
        python manage.py create_tenant \{"\n"}
        {"  "}--slug acme --owner-email {email}
      </pre>
    </section>
  );
}

function SignInPrompt() {
  return (
    <section className="empty-state" style={{ textAlign: "center", padding: "var(--space-12) var(--space-6)" }}>
      <h1 style={{ marginBottom: "var(--space-3)" }}>Welcome to SuperStar</h1>
      <p className="muted" style={{ marginBottom: "var(--space-6)" }}>
        You'll need to sign in to continue.
      </p>
      <a href="/admin/login/?next=/" className="btn btn-primary">Sign in</a>
    </section>
  );
}

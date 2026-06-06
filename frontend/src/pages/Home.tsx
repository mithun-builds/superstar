// Home — the first thing a user sees after signing in. Doubles as the
// unauthenticated landing: if /api/me/ 403s we render an inline sign-in
// form (no bounce to Django admin) on top of a branded hero.
//
// Signed-in routing:
//   - 0 workspaces       → empty state with create / ask-to-be-added CTA
//   - 1 workspace, regular user
//                        → auto-redirect to /o/<slug>. The picker would
//                          just be a one-item list with no real choice.
//   - 1 workspace, superuser
//                        → stay on the picker so the "Manage workspaces"
//                          link is reachable. Superusers operate across
//                          tenants — losing access to that affordance
//                          behind a URL-bar trip would be hostile.
//   - 2+ workspaces      → workspace picker.
//
// The brand voice ("Hello, <firstname>.") follows docs/brand.md — warm,
// confident, honest. Workspace = Org in code/URLs; we say "workspace" in
// every customer-facing string.

import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useApi } from "../api/hooks";
import type { Me, OrgMembership } from "../api/types";

export default function Home() {
  const me = useApi<Me>("/api/me/");

  if (me.loading) return <p className="muted">Loading…</p>;
  if (me.error) return <Landing onSignedIn={() => me.reload()} />;
  if (!me.data) return null;
  const u = me.data;

  // Skip the picker for the common case (regular user, single workspace).
  // Superusers keep the picker so they retain the "Manage workspaces"
  // entry point.
  if (u.memberships.length === 1 && !u.is_superuser) {
    return <Navigate to={`/o/${u.memberships[0].org_slug}`} replace />;
  }

  // First-name greeting if we have one, otherwise the local-part of
  // the email — never "user". Matches the brand voice (task-app inspired).
  const firstName = (u.full_name || u.email.split("@")[0] || "there").split(/\s+/)[0];

  return (
    <>
      <header className="page-header" style={{ display: "grid", gap: "var(--space-2)" }}>
        <h1 className="greeting-line">
          Hello, <span className="name">{firstName}</span>.
        </h1>
        <p className="greeting-sub">
          {u.memberships.length === 0
            ? "You're not in any workspaces yet."
            : u.memberships.length === 1
            ? "Pick up where you left off."
            : "Choose a workspace to continue."}
        </p>
      </header>

      {u.memberships.length === 0 ? (
        <EmptyState email={u.email} isSuperuser={u.is_superuser} />
      ) : (
        <ul className="org-list">
          {u.memberships.map((m) => (
            <li key={m.id}>
              <OrgTile membership={m} />
            </li>
          ))}
        </ul>
      )}

      {/* Superuser-only: discoverable entry point to the cross-tenant
          admin. Lives below the list so it doesn't compete with workspace
          tiles, but is visible without scrolling. */}
      {u.is_superuser && u.memberships.length > 0 && (
        <p className="manage-workspaces-line">
          <Link to="/admin/workspaces">Manage all workspaces →</Link>
        </p>
      )}

      {/* Sign-out lives as a quiet line at the bottom of the page — it's
          a session action, not a navigation choice, so it doesn't belong
          competing with the workspace tiles. */}
      <p className="signout-line">
        Signed in as {u.full_name || u.email}. <SignOutLink />
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
// Landing — unauthenticated state
// ---------------------------------------------------------------------------
function Landing({ onSignedIn }: { onSignedIn: () => void }) {
  return (
    <section className="landing">
      <div className="landing-hero">
        <div className="landing-brand">
          <img src="/logo.svg" alt="" className="landing-logo" aria-hidden="true" />
          <h1 className="landing-title">Superstar</h1>
        </div>
        <p className="landing-tagline">
          AI-native ticketing with grounded decisions.
        </p>
        <p className="landing-sub">
          Requests come in. The knowledge base decides most of them — citing
          the rules it used. The rest escalate to humans on configurable
          approval chains. Everything is auditable.
        </p>
      </div>
      <SignInCard onSignedIn={onSignedIn} />
    </section>
  );
}

function SignInCard({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api<Me>("/api/login/", {
        method: "POST",
        body: { email: email.trim(), password },
      });
      onSignedIn();
    } catch (e) {
      if (e instanceof ApiError) {
        const body = e.body as { detail?: string } | undefined;
        setError(body?.detail ?? `Sign-in failed (HTTP ${e.status}).`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="signin-card" onSubmit={handleSubmit}>
      <h2 className="signin-title">Sign in</h2>
      {/* No visible labels — the placeholder doubles as the label.
         aria-label keeps the input named for screen readers and tests. */}
      <input
        id="signin-email"
        type="email"
        autoComplete="email"
        placeholder="Email"
        aria-label="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoFocus
      />
      <input
        id="signin-password"
        type="password"
        autoComplete="current-password"
        placeholder="Password"
        aria-label="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <p className="error">{error}</p>}
      <button
        type="submit"
        className="btn btn-accent signin-submit"
        disabled={submitting || !email || !password}
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
      <p className="signin-note muted">
        No account? Ask whoever set up your Superstar workspace — accounts
        are provisioned per-workspace.
      </p>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Signed-in state — org picker
// ---------------------------------------------------------------------------
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

function EmptyState({ email, isSuperuser }: { email: string; isSuperuser: boolean }) {
  if (isSuperuser) {
    return (
      <section className="empty-state">
        <p className="muted">
          You're signed in as a Superstar superuser but aren't a member of
          any workspace yet. Create the first one (you can give yourself a
          membership after):
        </p>
        <p>
          <Link to="/admin/workspaces" className="btn btn-primary">
            Create a workspace
          </Link>
        </p>
      </section>
    );
  }
  return (
    <section className="empty-state">
      <p className="muted">
        You're signed in, but you're not a member of any workspace yet. Ask
        whoever runs your Superstar deployment to add you, or bootstrap one
        from the command line:
      </p>
      <pre>
        python manage.py create_tenant \{"\n"}
        {"  "}--slug acme --owner-email {email}
      </pre>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sign out
// ---------------------------------------------------------------------------
function SignOutLink() {
  const handleSignOut = async (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      await api("/api/logout/", { method: "POST" });
    } catch {
      // Logout endpoint is idempotent on the backend; reload regardless.
    }
    window.location.assign("/");
  };
  return (
    <a
      href="/api/logout/"
      onClick={handleSignOut}
      style={{ borderBottom: "1px solid var(--ink-300)" }}
    >
      Sign out
    </a>
  );
}

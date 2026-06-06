// Org picker — the first thing a user sees after signing in. Doubles as
// the unauthenticated landing: if /api/me/ 403s we render an inline sign-
// in form (no bounce to Django admin) on top of a branded hero.
//
// Three states the page renders:
//   - Loading           → quiet placeholder
//   - Not signed in     → branded landing with inline sign-in form
//   - Signed in         → "Pick a workspace" with org tiles
//
// The branded landing leans on the Superstar mark (red ticket + gold
// star) as the only visual flourish — everything else stays on the same
// minimal pattern as the rest of the app.

import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useApi } from "../api/hooks";
import type { Me, OrgMembership } from "../api/types";

export default function Home() {
  const me = useApi<Me>("/api/me/");

  if (me.loading) return <p className="muted">Loading…</p>;
  if (me.error) return <Landing onSignedIn={() => me.reload()} />;
  if (!me.data) return null;
  const u = me.data;

  return (
    <>
      <header className="page-header">
        <div style={{ display: "grid", gap: "var(--space-2)" }}>
          <h1>Pick a workspace</h1>
          <p className="muted" style={{ margin: 0 }}>
            Signed in as{" "}
            <strong style={{ color: "var(--ink-900)", fontWeight: 500 }}>
              {u.full_name || u.email}
            </strong>
            . <SignOutLink />
          </p>
        </div>
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
        No account? Ask your platform operator — accounts are provisioned
        per-tenant.
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
          You're signed in as a platform superuser but don't have any org
          memberships yet. Create the first tenant from the Platform admin
          (you can give yourself a membership later):
        </p>
        <p>
          <Link to="/o/_/admin/platform/orgs" className="btn btn-primary">
            Open Platform → Orgs
          </Link>
        </p>
      </section>
    );
  }
  return (
    <section className="empty-state">
      <p className="muted">
        You're signed in, but you're not a member of any org yet. Ask a
        platform admin to add you, or bootstrap one from the command line:
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

// Org picker. Shows the user's memberships; clicking one navigates into
// the tenant-scoped dashboard at /o/<slug>.

import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me } from "../api/types";

export default function Home() {
  const { data: me, loading, error } = useApi<Me>("/api/me/");

  if (loading) return <p>Loading…</p>;
  if (error) {
    return (
      <div className="error-block">
        <h2>Not signed in?</h2>
        <p>
          The API rejected the request. Sign in via{" "}
          <a href="/admin/login/?next=/">Django admin</a>, then return here.
        </p>
      </div>
    );
  }
  if (!me) return null;

  return (
    <section className="page-home">
      <h1>Hello, {me.full_name || me.email}</h1>
      {me.memberships.length === 0 ? (
        <p>
          You are not a member of any org yet. Ask a SuperStar admin to add you,
          or run <code>python manage.py create_tenant --slug … --owner-email {me.email}</code>.
        </p>
      ) : (
        <>
          <p>Pick an org to continue:</p>
          <ul className="org-list">
            {me.memberships.map((m) => (
              <li key={m.id}>
                <Link to={`/o/${m.org_slug}`} className="org-card">
                  <strong>{m.org_name}</strong>
                  <span className="org-slug">/o/{m.org_slug}</span>
                  <span className="org-role">role: {m.role}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

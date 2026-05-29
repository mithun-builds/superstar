// Shared chrome: header bar with brand, current org, sign-out (placeholder).

import { Link, Outlet } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me } from "../api/types";
import { useOrg } from "../contexts/OrgContext";

export default function Layout() {
  const slug = useOrg();
  const { data: me } = useApi<Me>("/api/me/");

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">SuperStar</Link>
        {slug && (
          <>
            <span className="sep">/</span>
            <Link to={`/o/${slug}`} className="org-pill">{slug}</Link>
            <nav className="header-nav">
              <Link to={`/o/${slug}`}>Tickets</Link>
              <Link to={`/o/${slug}/new`}>New ticket</Link>
              <Link to={`/o/${slug}/admin/ticket-types`}>Admin</Link>
            </nav>
          </>
        )}
        <div className="header-spacer" />
        {me && (
          <span className="user">
            {me.full_name || me.email}
            {me.is_superuser && <span className="badge">admin</span>}
          </span>
        )}
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

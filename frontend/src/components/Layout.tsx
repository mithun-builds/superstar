// Shared chrome: header bar with brand, current org, sign-out (placeholder).

import { Link, Outlet, useLocation } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me } from "../api/types";
import { useOrg } from "../contexts/OrgContext";

export default function Layout() {
  const slug = useOrg();
  const location = useLocation();
  const inAdmin = location.pathname.includes("/admin/");
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
      {slug && inAdmin && (
        <nav className="admin-subnav">
          <Link
            to={`/o/${slug}/admin/ticket-types`}
            className={location.pathname.includes("/admin/ticket-types") ? "active" : ""}
          >
            Ticket types
          </Link>
          <Link
            to={`/o/${slug}/admin/teams`}
            className={location.pathname.includes("/admin/teams") ? "active" : ""}
          >
            Teams
          </Link>
        </nav>
      )}
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

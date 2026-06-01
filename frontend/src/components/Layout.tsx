// Shared chrome: header, admin sub-nav, content container.
//
// Two container widths in play:
//   - .app-header-inner / .admin-subnav-inner / .app-main → max-content (740px)
//     by default, the reading width for forms/detail/admin pages.
//   - <main className="app-main wide"> → opt into max-wide (1040px) for
//     table-heavy pages (Tickets list, ticket types list).
// The list pages set `wide` themselves via useEffect, not done here so
// chrome stays dumb.

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
        <div className="app-header-inner">
          <Link to="/" className="brand">
            <img src="/logo.svg" alt="" className="brand-logo" aria-hidden="true" />
            <span>SuperStar</span>
          </Link>
          {slug && (
            <>
              <span className="sep">/</span>
              <Link to={`/o/${slug}`} className="org-pill">{slug}</Link>
              <nav className="header-nav">
                <Link to={`/o/${slug}`}>Tickets</Link>
                <Link to={`/o/${slug}/new`}>New</Link>
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
        </div>
      </header>
      {slug && inAdmin && (
        <nav className="admin-subnav">
          <div className="admin-subnav-inner">
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
          </div>
        </nav>
      )}
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

// Shared chrome: header, admin sub-nav, content container.
//
// Header is hidden on the unauthenticated landing (`/` when /api/me/ 403s)
// because the landing carries its own Superstar mark in the hero — showing
// the navbar above it would just duplicate the brand and add chrome that
// has no useful links on a signed-out page.
//
// Two container widths in play:
//   - .app-main → max-content (760 px) by default — the reading width
//     for forms / detail / admin pages.
//   - <main className="app-main wide"> → opt into max-wide (1180 px)
//     for table-heavy pages.
// The list pages set `wide` themselves; this component stays dumb.

import { Link, Outlet, useLocation } from "react-router-dom";
import { useApi } from "../api/hooks";
import type { Me } from "../api/types";
import { useOrg } from "../contexts/OrgContext";

export default function Layout() {
  const slug = useOrg();
  const location = useLocation();
  const inAdmin = location.pathname.includes("/admin/");
  const { data: me, error: meError } = useApi<Me>("/api/me/");

  // Hide the navbar on the unauthenticated landing. "Unauth" means we
  // actually saw an error from /api/me/ — NOT just "data hasn't arrived
  // yet". useApi's initial state is data=null, error=null, loading=false
  // (until the useEffect fires), so checking `me === null` would treat
  // that pre-fetch render as unauth and flash the no-header layout for
  // signed-in users. Only `meError !== null` reliably means signed out.
  const onUnauthLanding = location.pathname === "/" && meError !== null;

  return (
    <div className={`app-shell ${onUnauthLanding ? "unframed" : ""}`}>
      {!onUnauthLanding && (
        <header className="app-header">
          <div className="app-header-inner">
            <Link to="/" className="brand">
              <img src="/logo.svg" alt="" className="brand-logo" aria-hidden="true" />
              <span>Superstar</span>
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
      )}
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
            {/* Workspace-level admin (managing all tenants on this
                deployment) lives at the top level, NOT here — see the
                "Manage workspaces" link on the org picker for superusers. */}
          </div>
        </nav>
      )}
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

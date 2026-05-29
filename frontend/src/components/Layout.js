import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
// Shared chrome: header bar with brand, current org, sign-out (placeholder).
import { Link, Outlet } from "react-router-dom";
import { useApi } from "../api/hooks";
import { useOrg } from "../contexts/OrgContext";
export default function Layout() {
    const slug = useOrg();
    const { data: me } = useApi("/api/me/");
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("header", { className: "app-header", children: [_jsx(Link, { to: "/", className: "brand", children: "SuperStar" }), slug && (_jsxs(_Fragment, { children: [_jsx("span", { className: "sep", children: "/" }), _jsx(Link, { to: `/o/${slug}`, className: "org-pill", children: slug }), _jsxs("nav", { className: "header-nav", children: [_jsx(Link, { to: `/o/${slug}`, children: "Tickets" }), _jsx(Link, { to: `/o/${slug}/new`, children: "New ticket" }), _jsx(Link, { to: `/o/${slug}/admin/ticket-types`, children: "Admin" })] })] })), _jsx("div", { className: "header-spacer" }), me && (_jsxs("span", { className: "user", children: [me.full_name || me.email, me.is_superuser && _jsx("span", { className: "badge", children: "admin" })] }))] }), _jsx("main", { className: "app-main", children: _jsx(Outlet, {}) })] }));
}

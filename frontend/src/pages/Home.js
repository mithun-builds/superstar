import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
// Org picker. Shows the user's memberships; clicking one navigates into
// the tenant-scoped dashboard at /o/<slug>.
import { Link } from "react-router-dom";
import { useApi } from "../api/hooks";
export default function Home() {
    const { data: me, loading, error } = useApi("/api/me/");
    if (loading)
        return _jsx("p", { children: "Loading\u2026" });
    if (error) {
        return (_jsxs("div", { className: "error-block", children: [_jsx("h2", { children: "Not signed in?" }), _jsxs("p", { children: ["The API rejected the request. Sign in via", " ", _jsx("a", { href: "/admin/login/?next=/", children: "Django admin" }), ", then return here."] })] }));
    }
    if (!me)
        return null;
    return (_jsxs("section", { className: "page-home", children: [_jsxs("h1", { children: ["Hello, ", me.full_name || me.email] }), me.memberships.length === 0 ? (_jsxs("p", { children: ["You are not a member of any org yet. Ask a SuperStar admin to add you, or run ", _jsxs("code", { children: ["python manage.py create_tenant --slug \u2026 --owner-email ", me.email] }), "."] })) : (_jsxs(_Fragment, { children: [_jsx("p", { children: "Pick an org to continue:" }), _jsx("ul", { className: "org-list", children: me.memberships.map((m) => (_jsx("li", { children: _jsxs(Link, { to: `/o/${m.org_slug}`, className: "org-card", children: [_jsx("strong", { children: m.org_name }), _jsxs("span", { className: "org-slug", children: ["/o/", m.org_slug] }), _jsxs("span", { className: "org-role", children: ["role: ", m.role] })] }) }, m.id))) })] }))] }));
}

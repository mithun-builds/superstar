import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { OrgProvider } from "./contexts/OrgContext";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";
import RuleEdit from "./pages/admin/RuleEdit";
import RuleList from "./pages/admin/RuleList";
import TicketTypeEdit from "./pages/admin/TicketTypeEdit";
import TicketTypeList from "./pages/admin/TicketTypeList";
export default function App() {
    return (_jsx(Routes, { children: _jsxs(Route, { element: _jsx(OrgProvider, { children: _jsx(Layout, {}) }), children: [_jsx(Route, { path: "/", element: _jsx(Home, {}) }), _jsx(Route, { path: "/o/:orgSlug", element: _jsx(Dashboard, {}) }), _jsx(Route, { path: "/o/:orgSlug/new", element: _jsx(NewTicket, {}) }), _jsx(Route, { path: "/o/:orgSlug/tickets/:ticketId", element: _jsx(TicketDetail, {}) }), _jsx(Route, { path: "/o/:orgSlug/admin/ticket-types", element: _jsx(TicketTypeList, {}) }), _jsx(Route, { path: "/o/:orgSlug/admin/ticket-types/:ticketTypeId", element: _jsx(TicketTypeEdit, {}) }), _jsx(Route, { path: "/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules", element: _jsx(RuleList, {}) }), _jsx(Route, { path: "/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules/:ruleId", element: _jsx(RuleEdit, {}) })] }) }));
}

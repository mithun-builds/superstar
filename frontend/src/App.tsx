import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { OrgProvider } from "./contexts/OrgContext";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";
import PlatformOrgList from "./pages/admin/PlatformOrgList";
import RuleEdit from "./pages/admin/RuleEdit";
import RuleList from "./pages/admin/RuleList";
import TeamEdit from "./pages/admin/TeamEdit";
import TeamList from "./pages/admin/TeamList";
import TicketTypeEdit from "./pages/admin/TicketTypeEdit";
import TicketTypeList from "./pages/admin/TicketTypeList";

export default function App() {
  return (
    <Routes>
      {/* Wrap every route under an OrgProvider so useOrg() works everywhere. */}
      <Route
        element={
          <OrgProvider>
            <Layout />
          </OrgProvider>
        }
      >
        <Route path="/" element={<Home />} />
        {/* Platform-level admin — superuser-only (server-side gate). Lives
            at the top level, NOT inside /o/<slug>/, because managing the
            list of tenants is conceptually above any one tenant. */}
        <Route path="/admin/workspaces" element={<PlatformOrgList />} />
        {/* Legacy alias — the old URL lived under a specific org. Keep a
            permanent redirect so existing bookmarks land on the new home. */}
        <Route
          path="/o/:orgSlug/admin/platform/orgs"
          element={<Navigate to="/admin/workspaces" replace />}
        />
        <Route path="/o/:orgSlug" element={<Dashboard />} />
        <Route path="/o/:orgSlug/new" element={<NewTicket />} />
        <Route path="/o/:orgSlug/tickets/:ticketId" element={<TicketDetail />} />
        {/* Per-org admin section — gated server-side by IsOrgAdmin. */}
        <Route path="/o/:orgSlug/admin/ticket-types" element={<TicketTypeList />} />
        <Route path="/o/:orgSlug/admin/ticket-types/:ticketTypeId" element={<TicketTypeEdit />} />
        <Route path="/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules" element={<RuleList />} />
        <Route
          path="/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules/:ruleId"
          element={<RuleEdit />}
        />
        <Route path="/o/:orgSlug/admin/teams" element={<TeamList />} />
        <Route path="/o/:orgSlug/admin/teams/:teamId" element={<TeamEdit />} />
      </Route>
    </Routes>
  );
}

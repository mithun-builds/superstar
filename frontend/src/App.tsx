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
        <Route path="/o/:orgSlug" element={<Dashboard />} />
        <Route path="/o/:orgSlug/new" element={<NewTicket />} />
        <Route path="/o/:orgSlug/tickets/:ticketId" element={<TicketDetail />} />
        {/* Admin section — gated server-side by IsOrgAdmin. */}
        <Route path="/o/:orgSlug/admin/ticket-types" element={<TicketTypeList />} />
        <Route path="/o/:orgSlug/admin/ticket-types/:ticketTypeId" element={<TicketTypeEdit />} />
        <Route path="/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules" element={<RuleList />} />
        <Route
          path="/o/:orgSlug/admin/ticket-types/:ticketTypeId/rules/:ruleId"
          element={<RuleEdit />}
        />
      </Route>
    </Routes>
  );
}

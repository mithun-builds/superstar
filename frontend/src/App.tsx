import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { OrgProvider } from "./contexts/OrgContext";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";

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
      </Route>
    </Routes>
  );
}

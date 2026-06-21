import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import RunDetail from "./pages/RunDetail";
import SettingsPage from "./pages/Settings";

function Sidebar() {
  const { logout, authRequired } = useAuth();
  return (
    <aside className="sidebar">
      <div className="brand">
        AI<span>·</span>Newsletter
        <div className="faint" style={{ fontSize: 11, fontWeight: 400, marginTop: 2 }}>
          Operator console
        </div>
      </div>
      <NavLink to="/" end className="nav-link">
        Dashboard
      </NavLink>
      <NavLink to="/history" className="nav-link">
        History
      </NavLink>
      <NavLink to="/settings" className="nav-link">
        Settings
      </NavLink>
      <div className="sidebar-footer">
        {authRequired && (
          <button className="btn btn-ghost btn-sm" onClick={logout} style={{ width: "100%" }}>
            Log out
          </button>
        )}
        <div style={{ marginTop: 8 }}>AI &amp; Quality Engineering Weekly</div>
      </div>
    </aside>
  );
}

export default function App() {
  const { ready, authRequired, authenticated } = useAuth();

  if (!ready) {
    return (
      <div className="center-screen">
        <span className="spin" />
      </div>
    );
  }

  if (authRequired && !authenticated) {
    return <Login />;
  }

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/history" element={<History />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

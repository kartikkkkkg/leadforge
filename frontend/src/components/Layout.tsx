import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/dashboard" className="brand">
            LeadForge
          </NavLink>
          <nav className="nav" aria-label="Primary">
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              Dashboard
            </NavLink>
            <NavLink to="/research/new" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              New Research
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              Settings
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <footer className="footer">
        <span>LeadForge — automated B2B lead research. Synthetic demo data is labeled and never presented as real.</span>
      </footer>
    </div>
  );
}

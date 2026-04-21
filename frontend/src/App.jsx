import { Routes, Route, Link } from "react-router-dom";
import Upload from "./pages/Upload";
import Processing from "./pages/Processing";
import Results from "./pages/Results";

export default function App() {
  return (
    <div className="app-shell">
      {/* Background orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      {/* Navbar */}
      <nav className="navbar">
        <Link to="/" className="navbar-brand">
          <span className="logo-icon">⚡</span>
          Veda AI
        </Link>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Viral Clip Generator
          </span>
        </div>
      </nav>

      {/* Pages */}
      <div style={{ position: "relative", zIndex: 1, flex: 1 }}>
        <Routes>
          <Route path="/" element={<Upload />} />
          <Route path="/processing/:jobId" element={<Processing />} />
          <Route path="/results/:jobId" element={<Results />} />
        </Routes>
      </div>
    </div>
  );
}

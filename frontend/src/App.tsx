/**
 * App — root component with a two-column layout: left sidebar + main content area.
 * Holds shared archivedIds state so archiving on any page instantly hides the article
 * everywhere without a refetch. Phase 3 adds Trends, Synthesis, and KnowledgeMap pages.
 * Token validation on app load for Version 2.0 demo access control.
 */

import { useEffect, useState } from "react";
import { toggleArchive } from "./api/client";
import Sidebar, { type Tab } from "./components/Sidebar";
import Archived from "./pages/Archived";
import Articles from "./pages/Articles";
import Home from "./pages/Home";
import KnowledgeMap from "./pages/KnowledgeMap";
import Saved from "./pages/Saved";
import Search from "./pages/Search";
import Sources from "./pages/Sources";
import SynthesisPage from "./pages/Synthesis";
import Trends from "./pages/Trends";
import "./index.css";

/**
 * Renders the sidebar and the currently active page side-by-side.
 * Tab state and archivedIds live here and are passed to pages that need them.
 */
function App() {
  const [tab, setTab] = useState<Tab>("digest");
  const [archivedIds, setArchivedIds] = useState<Set<number>>(new Set());
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get token from URL
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (!token) {
      // No token, redirect to landing page
      window.location.href = "/join-demo.html";
      return;
    }

    // Validate token with backend
    fetch(`/api/validate-token?token=${token}`)
      .then((res) => {
        if (res.ok) {
          setAuthenticated(true);
          // Remove token from URL for cleanliness
          window.history.replaceState({}, document.title, window.location.pathname);
        } else {
          alert("Invalid or expired token. Please join the demo again.");
          window.location.href = "/join-demo.html";
        }
      })
      .catch((err) => {
        console.error("Token validation failed:", err);
        window.location.href = "/join-demo.html";
      })
      .finally(() => setLoading(false));
  }, []);

  /** Toggle archive on the server and update shared archivedIds set. */
  const handleArchive = (id: number) => {
    toggleArchive(id).catch(() => null);
    setArchivedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Validating access...</div>;
  }

  if (!authenticated) {
    return <div className="flex items-center justify-center min-h-screen">Redirecting...</div>;
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Left sidebar — navigation + pipeline status */}
      <Sidebar activeTab={tab} onTabChange={setTab} />

      {/* Main content area */}
      <main className="flex-1 overflow-auto">
        {tab === "digest"    && <Home        archivedIds={archivedIds} onArchive={handleArchive} />}
        {tab === "articles"  && <Articles    archivedIds={archivedIds} onArchive={handleArchive} />}
        {tab === "trends"    && <Trends />}
        {tab === "synthesis" && <SynthesisPage />}
        {tab === "knowledge" && <KnowledgeMap />}
        {tab === "search"    && <Search />}
        {tab === "saved"     && <Saved />}
        {tab === "archived"  && <Archived />}
        {tab === "sources"   && <Sources />}
      </main>
    </div>
  );
}

export default App;

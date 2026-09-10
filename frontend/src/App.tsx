/**
 * App — root component with a two-column layout: left sidebar + main content area.
 * Holds shared archivedIds state so archiving on any page instantly hides the article
 * everywhere without a refetch. Phase 3 adds Trends, Synthesis, and KnowledgeMap pages.
 */

import { useState } from "react";
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

  /** Toggle archive on the server and update shared archivedIds set. */
  const handleArchive = (id: number) => {
    toggleArchive(id).catch(() => null);
    setArchivedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

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

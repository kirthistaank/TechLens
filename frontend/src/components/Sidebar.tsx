/**
 * Sidebar — left navigation and live pipeline status panel.
 * Shows nav links, Ollama health, per-stage article counts, and a Run Pipeline button.
 * Polls pipeline status every 20 seconds so counts update while the pipeline runs.
 */

import { useEffect, useState } from "react";
import { applyFeedbackWeights, fetchPipelineStatus, triggerPipeline } from "../api/client";
import type { PipelineStatus } from "../types";

/** Navigation tab identifiers shared with App.tsx. */
export type Tab = "digest" | "articles" | "search" | "saved" | "archived" | "sources" | "trends" | "synthesis" | "knowledge";

/** A single pipeline stage row shown in the status panel. */
interface StageRowProps {
  /** Emoji icon for the stage. */
  icon: string;
  /** Human-readable stage name. */
  label: string;
  /** Article count for this stage. */
  count: number;
  /** Highlight this row as the active/busy stage. */
  active?: boolean;
}

/** Renders one row of the pipeline stage breakdown. */
function StageRow({ icon, label, count, active }: StageRowProps) {
  return (
    <div className={`flex items-center justify-between py-1.5 px-2 rounded-md ${active ? "bg-blue-50" : ""}`}>
      <span className={`text-sm flex items-center gap-2 ${active ? "text-blue-700 font-medium" : "text-gray-500"}`}>
        <span>{icon}</span>
        <span>{label}</span>
      </span>
      <span className={`text-sm font-semibold tabular-nums ${active ? "text-blue-700" : "text-gray-700"}`}>
        {count}
      </span>
    </div>
  );
}

interface Props {
  /** Currently active navigation tab. */
  activeTab: Tab;
  /** Called when the user clicks a nav link. */
  onTabChange: (tab: Tab) => void;
}

/**
 * Sidebar with navigation links, Ollama health indicator, pipeline stage counts,
 * and a manual Run Pipeline button. Refreshes status every 20 seconds.
 */
export default function Sidebar({ activeTab, onTabChange }: Props) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState("");
  const [adapting, setAdapting] = useState(false);
  const [adaptMessage, setAdaptMessage] = useState("");
  const [showLegend, setShowLegend] = useState(false);

  /** Fetch latest pipeline status from the API. */
  const refresh = () => {
    fetchPipelineStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 20_000);
    return () => clearInterval(id);
  }, []);

  /** Trigger a manual pipeline run and show a brief confirmation. */
  const handleRun = async () => {
    setRunning(true);
    setRunMessage("");
    try {
      await triggerPipeline();
      setRunMessage("Pipeline started");
      setTimeout(() => setRunMessage(""), 4000);
    } catch {
      setRunMessage("Failed to start");
    } finally {
      setRunning(false);
      setTimeout(refresh, 3000);
    }
  };

  /** Compute and save adaptive scoring weights from accumulated feedback. */
  const handleAdapt = async () => {
    setAdapting(true);
    setAdaptMessage("");
    try {
      const result = await applyFeedbackWeights();
      if (result.topics_computed === 0) {
        setAdaptMessage("Need more feedback");
      } else {
        setAdaptMessage(`Adapted (${result.topics_computed} topics)`);
      }
      setTimeout(() => setAdaptMessage(""), 5000);
    } catch {
      setAdaptMessage("Failed");
    } finally {
      setAdapting(false);
    }
  };

  /** Determine which stage currently has articles in-progress (for highlight). */
  // Highlight the stage currently processing — detected by comparing cumulative counts.
  // All counts are cumulative so we compare adjacent stages to find the active gap.
  const activeStage = (() => {
    if (!status) return null;
    if (status.pending > 0) return "pending";
    if (status.extracted < status.total_articles - (status.failed ?? 0)) return "extracted";
    if (status.embedded < status.extracted) return "embedded";
    if (status.scored < status.extracted) return "scored";
    return null;
  })();

  const navItems: { id: Tab; label: string; icon: string }[] = [
    { id: "digest",    label: "Today's Brief", icon: "📰" },
    { id: "articles",  label: "Articles",       icon: "📄" },
    { id: "trends",    label: "Trends",         icon: "📈" },
    { id: "synthesis", label: "Synthesis",      icon: "🔀" },
    { id: "knowledge", label: "Knowledge",      icon: "🧠" },
    { id: "search",    label: "Search",         icon: "🔍" },
    { id: "saved",     label: "Saved",          icon: "🔖" },
    { id: "archived",  label: "Archived",       icon: "🗂️" },
    { id: "sources",   label: "Sources",        icon: "🔗" },
  ];

  return (
    <aside className="w-56 shrink-0 bg-white border-r border-gray-200 min-h-screen flex flex-col">

      {/* App name */}
      <div className="px-5 py-4 border-b border-gray-100">
        <span className="text-xl font-extrabold tracking-tight">
          <span className="text-blue-600">Tech</span><span className="text-red-500">Lens</span>
        </span>
        <p className="text-xs text-gray-400 mt-0.5">From information overload to connected insight</p>
      </div>

      {/* Navigation links */}
      <nav className="px-3 pt-4 space-y-0.5">
        {navItems.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === id
                ? "bg-blue-50 text-blue-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            }`}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Legend toggle */}
      <div className="px-3 pt-2">
        <button
          onClick={() => setShowLegend((v) => !v)}
          className="w-full text-left flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
        >
          <span className="text-sm">{showLegend ? "▾" : "▸"}</span>
          <span>How it works</span>
          <span className="ml-auto flex items-center justify-center w-4 h-4 rounded-full border border-gray-300 text-gray-400 text-[10px] font-bold leading-none">
            ?
          </span>
        </button>
        {showLegend && (
          <div className="mx-1 mb-2 px-3 py-2.5 bg-gray-50 rounded-lg text-xs text-gray-500 space-y-2">
            <div>
              <span className="font-semibold text-gray-700">📰 Today's Brief</span>
              <p className="mt-0.5">Concise daily summary. For the full breakdown of each article, switch to Articles.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">📄 Articles</span>
              <p className="mt-0.5">Full scored list with detailed summaries, insights, and tradeoffs.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">🔍 Search</span>
              <p className="mt-0.5">Semantic search — find articles on a similar topic using natural language.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">🔖 Saved</span>
              <p className="mt-0.5">Good articles bookmarked for future reference.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">🗂️ Archived</span>
              <p className="mt-0.5">Done reading — archived to keep your feed clean.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">📈 Trends</span>
              <p className="mt-0.5">LLM-detected signals appearing across multiple sources.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">🔀 Synthesis</span>
              <p className="mt-0.5">Same story from multiple sources, distilled into one card.</p>
            </div>
            <div>
              <span className="font-semibold text-gray-700">🧠 Knowledge</span>
              <p className="mt-0.5">Concepts you've seen vs read — track your coverage gaps.</p>
            </div>
            <div className="border-t border-gray-200 pt-2">
              <p>Click <span className="font-semibold">Read original →</span> on any card for the full article.</p>
            </div>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="mx-4 my-4 border-t border-gray-100" />

      {/* Pipeline status */}
      <div className="px-3 flex-1">
        <div className="flex items-center justify-between mb-2 px-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Pipeline</span>
          {/* Ollama health dot */}
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <span className={`w-1.5 h-1.5 rounded-full ${status?.ollama_available ? "bg-green-500" : "bg-red-400"}`} />
            {status?.ollama_available ? "Ollama on" : "Ollama off"}
          </span>
        </div>

        <div className="space-y-0.5">
          <StageRow icon="📥" label="Collected"   count={status?.total_articles ?? 0} />
          <StageRow icon="🔍" label="Extracted"   count={status?.extracted ?? 0}  active={activeStage === "extracted"} />
          <StageRow icon="🧮" label="Embedded"    count={status?.embedded ?? 0}   active={activeStage === "embedded"} />
          <StageRow icon="⭐" label="Scored"       count={status?.scored ?? 0}     active={activeStage === "scored"} />
          <StageRow icon="✅" label="Summarized"  count={status?.summarized ?? 0} />
          <StageRow icon="🚫" label="Ignored"    count={status?.ignored ?? 0} />
          <StageRow icon="❌" label="Failed"      count={status?.failed ?? 0} />
        </div>

        {/* Progress bar — visible while pipeline is running */}
        {status && status.total_articles > 0 && status.summarized < status.total_articles && (
          <div className="mt-3 px-2">
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div
                className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                style={{
                  width: `${Math.round((status.summarized / status.total_articles) * 100)}%`,
                }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1 text-center">
              {Math.round((status.summarized / status.total_articles) * 100)}% complete
            </p>
          </div>
        )}
      </div>

      {/* Run Pipeline button at bottom */}
      <div className="px-3 pb-5 pt-4 border-t border-gray-100 mt-4">
        <button
          onClick={handleRun}
          disabled={running}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors"
        >
          {running ? "Starting…" : "Run Pipeline"}
        </button>
        {runMessage && (
          <p className="text-xs text-center mt-1.5 text-green-600">{runMessage}</p>
        )}
        <p className="text-xs text-gray-400 text-center mt-2">
          Runs daily at 06:00
        </p>

        {/* Adapt Scoring from feedback */}
        <button
          onClick={handleAdapt}
          disabled={adapting}
          title="Learn from your saves, ratings & opens to personalise future scoring"
          className="w-full mt-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 text-xs font-medium py-1.5 rounded-lg transition-colors"
        >
          {adapting ? "Adapting…" : "Adapt Scoring"}
        </button>
        {adaptMessage && (
          <p className="text-xs text-center mt-1 text-blue-500">{adaptMessage}</p>
        )}
      </div>

    </aside>
  );
}

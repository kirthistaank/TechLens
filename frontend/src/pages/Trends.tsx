/**
 * Trends page — displays LLM-detected technology trend cards from the knowledge graph.
 * Users can filter by 7- or 30-day window and trigger a fresh trend detection run.
 */

import { useEffect, useState } from "react";
import { fetchTrends, triggerTrendDetection } from "../api/client";
import type { Trend } from "../types";

/** Tailwind class sets for each confidence level badge. */
const CONFIDENCE_CLASSES: Record<Trend["confidence"], string> = {
  high:   "bg-green-100 text-green-700 border border-green-200",
  medium: "bg-amber-100 text-amber-700 border border-amber-200",
  low:    "bg-gray-100 text-gray-500 border border-gray-200",
};

/** Human-readable label for each confidence level. */
const CONFIDENCE_LABEL: Record<Trend["confidence"], string> = {
  high:   "High confidence",
  medium: "Medium confidence",
  low:    "Low confidence",
};

/**
 * Renders a single trend card with confidence badge, metadata, summary, and concept tags.
 */
function TrendCard({ trend }: { trend: Trend }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3">
      {/* Header row: name + confidence badge */}
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-base font-semibold text-gray-900 leading-snug">{trend.name}</h2>
        <span
          className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${CONFIDENCE_CLASSES[trend.confidence]}`}
        >
          {CONFIDENCE_LABEL[trend.confidence]}
        </span>
      </div>

      {/* Meta: window + article/source counts */}
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span className="bg-gray-100 px-2 py-0.5 rounded">
          {trend.window_days}d window
        </span>
        <span>{trend.article_count} article{trend.article_count !== 1 ? "s" : ""}</span>
        <span>{trend.source_count} source{trend.source_count !== 1 ? "s" : ""}</span>
        <span className="ml-auto">
          {new Date(trend.detected_at).toLocaleDateString(undefined, {
            month: "short", day: "numeric",
          })}
        </span>
      </div>

      {/* Summary text */}
      <p className="text-sm text-gray-700 leading-relaxed">{trend.summary}</p>

      {/* Concept tags */}
      {trend.concepts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {trend.concepts.map((c) => (
            <span
              key={c}
              className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-100"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Window filter pill button component. */
function FilterPill({
  label, active, onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-4 py-1.5 rounded-full font-medium border transition-colors ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-600 border-gray-200 hover:border-blue-400 hover:text-blue-600"
      }`}
    >
      {label}
    </button>
  );
}

/**
 * Trends page: lists active trend cards with window filtering and a manual detect button.
 */
export default function Trends() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const [windowFilter, setWindowFilter] = useState<7 | 30>(30);
  const [detecting, setDetecting] = useState(false);
  const [detectMsg, setDetectMsg] = useState("");

  /** Load trends from the API for the current window filter. */
  const load = (w: 7 | 30) => {
    setLoading(true);
    fetchTrends(w)
      .then(setTrends)
      .catch(() => setTrends([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(windowFilter);
  }, [windowFilter]);

  /** Trigger a background trend detection run and poll after a short delay. */
  const handleDetect = async () => {
    setDetecting(true);
    setDetectMsg("");
    try {
      await triggerTrendDetection();
      setDetectMsg("Detection started — check back in a moment");
      setTimeout(() => {
        load(windowFilter);
        setDetectMsg("");
      }, 8000);
    } catch {
      setDetectMsg("Failed to start detection");
    } finally {
      setDetecting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Trends</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Emerging technology signals detected across your sources
          </p>
        </div>
        <button
          onClick={handleDetect}
          disabled={detecting}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {detecting ? "Detecting…" : "Detect Trends"}
        </button>
      </div>

      {detectMsg && (
        <p className="text-sm text-blue-600 mb-4">{detectMsg}</p>
      )}

      {/* Window filter pills */}
      <div className="flex gap-2 mb-6">
        <FilterPill
          label="7 days"
          active={windowFilter === 7}
          onClick={() => setWindowFilter(7)}
        />
        <FilterPill
          label="30 days"
          active={windowFilter === 30}
          onClick={() => setWindowFilter(30)}
        />
      </div>

      {/* Trend cards list */}
      {loading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : trends.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-4">📈</p>
          <p className="font-medium text-gray-600">No trends detected yet</p>
          <p className="text-sm mt-1">
            Run the pipeline a few times so articles accumulate, then hit Detect Trends.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {trends.map((t) => (
            <TrendCard key={t.id} trend={t} />
          ))}
        </div>
      )}
    </div>
  );
}

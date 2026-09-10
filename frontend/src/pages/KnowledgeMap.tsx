/**
 * KnowledgeMap page — personal concept knowledge tracker.
 * Shows which concepts the user has "seen" (article collected) vs "read" (article opened),
 * highlights Tier 1 topic gaps, and provides article coverage fractions per concept.
 * Foundation for Phase 4 quiz generation and gap-driven recommendations.
 */

import { useEffect, useState } from "react";
import { fetchKnowledgeMap } from "../api/client";
import type { ConceptKnowledgeItem, KnowledgeMapOut } from "../types";

/** Badge colours by concept type. */
const TYPE_CLASSES: Record<string, string> = {
  technology:           "bg-blue-50 text-blue-700 border-blue-100",
  architecture_pattern: "bg-purple-50 text-purple-700 border-purple-100",
  concept:              "bg-gray-100 text-gray-600 border-gray-200",
  company:              "bg-orange-50 text-orange-700 border-orange-100",
  product:              "bg-green-50 text-green-700 border-green-100",
  research_area:        "bg-pink-50 text-pink-700 border-pink-100",
};

/** Return Tailwind class string for a concept type badge. */
function typeClass(conceptType: string): string {
  return TYPE_CLASSES[conceptType] ?? "bg-gray-100 text-gray-600 border-gray-200";
}

/**
 * Renders a single concept row: name, type badge, article count, read fraction, state badge.
 */
function ConceptRow({ item }: { item: ConceptKnowledgeItem }) {
  const isRead = item.state === "read";

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-gray-50 transition-colors">
      {/* State indicator dot */}
      <span
        className={`shrink-0 w-2 h-2 rounded-full ${isRead ? "bg-green-500" : "bg-gray-300"}`}
        title={isRead ? "Read" : "Seen"}
      />

      {/* Concept name */}
      <span className="flex-1 text-sm font-medium text-gray-800 truncate" title={item.name}>
        {item.name}
      </span>

      {/* Type badge */}
      <span
        className={`shrink-0 text-xs px-2 py-0.5 rounded-full border font-medium ${typeClass(item.concept_type)}`}
      >
        {item.concept_type.replace("_", " ")}
      </span>

      {/* Article coverage fraction */}
      <span className="shrink-0 text-xs text-gray-400 w-16 text-right tabular-nums">
        {item.read_count}/{item.article_count}
      </span>

      {/* State badge */}
      <span
        className={`shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full w-12 text-center ${
          isRead
            ? "bg-green-100 text-green-700"
            : "bg-gray-100 text-gray-500"
        }`}
      >
        {isRead ? "READ" : "SEEN"}
      </span>
    </div>
  );
}

/**
 * KnowledgeMap page: summary stats, tier1 gap alert, and a concept table
 * showing each extracted concept's seen/read state ordered by coverage.
 */
export default function KnowledgeMap() {
  const [data, setData] = useState<KnowledgeMapOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchKnowledgeMap()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Map</h1>
        <p className="text-sm text-gray-500 mt-0.5">Concepts you've seen vs read</p>
      </div>

      {loading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : !data || data.concepts.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-4">🧠</p>
          <p className="font-medium text-gray-600">No concepts extracted yet</p>
          <p className="text-sm mt-1">
            Run the pipeline first, then click Detect Trends to populate the knowledge graph.
          </p>
        </div>
      ) : (
        <>
          {/* Summary row */}
          <div className="flex items-center gap-4 mb-5">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2.5 flex flex-col items-center min-w-[90px]">
              <span className="text-xl font-bold text-gray-900">{data.total_seen}</span>
              <span className="text-xs text-gray-500 mt-0.5">concepts seen</span>
            </div>
            <div className="bg-white border border-green-200 rounded-lg px-4 py-2.5 flex flex-col items-center min-w-[90px]">
              <span className="text-xl font-bold text-green-700">{data.total_read}</span>
              <span className="text-xs text-gray-500 mt-0.5">concepts read</span>
            </div>
          </div>

          {/* Tier 1 gap alert */}
          {data.tier1_gaps.length > 0 && (
            <div className="mb-5 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              <p className="text-sm font-semibold text-amber-800 mb-1">
                Gaps in Tier 1 topics
              </p>
              <p className="text-xs text-amber-700 leading-relaxed">
                These high-priority topics have no articles seen yet:{" "}
                <span className="font-medium">
                  {data.tier1_gaps.join(", ")}
                </span>
              </p>
            </div>
          )}

          {/* Column headers */}
          <div className="flex items-center gap-3 px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">
            <span className="w-2 shrink-0" />
            <span className="flex-1">Concept</span>
            <span className="shrink-0 w-28 text-right">Type</span>
            <span className="shrink-0 w-16 text-right">Read/Total</span>
            <span className="shrink-0 w-12 text-center">State</span>
          </div>

          {/* Concept rows */}
          <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
            {data.concepts.map((item) => (
              <ConceptRow key={item.name} item={item} />
            ))}
          </div>

          <p className="text-xs text-gray-400 mt-3 text-right">
            Showing top {data.concepts.length} concepts by article count
          </p>
        </>
      )}
    </div>
  );
}

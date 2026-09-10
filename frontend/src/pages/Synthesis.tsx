/**
 * Synthesis page — displays cross-source synthesis cards.
 * When 3+ articles from 2+ sources cover the same topic, the pipeline collapses them
 * into a single card showing the synthesised summary, unique per-source perspectives,
 * and the key architecture takeaway. Users can expand to view constituent article titles.
 */

import { useEffect, useState } from "react";
import { fetchSynthesisArticles, fetchSyntheses, generateSynthesis } from "../api/client";
import type { Article, Synthesis } from "../types";

/**
 * Renders a single synthesis card with topic, source badges, summary,
 * unique perspectives list, key insight box, concept tags, and expandable article list.
 */
function SynthesisCard({ synthesis }: { synthesis: Synthesis }) {
  const [expanded, setExpanded] = useState(false);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loadingArticles, setLoadingArticles] = useState(false);

  /** Toggle the constituent article list, fetching on first open. */
  const handleExpandToggle = async () => {
    if (!expanded && articles.length === 0) {
      setLoadingArticles(true);
      try {
        const fetched = await fetchSynthesisArticles(synthesis.id);
        setArticles(fetched);
      } catch {
        setArticles([]);
      } finally {
        setLoadingArticles(false);
      }
    }
    setExpanded((v) => !v);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4">
      {/* Header: topic label + badges */}
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-base font-bold text-gray-900 leading-snug">{synthesis.topic}</h2>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs bg-purple-50 text-purple-700 border border-purple-100 px-2 py-0.5 rounded-full font-medium">
            {synthesis.article_count} article{synthesis.article_count !== 1 ? "s" : ""}
          </span>
          <span className="text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full font-medium">
            {synthesis.source_count} source{synthesis.source_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Synthesis summary */}
      <p className="text-sm text-gray-700 leading-relaxed">{synthesis.summary}</p>

      {/* Unique perspectives */}
      {synthesis.unique_perspectives.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Unique Perspectives
          </p>
          <ul className="space-y-1.5">
            {synthesis.unique_perspectives.map((perspective, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="mt-1 text-purple-400 shrink-0">•</span>
                <span>{perspective}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Key insight box */}
      {synthesis.key_insight && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">
            Architecture Takeaway
          </p>
          <p className="text-sm text-blue-900 leading-relaxed">{synthesis.key_insight}</p>
        </div>
      )}

      {/* Concept tags */}
      {synthesis.concepts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {synthesis.concepts.map((c) => (
            <span
              key={c}
              className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full border border-gray-200"
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Expandable source articles */}
      <div>
        <button
          onClick={handleExpandToggle}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium transition-colors"
        >
          {expanded ? "Hide source articles ↑" : "View source articles →"}
        </button>

        {expanded && (
          <div className="mt-3 space-y-2">
            {loadingArticles ? (
              <p className="text-sm text-gray-400">Loading articles…</p>
            ) : articles.length === 0 ? (
              <p className="text-sm text-gray-400">No articles found.</p>
            ) : (
              articles.map((a) => (
                <div
                  key={a.id}
                  className="flex items-start gap-2 text-sm text-gray-600 pl-2 border-l-2 border-gray-200"
                >
                  <span className="shrink-0 text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded mt-0.5">
                    {a.source}
                  </span>
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-blue-600 hover:underline leading-snug"
                  >
                    {a.title}
                  </a>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Timestamp */}
      <p className="text-xs text-gray-400 text-right -mt-2">
        {new Date(synthesis.generated_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })}
      </p>
    </div>
  );
}

/**
 * Synthesis page: lists all active cross-source synthesis cards, newest first.
 * Shows an empty state prompt when no synthesis has been generated yet.
 * Provides a "Generate Synthesis" button to trigger the synthesis pipeline stage on demand.
 */
export default function SynthesisPage() {
  const [syntheses, setSyntheses] = useState<Synthesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateMessage, setGenerateMessage] = useState("");

  useEffect(() => {
    fetchSyntheses()
      .then(setSyntheses)
      .catch(() => setSyntheses([]))
      .finally(() => setLoading(false));
  }, []);

  /** Trigger background synthesis and show a brief confirmation. */
  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateMessage("");
    try {
      await generateSynthesis();
      setGenerateMessage("Synthesis started — refresh in a moment");
      setTimeout(() => setGenerateMessage(""), 6000);
    } catch {
      setGenerateMessage("Failed to start synthesis");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cross-Source Synthesis</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Same story, multiple angles — distilled into one
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="shrink-0 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {generating ? "Starting…" : "Generate Synthesis"}
          </button>
          {generateMessage && (
            <p className="text-xs text-purple-600">{generateMessage}</p>
          )}
        </div>
      </div>

      {loading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : syntheses.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-4">🔀</p>
          <p className="font-medium text-gray-600">No synthesis yet</p>
          <p className="text-sm mt-1">
            Run the pipeline after concepts are extracted. Synthesis cards appear when
            3+ articles from 2+ sources cover the same topic.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {syntheses.map((s) => (
            <SynthesisCard key={s.id} synthesis={s} />
          ))}
        </div>
      )}
    </div>
  );
}

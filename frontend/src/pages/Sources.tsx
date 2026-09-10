/**
 * Sources page — lists all configured RSS/Substack sources with enable/disable toggles.
 * Shows last poll time, failure count, and source priority.
 */

import { useEffect, useState } from "react";
import { fetchSources, toggleSource } from "../api/client";
import type { Source } from "../types";

/**
 * Renders the source management table.
 * Each row shows source metadata and an enable/disable toggle button.
 */
export default function Sources() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSources()
      .then(setSources)
      .finally(() => setLoading(false));
  }, []);

  /** Toggle a source enabled/disabled and refresh the list optimistically. */
  const handleToggle = async (sourceId: string) => {
    const updated = await toggleSource(sourceId);
    setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Sources</h1>
      <p className="text-sm text-gray-500 mb-6">
        Add new sources via <code className="bg-gray-100 px-1 rounded">config/sources.yaml</code>, then restart or run the pipeline.
      </p>

      {loading ? (
        <p className="text-gray-400">Loading…</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          {sources.map((source) => (
            <div key={source.id} className="flex items-center gap-4 px-5 py-4">
              {/* Source info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-medium text-gray-900 truncate">{source.name}</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                    {source.source_type}
                  </span>
                  <span className="text-xs text-gray-400">Priority {source.priority}</span>
                </div>
                <div className="text-xs text-gray-400 truncate">
                  <a href={source.home_url} target="_blank" rel="noopener noreferrer"
                     className="hover:text-blue-600">{source.home_url}</a>
                </div>
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  {source.last_polled_at && (
                    <span>Last polled: {new Date(source.last_polled_at).toLocaleString()}</span>
                  )}
                  {source.failure_count > 0 && (
                    <span className="text-red-400">Failures: {source.failure_count}</span>
                  )}
                </div>
              </div>

              {/* Categories */}
              <div className="hidden sm:flex flex-wrap gap-1 max-w-[200px]">
                {source.categories.slice(0, 3).map((cat) => (
                  <span key={cat} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">
                    {cat}
                  </span>
                ))}
              </div>

              {/* Toggle button */}
              <button
                onClick={() => handleToggle(source.id)}
                className={`text-xs px-3 py-1.5 rounded font-medium border transition-colors ${
                  source.enabled
                    ? "border-green-200 bg-green-50 text-green-700 hover:bg-green-100"
                    : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"
                }`}
              >
                {source.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

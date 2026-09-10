/**
 * Articles page — lists all processed articles with filter tabs (READ / SKIM / IGNORE / ALL).
 * Receives archivedIds from App so archiving here also hides articles on Today's Brief.
 */

import { useEffect, useState } from "react";
import { fetchArticles } from "../api/client";
import ArticleCard from "../components/ArticleCard";
import type { Article } from "../types";

/** Filter tabs available on the articles page. */
const FILTERS = ["ALL", "READ", "SKIM", "IGNORE"] as const;
type Filter = (typeof FILTERS)[number];

interface Props {
  archivedIds: Set<number>;
  onArchive: (id: number) => void;
}

/**
 * Renders a filterable list of all scored, non-archived articles.
 * Fetches fresh data whenever the active filter tab changes.
 */
export default function Articles({ archivedIds, onArchive }: Props) {
  const [articles, setArticles] = useState<Article[]>([]);
  const [filter, setFilter] = useState<Filter>("READ");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchArticles(filter === "ALL" ? undefined : filter)
      .then(setArticles)
      .finally(() => setLoading(false));
  }, [filter]);

  const visible = articles.filter((a) => !archivedIds.has(a.id));

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Articles</h1>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:border-blue-300"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-400">Loading…</p>
      ) : visible.length === 0 ? (
        <p className="text-gray-400">No articles in this category yet.</p>
      ) : (
        <div className="space-y-5">
          {visible.map((a) => (
            <ArticleCard key={a.id} data={a} onArchive={onArchive} />
          ))}
        </div>
      )}
    </div>
  );
}

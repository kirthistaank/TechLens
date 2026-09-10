/**
 * Archived page — shows all articles the user has archived.
 * Articles can be unarchived from here and will be removed from the list.
 */

import { useEffect, useState } from "react";
import { fetchArchivedArticles } from "../api/client";
import ArticleCard from "../components/ArticleCard";
import type { Article } from "../types";

/**
 * Renders the list of archived articles.
 * Unarchiving an article removes it from the list immediately.
 */
export default function Archived() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchArchivedArticles()
      .then(setArticles)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Archived</h1>
      <p className="text-sm text-gray-400 mb-6">{articles.length} article{articles.length !== 1 ? "s" : ""}</p>

      {loading ? (
        <p className="text-gray-400">Loading…</p>
      ) : articles.length === 0 ? (
        <p className="text-gray-400">No archived articles yet. Archive articles from the Articles tab.</p>
      ) : (
        <div className="space-y-5">
          {articles.map((a) => (
            <ArticleCard
              key={a.id}
              data={a}
              onArchive={(id) => setArticles((prev) => prev.filter((x) => x.id !== id))}
            />
          ))}
        </div>
      )}
    </div>
  );
}

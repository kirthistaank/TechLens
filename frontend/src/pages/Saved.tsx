/**
 * Saved page — articles the user bookmarked for later reading.
 * Unsaving an article removes it from the list immediately.
 */

import { useEffect, useState } from "react";
import { fetchSavedArticles } from "../api/client";
import ArticleCard from "../components/ArticleCard";
import type { Article } from "../types";

export default function Saved() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchSavedArticles()
      .then(setArticles)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Saved</h1>
      <p className="text-sm text-gray-400 mb-6">{articles.length} article{articles.length !== 1 ? "s" : ""} saved for later</p>

      {loading ? (
        <p className="text-gray-400">Loading…</p>
      ) : articles.length === 0 ? (
        <p className="text-gray-400">No saved articles yet. Click 🔖 on any article to save it for later.</p>
      ) : (
        <div className="space-y-5">
          {articles.map((a) => (
            <ArticleCard
              key={a.id}
              data={a}
              onFeedback={(id, patch) => {
                if (patch.is_saved === false) {
                  setArticles((prev) => prev.filter((x) => x.id !== id));
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

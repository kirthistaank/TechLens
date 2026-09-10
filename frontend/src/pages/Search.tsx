/**
 * Search page — semantic search over all embedded articles.
 * Embeds the query server-side with nomic-embed-text and returns articles
 * ranked by cosine similarity. Results use the same ArticleCard as the Articles page.
 */

import { useState } from "react";
import { searchArticles } from "../api/client";
import ArticleCard from "../components/ArticleCard";
import type { Article } from "../types";

/** Example queries shown as clickable chips below the search box. */
const EXAMPLE_QUERIES = [
  "agent memory and planning",
  "RAG retrieval quality",
  "enterprise AI governance",
  "MCP architecture patterns",
  "LLM production reliability",
];

/**
 * Semantic search page. Debounces nothing — user submits with Enter or the button.
 * Shows a loading state while waiting for the embedding + vector search to complete.
 */
export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Run a search for the current query string. */
  const runSearch = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setSearched(true);
    setError(null);
    try {
      const hits = await searchArticles(trimmed);
      setResults(hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") runSearch(query);
  };

  const handleExample = (q: string) => {
    setQuery(q);
    runSearch(q);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Search</h1>
      <p className="text-sm text-gray-400 mb-6">
        Semantic search across all articles you've collected. Ask in plain English.
      </p>

      {/* Search input */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder='e.g. "how do agents handle memory?" or "RAG vs fine-tuning tradeoffs"'
          className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400
                     placeholder:text-gray-300"
        />
        <button
          onClick={() => runSearch(query)}
          disabled={loading || !query.trim()}
          className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg
                     hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </div>

      {/* Example query chips */}
      {!searched && (
        <div className="flex flex-wrap gap-2 mb-8">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => handleExample(q)}
              className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full
                         border border-blue-100 hover:bg-blue-100 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error.includes("503")
            ? "Embedding service unavailable — make sure Ollama is running."
            : error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <p className="text-sm text-gray-400 mt-4">
          Embedding query and searching… (first search loads the model)
        </p>
      )}

      {/* Results */}
      {!loading && searched && (
        <>
          <p className="text-sm text-gray-400 mb-4">
            {results.length === 0
              ? `No results for "${query}" — try running the pipeline to collect more articles.`
              : `${results.length} result${results.length !== 1 ? "s" : ""} for "${query}"`}
          </p>
          <div className="space-y-5">
            {results.map((a) => (
              <ArticleCard key={a.id} data={a} />
            ))}
          </div>
        </>
      )}

      {/* Empty state before first search */}
      {!searched && !loading && (
        <div className="mt-12 text-center text-gray-300 text-sm">
          <p className="text-3xl mb-3">🔍</p>
          <p>Search across everything you've read and collected.</p>
          <p className="mt-1">Powered by local embeddings — no cloud required.</p>
        </div>
      )}
    </div>
  );
}

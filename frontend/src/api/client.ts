/**
 * API client for TechLens backend.
 * All fetch calls to /api/* go through here so base URL and error handling are centralised.
 * Phase 3 adds fetchTrends, triggerTrendDetection, fetchTopConcepts, fetchSyntheses,
 * fetchSynthesisArticles, and fetchKnowledgeMap.
 */

import type { Article, ConceptStat, Digest, KnowledgeMapOut, PipelineStatus, Source, Synthesis, Trend } from "../types";

const BASE = "/api";

export class RateLimitError extends Error {
  constructor() { super("Rate limited — too many requests"); }
}

/** Throw a descriptive error if the response is not OK. */
async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 429) throw new RateLimitError();
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/** Fetch today's daily digest. */
export async function fetchDailyDigest(): Promise<Digest> {
  const res = await fetch(`${BASE}/digest/daily`);
  return handleResponse<Digest>(res);
}

/** Fetch paginated article list, optionally filtered by recommendation. */
export async function fetchArticles(
  recommendation?: string,
  limit = 50,
  offset = 0,
): Promise<Article[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (recommendation) params.set("recommendation", recommendation);
  const res = await fetch(`${BASE}/articles?${params}`);
  return handleResponse<Article[]>(res);
}

/** Fetch archived articles. */
export async function fetchArchivedArticles(limit = 100): Promise<Article[]> {
  const params = new URLSearchParams({ archived: "true", limit: String(limit) });
  const res = await fetch(`${BASE}/articles?${params}`);
  return handleResponse<Article[]>(res);
}

/** Toggle archived state for an article. */
export async function toggleArchive(articleId: number): Promise<Article> {
  const res = await fetch(`${BASE}/articles/${articleId}/archive`, { method: "PATCH" });
  return handleResponse<Article>(res);
}

/** Fetch all configured sources. */
export async function fetchSources(): Promise<Source[]> {
  const res = await fetch(`${BASE}/sources`);
  return handleResponse<Source[]>(res);
}

/** Toggle a source's enabled state. */
export async function toggleSource(sourceId: string): Promise<Source> {
  const res = await fetch(`${BASE}/sources/${sourceId}/toggle`, { method: "PATCH" });
  return handleResponse<Source>(res);
}

/** Trigger a manual pipeline run (returns immediately, runs in background). */
export async function triggerPipeline(): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/pipeline/run`, { method: "POST" });
  return handleResponse<{ message: string }>(res);
}

/** Fetch current pipeline / system status. */
export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${BASE}/pipeline/status`);
  return handleResponse<PipelineStatus>(res);
}

/** Semantic search — returns articles ranked by similarity to the query. */
export async function searchArticles(query: string, limit = 10): Promise<Article[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const res = await fetch(`${BASE}/search?${params}`);
  return handleResponse<Article[]>(res);
}

/** Fetch saved (read-later) articles. */
export async function fetchSavedArticles(limit = 100): Promise<Article[]> {
  const params = new URLSearchParams({ saved: "true", limit: String(limit) });
  const res = await fetch(`${BASE}/articles?${params}`);
  return handleResponse<Article[]>(res);
}

/** Toggle saved state for an article. */
export async function toggleSave(articleId: number): Promise<Article> {
  const res = await fetch(`${BASE}/articles/${articleId}/save`, { method: "PATCH" });
  return handleResponse<Article>(res);
}

/** Toggle important flag for an article. */
export async function toggleImportant(articleId: number): Promise<Article> {
  const res = await fetch(`${BASE}/articles/${articleId}/important`, { method: "PATCH" });
  return handleResponse<Article>(res);
}

/** Record that the user opened an article (first open only). */
export async function recordOpen(articleId: number): Promise<void> {
  await fetch(`${BASE}/articles/${articleId}/open`, { method: "POST" });
}

/** Set or clear a thumbs up/down rating. */
export async function rateArticle(articleId: number, rating: "up" | "down" | null): Promise<Article> {
  const res = await fetch(`${BASE}/articles/${articleId}/rate`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  return handleResponse<Article>(res);
}

/** Fetch feedback insights — topic engagement stats. */
export async function fetchFeedbackInsights(): Promise<{
  total_articles_with_feedback: number;
  topics: { topic: string; total: number; opened: number; saved: number; important: number; rated_up: number; rated_down: number; engagement_score: number }[];
}> {
  const res = await fetch(`${BASE}/feedback/insights`);
  return handleResponse(res);
}

/** Apply accumulated feedback to compute and save adaptive scoring weights. */
export async function applyFeedbackWeights(): Promise<{
  message: string;
  topics_computed: number;
  boosted: string[];
  penalized: string[];
}> {
  const res = await fetch(`${BASE}/feedback/apply-weights`, { method: "POST" });
  return handleResponse(res);
}

// --- Phase 3: Trends & Concepts ---

/** Fetch active trend cards, optionally filtered by window (7 or 30 days). */
export async function fetchTrends(windowDays?: number): Promise<Trend[]> {
  const params = new URLSearchParams();
  if (windowDays !== undefined) params.set("window_days", String(windowDays));
  const query = params.toString() ? `?${params}` : "";
  const res = await fetch(`${BASE}/trends${query}`);
  return handleResponse<Trend[]>(res);
}

/** Trigger background concept extraction + trend detection. Returns 202. */
export async function triggerTrendDetection(): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/trends/detect`, { method: "POST" });
  return handleResponse<{ message: string }>(res);
}

/** Fetch top 20 concepts by article mention count. */
export async function fetchTopConcepts(): Promise<ConceptStat[]> {
  const res = await fetch(`${BASE}/concepts/top`);
  return handleResponse<ConceptStat[]>(res);
}

// --- Phase 3: Cross-Source Synthesis ---

/** Fetch active synthesis cards ordered by most recent first. */
export async function fetchSyntheses(): Promise<Synthesis[]> {
  const res = await fetch(`${BASE}/synthesis`);
  return handleResponse<Synthesis[]>(res);
}

/** Trigger background cross-source synthesis. Returns 202 immediately. */
export async function generateSynthesis(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/synthesis/generate`, { method: "POST" });
  return handleResponse<{ status: string }>(res);
}

/** Fetch the constituent articles for a synthesis card. */
export async function fetchSynthesisArticles(synthesisId: number): Promise<Article[]> {
  const res = await fetch(`${BASE}/synthesis/${synthesisId}/articles`);
  return handleResponse<Article[]>(res);
}

// --- Phase 3: Personal Knowledge Memory ---

/** Fetch the knowledge map — per-concept seen/read state plus tier1 gaps. */
export async function fetchKnowledgeMap(): Promise<KnowledgeMapOut> {
  const res = await fetch(`${BASE}/knowledge/map`);
  return handleResponse<KnowledgeMapOut>(res);
}

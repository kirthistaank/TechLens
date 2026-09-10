export interface Article {
  id: number;
  title: string;
  url: string;
  source: string;
  publication: string;
  score: number | null;
  recommendation: "READ" | "SKIM" | "IGNORE" | null;
  score_rationale: string | null;
  what_happened: string | null;
  why_it_matters: string | null;
  technical_insights: string[];
  architecture_implication: string | null;
  tradeoffs: string | null;
  estimated_reading_minutes: number | null;
  categories: string[];
  published_at: string | null;
  is_duplicate: boolean;
  is_archived: boolean;
  is_saved: boolean;
  is_important: boolean;
  opened_at: string | null;
  user_rating: "up" | "down" | null;
}

export interface DigestItem {
  id: number;
  title: string;
  url: string;
  source: string;
  score: number;
  recommendation: "READ" | "SKIM" | "IGNORE";
  what_happened: string | null;
  why_it_matters: string | null;
  technical_insights: string[];
  architecture_implication: string | null;
  tradeoffs: string | null;
  estimated_reading_minutes: number | null;
  categories: string[];
}

export interface Digest {
  date: string;
  generated_at: string;
  total_collected: number;
  total_scored: number;
  items: DigestItem[];
}

export interface Source {
  id: string;
  name: string;
  feed_url: string;
  home_url: string;
  source_type: string;
  priority: number;
  categories: string[];
  enabled: boolean;
  last_polled_at: string | null;
  failure_count: number;
}

export interface PipelineStatus {
  ollama_available: boolean;
  total_articles: number;
  pending: number;
  extracted: number;
  embedded: number;
  scored: number;
  summarized: number;
  ignored: number;
  failed: number;
}

// Phase 3: knowledge graph

export type Trend = {
  id: number;
  name: string;
  summary: string;
  confidence: "high" | "medium" | "low";
  window_days: number;
  article_count: number;
  source_count: number;
  concepts: string[];
  detected_at: string;
};

export type ConceptStat = {
  name: string;
  concept_type: string;
  article_count: number;
  source_count: number;
  first_seen_at: string;
  last_seen_at: string;
};

// Phase 3: Cross-source synthesis

export type Synthesis = {
  id: number;
  topic: string;
  summary: string;
  unique_perspectives: string[];
  key_insight: string;
  source_count: number;
  article_count: number;
  concepts: string[];
  article_ids: number[];
  generated_at: string;
};

// Phase 3: Personal knowledge memory

export type ConceptKnowledgeItem = {
  name: string;
  concept_type: string;
  article_count: number;
  source_count: number;
  read_count: number;
  state: "seen" | "read";
};

export type KnowledgeMapOut = {
  concepts: ConceptKnowledgeItem[];
  tier1_gaps: string[];
  total_seen: number;
  total_read: number;
};

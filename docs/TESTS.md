# TechLens Test Suite

Complete reference for all tests in the project. Every test runs against an in-memory SQLite database (no disk state) and mocked LLM providers (no Ollama calls). Kuzu graph store calls are patched at the module level in Phase 3 tests.

Run all tests:
```bash
PYTHONPATH=src uv run pytest
```

Run a specific file:
```bash
PYTHONPATH=src uv run pytest tests/unit/test_scorer.py -v
```

---

## Test Infrastructure — `tests/conftest.py`

Shared fixtures available to every test file.

### Fixtures

| Fixture | Type | What it provides |
|---|---|---|
| `db_session` | SQLAlchemy Session | In-memory SQLite session. Schema created fresh per test; closed on teardown. |
| `mock_scorer_llm` | `MockScorerLLM` | Always returns score=85, recommendation=READ, categories=[agentic_ai, rag, enterprise_ai]. |
| `mock_summary_llm` | `MockSummaryLLM` | Always returns a valid 6-field summary (what/why/technical/architecture/tradeoffs/reading_time). |
| `mock_failing_llm` | `MockFailingLLM` | Always raises `RuntimeError("LLM unavailable")`. Used to verify error handling paths. |
| `mock_extractor_llm` | `MockExtractorLLM` | Returns 3 concept entries: Agent Memory (architecture_pattern), Retrieval Augmented Generation (technology), Anthropic (company). |
| `mock_trend_llm` | `MockTrendLLM` | Returns a valid trend card: name, 3-sentence summary, confidence=high. |
| `mock_synthesis_llm` | `MockSynthesisLLM` | Returns a valid synthesis card: topic, summary, 2 unique_perspectives, key_insight. |

---

## Unit Tests

### `tests/unit/test_rss_collector.py`

Tests the RSS ingestion stage (`techlens.ingestion.rss_collector`). Feedparser is mocked — no network calls. Uses `tests/fixtures/sample_feed.xml` which contains 2 recent articles and 1 article older than 7 days.

| Test | What it verifies |
|---|---|
| `test_collect_source_inserts_recent_articles` | Two recent articles from the fixture feed are inserted into SQLite; returns count=2. |
| `test_collect_source_skips_duplicate_url` | Running `collect_source` twice on the same feed inserts 0 articles on the second call. |
| `test_collect_source_filters_old_articles` | The article older than 7 days in the fixture is not inserted. |
| `test_collect_source_handles_feed_error` | When feedparser raises, `collect_source` returns 0 and increments `source.failure_count`. |

---

### `tests/unit/test_extractor.py`

Tests the content extraction stage (`techlens.processing.extractor`). Trafilatura's HTTP fetch and extraction functions are mocked.

| Test | What it verifies |
|---|---|
| `test_extract_article_uses_trafilatura_content` | `extract_article` returns the cleaned text from trafilatura when it succeeds. |
| `test_extract_article_falls_back_to_raw_content` | When trafilatura fetch returns `None`, falls back to the article's `raw_content` from RSS. |
| `test_process_pending_marks_article_extracted` | After `process_pending`, article `status=extracted` and `clean_content` is populated. |
| `test_process_pending_marks_failed_when_no_content` | When both trafilatura and `raw_content` are empty, article `status=failed`. |
| `test_process_pending_detects_duplicate_content` | Two articles with identical extracted content — the second is flagged `is_duplicate=True`. |

---

### `tests/unit/test_scorer.py`

Tests the relevance scoring stage (`techlens.scoring.relevance_scorer`). Uses `mock_scorer_llm` and `mock_failing_llm`.

| Test | What it verifies |
|---|---|
| `test_score_article_returns_valid_result` | `score_article` parses the LLM JSON and returns score=85, recommendation=READ, correct categories. |
| `test_score_article_fallback_on_llm_error` | When LLM raises, returns zero-score fallback: score=0.0, recommendation=IGNORE, rationale="Scoring failed." |
| `test_score_all_updates_article_status` | `score_all` sets score, recommendation, and `status=scored` on all extracted articles. |
| `test_score_all_skips_duplicates` | Articles with `is_duplicate=True` are not scored; returns count=0. |

---

### `tests/unit/test_summarizer.py`

Tests the summarization stage (`techlens.summarization.summarizer`). Uses `mock_summary_llm` and `mock_failing_llm`.

| Test | What it verifies |
|---|---|
| `test_summarize_article_populates_all_fields` | `summarize_article` returns all 6 summary fields; `estimated_reading_minutes=6`; `technical_insights` is a list of 2. |
| `test_summarize_article_returns_none_on_llm_error` | When LLM raises, `summarize_article` returns `None` (caller handles). |
| `test_summarize_all_processes_read_and_skim` | `summarize_all` processes both READ and SKIM articles; sets `status=summarized` and populates all summary fields. |
| `test_summarize_all_skips_ignore_articles` ⚠️ | IGNORE-scored articles should not be summarized. **Known failing** — `summarize_all` currently transitions IGNORE articles to `status=ignored` rather than leaving them as `status=scored`. |

---

### `tests/unit/test_digest.py`

Tests the daily digest builder (`techlens.digest.daily_digest`). No LLM calls; pure SQLite logic.

| Test | What it verifies |
|---|---|
| `test_build_digest_includes_high_score_articles` | Articles above `min_score` (60) appear in the digest; ordered by score descending. |
| `test_build_digest_excludes_low_score_articles` | Articles below `min_score` are excluded; only high-score article appears. |
| `test_build_digest_caps_at_max_items` ⚠️ | Digest should not exceed `max_daily_items` (7) from `profile.yaml`. **Known failing** — digest does not currently apply the cap from config. |
| `test_build_digest_caches_on_second_call` | Calling `build_daily_digest` twice on the same day returns the cached record; new articles added after first call are not included. |
| `test_build_digest_excludes_duplicates` | Articles with `is_duplicate=True` are never included in the digest. |

---

### `tests/unit/test_web_collector.py`

Tests the web listing collector (`techlens.ingestion.web_collector`). HTTP calls are mocked with `httpx`. Uses `tests/fixtures/sample_listing.html`.

| Test | What it verifies |
|---|---|
| `test_extract_links_returns_unique_article_urls` | `_extract_links` returns 3 unique article URLs from the fixture HTML (duplicate link deduplicated). |
| `test_extract_links_excludes_nav_pages` | Single-segment slugs like `/about` and `/search` do not match the article link pattern. |
| `test_collect_web_source_inserts_stubs` | `collect_web_source` inserts one stub article per discovered URL; returns count=3. |
| `test_collect_web_source_skips_existing_urls` | Running the collector twice inserts 0 articles on the second run. |
| `test_collect_web_source_handles_http_error` | When `httpx.get` raises, returns 0 and increments `source.failure_count`. |

---

### `tests/unit/test_concept_extractor.py`

Tests the Phase 3 concept extraction stage (`techlens.knowledge_graph.extractor`). All Kuzu `graph_store` functions (`get_conn`, `upsert_article_node`, `upsert_concept`, `link_article_concept`, `refresh_source_counts`) are patched at the module level.

| Test | What it verifies |
|---|---|
| `test_extract_concepts_writes_to_graph` | For a summarized article, `extract_concepts` calls `upsert_concept` and `link_article_concept` for each of the 3 mock concepts; returns count=3; marks `concepts_extracted=True`. |
| `test_extract_concepts_empty_summary_skips_llm` | An article with no summary fields (what/why/architecture all empty) marks `concepts_extracted=True` without calling `get_conn`. |
| `test_extract_concepts_llm_failure_marks_done` | When the LLM raises, `extract_concepts` returns 0 and still sets `concepts_extracted=True` so the article is not retried. |
| `test_extract_all_processes_unextracted_articles` | `extract_all` processes all READ and SKIM summarized articles with `concepts_extracted=False`; calls `refresh_source_counts` once at the end. |
| `test_extract_all_skips_already_extracted` | Articles with `concepts_extracted=True` are skipped; `refresh_source_counts` is not called when nothing is processed. |
| `test_extract_all_skips_ignore_recommendation` | IGNORE articles are excluded even if `concepts_extracted=False` and `status=summarized`. |

---

### `tests/unit/test_trend_detector.py`

Tests the Phase 3 trend detection agent (`techlens.knowledge_graph.trend_detector`). `get_concepts_in_window` and `get_article_ids_for_concept` are patched. Covers both the dedup helper and the main agent loop.

**Important:** `detect_trends` iterates over two time windows (7-day and 30-day). Tests use `side_effect=[cluster_list, []]` to return a cluster only for the first window, preventing duplicate trend creation across windows.

| Test | What it verifies |
|---|---|
| `test_trend_already_active_returns_false_when_no_trends` | Returns `False` when no trends exist in the database. |
| `test_trend_already_active_returns_true_for_recent_matching_trend` | Returns `True` when a fresh active trend covering the same concept and window exists. |
| `test_trend_already_active_ignores_inactive_trend` | A deactivated trend (`is_active=False`) does not suppress detection. |
| `test_trend_already_active_ignores_old_trend` | An active trend older than the 7-day dedup window does not suppress detection. |
| `test_detect_trends_creates_trend_for_qualifying_cluster` | A concept with 3 articles from 2 sources creates 1 new `Trend` record with correct article_count, source_count, and confidence. |
| `test_detect_trends_skips_unqualified_cluster` | A concept with 1 article from 1 source does not meet the threshold; no Trend is created. |
| `test_detect_trends_deduplicates_existing_trend` | When a matching active trend already exists, `detect_trends` creates 0 new trends. |
| `test_detect_trends_deactivates_stale_trends` | Trends older than 35 days are set to `is_active=False` at the start of each run. |

---

### `tests/unit/test_synthesizer.py`

Tests the Phase 3 cross-source synthesizer (`techlens.knowledge_graph.synthesizer`). The internal `get_conn()` call inside `synthesize_all` is a local import — patch target is `techlens.storage.graph_store.get_conn`, not the synthesizer module. The Kuzu result object is mocked with `has_next.side_effect` and `get_next.side_effect` to simulate row iteration.

| Test | What it verifies |
|---|---|
| `test_overlap_fraction_zero_when_no_overlap` | `_overlap_fraction` returns 0.0 when no IDs intersect. |
| `test_overlap_fraction_full_overlap` | Returns 1.0 when all IDs are already covered. |
| `test_overlap_fraction_partial` | Returns 0.5 when half the IDs overlap. |
| `test_overlap_fraction_empty_new_ids` | Returns 0.0 for an empty input list (no division by zero). |
| `test_build_articles_block_contains_source_and_title` | Output block contains the article's source_id, title, and summary_what text. |
| `test_build_articles_block_separates_articles` | Multiple articles are separated by blank lines in the output. |
| `test_synthesize_cluster_creates_synthesis_record` | `synthesize_cluster` persists a `Synthesis` row with correct topic, article_count=3, source_count=2, `is_active=True`, and 2 unique_perspectives. |
| `test_synthesize_cluster_returns_none_on_llm_failure` | When LLM raises, `synthesize_cluster` returns `None` without writing any record. |
| `test_synthesize_all_creates_card_for_qualifying_cluster` | A Kuzu result with 3 articles from 2 sources produces 1 new `Synthesis` record. |
| `test_synthesize_all_skips_cluster_under_threshold` | A cluster with only 2 articles from 1 source (below the 3-article / 2-source threshold) produces no Synthesis. |
| `test_synthesize_all_skips_already_covered_cluster` | When all 3 article IDs are already in an active Synthesis, the overlap check (>50%) prevents a duplicate. |
| `test_synthesize_all_deactivates_stale_records` | Synthesis cards older than 14 days are set to `is_active=False` at the start of each run. |

---

## Integration Tests

### `tests/integration/test_pipeline_e2e.py`

End-to-end smoke test for the Phase 1 pipeline. Runs all 5 stages in sequence against the same in-memory database. Uses the fixture RSS feed; trafilatura and LLM calls are mocked. No network, no Ollama.

| Test | What it verifies |
|---|---|
| `test_full_pipeline_produces_digest` | Full path: fixture RSS → `collect_source` → `process_pending` → `score_all` → `summarize_all` → `build_daily_digest`. Asserts 2 articles collected, extracted, scored, summarized; digest contains at least 1 item with all fields populated and score=85.0. |

---

### `tests/integration/test_phase3_pipeline.py`

Phase 3 integration tests. Each stage is tested in isolation and together as a full pipeline. All Kuzu `graph_store` calls are mocked. The `detect_trends` tests use `side_effect` on `get_concepts_in_window` to control which window receives the cluster (7-day only), preventing double-counting across the two detection windows.

| Test | What it verifies |
|---|---|
| `test_extract_all_phase3_stage` | `extract_all` processes 3 summarized articles from 2 sources; all marked `concepts_extracted=True`; `refresh_source_counts` called once. |
| `test_detect_trends_phase3_stage` | `detect_trends` produces 1 active `Trend` record with correct article_count=3, source_count=2, and the concept name in the `concepts` JSON field. |
| `test_synthesize_all_phase3_stage` | `synthesize_all` produces 1 active `Synthesis` with source_count=2, article_count=3, and at least 1 unique_perspective. |
| `test_full_phase3_pipeline` | Full Phase 3 path: `extract_all` → `detect_trends` → `synthesize_all` on the same 3 articles. Final state: 1 active Trend, 1 active Synthesis. |

---

## Known Failures

These 2 tests fail against the current implementation. They document intended behavior that has not yet been aligned with the code.

| Test | File | Reason |
|---|---|---|
| `test_summarize_all_skips_ignore_articles` | `test_summarizer.py` | `summarize_all` sets IGNORE articles to `status=ignored` instead of leaving them as `status=scored`. The test expects `status=scored` (unchanged). |
| `test_build_digest_caps_at_max_items` | `test_digest.py` | `build_daily_digest` does not currently enforce the `max_daily_items` cap from `config/profile.yaml`. |

---

## Test Counts

| Scope | Files | Tests | Passing |
|---|---|---|---|
| Unit | 8 | 53 | 51 |
| Integration | 2 | 5 | 5 |
| **Total** | **10** | **58** | **56** |

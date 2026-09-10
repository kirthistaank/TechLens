# TechLens — Inference Calls

Every model call in the full system: which model, which stage, what it's asked to do, token budget, daily volume, alternative models, and how to swap.

---

## Models in use (defaults)

| Role | Model | Provider | How it runs |
|---|---|---|---|
| Reasoning / generation | `qwen3:32b` | Ollama (local) | Scoring, summarization, concept extraction, trend detection, synthesis |
| Embeddings | `nomic-embed-text` | Ollama (local) | Semantic dedup + search — 768-dimensional vectors |

All inference runs locally. No cloud keys, no per-token cost, no data leaving the machine.

---

## Context window — why 8192 and not 4096

Ollama's default context window is **4096 tokens**. That sounds like a lot until you factor in the system prompt:

- Scoring system prompt: ~600 tokens (profile, tier definitions, JSON schema)
- Summarization system prompt: ~500 tokens (output schema, instructions)
- That leaves ~3,500 tokens for article content at 4096

A typical ByteByteGo newsletter or Substack deep-dive runs 3,000–6,000 words (~4,000–8,000 tokens). At 4096 total context, the article gets **silently truncated** mid-paragraph. The LLM never sees the conclusion, the tradeoffs section, or the architecture diagram caption — and scores it as if it did.

**TechLens always passes `num_ctx=8192`** via the `LLMProvider` abstraction. This is enforced at the provider level — no call site can accidentally omit it. Cost: ~1 GB extra VRAM at `qwen3:32b` scale, which is negligible.

```python
# src/techlens/llm/ollama_provider.py — enforced here, never at call sites
options = {"num_ctx": settings.ollama_num_ctx}   # default: 8192
```

Set via env: `OLLAMA_NUM_CTX=8192` (`.env.example` default).

---

## Per-article inference calls (scales with volume)

Each article triggers up to 3 reasoning calls depending on its score and dedup status.

### Stage 4 — Relevance Scoring

**Called:** Once per non-duplicate article  
**Model:** `qwen3:32b`  
**Input:** Article title + cleaned content (up to ~6,000 tokens)  
**Output:** Structured JSON

```json
{
  "score": 82,
  "recommendation": "READ",
  "rationale": "Directly addresses production agent memory patterns — gap in current sources.",
  "categories": ["agentic_ai", "rag"]
}
```

**System prompt contents:**
- User's relevance profile (tier-1 and tier-2 topics from `config/profile.yaml`)
- Scoring rubric (what earns a 90 vs a 40)
- Optional personalization hint from `config/user_weights.yaml` if adaptive scoring has been run
- JSON output schema

**Token budget:**  
~500 tokens system prompt + up to 6,500 tokens article content + ~80 tokens output = ~7,100 tokens peak

---

### Stage 5 — Summarization

**Called:** Once per article that passed scoring (not IGNORE)  
**Model:** `qwen3:32b`  
**Input:** Cleaned article content  
**Output:** Structured JSON

```json
{
  "what_happened": "Anthropic released a memory management spec for production agents...",
  "why_it_matters": "Without explicit memory boundaries, agents in multi-tenant systems leak context across sessions.",
  "technical_insights": [
    "Episodic vs semantic memory separation requires two distinct retrieval strategies",
    "Write-through caching at the tool-call boundary reduces latency by 40% in benchmarks"
  ],
  "architecture_implication": "Any agent platform needs a memory tier between working context and long-term vector store.",
  "tradeoffs": "Richer memory = higher retrieval cost + privacy surface area for multi-user deployments.",
  "estimated_reading_minutes": 8
}
```

**System prompt contents:**
- Output schema with field-level instructions
- Audience framing: "Principal AI Architect, Principal-level systems thinking"
- Instruction to derive architecture implications specifically, not general summaries

**Token budget:**  
~450 tokens system prompt + up to 6,500 tokens article + ~300 tokens output = ~7,250 tokens peak

---

### Stage 6 — Concept Extraction

**Called:** Once per summarized article  
**Model:** `qwen3:32b`  
**Input:** Article title + summary fields (not full content — already extracted)  
**Output:** Structured JSON list

```json
{
  "concepts": [
    {"name": "Agent Memory", "type": "pattern"},
    {"name": "Retrieval Augmented Generation", "type": "technology"},
    {"name": "Anthropic", "type": "company"},
    {"name": "Multi-Tenant Systems", "type": "architecture_pattern"}
  ]
}
```

**Concept types:** `technology`, `framework`, `pattern`, `company`, `person`, `event`, `architecture_pattern`

**System prompt contents:**
- Taxonomy of concept types with examples
- Instruction to extract 3–8 concepts, prioritizing architectural signal over brand names
- JSON schema

**Token budget:**  
~400 tokens system prompt + ~500 tokens summary = ~900 tokens total (cheapest LLM call in the pipeline)

---

## Per-run inference calls (batch-level)

These run once per pipeline execution, after all articles are processed. Call count depends on how many concept clusters qualify — not on article volume.

### Stage 7 — Trend Detection (Agent)

**Called:** 1 LLM call per qualifying trend cluster  
**Model:** `qwen3:32b`  
**Qualification:** A concept cluster must have 3+ articles from 2+ sources (or 5+ articles from one source) within the detection window (7 days or 30 days)

**Agent flow:**
1. Query Kuzu graph for concept co-occurrence across recent articles
2. For each qualifying cluster, check if an active trend already covers it (dedup)
3. Fetch article metadata from SQLite (title, source, summary fields)
4. Call LLM once per new trend

**LLM input:** Up to 10 article summaries + metadata for the concept cluster  
**LLM output:** Structured JSON

```json
{
  "name": "Production Agent Observability",
  "summary": "Five sources this week converged on the challenge of observing agent behaviour in production...",
  "confidence": "high",
  "key_signal": "ByteByteGo, Anthropic Blog, and two Substack newsletters all independently reached the same conclusion..."
}
```

**Token budget:** ~600 tokens system prompt + ~2,000 tokens evidence articles = ~2,600 tokens  
**Typical daily calls:** 2–5 (depends on how much converges across sources that week)

---

### Stage 8 — Cross-Source Synthesis

**Called:** 1 LLM call per qualifying synthesis cluster  
**Model:** `qwen3:32b`  
**Qualification:** 3+ articles from 2+ unique sources covering the same primary concept, within 30 days

**LLM input:** Articles grouped by concept cluster — title, source_id, what_happened, why_it_matters  
**LLM output:** Structured JSON

```json
{
  "topic": "OpenAI o3 Reasoning Architecture",
  "summary": "Three sources covered the o3 release from different angles...",
  "unique_perspectives": [
    "The Batch focused on benchmark performance vs previous models",
    "Simon Willison's blog analysed the compute-vs-capability tradeoff",
    "ByteByteGo broke down the chain-of-thought scaffolding architecture"
  ],
  "key_insight": "The inference-time compute scaling approach fundamentally changes how you size GPU fleets for production reasoning workloads."
}
```

**Token budget:** ~500 tokens system prompt + ~1,500 tokens article summaries = ~2,000 tokens  
**Typical daily calls:** 1–3

---

## Embedding calls (nomic-embed-text)

Embedding calls are fast and cheap relative to LLM calls — the model is ~274M parameters vs ~32B for `qwen3:32b`.

| Task | When | Calls |
|---|---|---|
| Semantic dedup check | Stage 3, every new article | 1 per article |
| Store embedding (if unique) | Stage 3, after dedup check | Same request |
| Semantic search | User triggers `/api/search` | 1 per query |

**Dimensions:** 768  
**Dedup threshold:** cosine distance < 0.08 → flagged as duplicate (same story, different source)

---

## Daily volume summary

At a typical feed of **40–100 articles/day** with ~30% IGNORE rate:

| Call type | Low (40 articles) | High (100 articles) |
|---|---|---|
| Scoring — Stage 4 | 40 | 100 |
| Summarization — Stage 5 (~70% pass) | 28 | 70 |
| Concept extraction — Stage 6 | 28 | 70 |
| Trend detection — Stage 7 | 2 | 5 |
| Synthesis — Stage 8 | 1 | 3 |
| **Total LLM calls/day** | **~99** | **~248** |
| Embedding calls (nomic) | 40 | 100 |

At `LLM_THROTTLE_SECONDS=1.0`, a full run of 100 articles takes roughly **4–5 minutes** of active inference time.

---

## Throttling and batching controls

```bash
# .env
LLM_THROTTLE_SECONDS=1.0   # sleep between LLM calls — reduces fan noise and thermal load
LLM_BATCH_SIZE=0           # 0 = no limit; set to e.g. 20 to cap articles per run
```

**Practical settings:**

| Use case | `LLM_THROTTLE_SECONDS` | `LLM_BATCH_SIZE` |
|---|---|---|
| Full daily run, laptop plugged in | 1.0 | 0 |
| Quick catch-up, 20 articles max | 0.5 | 20 |
| Background run, quieter thermals | 2.0 | 0 |
| Testing / debugging | 0 | 5 |

---

## Alternative reasoning models

All alternatives work with the existing `LLMProvider` abstraction. Swap by changing `OLLAMA_MODEL` in `.env` — no code changes needed.

### Local models (Ollama)

| Model | RAM required | Speed vs qwen3:32b | Quality | Best for |
|---|---|---|---|---|
| **`qwen3:32b`** *(default)* | ~20 GB | baseline | ★★★★★ | Best balance of quality + local privacy |
| `qwen3:14b` | ~9 GB | ~2× faster | ★★★★☆ | Laptops with 16 GB RAM — minimal quality loss on scoring and summarization |
| `qwen3:8b` | ~5 GB | ~3× faster | ★★★☆☆ | Fast iteration; acceptable for scoring, weaker on nuanced architecture summaries |
| `qwen2.5:32b` | ~20 GB | similar | ★★★★☆ | Strong on technical/code content; qwen3 generally better for prose synthesis |
| `llama3.3:70b` | ~40 GB | ~0.5× slower | ★★★★★ | Best open-source quality if you have 64 GB RAM (Mac Studio / Mac Pro) |
| `llama3.1:8b` | ~5 GB | ~3× faster | ★★★☆☆ | Fast prototyping; can be inconsistent with strict JSON schema adherence |
| `gemma3:12b` | ~8 GB | ~2× faster | ★★★★☆ | Google's model; strong structured extraction; good alternative to qwen3:14b |
| `mistral-small:22b` | ~14 GB | ~1.5× faster | ★★★★☆ | Strong instruction following; solid alternative when qwen3:14b is unavailable |
| `phi4:14b` | ~9 GB | ~2× faster | ★★★★☆ | Microsoft's model; notably strong reasoning per GB of RAM |

**If your laptop has less than 16 GB RAM:** Use `qwen3:14b`. Quality is nearly indistinguishable from `qwen3:32b` for scoring and summarization. The 32B advantage shows mainly in nuanced multi-hop reasoning during trend detection.

**Key requirement for any swap:** The model must support reliable **JSON mode output**. `qwen3`, `llama3.x`, `gemma3`, and `mistral` families all do. Avoid very small models (`phi3:mini`, `tinyllama`) — they are inconsistent with structured JSON at this complexity level.

```bash
# Swap reasoning model
OLLAMA_MODEL=qwen3:14b

# Pull it first
ollama pull qwen3:14b
```

### Cloud models (via LLMProvider abstraction)

Swapping to a cloud provider requires changing two env vars and zero lines of code. The `LLMProvider` abstraction is OpenAI-API-compatible, so any provider that speaks that protocol works.

```bash
# Example: switch to Groq
OLLAMA_BASE_URL=https://api.groq.com/openai/v1
OLLAMA_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...
```

| Provider | Model | Strengths | Free tier | Cost at ~150 calls/day × 365 days |
|---|---|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | ~500 tok/s inference — fastest available; OpenAI-compatible | ~14,400 req/day free | Free within tier |
| **Groq** | `mixtral-8x7b-32768` | Long context window; good JSON adherence | Included | Free within tier |
| **OpenAI** | `gpt-4o-mini` | Reliable JSON, fast, very cheap | None | ~$11/year |
| **OpenAI** | `gpt-4o` | Best quality for complex synthesis and trend analysis | None | ~$110/year |
| **Anthropic** | `claude-haiku-4-5` | Fast, cheap, excellent structured output | None | ~$16/year |
| **Anthropic** | `claude-sonnet-4-6` | Best reasoning quality for synthesis and trend detection | None | ~$150/year |
| **Together AI** | `meta-llama/Llama-3-70b` | Open weights, OpenAI-compatible | Free credits | ~$5/year |

**Privacy note:** Switching to any cloud provider sends your article content and reading habits to a third party. The local-first default exists precisely to avoid this. See `docs/architecture-tradeoffs.md` §1 for the full reasoning.

---

## Alternative embedding models

Swapping the embedding model requires re-embedding all articles (ChromaDB collection must be rebuilt). One-time operation.

| Model | Dimensions | Approx RAM | Quality | Notes |
|---|---|---|---|---|
| **`nomic-embed-text`** *(default)* | 768 | ~274M params | ★★★★☆ | Best local option — strong on technical English; fast |
| `mxbai-embed-large` | 1024 | ~335M params | ★★★★★ | Marginally better dedup precision; slightly larger ChromaDB index |
| `snowflake-arctic-embed` | 1024 | ~335M params | ★★★★★ | Top MTEB benchmark scores; good direct alternative to mxbai |
| `all-minilm:l6-v2` | 384 | ~22M params | ★★★☆☆ | Very fast; 384 dims compresses meaning aggressively — slightly worse dedup on similar-title articles |
| `text-embedding-3-small` (OpenAI) | 1536 | cloud | ★★★★★ | Best quality; $0.02 per million tokens; requires cloud |
| `text-embedding-3-large` (OpenAI) | 3072 | cloud | ★★★★★ | Overkill for dedup at this scale — 3072 dims adds no measurable benefit vs 3-small |

**Recommendation:** `nomic-embed-text` is the right default. If duplicate articles are slipping through, try `mxbai-embed-large` — same local setup, higher-fidelity vectors, same swap procedure.

**How to re-embed after swapping:**

```bash
# 1. Clear the ChromaDB collection
rm -rf data.nosync/chroma

# 2. Reset all articles to 'extracted' so they re-enter the embedding stage
PYTHONPATH=src uv run python -c "
from techlens.storage.db import get_session
from techlens.storage.models import Article, ArticleStatus
with get_session() as s:
    s.query(Article).filter(
        Article.status.in_([ArticleStatus.scored, ArticleStatus.summarized])
    ).update({'status': ArticleStatus.extracted}, synchronize_session=False)
    s.commit()
print('Reset complete — re-run pipeline to re-embed')
"

# 3. Re-run the pipeline — Stage 3 will re-embed everything
make pipeline
```

---

## Where each call is made in code

| Call | File | Function |
|---|---|---|
| Relevance scoring | `src/techlens/scoring/relevance_scorer.py` | `score_article()` |
| Personalization hint (adaptive) | `src/techlens/scoring/feedback_weights.py` | `build_personalization_hint()` |
| Summarization | `src/techlens/summarization/summarizer.py` | `summarize_article()` |
| Concept extraction | `src/techlens/knowledge_graph/extractor.py` | `extract_concepts()` |
| Trend detection | `src/techlens/knowledge_graph/trend_detector.py` | `detect_trends()` |
| Cross-source synthesis | `src/techlens/knowledge_graph/synthesizer.py` | `synthesize_all()` |
| Embeddings | `src/techlens/embeddings/ollama_embeddings.py` | `embed()` |

All reasoning calls go through `LLMProvider.chat(system, user, json_mode=True)`.  
All embedding calls go through `EmbeddingProvider.embed(texts)`.  
Neither abstraction is bypassed anywhere in application code.

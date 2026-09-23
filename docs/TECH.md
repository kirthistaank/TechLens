# TechLens — Tech Stack & Constraints

## Deployment

- **Local-first.** Core functionality must work without any cloud service.
- **Scheduling:** APScheduler (in-process, no OS config required). Runs as a long-lived Python background process.

## Language & Framework

- **Python 3.11+**
- **FastAPI** (HTTP API + serves React frontend via static build)
- **Frontend:** React + TypeScript (Vite build, served by FastAPI in dev; standalone in prod)
- **Package manager:** `uv` (fast, PEP 517/518, lockfile, replaces pip+venv)

## LLM

### Primary — Ollama (local, required)

- **Model:** `qwen3:32b` (already pulled)
- **Embedding model:** `nomic-embed-text` via Ollama (pull if not present)

### Critical — Context Window

Ollama's default context is **4096 tokens**. With system prompt + instructions consuming ~500–800 tokens, only ~3,200 tokens remain for article content — which silently truncates most substantive blog posts and newsletters (ByteByteGo, Substack deep-dives routinely run 3,000–6,000 words).

TechLens does not ingest papers, so 32K is overkill. **8,192 is the correct setting** — covers ~95% of newsletter and blog content at ~1 GB extra VRAM cost.

**One-time setup (add to `~/.zshrc`):**

```bash
export OLLAMA_NUM_CTX=8192
```

**In code:** Every Ollama API call must pass `"num_ctx": 8192` via settings. Handled centrally in the LLM abstraction — never scattered across call sites.

```python
# enforced in src/techlens/llm/ollama_provider.py
options = {"num_ctx": self.settings.ollama_num_ctx}  # default: 8192
```

### Cloud LLM — placeholder only

Keep the provider abstraction wired for OpenAI but do not require it. Placeholder config in `.env.example`:

```
# OPENAI_API_KEY=sk-...   # optional cloud fallback — not used by default
```

## Storage

| Purpose | Choice | Phase |
|---|---|---|
| Relational (sources, articles, metadata, scores, feedback, reading state, digests, trends, syntheses) | SQLite | 1 |
| Vector store (embeddings, semantic dedup, semantic search) | ChromaDB (local, embedded) | 2 |
| Knowledge graph (concept nodes, article nodes, MENTIONS edges) | Kuzu (embedded graph DB) | 3 |

**Rule:** Use each storage tech for a clear purpose. Concept/graph data lives in Kuzu (Cypher queries, graph traversal). Trend and synthesis records live in SQLite (they're LLM-generated output with article foreign keys — relational data, not graph data).

## Embeddings

- **Provider:** Ollama — `nomic-embed-text` (local, no key required)
- Abstracted behind `EmbeddingProvider` interface; swap without changing call sites

## Content Acquisition Priority

1. RSS (default for Phase 1)
2. Newsletter email ingestion via Gmail MCP (Phase 2)
3. Official APIs
4. Public feeds
5. Web pages (only where permitted; respect robots.txt, ToS, rate limits, copyright)

**Do NOT scrape aggressively.** Store metadata + reasonable extracted content — never mirror publications.

## Initial Source Registry

Configurable via `config/sources.yaml`. Never hard-code URLs in application logic.

**Phase 1 bootstrap:**
1. DeepLearning.AI / The Batch — `https://www.deeplearning.ai/the-batch/`
2. Berkeley RDI — `https://rdi.berkeley.edu/`
3. ByteByteGo — `https://bytebytego.com/` *(high priority for architecture)*
4. Substack — configurable per-newsletter (RSS-based)

**Phase 2 additions:**
5. Medium — per-publication/author/topic RSS
6. OpenAI, Anthropic, Google DeepMind, Google Cloud AI, Microsoft Research, AWS ML, Meta AI, NVIDIA Developer, Hugging Face

**Phase 3 additions:**
7. arXiv, Papers With Code

## Secrets & Credentials

- All config via environment variables — `.env` file, git-ignored
- Never hard-code credentials
- `pydantic-settings` (`BaseSettings`) for typed env-var loading

```
# .env.example
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:32b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_NUM_CTX=8192
# OPENAI_API_KEY=             # optional cloud placeholder
DATABASE_URL=sqlite:///./techlens.db
CHROMA_PATH=./data.nosync/chroma
KUZU_PATH=./data.nosync/kuzu_graph   # directory — created on first run
LOG_LEVEL=INFO
```

## Quality Requirements

Modular · Testable · Observable · Configurable · Local-first · Provider-independent · Easy to extend.

Clear separation: **ingestion / processing / AI reasoning / storage / retrieval / UI**.

Logging + error handling throughout. Avoid unnecessary complexity.

## Repository Structure

```
techlens/
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── config/
│   ├── sources.yaml            # source registry (add/remove without code changes)
│   ├── profile.yaml            # personal relevance profile (tiers, weights)
│   └── user_weights.yaml       # adaptive scoring weights (written by feedback loop)
├── docs/
│   ├── PROJECT.md              # product vision, UX spec, phased roadmap
│   ├── AGENTS.md               # pipeline stage specs, agent designs
│   ├── TECH.md                 # this file — tech stack, storage strategy
│   ├── TESTS.md                # full test suite reference
│   ├── architecture-tradeoffs.md
│   ├── inference-calls.md
│   ├── hosting-options.md
│   └── lessons-learned.md
├── src/techlens/
│   ├── config.py               # Pydantic BaseSettings — all env vars
│   ├── llm/
│   │   ├── base.py             # LLMProvider ABC
│   │   ├── ollama_provider.py  # primary — enforces num_ctx
│   │   └── openai_provider.py  # placeholder stub
│   ├── embeddings/
│   │   ├── base.py             # EmbeddingProvider ABC
│   │   └── ollama_embeddings.py
│   ├── ingestion/              # Stage 1: RSS + web collectors
│   ├── processing/             # Stages 2–4: extract, normalize, dedupe, classify
│   ├── scoring/                # Stage 5: relevance scorer + adaptive feedback weights
│   ├── summarization/          # Stage 6: summarizer
│   ├── knowledge_graph/        # Phase 3: concept extractor, trend detector, synthesizer
│   ├── digest/                 # daily digest assembly
│   ├── storage/
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── db.py               # SQLite session factory
│   │   ├── graph_store.py      # Kuzu graph DB — concept nodes + MENTIONS edges
│   │   └── vector_store.py     # ChromaDB wrapper — semantic dedup + search
│   ├── scheduling/             # APScheduler setup — full pipeline job
│   └── api/                    # FastAPI routes
├── frontend/                   # React + TypeScript + Vite source
│   ├── src/
│   └── package.json
└── tests/
    ├── conftest.py             # shared fixtures — db_session, mock LLM providers
    ├── fixtures/               # sample RSS XML, article HTML
    ├── unit/                   # per-stage unit tests (mocked LLM, no Kuzu)
    └── integration/            # Phase 1 e2e smoke test + Phase 3 pipeline tests
```

## Test Strategy

- Unit tests per pipeline stage — LLM calls mocked via dependency injection
- Phase 1 integration: fixture RSS XML → parsed → scored → summarized → digest
- Phase 3 integration: summarized articles → extract concepts → detect trends → synthesize (all Kuzu calls mocked)
- All tests runnable with `uv run pytest` — no external services required

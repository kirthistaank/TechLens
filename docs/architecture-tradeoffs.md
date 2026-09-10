# TechLens — Architecture Tradeoffs

Every non-obvious tech decision made during the build, with the alternatives considered and the reasons behind the choices. Written for someone who wants to understand the *why*, not just the *what*.

---

## 1. LLM Runtime: Ollama vs Cloud APIs

**Decision: Ollama (local)**

| | Ollama (local) | Groq | OpenAI / Anthropic |
|---|---|---|---|
| Cost | Free forever | Free tier (~14,400 req/day) | Per-token |
| Privacy | Full — prompts never leave machine | Prompts sent to Groq | Prompts sent to third party |
| Rate limits | None | Yes (free tier) | Yes |
| Inference speed | Depends on CPU/GPU | ~500 tok/s | Fast |
| Setup | Install Ollama, pull model | API key, one config change | API key |
| Vendor lock-in | None | Low (OpenAI-compatible) | Medium |

**Why Ollama:** The pipeline runs daily on 40–100 articles. At ~2 LLM calls per article (score + summarise), that's 80–200 calls/day. Groq's free tier technically covers this, but there are two stronger reasons to stay local:

- **Privacy.** Every article sent to an external LLM leaks your reading habits, interests, and career focus to a third party. This is a personal intelligence tool — that data is sensitive.
- **Cost at scale.** Running the pipeline every day for two years means ~140,000 LLM calls. Free tiers have quotas that reset daily; if the pipeline ever runs twice (debug, backfill), you hit limits. Local has no ceiling.

The downside is laptop fan noise during inference. Mitigated with `LLM_THROTTLE_SECONDS` (1s sleep between calls) and `LLM_BATCH_SIZE` (cap articles per run).

**Escape hatch:** The `LLMProvider` abstraction means swapping to Groq is a config change — `ollama_base_url = https://api.groq.com/openai/v1`. No code changes. See `docs/hosting-options.md`.

---

## 2. Vector Store: ChromaDB vs Pinecone vs pgvector

**Decision: ChromaDB (local, embedded)**

| | ChromaDB | Pinecone | pgvector |
|---|---|---|---|
| Hosting | Local file | Cloud (free: 100k vectors) | Needs Postgres |
| Setup | `pip install chromadb` | API key + account | Postgres extension |
| Privacy | Full | Vectors + content sent to cloud | Local if self-hosted |
| Query speed | Fast for <1M vectors | Very fast at scale | Depends on PG config |
| Persistence | Local `.db` file | Cloud-managed | Postgres table |

**Why ChromaDB:** At ~100 articles/week the collection stays well under 10k vectors — ChromaDB embedded mode handles this without breaking a sweat. The alternatives don't hold up under the local-first constraint:

- **Pinecone** sends article content (as embeddings) to the cloud. Even though embeddings are not raw text, they can be approximately reversed. Not acceptable for a personal intelligence tool.
- **pgvector** requires standing up a Postgres instance, adding operational overhead for no benefit at this scale.

ChromaDB also handles semantic deduplication — if a new article embeds close enough to an existing one (cosine distance < 0.08), it's flagged as a duplicate before any LLM calls are made. This saves both inference time and cost.

---

## 3. Relational Database: SQLite vs PostgreSQL

**Decision: SQLite**

| | SQLite | PostgreSQL |
|---|---|---|
| Setup | Zero — single file on disk | Separate process, connection pooling |
| Concurrent writes | Single writer (fine for one user) | Multi-writer, row-level locking |
| Hosting | Trivial — copy the file | Managed DB or Docker container |
| Schema changes | `ALTER TABLE` | Alembic migrations recommended |
| Scale ceiling | ~100k articles comfortably | Effectively unlimited |

**Why SQLite:** This system has one user and one pipeline process. There is no concurrent write contention — the pipeline writes sequentially, the API reads between pipeline runs. SQLite is not a compromise here; it's the right tool for the workload.

The common mistake is reaching for Postgres "for production readiness" before the single-user, single-process assumption is ever violated. SQLite also makes backups trivial — `cp techlens.db techlens.db.bak`.

Migration path: the `DATABASE_URL` env var and SQLAlchemy mean moving to Postgres (e.g. Supabase free tier) is a one-line config change, not a migration project.

---

## 4. Knowledge Graph Store: Kuzu vs Neo4j vs SQLite adjacency tables

**Decision: Kuzu (embedded graph DB)**

This was the most considered Phase 3 decision. Three real options:

| | Kuzu | Neo4j (local) | SQLite adjacency |
|---|---|---|---|
| Setup | `pip install kuzu` | Docker or Neo4j Desktop (Java/JVM) | Already have SQLite |
| External process | None — embedded | Yes, ~500MB RAM minimum | None |
| Query language | Cypher (Neo4j-compatible) | Cypher | SQL JOINs |
| Graph traversal | Native, fast | Native, very fast | Painful beyond 2 hops |
| Browser/visualisation | Kuzu Explorer (via Docker) | Neo4j Browser (excellent) | None |
| Migration to Neo4j later | Trivial — same Cypher syntax | — | Significant rewrite |
| Maturity | 2023, active development | 15+ years | N/A |
| Additional Docker container | Not needed | Required | Not needed |

**Why not Neo4j:** Neo4j requires a JVM process (500MB+ RAM minimum) running alongside Ollama (8GB+) and FastAPI. On a laptop that's already hot from LLM inference, adding a Java process is a real problem. It also requires a separate Docker container in deployment. Kuzu is embedded — it starts and stops with the Python process.

**Why not SQLite adjacency tables:** For simple aggregations ("how many articles mention RAG?") SQLite JOINs work fine. But Phase 4 needs queries like "find all concepts two hops from Agentic AI" or "which concept clusters co-occur most often across sources?" Those queries become multi-level self-JOINs in SQL — hard to write, harder to optimise. Cypher expresses them in one line.

**Why Kuzu:** It's the only option that is simultaneously embedded (no process overhead), uses Cypher (same as Neo4j, so knowledge transfers and migration is trivial), and is actively maintained. The tradeoff is maturity — it's a 2023 project. For Phase 3 queries it's proven stable.

**Data split:** Concept nodes and MENTIONS edges live in Kuzu (graph semantics). Trend records live in SQLite (they're LLM-generated output tied to article foreign keys — relational data).

### Visualising the Kuzu graph (Kuzu Explorer)

Kuzu ships a browser-based graph explorer. Stop the TechLens backend first (Kuzu allows only one writer at a time), then:

```bash
docker run -p 55000:8000 \
  -v /Users/kirthi/Documents/NewMe2026/SideProject_aftergraduation/techlens/data.nosync:/database \
  -e KUZU_FILE=kuzu_graph \
  --rm kuzudb/explorer:latest
```

Open `http://localhost:55000`. The Kuzu database is a **directory** (`data.nosync/kuzu_graph/`) — mount its parent and set `KUZU_FILE` to the directory name.

Useful Cypher queries:
```cypher
-- Top concepts by mention count
MATCH (c:Concept) RETURN c ORDER BY c.article_count DESC LIMIT 20;

-- Which articles mention a specific concept
MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept {name: "Retrieval Augmented Generation"})
RETURN a.article_id, c.name;

-- Concept pairs that co-occur most often (proto-trend signal)
MATCH (a:ArticleNode)-[:MENTIONS]->(c1:Concept),
      (a)-[:MENTIONS]->(c2:Concept)
WHERE c1.name < c2.name
RETURN c1.name, c2.name, count(a) AS co_occurrences
ORDER BY co_occurrences DESC LIMIT 10;
```

---

## 5. Task Scheduler: APScheduler vs Cron vs Celery

**Decision: APScheduler (in-process)**

| | APScheduler | OS Cron | Celery + Redis |
|---|---|---|---|
| Setup | `pip install apscheduler` | Edit crontab / launchd | Redis + worker process |
| Runs inside app process | Yes | No | No |
| Container-friendly | Yes — no OS config | Needs crontab access | Needs Redis container |
| Visibility | App logs | System logs | Flower dashboard |
| Appropriate scale | Single recurring job | Simple OS-level tasks | High-volume distributed queues |

**Why APScheduler:** The pipeline is one job, runs once a day, for one user. Celery + Redis is designed for distributed task queues with many workers and thousands of jobs — using it here would mean running three processes (FastAPI + Celery worker + Redis) to do one thing per day.

OS cron seems simpler but breaks in containers (needs crontab or launchd access) and separates the schedule from the application code (configuration drift risk). APScheduler lives inside the FastAPI process: it starts when the app starts, respects the same environment variables, and writes to the same log stream. One process, one log.

---

## 6. Content Extraction: Trafilatura vs BeautifulSoup vs Readability

**Decision: Trafilatura**

| | Trafilatura | BeautifulSoup | Readability-lxml |
|---|---|---|---|
| Purpose | Article extraction | Generic HTML parsing | Article extraction |
| Boilerplate removal | Yes (nav, ads, footers, sidebars) | Manual CSS selectors per site | Yes |
| Language detection | Built-in | No | No |
| Encoding handling | Robust | Manual | Good |
| Maintenance | Actively maintained | Actively maintained | Slower updates |

**Why Trafilatura:** Content extraction is the most brittle part of any pipeline that reads from the open web. Every site structures its HTML differently; navigation, ads, cookie banners, and related-article widgets all pollute the extracted text. If they reach the LLM, they distort scoring and summarization.

Trafilatura is purpose-built for this problem — it uses a combination of HTML structure heuristics, density analysis, and XPath patterns to isolate main content. BeautifulSoup requires custom CSS selectors per site, which doesn't scale across 20+ sources. Readability-lxml is a good alternative but receives fewer updates and has weaker language handling.

---

## 7. Embedding Model: nomic-embed-text vs OpenAI ada-002 vs BGE

**Decision: nomic-embed-text (via Ollama)**

| | nomic-embed-text | OpenAI ada-002 | BGE-small-en |
|---|---|---|---|
| Hosting | Local via Ollama | Cloud — per-token cost | Local |
| Vector dimensions | 768 | 1536 | 384 |
| Privacy | Full | Article text sent to OpenAI | Full |
| Semantic quality | Good — strong on technical text | Excellent | Good |
| Cost | Free | ~$0.0001 / 1k tokens | Free |

**Why nomic-embed-text:** The local-first constraint rules out ada-002. For semantic deduplication (the main use case in Phase 2), 768-dimensional embeddings are more than sufficient — the goal is detecting "did two articles cover the same story?" not fine-grained semantic similarity scoring.

BGE-small is faster but its 384 dimensions compress meaning more aggressively, which slightly hurts dedup precision on technical content where terminology differences matter. nomic-embed-text hits the right balance of quality, speed, and dimension count.

---

## 8. Frontend Stack: React vs Vue vs plain HTML

**Decision: React + TypeScript + Vite + Tailwind**

| | React + TypeScript | Vue 3 | Plain HTML + Alpine.js |
|---|---|---|---|
| Component model | Strong, composable | Strong, composable | Minimal |
| Type safety | Excellent — catches API mismatches | Good with `<script setup lang="ts">` | None |
| Ecosystem | Largest | Large | Small |
| Build tooling | Vite (instant HMR) | Vite | Not needed |
| Bundle size | Medium | Smaller | Minimal |

**Why React + TypeScript:** The user is already familiar with React, which reduces friction. More importantly, TypeScript earns its keep specifically at the API boundary — when a backend schema changes (new field, renamed field, changed type), TypeScript catches the mismatch at build time, not at runtime when a user sees a blank card.

Tailwind was chosen because the UI needs to evolve quickly during development. Utility classes allow layout changes without context-switching to a CSS file; the purge step keeps the production bundle small.

---

## 9. Hosting Strategy (if moving off laptop)

See [`docs/hosting-options.md`](hosting-options.md) for the full breakdown. The core constraint is Ollama: the `qwen3:32b` model needs ~20GB RAM to load, which eliminates most free cloud tiers.

| Goal | Recommended path | Key constraint |
|---|---|---|
| Zero cost, keep Ollama | Oracle Cloud Always Free — Ampere A1, 24GB RAM | ARM-compatible; Ollama runs on ARM natively |
| Easiest deployment | Swap Ollama → Groq API; backend on Railway; frontend on Vercel | Prompts leave machine; free tier has daily quota |
| Local but accessible anywhere | Tailscale (free private VPN) — no cloud hosting at all | Laptop must stay on |

The architecture (provider abstractions, env-var config, SQLite file) was deliberately designed so any of these paths requires configuration changes only, not code changes.

---

## 10. Pipeline Design: Deterministic Workflow vs Multi-Agent

**Decision: Deterministic pipeline for Phases 1–2; true agents only where autonomy is genuinely needed (Phase 3+)**

The core pipeline — ingest → extract → deduplicate → score → summarise → digest — is a **deterministic workflow**. Each stage has a defined input contract, makes one LLM call with a structured prompt, and produces a defined output. This is intentional, not a limitation.

**Why not agents everywhere:** An agent is the right abstraction when a task requires autonomous decision-making across multiple steps — querying different tools, evaluating intermediate results, and deciding what to do next. That's not what scoring or summarisation needs. They need a well-engineered prompt and a reliable JSON response.

Agents add non-determinism (the same input can produce different tool call sequences), latency (multiple round-trips), and debugging complexity (harder to trace why an output changed). For a daily pipeline where reproducibility and observability matter, deterministic stages are the correct choice.

| Stage | Design | Reason |
|---|---|---|
| Score / Summarise | Pipeline stage (single LLM call) | Fixed input → fixed output; no multi-step reasoning needed |
| Concept extraction | Pipeline stage | Structured extraction from a known summary format |
| **Trend Detector** | **True agent** | Must query graph across time windows, evaluate evidence thresholds, and decide autonomously what constitutes a trend |
| Knowledge-Gap Detector (Phase 4) | True agent | Must reason across knowledge state graph + article history |
| Interview Coach (Phase 4) | True agent | Interactive, conversational, stateful across multiple turns |

Demonstrating *when not to use agents* is itself a Principal-level architectural judgment. The trend detector is an agent because no simpler design can express its logic cleanly. Everything else is not an agent because a simpler design is sufficient.

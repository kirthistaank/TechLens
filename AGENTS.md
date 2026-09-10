# TechLens — Agents & Pipeline Stages

## Pipeline (v1)

```
SOURCE INGESTION
      ↓
CONTENT EXTRACTION
      ↓
NORMALIZATION
      ↓
DEDUPLICATION
      ↓
CONTENT CLASSIFICATION
      ↓
RELEVANCE SCORING
      ↓
SUMMARIZATION
      ↓
TREND DETECTION           (Phase 3)
      ↓
KNOWLEDGE STORE
      ↓
PERSONALIZED DIGEST
      ↓
INTERACTIVE AI ASSISTANT  (Phase 4)
```

**Design note:** v1 stages are deterministic workflow steps that *use* LLMs. Only trend detection, knowledge-gap detection, and the interview coach are true agents (autonomous, multi-step, tool-using). Everything else is a pipeline stage.

---

## Stage 1 — Source Collector

**Type:** Scheduled job (not an agent)

**Responsibilities:**
- Retrieve RSS feeds, newsletter content, configured web sources
- Detect new content, avoid reprocessing
- Store metadata
- Resilient to temporary failures (retry with backoff)

**Trigger:** Scheduled (cron/launchd), configurable per-source polling frequency

**Inputs:** Source registry entries

**Outputs:** Raw article records + metadata (Title, URL, Author, Publication, Published date, Retrieved date, Source type, Categories, Content, Content hash)

**Failure behavior:** Log, mark source as degraded after N failures, continue with other sources

**Source acquisition priority order:**
1. RSS
2. Newsletter email ingestion
3. Official APIs
4. Public feeds
5. Web pages (only where permitted; respect robots.txt, ToS, rate limits, copyright)

---

## Stage 2 — Content Processor

**Type:** Pipeline stage

**Responsibilities:**
- Extract readable article content (strip nav, ads, boilerplate)
- Normalize text, detect language
- Extract title/author/date
- Split long documents into meaningful sections
- Preserve original URL

**Inputs:** Raw article HTML/text

**Outputs:** Cleaned article record with extracted content

**Constraint:** Do not store duplicate content unnecessarily

---

## Stage 3 — Deduplication

**Type:** Pipeline stage (uses embeddings in Phase 2+)

**Responsibilities:** Detect three classes of duplication:

1. **Exact duplicates** — same URL/content hash
2. **Near duplicates** — different articles discussing the same announcement
3. **Related stories** — different sources discussing the same underlying tech

Create a **canonical topic/event** where appropriate.

**Example output:**
> **Topic: New model announcement**
> 4 sources covered this.
> Best source: X
> Additional perspectives: Y, Z

**Phase 1:** URL + content-hash exact match; title similarity heuristic
**Phase 2+:** Embedding-based semantic clustering

---

## Stage 4 — Content Classifier

**Type:** Pipeline stage (LLM call)

**Responsibilities:** Assign one or more categories per article (see PROJECT.md Content Categories).

**Inputs:** Cleaned article + category taxonomy

**Outputs:** Article with category tags + confidence scores

---

## Stage 5 — Relevance Scorer

**Type:** Pipeline stage (LLM call, rubric-based)

**Responsibilities:** Score every article 0–100 based on:

- **Career relevance** — helps a Principal/Senior Staff AI Architect?
- **Technical depth** — substantive technical info?
- **Novelty** — actually new?
- **Architecture value** — teaches a design pattern, tradeoff, or failure mode?
- **Industry importance** — likely to influence the ecosystem?
- **Personal interest** — matches configured interests?
- **Duplication penalty** — already appeared?

**Output includes:** score, recommendation (READ/SKIM/IGNORE), rationale (1–2 sentences)

**Example:**
| Article | Score | Recommendation |
|---|---:|---|
| New agent architecture | 94 | READ |
| Kubernetes optimization | 78 | SKIM |
| Generic "AI will change everything" | 12 | IGNORE |

---

## Stage 6 — Summarizer

**Type:** Pipeline stage (LLM call)

**Constraint:** Do NOT produce long summaries.

**Output per important article:**
- **What happened?** — max 2 sentences
- **Why does it matter?** — max 2 sentences
- **Technical insight** — 1–3 bullets
- **Architecture implication** — what changes architecturally?
- **Tradeoffs** — benefits and costs
- **Should I read it?** — READ / SKIM / IGNORE
- **Estimated reading time** — e.g., "READ — 7 minutes"

---

## Agent A — Trend Detector (Phase 3)

**Type:** True agent (multi-step, autonomous, tool-using)

**Why an agent:** Requires querying knowledge store across time windows, embedding comparisons, cluster analysis, and iterative refinement — a workflow step can't cleanly express this.

**Responsibilities:** Identify recurring themes across articles/sources over rolling windows (7d, 30d, 90d).

**Example output:**
> **Emerging trend: Production agent infrastructure**
> **Trend:** Production-grade agent infrastructure is becoming a distinct architecture layer.
> **Evidence:** 12 articles across 7 sources during the last 30 days.
> **Why it matters:** [Enterprise AI architecture implication.]
> **Related technologies:** MCP, agent memory, evaluation, observability, guardrails
> **Confidence:** High / Medium / Low

---

## Agent B — Knowledge-Gap Detector (Phase 4)

**Type:** True agent

**Responsibilities:** Compare user's knowledge-state graph (Seen/Read/Understood/Mastered) against trending topics and Tier-1 categories. Surface gaps like: "You've seen 8 articles about agent evaluation but never demonstrated understanding — suggested learning path: X."

---

## Agent C — Interview Coach (Phase 4)

**Type:** True agent (interactive, conversational)

**Responsibilities:**
- Generate architecture/system-design questions grounded in recently consumed content
- Evaluate answers on: architecture, tradeoffs, scalability, reliability, security, cost, observability, operational complexity
- Update knowledge-state graph based on quiz performance

**Example:**
> You read three articles about agentic RAG.
> "You're designing an enterprise RAG platform for 10,000 users. When would you introduce agentic retrieval instead of a deterministic retrieval pipeline?"

---

## Knowledge Graph (Phase 3)

Lightweight graph used by Trend Detector, Knowledge-Gap Detector, and semantic search.

**Entities:** Technology, Company, Product, Research paper, Architecture pattern, Concept, Trend, Person, Article, Source

**Relationships:** ARTICLE_ABOUT, RELATED_TO, EXTENDS, CONTRADICTS, INTRODUCES, USED_BY, COMPETES_WITH, PART_OF, EVIDENCE_FOR

**Answers questions like:**
- "What have I learned about agent evaluation?"
- "What trends have appeared repeatedly over the last 3 months?"
- "Which concepts are related to GraphRAG?"
- "Show me everything I've consumed about AI observability."

**Constraint:** Do not use Neo4j everywhere just because it's available. Use each storage tech for a clear purpose.

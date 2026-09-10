# Building TechLens: Lessons Learned from a Local-First AI Intelligence Agent

*A Principal AI Architect's notes on building a personal AI pipeline that filters the internet so you don't have to.*

---

## What is TechLens?

TechLens is a local-first AI tech intelligence agent I built as a side project. Every day it ingests 15+ RSS feeds and web sources, extracts full article content, embeds them into a vector store, scores each article for relevance to my career goals as a Principal AI Architect, summarises the ones worth reading, and delivers a curated daily brief — all running entirely on my laptop with no cloud dependencies.

The stack: Python + FastAPI backend, React + TypeScript frontend, SQLite, ChromaDB, and Ollama running `qwen2.5:7b` locally.

This post is a collection of hard-won lessons from building it — bugs, architecture mistakes, and things I'd do differently.

---

## 1. ChromaDB Will Silently Use the Wrong Embedding Model

**The bug:** After wiring up Phase 2 (embeddings + semantic dedup), I got this error mid-pipeline:

```
chromadb.errors.InvalidArgumentError: Collection expecting embedding
with dimension of 384, got 768
```

**Root cause:** I was calling `collection.upsert()` with `documents=[content]` but without `embeddings=[vector]`. ChromaDB, seeing no explicit embedding, auto-embedded the content using its built-in `all-MiniLM-L6-v2` model — which produces 384-dim vectors. Then when I queried with my `nomic-embed-text` 768-dim vectors, the dimensions didn't match.

**Fix:** Always pass the embedding explicitly. Never let ChromaDB embed for you unless you're using its default model everywhere:

```python
collection.upsert(
    ids=[str(article_id)],
    embeddings=[embedding],   # always explicit
    documents=[content[:4000]],
    metadatas=[metadata],
)
```

**Lesson:** If you bring your own embedding model, own the embedding call end-to-end. ChromaDB's silent fallback to its own model is a footgun that only surfaces once you have data in the collection.

---

## 2. Never Cache a ChromaDB Collection Object

**The bug:** After deleting the ChromaDB collection externally (e.g. wiping `data/chroma` during dev), the app crashed with:

```
chromadb.errors.NotFoundError: Collection [uuid] does not exist.
```

**Root cause:** I had a global `_collection` variable caching the collection object. ChromaDB collection objects hold an internal UUID. When the collection is deleted and recreated, the cached object's UUID is stale and all subsequent calls fail.

**Fix:** Cache only the client, never the collection. Call `get_or_create_collection()` fresh on every access — it's cheap:

```python
_client: chromadb.ClientAPI | None = None

def get_collection() -> chromadb.Collection:
    return _get_client().get_or_create_collection(
        name="articles",
        metadata={"hnsw:space": "cosine"},
    )
```

**Lesson:** Treat collection objects as short-lived handles, not long-lived singletons. The extra `get_or_create_collection()` call is negligible and saves you a class of stale-reference bugs entirely.

---

## 3. Ollama's Default Timeout Will Silently Fail Long Inferences

**The bug:** Articles were being scored with `score: 0.0` and `"Scoring failed."` rationale, despite Ollama appearing healthy.

**Root cause:** I had set `keep_alive: 0` to unload the model from memory after each call (freeing RAM between pipeline stages). What I didn't account for: when the next call comes in, Ollama has to reload `qwen2.5:7b` from disk before it can run inference. On a laptop, that reload + inference easily exceeds the default 180-second HTTP timeout.

**Fix:** Increase the timeout significantly for local LLM calls:

```python
_TIMEOUT_SECONDS = 600.0  # 10 min: model reload + inference

response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
```

**Lesson:** `keep_alive=0` and short timeouts are mutually incompatible. Either keep the model warm (`keep_alive=-1`) and use a normal timeout, or unload it and give yourself a generous timeout that accounts for cold-load time.

---

## 4. LLM Inference Will Thermal-Throttle Your Laptop

**The observation:** Running 88 sequential LLM calls (44 articles × score + summarise) pegged all CPU cores continuously, spun up the fan to max, and caused the laptop to thermally throttle — making subsequent calls slower, not faster.

**Root cause:** Local LLM inference is extremely CPU-intensive. Running them back-to-back with no breathing room means the CPU temperature stays at the ceiling the entire time.

**Fix — two complementary levers:**

1. **Throttle between calls:** A 1-second sleep between LLM calls gives the CPU time to dissipate heat. The pipeline takes ~90 seconds longer total but sustained thermal load drops significantly.

2. **Batch size limit:** Cap how many articles a single pipeline run processes. With `llm_batch_size=15`, the scheduler runs more frequently with shorter, cooler bursts instead of one long hot run.

```python
# config.py
llm_throttle_seconds: float = 1.0   # sleep between LLM calls
llm_batch_size: int = 0             # 0 = no limit
```

**Bonus tip:** Move ML data directories (ChromaDB, model weights) out of iCloud-synced folders. I stored my project in `~/Documents/` which iCloud syncs. After every pipeline run, `fileproviderd` would try to upload gigabytes of embedding data — adding CPU load long after inference finished. Renaming the data folder to `data.nosync` tells iCloud to skip it.

---

## 5. Pipeline Stage Counts Should Be Cumulative, Not Point-in-Time

**The confusion:** The sidebar showed "Extracted: 0, Scored: 2, Summarised: 44" — which looks like nothing was extracted and most things are broken.

**Root cause:** Each count was filtering for articles *currently at* that status. Since articles advance through stages (`extracted → scored → summarised`), a summarised article no longer has status `extracted`. So "Extracted: 0" just means no articles are *stuck* at extraction — which is actually good news.

**Fix:** Use cumulative counts — how many articles have *reached* each stage:

```python
_past_extracted = (ArticleStatus.extracted, ArticleStatus.scored,
                   ArticleStatus.summarized, ArticleStatus.ignored)
_past_scored    = (ArticleStatus.scored, ArticleStatus.summarized, ArticleStatus.ignored)

extracted  = session.query(Article).filter(Article.status.in_(_past_extracted)).count()
scored     = session.query(Article).filter(Article.status.in_(_past_scored)).count()
summarized = session.query(Article).filter_by(status=ArticleStatus.summarized).count()
```

**Lesson:** Pipeline status UIs should show a *funnel* (how many articles have passed each checkpoint), not a *queue* (how many are waiting at each stage). The funnel is more useful when everything is working; the queue is more useful when something is broken. Build the funnel and add per-stage queue counts only in a debug view.

---

## 6. Model the Full Article Lifecycle in Your Status Enum

I started with a simple enum: `pending → extracted → scored → summarised → failed`. This worked until I noticed articles with IGNORE recommendation sitting permanently in `scored` status — they were intentionally not summarised but looked like a processing backlog.

**Fix:** Add explicit terminal states for intentional non-actions:

```python
class ArticleStatus(str, Enum):
    pending    = "pending"
    extracted  = "extracted"
    scored     = "scored"
    summarized = "summarized"
    ignored    = "ignored"   # IGNORE-scored: pipeline complete, no summary needed
    failed     = "failed"
```

The summariser now marks IGNORE articles as `ignored` instead of leaving them in limbo:

```python
if article.recommendation == Recommendation.IGNORE:
    article.status = ArticleStatus.ignored
    continue
```

**Lesson:** Every branch of your processing logic should result in a meaningful terminal state. "Stuck in an intermediate state by design" is a bug waiting to confuse you.

---

## 7. Web Scrapers Need Strict URL Patterns

**The bug:** Articles titled "About", "Search", and "Newsletter Archive" were appearing in the pipeline, getting scored (poorly), and polluting the digest.

**Root cause:** The link pattern for web sources was too permissive. Any path on the domain matched, including navigation pages.

**Fix:** Tighten the regex to require article-shaped slugs (hyphens, multiple segments):

```python
# Too permissive — matches /about, /search, /contact
href="(/the-batch/[a-z0-9-]+)"

# Correct — requires at least one hyphen, excludes single-word paths
href="(/the-batch/[a-z0-9][a-z0-9-]*-[a-z0-9][a-z0-9-]*)"
```

**Lesson:** RSS feeds have structure that naturally excludes nav pages. Web scrapers don't — you have to build that exclusion yourself. Always check what your scraper actually collected after the first run; it will surprise you.

---

## 8. Provider Abstractions Are Worth the Upfront Investment

I built `LLMProvider` and `EmbeddingProvider` ABCs from the start, even though I only had one implementation each (Ollama). This felt like over-engineering at the time.

It paid off when:
- I needed to swap `qwen3:32b` for `qwen2.5:7b` (a one-line config change)
- I added a separate embedding model (`nomic-embed-text`) alongside the chat model
- Unit tests could use `MockLLMProvider` without touching Ollama

```python
class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system: str, user: str, json_mode: bool = False) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...
```

**Lesson:** For infrastructure-level dependencies (LLMs, vector stores, databases), one abstraction layer is almost always worth it — even in a solo side project. The cost is 30 minutes. The payoff is every future model swap, test, or provider change.

---

## 9. Stale Cached Digests Are a Silent Data Bug

**The bug:** After the pipeline ran for the first time (before any articles were summarised), it built and cached an empty digest. On subsequent API calls, the route returned the cached empty digest — even after 44 articles had been fully summarised.

**Root cause:** The cache-return logic only checked if the record existed, not if the cached content was stale relative to the current pipeline state.

**Fix:** Check both the cache content and the current DB state:

```python
if record:
    cached = json.loads(record.content)
    summarized_count = session.query(Article).filter_by(
        status=ArticleStatus.summarized
    ).count()
    if cached["items"] or summarized_count == 0:
        return cached  # valid cache
    # Stale empty cache — delete and rebuild
    session.delete(record)
    session.commit()
```

Also: filter archived articles from the cached digest at read time, not build time, so archiving an article takes effect immediately without rebuilding the digest.

**Lesson:** Caches need invalidation logic that understands your domain. "Record exists" is almost never sufficient — you need to validate the cache against the current source of truth.

---

## 10. Cross-Page UI State Needs a Single Source of Truth

**The bug:** Archiving an article on "Today's Brief" didn't remove it from the "Articles" page, and vice versa.

**Root cause:** Each page managed its own local state. Archiving updated one page's list but the other page had no way to know.

**Fix:** Lift shared state to the App root. A `Set<number>` of archived IDs in `App.tsx`, passed down to both pages. Archiving anywhere updates the single set, and both pages filter against it:

```tsx
// App.tsx
const [archivedIds, setArchivedIds] = useState<Set<number>>(new Set());

const handleArchive = (id: number) => {
    toggleArchive(id).catch(() => null);   // persist to backend
    setArchivedIds(prev => {
        const next = new Set(prev);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
    });
};
```

**Lesson:** For UI actions that affect multiple views, the state lives at the lowest common ancestor — not in each view. This is React 101, but it's easy to skip when building features incrementally.

---

## Final Thoughts

Building TechLens took longer than expected, mostly because of the bugs above. But every one of them taught me something useful about local AI systems that I wouldn't have learned from a tutorial.

The most important meta-lesson: **build the boring thing first.** The pipeline was working end-to-end in Phase 1 (SQLite, no vectors, no dedup) before I added any Phase 2 complexity. That foundation meant every Phase 2 bug was isolated — I knew the data was good and the issue was in the new layer.

The code is on my local machine for now. Maybe Phase 3 next — knowledge graph of concepts across articles, trend detection, and a "what should I learn next" recommender. But first, let the fan cool down.

---

*Stack: Python 3.11 · FastAPI · React + TypeScript · Vite · SQLite · ChromaDB · Ollama (qwen2.5:7b + nomic-embed-text) · APScheduler · Tailwind CSS*

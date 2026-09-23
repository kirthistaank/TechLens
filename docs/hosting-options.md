# Hosting TechLens: What Are Your Options?

TechLens was built local-first by design — no cloud dependencies, no API keys, no per-token costs. But what if you want to move it off your laptop? Here's the full picture.

---

## The Core Constraint: Ollama

Everything hinges on one question: **do you keep Ollama or replace it?**

Ollama runs `qwen3:32b` locally. That model needs **~20GB RAM** just to load. Free cloud tiers almost never offer that. This single constraint determines which hosting path makes sense for you.

---

## Option A: Keep Ollama (Local-First, No API Key)

If you want to preserve the original architecture — no API keys, no per-token cost, full control — you need a machine with enough RAM.

### Oracle Cloud Always Free

The only cloud platform that gives enough free compute to run Ollama:

| Resource | What You Get |
|---|---|
| CPU | 4 ARM Cores (Ampere A1) |
| RAM | **24 GB** |
| Storage | 200 GB block storage |
| Cost | Free forever |

**Why it works:**
- Ollama runs on ARM — no compatibility issues
- 24GB RAM is sufficient for `qwen3:32b` (needs ~20GB)
- Persistent storage for SQLite DB and ChromaDB
- APScheduler runs inside the app — no separate scheduler needed

**What you need to do:**
- Sign up at cloud.oracle.com (requires credit card, won't charge on Always Free tier)
- Provision an Ampere A1 VM
- Install Docker + Ollama + pull your models
- Update `ollama_base_url` in config if running Ollama as a separate service
- Mount volumes for `techlens.db` and `data/chroma`

**Verdict:** Best option if you want zero ongoing cost and no architecture changes. Note: 24GB is tight for `qwen3:32b` (~20GB model weight). Consider switching to `qwen3:14b` (~9GB) on this tier for comfortable headroom.

---

## Option B: Replace Ollama with a Cloud LLM API

If you're open to using an external LLM, the backend becomes lightweight (no GPU/CPU-heavy inference) and almost any free hosting tier works.

### LLM API Options

| Provider | Free Tier | Notes |
|---|---|---|
| **Groq** | ~14,400 req/day | Fastest inference, OpenAI-compatible API |
| **OpenRouter** | Free credits on signup | Routes to multiple models |
| **Together AI** | Free credits on signup | Good open-source model selection |
| **Google Gemini** | Generous free tier | Requires Google account |

At ~44 articles/day (score + summarise = ~88 LLM calls), Groq's free tier covers the pipeline comfortably.

**Code change required:** Swap `OllamaProvider` for an `OpenAICompatibleProvider` — about 30 lines since `LLMProvider` is already an abstraction. The rest of the pipeline doesn't change.

### Hosting the Backend (without Ollama)

| Platform | Free RAM | Persistent Storage | Verdict |
|---|---|---|---|
| **Render** | 512 MB | ❌ Ephemeral | OK for API only |
| **Railway** | ~512 MB | ✅ Volume mounts | Better option |
| **Fly.io** | 256 MB | ✅ Volume mounts | Works, tight on RAM |

### Hosting the Frontend

The React build is static files — any CDN works:

| Platform | Free Tier | Notes |
|---|---|---|
| **Vercel** | Unlimited static | Best DX, instant deploys |
| **Netlify** | 100GB/month bandwidth | Also excellent |
| **Cloudflare Pages** | Unlimited requests | Fastest CDN globally |

### Database

| Current | Free Cloud Alternative |
|---|---|
| SQLite (file) | **Supabase** (PostgreSQL, 500MB free) |
| ChromaDB (file) | **Pinecone** (1 index, 100k vectors free) |

---

## Side-by-Side Comparison

| | Oracle Cloud (Ollama) | Cloud LLM (e.g. Groq) |
|---|---|---|
| API key needed | ❌ No | ✅ Yes |
| Per-token cost | ❌ None | ✅ Possible (free tiers exist) |
| Inference speed | Depends on VM CPU | Very fast (Groq ~500 tok/s) |
| Architecture change | None | Swap LLM provider (~30 lines) |
| Privacy | Full — data never leaves your VM | Prompts sent to third party |
| Setup complexity | Medium (VM setup, Docker) | Low (just an API key) |
| Ongoing cost | Free forever | Free within quota |

---

## Recommended Path by Goal

**"I want zero cost and no API keys"**
→ Oracle Cloud Always Free. Provision an Ampere A1, install Ollama, containerise the app.

**"I want the easiest deployment"**
→ Swap Ollama for Groq, deploy backend on Railway, frontend on Vercel. Done in an afternoon.

**"I want to keep it local but accessible from anywhere"**
→ Keep running on your laptop, expose via **Tailscale** (free, private VPN). No hosting required — access from any device on your Tailscale network.

---

## What Would Need to Change in the Code

### For Oracle Cloud (minimal changes)
```python
# config.py — point to absolute paths on the VM
database_url: str = "sqlite:////data/techlens.db"
chroma_path: str = "/data/chroma"

# If Ollama runs as a separate Docker service
ollama_base_url: str = "http://ollama:11434"
```

### For Cloud LLM (swap provider)
```python
# config.py — add API key
groq_api_key: str = ""
ollama_model: str = "llama-3.1-70b-versatile"  # or any Groq model
ollama_base_url: str = "https://api.groq.com/openai/v1"
```
The `LLMProvider` abstraction means the rest of the codebase doesn't change.

---

## The Local-First Argument

TechLens was designed this way deliberately:

- **No per-token cost** — run the pipeline daily for years at zero marginal cost
- **Privacy** — your reading habits, interests, and career goals never leave your machine
- **No rate limits** — process 100 articles or 1000, same speed
- **No vendor lock-in** — swap models by changing one config line

If you move to a cloud LLM, you trade these properties for easier deployment and faster inference. Neither is wrong — it depends on how much you value data privacy and zero cost versus operational simplicity.

---

*Stack reference: Python 3.11 · FastAPI · React + TypeScript · SQLite · ChromaDB · Ollama · APScheduler · Tailwind CSS*

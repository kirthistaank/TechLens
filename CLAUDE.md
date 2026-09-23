# CLAUDE.md — Working agreements for this project

Auto-loaded every session. Full spec in `docs/PROJECT.md`, `docs/AGENTS.md`, `docs/TECH.md`.

## Project one-liner

Local-first AI Tech Intelligence Agent. Ingests tech/AI sources, filters ruthlessly, produces a 5–10 min/day personalized briefing for a Principal AI Architect audience.

## Non-negotiables

- **Local-first.** Core functionality must work without any cloud service. Ollama is the LLM — `qwen3:32b`, always with `num_ctx=32768`.
- **Context window always 8192.** Every Ollama API call must pass `num_ctx` from settings. Never use the 4096 default — it silently truncates long blog posts and newsletters.
- **Provider-agnostic LLM/embeddings.** Never call Ollama SDK directly in application code — always go through the `LLMProvider` / `EmbeddingProvider` abstraction.
- **Secrets via env vars only.** Never hard-code credentials. Use `pydantic-settings`.
- **Respect source ToS.** RSS first; scrape only where explicitly permitted.
- **No premature multi-agent orchestration.** v1 is a deterministic pipeline with LLM stage calls. True agents (autonomous, multi-step) only for trend detection (Phase 3), knowledge-gap detection (Phase 4), interview coach (Phase 4).

## Stack (locked)

- Python 3.11+, `uv` package manager, `ruff` formatter
- FastAPI backend, React + TypeScript + Vite frontend
- SQLite (v1), ChromaDB (Phase 2), Kuzu embedded graph DB (Phase 3)
- APScheduler (in-process scheduler — no OS config)
- Pydantic v2 for all config and data models

## Coding conventions

- Type-hint everything. No `Any` without justification.
- Pydantic models for all data shapes that cross layer boundaries.
- Small, testable modules. No god-classes.
- Prefer composition over inheritance.
- Log at boundaries (ingestion, LLM calls, storage writes). Don't log every internal step.
- **Every file must have a comment block at the top** describing what the file does (1–3 sentences). Use the language's native comment style (`"""` for Python, `//` for TypeScript/JS, `#` for YAML/shell).
- **Every function, method, and class must have a comment/docstring** describing purpose, parameters, and return value where non-obvious.
- This applies to all file types: `.py`, `.ts`, `.tsx`, `.yaml`, `.toml`, `.sh`.
- `ruff` must pass before committing.

## Ollama num_ctx reminder

Before wiring any LLM call, confirm `num_ctx` flows from `settings.ollama_num_ctx` (default 8192). If you see a raw Ollama call without this option, it is a bug.

## Testing

- Every pipeline stage has a unit test with a mocked `LLMProvider`.
- Phase 1 end-to-end smoke test: fixture RSS XML → digest output. Must pass with `uv run pytest`.
- Snapshot tests for summarizer prompts (tolerance-based diff, not exact string match).

## Build discipline

- **Ship phases in order.** No Phase 2 code until Phase 1 is working end-to-end.
- **Before significant code**, produce: architecture, data model, Phase-1 implementation plan. Then build.
- **Ask before adding a dependency.** Can stdlib or an already-installed package do it?

## When in doubt

- Prefer the boring solution.
- Prefer SQLite over Postgres until Phase 1 is proven.
- Add complexity only when the current phase requires it.

## User profile

Principal-level AI/software architect. Career goal: Principal AI Architect / Enterprise AI Platform Architecture. Assume deep systems knowledge — explain *novel* architecture patterns and tradeoffs, not basics.

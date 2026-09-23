# TechLens — Local AI Tech Intelligence Agent

## Problem

I consume a large volume of high-quality tech/AI content (newsletters, blogs, Substacks, research, engineering blogs) but suffer from:

- Too much information, too much duplication across sources
- Poor prioritization and generic summaries that don't tell me *why* something matters
- Difficulty connecting individual articles into larger trends
- Difficulty retaining what I read
- Difficulty translating technical developments into architecture knowledge
- Difficulty turning information consumption into career preparation

The problem is NOT lack of access. It is signal extraction from noise.

## Product Vision

A **local-first AI Tech Intelligence Agent** that acts as a personal technology research assistant. Instead of asking me to read everything, it continuously collects, filters, connects, and produces a concise personalized briefing.

## Optimization Target

> **Maximum useful knowledge gained per minute of my attention.**

## Core Question the System Answers

> "What happened in technology, what matters to me, why does it matter, and what should I learn from it?"

Every piece of content is ultimately classified as: **READ / SKIM / IGNORE**.

## Primary User

Senior/Principal-level software and AI architect with expertise in:
- Distributed systems, data engineering, AI/ML, GenAI, RAG, Agentic AI, Multi-agent systems, Knowledge graphs, Cloud, AI platforms, Enterprise AI

Career trajectory:
- Senior Staff AI Engineer → Principal AI Engineer → AI Architect → Principal Architect → Enterprise AI Platform Architecture

System must prioritize content that improves: technical depth, architecture knowledge, emerging AI understanding, system-design capability, enterprise AI knowledge, interview readiness, ability to discuss current trends intelligently.

## Success Criteria

- I spend **5–10 minutes/day** and understand what happened, what matters, what to read, what to ignore.
- After several months, I can answer: *"What are the important AI architecture trends right now, and why do they matter?"* without remembering which newsletter it came from.

## Non-Goals

- Generic chatbot
- Generic RSS reader
- Generic news website
- Complicated autonomous agent framework
- Social network
- Full document-management platform

## Guiding Design Principle (Architect's Note)

**Do NOT start with multi-agent orchestration.** v1 is a workflow with specialized AI stages:

`RSS → Extract → Deduplicate → Score → Summarize → Store → Digest`

Add agents only where autonomy genuinely helps — specifically **trend detection, knowledge-gap detection, and the interview coach**. Demonstrating *when not to use agents* is itself a Principal-level signal.

## Phased Roadmap

### Phase 1 (MVP)
RSS ingestion, source registry, article storage, content extraction, basic deduplication, relevance scoring, short summarization, READ/SKIM/IGNORE, local web UI, daily digest.
Sources: DeepLearning.AI, ByteByteGo, Berkeley RDI, configurable RSS, Substack RSS.

### Phase 2
Medium, more engineering blogs, semantic deduplication, embeddings, search, user feedback.

### Phase 3
Knowledge graph, trend detection, cross-source synthesis, personal knowledge memory.

### Phase 4
Interview coach, knowledge-gap detection, adaptive learning, weekly architecture briefing.

## Personal Relevance Profile

### Tier 1 (highest priority)
Agentic AI, Multi-agent architecture, Enterprise AI, AI platform architecture, RAG, Knowledge graphs, LLM evaluation, AI observability, AI governance, AI security, AI infrastructure, Distributed systems, System design.

### Tier 2
Generative AI, Vector databases, Model serving, Kubernetes, Cloud AI, Data engineering, ML engineering.

### Tier 3
Foundation model announcements, Multimodal AI, AI research, New model architectures.

### Low Priority
Consumer AI apps, AI funding news, generic AI productivity tips, marketing-heavy announcements, repetitive AI news, opinion pieces without technical substance.

Profile is configurable.

## Content Categories

- **AI/ML** — LLMs, foundation models, GenAI, multimodal, training, fine-tuning, inference, evaluation
- **Agentic AI** — Agents, orchestration, multi-agent, memory, tool use, MCP, planning, evaluation
- **RAG** — RAG, GraphRAG, vector search, hybrid search, retrieval, knowledge graphs, semantic search, reranking
- **Enterprise AI** — Platforms, governance, security, observability, gateways, guardrails, responsible AI, enterprise architecture
- **Infrastructure** — Kubernetes, cloud, distributed systems, data platforms, databases, vector DBs, model serving, GPU
- **Software Architecture** — System design, scalability, reliability, distributed systems, event-driven, microservices, data architecture
- **Career / Architecture** — Principal architect, Staff+ engineering, tradeoffs, technical leadership, system design interviews

## User Experience

### Daily Digest (≤5–7 items)
- 🔥 **You should know** — 3 highest-value items (headline, why you care, architecture takeaway, READ/SKIM/IGNORE)
- 📈 **Emerging trend** — 1 theme
- 🧠 **One concept to learn** — 1 technical concept

### Weekly Briefing (≤10 min read)
1. Top 5 developments
2. Emerging trends
3. Architecture patterns
4. Technologies gaining importance
5. Technologies losing relevance
6. What I should learn
7. What I can safely ignore
8. Principal Architect interview questions (3–5 generated from the week)

### Article Card
Score/badge (READ/SKIM/IGNORE) · source · est. time · What happened · Why should I care · Architecture takeaway · Tradeoffs · [Read Original] [Save] [Mark Important] [Ask AI]

### Interview Coach Mode
"Quiz me on what I learned this week." System generates architecture/system-design questions grounded in consumed content. Evaluates on: architecture, tradeoffs, scalability, reliability, security, cost, observability, operational complexity.

### "Why Should I Care?" Mode
For every important article: generic summary → personal interpretation → architecture interpretation → interview interpretation.

### Search (semantic)
Examples: "What have I read about agent memory?" · "Best articles on GraphRAG?" · "What changed in RAG in the last six months?" · "Major trends in enterprise AI?" · "What should I learn before interviewing for Principal AI Architect?"

## Feedback Loop

Track: articles opened/skipped/saved/marked-important, topics searched, questions asked, quiz performance. Adjust ranking weights so repeated skips lower a topic and repeated opens raise it. Gradually build a personalized filter.

## Personal Knowledge States

- **Seen** — encountered
- **Read** — actually read
- **Understood** — demonstrated understanding via interaction
- **Important** — user-flagged
- **Mastered** — answered questions correctly multiple times

Used to avoid re-explaining known material.

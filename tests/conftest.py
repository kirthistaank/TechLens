"""
Shared pytest fixtures for TechLens tests.
Provides an in-memory SQLite session and a mock LLMProvider used across all unit tests.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from techlens.llm.base import LLMProvider
from techlens.storage.models import Base


@pytest.fixture()
def db_session():
    """In-memory SQLite session — isolated per test, no disk state."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class MockScorerLLM(LLMProvider):
    """Mock LLM that always returns a valid scoring JSON response."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        return json.dumps({
            "score": 85,
            "recommendation": "READ",
            "rationale": "Highly relevant to enterprise AI architecture and RAG systems.",
            "categories": ["agentic_ai", "rag", "enterprise_ai"],
        })

    def is_available(self) -> bool:
        return True


class MockSummaryLLM(LLMProvider):
    """Mock LLM that always returns a valid summarization JSON response."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        return json.dumps({
            "what_happened": "A new approach to enterprise RAG was published.",
            "why_it_matters": "Directly applicable to AI platform architecture design.",
            "technical_insights": [
                "Bi-encoder outperforms cross-encoder at scale",
                "HyDE adds latency but improves recall by 20%",
            ],
            "architecture_implication": "Requires a separate retrieval microservice boundary.",
            "tradeoffs": "Higher recall at the cost of 2x query latency.",
            "estimated_reading_minutes": 6,
        })

    def is_available(self) -> bool:
        return True


class MockFailingLLM(LLMProvider):
    """Mock LLM that always raises — tests fallback/error handling."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        raise RuntimeError("LLM unavailable")

    def is_available(self) -> bool:
        return False


@pytest.fixture()
def mock_scorer_llm() -> MockScorerLLM:
    return MockScorerLLM()


@pytest.fixture()
def mock_summary_llm() -> MockSummaryLLM:
    return MockSummaryLLM()


@pytest.fixture()
def mock_failing_llm() -> MockFailingLLM:
    return MockFailingLLM()


class MockExtractorLLM(LLMProvider):
    """Mock LLM that returns 3 valid concept extraction entries."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        return json.dumps({
            "concepts": [
                {"name": "Agent Memory", "type": "architecture_pattern", "role": "primary"},
                {"name": "Retrieval Augmented Generation", "type": "technology", "role": "mentions"},
                {"name": "Anthropic", "type": "company", "role": "mentions"},
            ]
        })

    def is_available(self) -> bool:
        return True


class MockTrendLLM(LLMProvider):
    """Mock LLM that returns a valid trend card."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        return json.dumps({
            "name": "Rising Agent Memory Trend",
            "summary": "Multiple sources this week converged on production agent memory design. "
                       "The core pattern is separating episodic from semantic memory. "
                       "Principal architects should treat memory as a first-class infrastructure concern.",
            "confidence": "high",
        })

    def is_available(self) -> bool:
        return True


class MockSynthesisLLM(LLMProvider):
    """Mock LLM that returns a valid synthesis card."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        return json.dumps({
            "topic": "Agent Memory In Production Systems",
            "summary": "Three sources independently reached the same conclusion: production agents "
                       "need explicit memory boundaries. Episodic and semantic stores require "
                       "separate retrieval strategies.",
            "unique_perspectives": [
                "Source A focused on benchmark performance of memory retrieval.",
                "Source B analysed the privacy implications of shared memory in multi-tenant systems.",
            ],
            "key_insight": "Treat the memory tier as a microservice boundary, not an implementation detail.",
        })

    def is_available(self) -> bool:
        return True


@pytest.fixture()
def mock_extractor_llm() -> MockExtractorLLM:
    return MockExtractorLLM()


@pytest.fixture()
def mock_trend_llm() -> MockTrendLLM:
    return MockTrendLLM()


@pytest.fixture()
def mock_synthesis_llm() -> MockSynthesisLLM:
    return MockSynthesisLLM()

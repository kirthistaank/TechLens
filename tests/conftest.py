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

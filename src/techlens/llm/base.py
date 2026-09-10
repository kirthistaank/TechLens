"""
Abstract base class for LLM providers.
All LLM calls in TechLens go through this interface so the underlying model can be swapped
without changing application logic.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Send a chat message and return the response text."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is reachable."""

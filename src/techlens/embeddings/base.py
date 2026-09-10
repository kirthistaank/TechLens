"""
Abstract base class for embedding providers.
All embedding calls in TechLens go through this interface so the underlying model
(nomic-embed-text, OpenAI, etc.) can be swapped without changing call sites.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Provider-agnostic interface for generating text embeddings."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts. Default implementation calls embed() in a loop.
        Override for providers that support native batch endpoints.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors in the same order as the input.
        """
        return [self.embed(t) for t in texts]

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the embedding provider is reachable."""

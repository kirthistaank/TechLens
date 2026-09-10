"""
Ollama embedding provider — uses nomic-embed-text (768-dim) running locally.
Calls the Ollama /api/embeddings endpoint. No cloud dependency.
"""

import logging

import httpx

from techlens.config import settings
from techlens.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dimensional vectors
_TIMEOUT = 60.0


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Generates embeddings via the local Ollama server using nomic-embed-text."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_embed_model

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string via Ollama.

        Args:
            text: Text to embed (will be truncated to ~8k chars to stay within model limits).

        Returns:
            768-dimensional float vector.

        Raises:
            RuntimeError: If the Ollama request fails.
        """
        try:
            response = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text[:8000]},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            raise RuntimeError(f"Ollama embedding failed: {exc}") from exc

    def is_available(self) -> bool:
        """Return True if Ollama is reachable and nomic-embed-text is loaded."""
        try:
            httpx.get(f"{self.base_url}/api/tags", timeout=5.0).raise_for_status()
            return True
        except Exception:
            return False


def get_embedder() -> EmbeddingProvider:
    """Factory — returns the configured embedding provider."""
    return OllamaEmbeddingProvider()

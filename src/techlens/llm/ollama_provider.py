"""
Ollama LLM provider implementation.
Sends chat requests to the local Ollama API, always enforcing num_ctx=8192
to prevent silent truncation of long articles. Retries up to 3 times on failure.
OpenAIProvider is a non-functional stub for future use.
"""

import logging
import time

import httpx

from techlens.config import settings
from techlens.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY = 2.0
# Allow up to 10 min: covers model reload from disk (keep_alive=0) + inference on long prompts
_TIMEOUT_SECONDS = 600.0


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.num_ctx = settings.ollama_num_ctx
        self.temperature = settings.ollama_temperature

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": self.temperature,
            },
        }
        if json_mode:
            payload["format"] = "json"

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
            except Exception as exc:
                last_error = exc
                logger.warning("Ollama attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * attempt)

        raise RuntimeError(f"Ollama failed after {_MAX_RETRIES} attempts") from last_error

    def is_available(self) -> bool:
        try:
            httpx.get(f"{self.base_url}/api/tags", timeout=5.0).raise_for_status()
            return True
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """Placeholder stub — not used by default."""

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        raise NotImplementedError("OpenAI provider is a placeholder. Use OllamaProvider.")

    def is_available(self) -> bool:
        return False


def get_llm() -> LLMProvider:
    return OllamaProvider()

"""
Application settings loaded from environment variables and .env file.
All configuration for Ollama, database, email (SMTP + IMAP), and scheduling lives here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for TechLens, sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b" #"qwen3:32b" to heavy for oracle cloud Oracle Cloud Always Free — ARM Ampere A1 Cores
    ollama_embed_model: str = "nomic-embed-text"
    ollama_num_ctx: int = 8192
    ollama_temperature: float = 0.1
    # Unload model immediately after each call to free RAM (0 = no keep-alive)
    ollama_keep_alive: int = 0

    # Database
    database_url: str = "sqlite:///./techlens.db"

    # ChromaDB — local vector store for embeddings and semantic search (Phase 2)
    chroma_path: str = "./data/chroma"

    # Kuzu — embedded graph database for knowledge graph (Phase 3)
    kuzu_path: str = "./data/kuzu_graph"

    # Semantic dedup — cosine distance below this threshold = near-duplicate (0.08 ≈ similarity 0.92)
    semantic_dedup_threshold: float = 0.08

    # SMTP — outbound digest email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    digest_email_to: str = "kirthi.genai@gmail.com"
    digest_email_enabled: bool = True

    # IMAP — inbound newsletter ingestion (reuses smtp_user / smtp_password)
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_lookback_days: int = 7  # how far back to search for new newsletters

    # Article freshness — only collect/process articles published within this window
    article_lookback_days: int = 7       # ignore articles older than N days
    web_source_max_articles: int = 10    # max links to take from a web listing page

    # Thermal throttling — reduces sustained CPU load during LLM inference
    # Sleep this many seconds between each LLM call (score + summarize stages).
    # 0 = no throttle (full speed). 1-2s gives CPU time to cool between articles.
    llm_throttle_seconds: float = 1.0
    # Max articles to score/summarize per pipeline run. 0 = no limit (process all).
    # Set to e.g. 15 to process in smaller bursts across scheduled runs.
    llm_batch_size: int = 0

    # App
    log_level: str = "INFO"
    pipeline_schedule_hour: int = 6
    pipeline_schedule_minute: int = 0

    # Demo access (Version 2.0)
    demo_access_enabled: bool = True
    token_expiry_hours: int = 24
    ngrok_url: str = "http://localhost:8000"

    # Cloud LLM placeholder (not used by default)
    openai_api_key: str = ""


settings = Settings()

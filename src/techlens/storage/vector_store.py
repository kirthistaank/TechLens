"""
ChromaDB vector store wrapper for TechLens — Phase 2.
Stores article embeddings for semantic search and near-duplicate detection.
One collection: "articles". Document IDs are the SQLite article.id as strings.
"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from techlens.config import settings

logger = logging.getLogger(__name__)

# Cosine distance threshold for near-duplicate detection.
# Distance = 1 - cosine_similarity, so 0.08 ≈ similarity of 0.92.
NEAR_DUPLICATE_DISTANCE = 0.08

# Only cache the client, not the collection — collection objects go stale if
# the collection is deleted externally (e.g. during dev). get_or_create_collection
# is cheap so we call it fresh on every access.
_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    """Return (or create) the persistent ChromaDB client."""
    global _client
    if _client is None:
        path = Path(settings.chroma_path)
        path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB initialised at %s", path)
    return _client


def get_collection() -> chromadb.Collection:
    """
    Return the articles collection, creating it if it doesn't exist.
    Called fresh on every use — never caches the collection object to avoid
    stale references after external deletions.
    """
    return _get_client().get_or_create_collection(
        name="articles",
        metadata={"hnsw:space": "cosine"},
    )


def add_article(
    article_id: int,
    content: str,
    metadata: dict,
    embedding: list[float],
) -> None:
    """
    Add or update an article embedding in the vector store.

    Always pass the pre-computed embedding explicitly so ChromaDB never falls back
    to its built-in all-MiniLM model (384-dim), which would conflict with
    nomic-embed-text's 768-dim vectors used everywhere else.

    Args:
        article_id: SQLite article primary key — used as the ChromaDB document ID.
        content:    Cleaned article text stored alongside the embedding.
        metadata:   Dict of filterable fields (title, source, score, etc.).
        embedding:  Pre-computed 768-dim vector from nomic-embed-text.
    """
    get_collection().upsert(
        ids=[str(article_id)],
        embeddings=[embedding],
        documents=[content[:4000]],
        metadatas=[metadata],
    )


def find_similar(
    embedding: list[float],
    n_results: int = 5,
    exclude_id: int | None = None,
    max_distance: float = 1.0,
) -> list[dict]:
    """
    Query the vector store for articles similar to the given embedding.

    Args:
        embedding:    Query embedding vector.
        n_results:    Maximum number of results to return.
        exclude_id:   Article ID to exclude from results (the query article itself).
        max_distance: Only return results with cosine distance ≤ this value.

    Returns:
        List of dicts with keys: id, distance, metadata.
    """
    col = get_collection()
    count = col.count()
    if count == 0:
        return []

    results = col.query(
        query_embeddings=[embedding],
        n_results=min(n_results + 1, count),  # +1 to account for possible self-match
        include=["distances", "metadatas"],
    )

    hits = []
    for doc_id, dist, meta in zip(
        results["ids"][0], results["distances"][0], results["metadatas"][0]
    ):
        if exclude_id is not None and doc_id == str(exclude_id):
            continue
        if dist > max_distance:
            continue
        hits.append({"id": int(doc_id), "distance": dist, "metadata": meta})
        if len(hits) >= n_results:
            break

    return hits


def search(query_embedding: list[float], n_results: int = 10) -> list[dict]:
    """
    Full semantic search — return top-N articles by embedding similarity.

    Args:
        query_embedding: Embedding of the user's search query.
        n_results:       Number of results to return.

    Returns:
        List of dicts with id, distance, and metadata for the top matching articles.
    """
    return find_similar(query_embedding, n_results=n_results, max_distance=1.0)


def collection_count() -> int:
    """Return the number of articles currently stored in ChromaDB."""
    try:
        return get_collection().count()
    except Exception:
        return 0

"""
Kuzu embedded graph database for TechLens knowledge graph (Phase 3).
Manages Concept nodes, ArticleNode reference nodes, and MENTIONS relationships.
One Database singleton is shared; callers create lightweight per-operation Connections.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from techlens.config import settings

logger = logging.getLogger(__name__)

_db: kuzu.Database | None = None


def _get_db() -> kuzu.Database:
    """Return the singleton Kuzu Database, creating it on first call."""
    global _db
    if _db is None:
        Path(settings.kuzu_path).parent.mkdir(parents=True, exist_ok=True)
        _db = kuzu.Database(settings.kuzu_path)
    return _db


def get_conn() -> kuzu.Connection:
    """Return a new Connection to the shared Database. Create one per operation."""
    return kuzu.Connection(_get_db())


def init_graph() -> None:
    """Create graph schema tables if they do not already exist. Safe to call on every startup."""
    conn = get_conn()
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS Concept(
            name STRING,
            concept_type STRING,
            article_count INT64,
            source_count INT64,
            first_seen_at STRING,
            last_seen_at STRING,
            PRIMARY KEY(name)
        )
    """)
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS ArticleNode(
            article_id INT64,
            source_id STRING,
            PRIMARY KEY(article_id)
        )
    """)
    conn.execute("""
        CREATE REL TABLE IF NOT EXISTS MENTIONS(
            FROM ArticleNode TO Concept,
            role STRING
        )
    """)
    logger.info("Kuzu graph schema ready at %s", settings.kuzu_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_article_node(conn: kuzu.Connection, article_id: int, source_id: str) -> None:
    """Create an ArticleNode if it does not already exist."""
    result = conn.execute(
        "MATCH (a:ArticleNode {article_id: $id}) RETURN count(*)",
        parameters={"id": article_id},
    )
    if result.has_next() and result.get_next()[0] > 0:
        return
    conn.execute(
        "CREATE (:ArticleNode {article_id: $id, source_id: $src})",
        parameters={"id": article_id, "src": source_id},
    )


def upsert_concept(conn: kuzu.Connection, name: str, concept_type: str) -> None:
    """Create a Concept node or increment its article_count if it already exists."""
    now = _now_iso()
    result = conn.execute(
        "MATCH (c:Concept {name: $name}) RETURN c.article_count",
        parameters={"name": name},
    )
    if result.has_next():
        current = result.get_next()[0]
        conn.execute(
            "MATCH (c:Concept {name: $name}) SET c.article_count = $count, c.last_seen_at = $now",
            parameters={"name": name, "count": current + 1, "now": now},
        )
    else:
        conn.execute(
            "CREATE (:Concept {name: $name, concept_type: $type, article_count: 1, "
            "source_count: 0, first_seen_at: $now, last_seen_at: $now})",
            parameters={"name": name, "type": concept_type, "now": now},
        )


def link_article_concept(
    conn: kuzu.Connection, article_id: int, concept_name: str, role: str
) -> bool:
    """
    Create a MENTIONS edge from ArticleNode to Concept if none exists yet.
    Returns True if the edge was created, False if it already existed.
    """
    result = conn.execute(
        "MATCH (a:ArticleNode {article_id: $aid})-[:MENTIONS]->(c:Concept {name: $name}) "
        "RETURN count(*)",
        parameters={"aid": article_id, "name": concept_name},
    )
    if result.has_next() and result.get_next()[0] > 0:
        return False
    conn.execute(
        "MATCH (a:ArticleNode {article_id: $aid}), (c:Concept {name: $name}) "
        "CREATE (a)-[:MENTIONS {role: $role}]->(c)",
        parameters={"aid": article_id, "name": concept_name, "role": role},
    )
    return True


def refresh_source_counts(conn: kuzu.Connection) -> None:
    """
    Recalculate source_count for every concept from the graph.
    Run at the end of an extraction batch rather than per-article to reduce write churn.
    """
    result = conn.execute(
        "MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept) "
        "RETURN c.name, count(DISTINCT a.source_id) AS src_count"
    )
    while result.has_next():
        row = result.get_next()
        name, src_count = row[0], row[1]
        conn.execute(
            "MATCH (c:Concept {name: $name}) SET c.source_count = $count",
            parameters={"name": name, "count": src_count},
        )


def get_top_concepts(limit: int = 20) -> list[dict]:
    """Return top concepts ordered by article_count descending."""
    conn = get_conn()
    result = conn.execute(
        f"MATCH (c:Concept) "
        f"RETURN c.name, c.concept_type, c.article_count, c.source_count, "
        f"c.first_seen_at, c.last_seen_at "
        f"ORDER BY c.article_count DESC LIMIT {limit}"
    )
    rows = []
    while result.has_next():
        row = result.get_next()
        rows.append({
            "name": row[0],
            "concept_type": row[1],
            "article_count": row[2],
            "source_count": row[3],
            "first_seen_at": row[4],
            "last_seen_at": row[5],
        })
    return rows


def get_concepts_in_window(article_ids: list[int]) -> list[dict]:
    """
    Return per-concept article_count and source_count scoped to the given article ID set.
    Used by the trend detector to find qualifying clusters within a time window.
    """
    if not article_ids:
        return []
    conn = get_conn()
    ids_literal = ", ".join(str(i) for i in article_ids)
    result = conn.execute(
        f"MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept) "
        f"WHERE a.article_id IN [{ids_literal}] "
        f"RETURN c.name, c.concept_type, "
        f"count(a.article_id) AS article_count, "
        f"count(DISTINCT a.source_id) AS source_count"
    )
    rows = []
    while result.has_next():
        row = result.get_next()
        rows.append({
            "name": row[0],
            "concept_type": row[1],
            "article_count": row[2],
            "source_count": row[3],
        })
    return rows


def get_article_ids_for_concepts(concept_names: list[str]) -> dict[str, list[int]]:
    """
    Return a mapping of concept_name -> list of article_ids for each given concept.
    Queries the full graph (no window filter) — used by the knowledge map and synthesizer
    to resolve which articles are associated with each concept.

    Args:
        concept_names: List of Concept node names to look up.

    Returns:
        Dict mapping each concept name to its list of article IDs.
        Concepts with no articles map to an empty list.
    """
    result_map: dict[str, list[int]] = {name: [] for name in concept_names}
    if not concept_names:
        return result_map

    conn = get_conn()
    for name in concept_names:
        res = conn.execute(
            "MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept {name: $name}) RETURN a.article_id",
            parameters={"name": name},
        )
        ids: list[int] = []
        while res.has_next():
            ids.append(res.get_next()[0])
        result_map[name] = ids
    return result_map


def get_article_ids_for_concept(concept_name: str, article_ids_in_window: list[int]) -> list[int]:
    """Return the subset of article_ids_in_window that mention concept_name."""
    if not article_ids_in_window:
        return []
    conn = get_conn()
    ids_literal = ", ".join(str(i) for i in article_ids_in_window)
    result = conn.execute(
        f"MATCH (a:ArticleNode)-[:MENTIONS]->(c:Concept {{name: $name}}) "
        f"WHERE a.article_id IN [{ids_literal}] "
        f"RETURN a.article_id",
        parameters={"name": concept_name},
    )
    ids = []
    while result.has_next():
        ids.append(result.get_next()[0])
    return ids

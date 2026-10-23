from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.db.vector_store import get_profile_collection


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    source_type: str
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score between 0.0 and 1.0 (higher is better)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


def query_profile(
    query_text: str,
    top_k: int = 3,
    source_type: Optional[str] = None
) -> List[SearchResult]:
    """
    Performs semantic vector search against the profile collection.
    - query_text: The user question, ATS form prompt, or job requirement
    - top_k: Number of most relevant facts to return
    - source_type: Optional filter (e.g. 'faq', 'experience', 'project')
    """
    collection = get_profile_collection()

    where_filter = None
    if source_type:
        where_filter = {"source_type": source_type}

    # Query Chroma
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    search_results: List[SearchResult] = []

    # Chroma returns lists of lists (one per query_text)
    if not results["ids"] or not results["ids"][0]:
        return search_results

    ids = results["ids"][0]
    docs = results["documents"][0] if results.get("documents") else []
    metas = results["metadatas"][0] if results.get("metadatas") else []
    distances = results["distances"][0] if results.get("distances") else []

    for i in range(len(ids)):
        dist = distances[i] if i < len(distances) else 1.0
        # For cosine space: similarity = 1 - cosine_distance
        similarity = max(0.0, min(1.0, 1.0 - dist))

        meta = metas[i] if i < len(metas) else {}
        stype = meta.get("source_type", "unknown")

        search_results.append(
            SearchResult(
                chunk_id=ids[i],
                content=docs[i] if i < len(docs) else "",
                source_type=stype,
                similarity_score=round(similarity, 4),
                metadata=meta
            )
        )

    return search_results
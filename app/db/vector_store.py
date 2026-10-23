import os
from typing import List, Optional
import chromadb
from chromadb.utils import embedding_functions

from app.core.config import settings
from app.db.chunker import ProfileChunk

# Name of the Chroma collection storing profile data
PROFILE_COLLECTION_NAME = "user_profile_facts"

# Singletons to prevent re-initialization and memory thrashing
_chroma_client: Optional[chromadb.PersistentClient] = None
_embedding_function = None
_profile_collection = None


def get_embedding_function():
    """
    Returns the SentenceTransformer embedding function running locally.
    Configures single-threaded execution to prevent Windows OpenMP deadlocks.
    """
    global _embedding_function
    if _embedding_function is None:
        try:
            import torch
            torch.set_num_threads(1)
        except ImportError:
            pass

        _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL_NAME
        )
    return _embedding_function


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Returns a persistent ChromaDB client saving to disk.
    Cached as a singleton.
    """
    global _chroma_client
    if _chroma_client is None:
        settings.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_PERSIST_DIR))
    return _chroma_client


def get_profile_collection():
    """
    Retrieves or creates the vector collection for profile chunks.
    Cached as a singleton.
    """
    global _profile_collection
    if _profile_collection is None:
        client = get_chroma_client()
        embedding_func = get_embedding_function()
        _profile_collection = client.get_or_create_collection(
            name=PROFILE_COLLECTION_NAME,
            embedding_function=embedding_func,
            metadata={"hnsw:space": "cosine"}
        )
    return _profile_collection


def clear_profile_collection():
    """
    Deletes the current profile facts collection so no stale candidate facts remain.
    """
    global _profile_collection
    client = get_chroma_client()
    try:
        client.delete_collection(PROFILE_COLLECTION_NAME)
    except Exception:
        pass
    _profile_collection = None


def index_profile_chunks(chunks: List[ProfileChunk]) -> int:
    """
    Clears old profile chunks and indexes fresh chunks for the current candidate.
    """
    clear_profile_collection()
    collection = get_profile_collection()

    if not chunks:
        return 0

    ids = [chunk.chunk_id for chunk in chunks]
    documents = [chunk.content for chunk in chunks]
    metadatas = [
        {
            "source_type": chunk.source_type,
            **{k: str(v) for k, v in chunk.metadata.items()}
        }
        for chunk in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return collection.count()
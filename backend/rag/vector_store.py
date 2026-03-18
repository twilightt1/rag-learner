"""ChromaDB abstraction layer.

One persistent Chroma client shared across the app.
Collection name: 'rag_learner'
"""
import uuid
from typing import List, Dict, Any, Optional
import numpy as np

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings

_client: Optional[chromadb.PersistentClient] = None
_collection = None
COLLECTION_NAME = "rag_learner"


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(
    chunks: List[Dict[str, Any]],
    embeddings: np.ndarray,
) -> List[str]:
    """
    Store chunks + their embeddings in ChromaDB.

    Args:
        chunks:     List of chunk dicts (must have 'text', 'doc_id', etc.)
        embeddings: np.ndarray aligned with chunks list

    Returns:
        List of chroma_ids assigned to each chunk.
    """
    col = get_collection()
    ids = [str(uuid.uuid4()) for _ in chunks]

    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "doc_id": str(c["doc_id"]),
            "chunk_index": str(c.get("chunk_index", 0)),
            "page_num": str(c.get("page_num") or ""),
            "section": str(c.get("section") or ""),
            "source_type": str(c.get("source_type", "")),
            "token_count": str(c.get("token_count", 0)),
        }
        for c in chunks
    ]

    col.add(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=documents,
        metadatas=metadatas,
    )
    return ids


def query_chunks(
    query_embedding: np.ndarray,
    top_k: int = 8,
    doc_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k similar chunks from ChromaDB.

    Args:
        query_embedding: 1-D numpy array
        top_k:           Number of results
        doc_ids:         Optional filter — only return chunks from these docs

    Returns:
        List of result dicts: {chroma_id, text, score, metadata}
    """
    col = get_collection()

    where = None
    if doc_ids:
        str_ids = [str(d) for d in doc_ids]
        where = {"doc_id": {"$in": str_ids}}

    results = col.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "chroma_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "score": 1.0 - results["distances"][0][i],  # cosine: distance→similarity
            "metadata": results["metadatas"][0][i],
        })

    return output


def delete_chunks_by_doc(doc_id: int):
    """Remove all chunks belonging to a document."""
    col = get_collection()
    col.delete(where={"doc_id": str(doc_id)})


def get_collection_stats() -> Dict[str, Any]:
    col = get_collection()
    return {"total_chunks": col.count()}

"""ChromaDB abstraction layer.

One persistent Chroma client shared across the app.
Collection name: 'rag_learner'
"""
from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
import numpy as np

from fastapi import HTTPException
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
        chunks:     List of chunk dicts (must have 'text', 'doc_id', 'uuid', etc.)
        embeddings: np.ndarray aligned with chunks list

    Returns:
        List of chroma_ids assigned to each chunk.

    Raises:
        HTTPException: If embeddings shape mismatch or ChromaDB operation fails.
    """
    # Validate inputs
    if len(chunks) != embeddings.shape[0]:
        raise HTTPException(
            status_code=400,
            detail=f"Mismatched chunks ({len(chunks)}) and embeddings ({embeddings.shape[0]}) count"
        )

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
            "chunk_id": c.get("uuid"),  # Store the UUID of the Chunk row for later lookup
        }
        for c in chunks
    ]

    try:
        col.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector store add failed: {str(e)}")
    return ids


def query_chunks(
    query_embedding: np.ndarray,
    top_k: int = 8,
    doc_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k similar chunks from ChromaDB.

    Args:
        query_embedding: 1-D numpy array
        top_k:           Number of results
        doc_ids:         Optional filter — only return chunks from these docs

    Returns:
        List of result dicts: {chroma_id, chunk_id, text, score, metadata}
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
        metadata = results["metadatas"][0][i]
        output.append({
            "chroma_id": results["ids"][0][i],
            "chunk_id": metadata.get("chunk_id"),  # UUID of Chunk row
            "text": results["documents"][0][i],
            "score": 1.0 - results["distances"][0][i],  # cosine: distance→similarity
            "metadata": metadata,
        })

    return output


def delete_chunks_by_doc(doc_id: str):
    """Remove all chunks belonging to a document."""
    col = get_collection()
    col.delete(where={"doc_id": str(doc_id)})


def get_collection_stats() -> Dict[str, Any]:
    col = get_collection()
    return {"total_chunks": col.count()}


class VectorStore:
    """
    Optional OO wrapper around the functional API.

    Test suite uses this to inject a mock ChromaDB client.
    """

    def __init__(self, client=None):
        self._client = client
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            if self._client is None:
                self._collection = get_collection()
            else:
                self._collection = self._client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    def add_chunks(
        self, chunks: List[Dict[str, Any]], embeddings: np.ndarray
    ) -> List[str]:
        if len(chunks) != embeddings.shape[0]:
            raise HTTPException(
                status_code=400,
                detail=f"Mismatched chunks ({len(chunks)}) and embeddings ({embeddings.shape[0]}) count",
            )

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
                "chunk_id": c.get("uuid"),
            }
            for c in chunks
        ]

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Vector store add failed: {str(e)}")
        return ids

    def query_chunks(
        self,
        query_embedding: np.ndarray,
        top_k: int = 8,
        doc_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        where = None
        if doc_ids:
            str_ids = [str(d) for d in doc_ids]
            where = {"doc_id": {"$in": str_ids}}

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            output.append(
                {
                    "chroma_id": results["ids"][0][i],
                    "chunk_id": metadata.get("chunk_id"),
                    "text": results["documents"][0][i],
                    "score": 1.0 - results["distances"][0][i],
                    "metadata": metadata,
                }
            )
        return output

    def delete_chunks_by_doc(self, doc_id: str):
        self.collection.delete(where={"doc_id": str(doc_id)})

    def get_collection_stats(self) -> Dict[str, Any]:
        return {"total_chunks": self.collection.count()}

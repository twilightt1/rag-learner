"""RAG retriever with cross-encoder reranking.

Pipeline:
  1. Embed query with SentenceTransformer
  2. Retrieve top_k_retrieve candidates from ChromaDB
  3. Rerank with cross-encoder
  4. Return top_k_final chunks
"""
from __future__ import annotations

import threading
from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.rag.embedder import embed_query
from backend.rag.vector_store import query_chunks

_reranker = None
_rerank_lock = threading.Lock()


def get_reranker():
    global _reranker
    if _reranker is None:
        with _rerank_lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder
                _reranker = CrossEncoder(settings.rerank_model)
    return _reranker


def retrieve(
    query: str,
    doc_ids: Optional[List[str]] = None,
    top_k_retrieve: int = None,
    top_k_final: int = None,
) -> List[Dict[str, Any]]:
    """
    Full retrieval pipeline: embed → vector search → rerank.

    Args:
        query:          User's question string.
        doc_ids:        Optional list of document UUIDs to filter by.
        top_k_retrieve: Candidates to pull from ChromaDB.
        top_k_final:    Final chunks to return after reranking.

    Returns:
        List of chunk dicts sorted by relevance (best first):
        {chroma_id, chunk_id, text, score, rerank_score, metadata}
    """
    top_k_retrieve = top_k_retrieve or settings.top_k_retrieve
    top_k_final = top_k_final or settings.top_k_final

    # Step 1: embed query
    q_embedding = embed_query(query)

    # Step 2: vector search
    candidates = query_chunks(q_embedding, top_k=top_k_retrieve, doc_ids=doc_ids)

    if not candidates:
        return []

    # Step 3: cross-encoder rerank
    reranker = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    for i, c in enumerate(candidates):
        c["rerank_score"] = float(scores[i])

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

    return reranked[:top_k_final]

"""Singleton SentenceTransformer embedder.

Loads the model once at startup and provides encode() for both
single strings and batches. Thread-safe via a module-level lock.
"""
from __future__ import annotations

import threading
from typing import List, Union
import numpy as np

from backend.config import settings

_model = None
_lock = threading.Lock()


def get_embedder():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(settings.embed_model)
    return _model


def embed_texts(texts: List[str], batch_size: int = 64) -> np.ndarray:
    """
    Encode a list of strings into embeddings.

    Returns:
        np.ndarray of shape (len(texts), embedding_dim)
    """
    model = get_embedder()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,   # L2-normalised for cosine similarity
        convert_to_numpy=True,
    )
    return embeddings


def embed_query(query: str) -> np.ndarray:
    """Encode a single query string. Returns 1-D array."""
    return embed_texts([query])[0]

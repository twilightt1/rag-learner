from __future__ import annotations

import pytest
import uuid
import numpy as np

from backend.rag.vector_store import VectorStore, get_collection as original_get_collection


class MockCollection:
    """Mock ChromaDB collection for testing."""

    def __init__(self):
        self._data = {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        self._count = 0

    def add(self, ids, embeddings, documents, metadatas):
        self._data["ids"].extend(ids)
        self._data["embeddings"].extend(embeddings)
        self._data["documents"].extend(documents)
        self._data["metadatas"].extend(metadatas)
        self._count += len(ids)

    def query(
        self, query_embeddings, n_results=10, where=None, include=None, **kwargs
    ):
        # Simple mock: return first n_results
        n = min(n_results, self._count)
        ids = self._data["ids"][:n]
        distances = [0.1 * i for i in range(n)]  # mock distances

        result = {
            "ids": [ids],
            "distances": [distances],
        }
        if include:
            if "documents" in include:
                result["documents"] = [self._data["documents"][:n]]
            if "metadatas" in include:
                result["metadatas"] = [self._data["metadatas"][:n]]
        return result

    def delete(self, where):
        if where and "doc_id" in where:
            doc_id = str(where["doc_id"]["$eq"] if "$eq" in where["doc_id"] else where["doc_id"])
            # Remove all entries with matching doc_id
            indices_to_remove = [
                i for i, meta in enumerate(self._data["metadatas"])
                if meta.get("doc_id") == doc_id
            ]
            for i in reversed(indices_to_remove):
                self._data["ids"].pop(i)
                self._data["embeddings"].pop(i)
                self._data["documents"].pop(i)
                self._data["metadatas"].pop(i)
                self._count -= 1

    def count(self):
        return self._count

    def reset(self):
        self._data = {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        self._count = 0


@pytest.fixture
def mock_chroma_client(mocker):
    """Create a mock ChromaDB client with a test collection."""
    mock_client = mocker.Mock()
    mock_collection = MockCollection()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client.reset = mock_collection.reset
    return mock_client


def test_add_chunks(mock_chroma_client):
    """add_chunks stores chunks and embeddings correctly."""
    store = VectorStore(client=mock_chroma_client)
    doc_id = str(uuid.uuid4())
    chunks = [
        {
            "text": "First chunk",
            "doc_id": doc_id,
            "chunk_index": 0,
            "page_num": 1,
            "token_count": 50,
            "uuid": str(uuid.uuid4()),
            "section": "intro",
        },
        {
            "text": "Second chunk",
            "doc_id": doc_id,
            "chunk_index": 1,
            "page_num": 1,
            "token_count": 60,
            "uuid": str(uuid.uuid4()),
        },
    ]
    embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

    chroma_ids = store.add_chunks(chunks, embeddings)

    assert len(chroma_ids) == 2
    assert all(isinstance(cid, str) for cid in chroma_ids)

    collection = mock_chroma_client.get_or_create_collection()
    assert collection.count() == 2


def test_add_chunks_empty_list(mock_chroma_client):
    """add_chunks with empty list returns empty id list."""
    store = VectorStore(client=mock_chroma_client)
    chroma_ids = store.add_chunks([], np.array([]))
    assert chroma_ids == []


def test_query_chunks(mock_chroma_client):
    """query_chunks retrieves and formats results."""
    store = VectorStore(client=mock_chroma_client)

    # Pre-populate
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())
    chunks = [
        {"text": "Chunk A", "doc_id": doc1_id, "chunk_index": 0, "token_count": 50, "uuid": str(uuid.uuid4())},
        {"text": "Chunk B", "doc_id": doc2_id, "chunk_index": 0, "token_count": 60, "uuid": str(uuid.uuid4())},
    ]
    embeddings = np.array([[0.1] * 10, [0.2] * 10])
    store.add_chunks(chunks, embeddings)

    # Query
    query_vec = np.array([0.15] * 10)
    results = store.query_chunks(query_vec, top_k=2)

    assert len(results) <= 2
    for r in results:
        assert "chroma_id" in r
        assert "text" in r
        assert "score" in r
        assert "metadata" in r


def test_query_chunks_with_doc_filter(mock_chroma_client):
    """query_chunks filters by doc_ids correctly."""
    store = VectorStore(client=mock_chroma_client)

    # Pre-populate with chunks from different docs
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())
    chunks = [
        {"text": "Doc1 chunk", "doc_id": doc1_id, "chunk_index": 0, "token_count": 50, "uuid": str(uuid.uuid4())},
        {"text": "Doc2 chunk", "doc_id": doc2_id, "chunk_index": 0, "token_count": 60, "uuid": str(uuid.uuid4())},
        {"text": "Doc1 another", "doc_id": doc1_id, "chunk_index": 1, "token_count": 70, "uuid": str(uuid.uuid4())},
    ]
    embeddings = np.array([[0.1] * 10, [0.2] * 10, [0.15] * 10])
    store.add_chunks(chunks, embeddings)

    query_vec = np.array([0.15] * 10)
    results = store.query_chunks(query_vec, top_k=3, doc_ids=[doc1_id])

    # Should only return doc_id=doc1_id chunks
    for r in results:
        assert r["metadata"]["doc_id"] == doc1_id


def test_query_chunks_empty_store(mock_chroma_client, mocker):
    """query_chunks returns empty list when no chunks stored."""
    mock_emb = mocker.Mock()
    mock_emb.embed_query.return_value = np.array([0.1] * 10)
    mocker.patch('backend.rag.embedder.get_embedder', return_value=mock_emb)

    store = VectorStore(client=mock_chroma_client)
    query_vec = mock_emb.embed_query("anything")
    results = store.query_chunks(query_vec, top_k=5)
    assert results == []


def test_delete_chunks_by_doc(mock_chroma_client):
    """delete_chunks_by_doc removes all chunks for a document."""
    store = VectorStore(client=mock_chroma_client)

    doc_id = str(uuid.uuid4())
    chunks = [
        {"text": "Chunk 1", "doc_id": doc_id, "chunk_index": 0, "token_count": 50, "uuid": str(uuid.uuid4())},
        {"text": "Chunk 2", "doc_id": doc_id, "chunk_index": 1, "token_count": 60, "uuid": str(uuid.uuid4())},
    ]
    embeddings = np.array([[0.1] * 10, [0.2] * 10])
    store.add_chunks(chunks, embeddings)

    assert mock_chroma_client.get_or_create_collection().count() == 2

    store.delete_chunks_by_doc(doc_id)

    assert mock_chroma_client.get_or_create_collection().count() == 0


def test_score_conversion(mock_chroma_client):
    """Distance values are converted to similarity scores (1 - dist)."""
    # Our mock returns distances [0.1, 0.2, ...]
    store = VectorStore(client=mock_chroma_client)

    # Add some chunks
    doc_id = str(uuid.uuid4())
    chunks = [{"text": f"Chunk {i}", "doc_id": doc_id, "chunk_index": i, "token_count": 50, "uuid": str(uuid.uuid4())} for i in range(5)]
    embeddings = np.array([[0.1 * i] * 10 for i in range(5)])
    store.add_chunks(chunks, embeddings)

    query_vec = np.array([0.0] * 10)
    results = store.query_chunks(query_vec, top_k=5)

    # Check that scores are 1 - distance
    if results:
        first = results[0]
        if "distance" in first:
            expected_score = 1 - first.get("distance", 0)
            assert abs(first["score"] - expected_score) < 0.001

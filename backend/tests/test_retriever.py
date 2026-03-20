from __future__ import annotations

import pytest
import numpy as np

from backend.rag.retriever import retrieve, get_reranker


class DummyReranker:
    """Mock cross-encoder that returns predetermined scores."""

    def __init__(self, scores=None):
        self.scores = scores or [0.5]

    def predict(self, pairs):
        # Return fixed scores, cycling if fewer pairs than provided
        result = []
        for i in range(len(pairs)):
            score = self.scores[i % len(self.scores)]
            result.append(score)
        return np.array(result)


@pytest.fixture(autouse=True)
def mock_embedder(mocker):
    """Replace embed_query with a deterministic mock."""
    def mock_embed_query(text):
        # Return a consistent vector based on hash of text
        np.random.seed(hash(text) % (2**32))
        vec = np.random.randn(384).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    mocker.patch('backend.rag.retriever.embed_query', side_effect=mock_embed_query)


@pytest.fixture
def mock_vector_store(mocker):
    """Replace query_chunks with a mock that returns predictable results."""
    def _make_mock(results):
        async def mock_query(*args, **kwargs):
            return results
        return mock_query

    return _make_mock


def test_retrieve_returns_top_k_final(mocker, mock_vector_store):
    """retrieve returns exactly top_k_final chunks after reranking."""
    from backend.config import settings

    # Mock 8 candidates
    candidates = [
        {
            "chroma_id": f"c{i}",
            "text": f"Chunk {i}",
            "score": 0.5,
            "metadata": {"doc_id": str(i)},
        }
        for i in range(8)
    ]
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store(candidates))
    mocker.patch('backend.rag.retriever.get_reranker', return_value=DummyReranker(scores=list(range(8))))

    results = retrieve("test query", top_k_final=3)

    assert len(results) == 3
    # Should be sorted by rerank_score descending
    for i in range(len(results) - 1):
        assert results[i]["rerank_score"] >= results[i + 1]["rerank_score"]


def test_retrieve_empty_candidates(mocker, mock_vector_store):
    """retrieve returns empty list when no candidates found."""
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store([]))

    results = retrieve("test query")
    assert results == []


def test_retrieve_filters_by_doc_ids(mocker, mock_vector_store):
    """doc_ids parameter is passed to vector store."""
    candidates = [
        {"chroma_id": "c1", "text": "Chunk 1", "score": 0.5, "metadata": {"doc_id": "doc-uuid-1"}},
        {"chroma_id": "c2", "text": "Chunk 2", "score": 0.4, "metadata": {"doc_id": "doc-uuid-2"}},
    ]
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store(candidates))
    mocker.patch('backend.rag.retriever.get_reranker', return_value=DummyReranker(scores=[0.9, 0.8]))

    doc_id = "doc-uuid-1"
    results = retrieve("query", doc_ids=[doc_id])

    # Check that query_chunks was called with doc_ids filter
    mock_query.assert_called_once()
    call_kwargs = mock_query.call_args.kwargs
    assert "doc_ids" in call_kwargs
    assert call_kwargs["doc_ids"] == [doc_id]


def test_retrieve_custom_top_k(mocker, mock_vector_store):
    """Custom top_k_retrieve and top_k_final work."""
    from backend.config import settings

    # 10 candidates
    candidates = [
        {"chroma_id": f"c{i}", "text": f"Chunk {i}", "score": 0.5, "metadata": {"doc_id": str(i)}}
        for i in range(10)
    ]
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store(candidates))
    mocker.patch('backend.rag.retriever.get_reranker', return_value=DummyReranker(scores=list(range(10))))

    results = retrieve("query", top_k_retrieve=8, top_k_final=3)
    # Should fetch 8 candidates
    mock_query.assert_called_with(mocker.ANY, top_k=8, doc_ids=None)
    # Should return 3 final results
    assert len(results) == 3


def test_retrieve_reranker_scores_assigned(mocker, mock_vector_store):
    """Each returned chunk has rerank_score field."""
    candidates = [
        {"chroma_id": "c0", "text": "Chunk", "score": 0.5, "metadata": {"doc_id": "1"}}
    ]
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store(candidates))
    mocker.patch('backend.rag.retriever.get_reranker', return_value=DummyReranker(scores=[0.95]))

    results = retrieve("query")

    assert len(results) >= 1
    assert "rerank_score" in results[0]
    assert results[0]["rerank_score"] == 0.95


def test_get_reranker_singleton(mocker):
    """get_reranker returns singleton (lazy initialization)."""
    # Mock the CrossEncoder to avoid downloading
    mocker.patch('backend.rag.retriever.CrossEncoder')

    r1 = get_reranker()
    r2 = get_reranker()
    assert r1 is r2


def test_retrieve_uses_settings_defaults(mocker, mock_vector_store):
    """retrieve falls back to config settings for top_k values."""
    from backend.config import settings

    candidates = [
        {"chroma_id": f"c{i}", "text": f"Chunk {i}", "score": 0.5, "metadata": {"doc_id": str(i)}}
        for i in range(settings.top_k_retrieve)
    ]
    mock_query = mocker.patch('backend.rag.retriever.query_chunks', mock_vector_store(candidates))
    mocker.patch('backend.rag.retriever.get_reranker', return_value=DummyReranker(scores=[0.5] * len(candidates)))

    retrieve("query")

    mock_query.assert_called_with(mocker.ANY, top_k=settings.top_k_retrieve, doc_ids=None)

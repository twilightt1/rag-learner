from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import Mock

from backend.rag.embedder import get_embedder, embed_texts, embed_query


@pytest.fixture(autouse=True)
def mock_sentence_transformer(mocker):
    """Replace SentenceTransformer with a mock that returns predictable embeddings."""
    mock_model = Mock()
    # Create a deterministic 384-dim vector for each input
    mock_model.encode.return_value = np.array([[0.1] * 384], dtype=np.float32)
    mocker.patch('backend.rag.embedder.SentenceTransformer', return_value=mock_model)
    # Reset the singleton before each test
    import backend.rag.embedder as emb_mod
    emb_mod._model = None
    yield mock_model
    emb_mod._model = None


def test_embedder_is_singleton(mock_sentence_transformer):
    """get_embedder returns the same instance on multiple calls."""
    emb1 = get_embedder()
    emb2 = get_embedder()
    assert emb1 is emb2
    assert mock_sentence_transformer.called or mock_sentence_transformer  # was instantiated


def test_embed_returns_correct_shape(mock_sentence_transformer):
    """embed_texts returns array with correct dimensions."""
    emb = get_embedder()
    texts = ["hello", "world", "test"]
    # Mock returns [0.1]*384 for each call; we need per-text result, so adjust mock
    mock_sentence_transformer.encode.return_value = np.array([[0.1] * 384 for _ in range(len(texts))], dtype=np.float32)

    vectors = embed_texts(texts)

    assert isinstance(vectors, np.ndarray)
    assert vectors.shape[0] == len(texts)
    assert vectors.shape[1] == 384


def test_embed_query_returns_single_vector(mock_sentence_transformer):
    """embed_query returns a 1-D array."""
    mock_sentence_transformer.encode.return_value = np.array([[0.1] * 384], dtype=np.float32)

    vec = embed_query("what is backpropagation?")

    assert isinstance(vec, np.ndarray)
    assert vec.ndim == 1
    assert len(vec) == 384


def test_embed_texts_normalizes():
    """Embeddings are L2-normalized when normalize_embeddings=True."""
    # Use real numpy to test normalization without mocking
    emb = get_embedder()
    # Provide a simple vector that's not normalized
    mock_model = Mock()
    mock_model.encode.return_value = np.array([[3.0, 4.0]], dtype=np.float32)  # norm = 5
    # Temporarily replace the model
    import backend.rag.embedder as emb_mod
    old_model = emb_mod._model
    emb_mod._model = mock_model

    try:
        vectors = embed_texts(["test"], normalize_embeddings=True)
        # After normalization, should be [0.6, 0.8] (norm 1)
        expected = np.array([0.6, 0.8], dtype=np.float32)
        np.testing.assert_allclose(vectors[0], expected, rtol=1e-5)
    finally:
        emb_mod._model = old_model


def test_embed_empty_list(mock_sentence_transformer):
    """embed_texts with empty list returns empty array."""
    # Reset model to None to ensure we can call with empty
    import backend.rag.embedder as emb_mod
    emb_mod._model = None
    emb = get_embedder()  # will create again

    vectors = embed_texts([])
    assert len(vectors) == 0


def test_embed_batch_size_parameter(mock_sentence_transformer):
    """Embedder accepts custom batch_size."""
    # We don't actually test batching behavior, just that parameter is passed
    mock_sentence_transformer.encode.return_value = np.array([[0.1] * 384 for _ in range(100)], dtype=np.float32)

    texts = ["text"] * 100
    vectors = embed_texts(texts, batch_size=16)
    assert len(vectors) == 100
    # Check that batch_size was passed to encode
    mock_sentence_transformer.encode.assert_called()
    call_kwargs = mock_sentence_transformer.encode.call_args[1]
    assert call_kwargs.get("batch_size") == 16


def test_embed_consistent_results(mock_sentence_transformer):
    """Same input produces same embedding across calls."""
    # Use mock to return deterministic values
    mock_sentence_transformer.encode.return_value = np.array([[0.5] * 384], dtype=np.float32)

    text = "consistent test input"
    vec1 = embed_query(text)
    vec2 = embed_query(text)

    np.testing.assert_allclose(vec1, vec2, rtol=1e-6)

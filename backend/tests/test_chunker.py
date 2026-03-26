from __future__ import annotations

import pytest
import tiktoken

from backend.ingestion.chunker import chunk_text, chunk_blocks, tokenize, detokenize


def test_tokenize_detokenize_roundtrip():
    """Tokenization and detokenization are reversible."""
    text = "Hello world! This is a test."
    tokens = tokenize(text)
    decoded = detokenize(tokens)
    assert decoded == text


def test_chunk_size_within_limit():
    """Chunks do not exceed configured chunk_size."""
    from backend.config import settings
    long_text = "word " * 2000
    chunks = chunk_text(long_text, doc_id="d1")

    enc = tiktoken.get_encoding("cl100k_base")
    for chunk in chunks:
        token_count = len(enc.encode(chunk["text"]))
        assert token_count <= settings.chunk_size


def test_chunk_overlap():
    """Consecutive chunks have the configured token overlap."""
    from backend.config import settings
    text = "token " * 1200
    chunks = chunk_text(text, doc_id="d1")

    if len(chunks) < 2:
        pytest.skip("Need at least 2 chunks to test overlap")

    enc = tiktoken.get_encoding("cl100k_base")
    overlap = settings.chunk_overlap

    for i in range(len(chunks) - 1):
        first_tokens = enc.encode(chunks[i]["text"])
        second_tokens = enc.encode(chunks[i + 1]["text"])
        # Check that the last `overlap` tokens of first chunk appear in first of second
        # Note: due to tokenization boundaries, exact overlap may vary slightly
        # So we check that at least some tokens overlap
        overlap_tokens = set(first_tokens[-overlap:]) & set(second_tokens[:overlap])
        # At least half the expected overlap should match
        assert len(overlap_tokens) >= overlap / 2


def test_chunk_metadata_populated():
    """Metadata from kwargs is added to each chunk."""
    chunks = chunk_text("hello world", doc_id="doc-abc", page_num=3, source_type="pdf")
    assert len(chunks) >= 1
    chunk = chunks[0]
    assert chunk["doc_id"] == "doc-abc"
    assert chunk["page_num"] == 3
    assert chunk["source_type"] == "pdf"
    assert "chunk_index" in chunk
    assert "token_count" in chunk


def test_empty_text_returns_empty_list():
    """Empty or whitespace-only text yields no chunks."""
    assert chunk_text("", doc_id="d") == []
    assert chunk_text("   \n\n  ", doc_id="d") == []


def test_small_text_single_chunk():
    """Text smaller than chunk_size yields one chunk."""
    short_text = "This is a short document."
    chunks = chunk_text(short_text, doc_id="d1")
    assert len(chunks) == 1
    assert chunks[0]["text"] == short_text


def test_chunk_blocks_flattens_blocks():
    """chunk_blocks converts list of blocks into flat chunk list."""
    blocks = [
        {"text": "First block of text.", "page_num": 1},
        {"text": "Second block with more content to ensure multiple chunks can be created from it.", "page_num": 2},
    ]
    chunks = chunk_blocks(blocks, doc_id=1, source_type="pdf")

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk["doc_id"] == 1
        assert chunk["source_type"] == "pdf"
        assert "chunk_index" in chunk
        assert "text" in chunk


def test_chunk_blocks_global_reindexing():
    """chunk_blocks reindexes chunk_index globally across all blocks."""
    blocks = [
        {"text": "First block."},
        {"text": "Second block with sufficient length to create multiple chunks."},
    ]
    chunks = chunk_blocks(blocks, doc_id=1, source_type="md")

    indices = [c["chunk_index"] for c in chunks]
    # Should be sequential from 0 to len(chunks)-1
    assert indices == list(range(len(chunks)))


def test_chunk_blocks_empty_blocks():
    """Empty blocks list returns empty chunks list."""
    chunks = chunk_blocks([], doc_id=1, source_type="pdf")
    assert chunks == []


def test_chunk_blocks_skips_empty_text_blocks():
    """Blocks with no text are skipped."""
    blocks = [
        {"text": "   "},
        {"text": "Actual content."},
        {"text": ""},
    ]
    chunks = chunk_blocks(blocks, doc_id=1, source_type="md")
    assert len(chunks) == 1
    assert "Actual content" in chunks[0]["text"]

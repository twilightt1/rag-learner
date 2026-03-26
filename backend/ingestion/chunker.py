"""Sliding-window token chunker.

Uses tiktoken (cl100k_base) for token counting.
Splits text blocks into overlapping chunks of `chunk_size` tokens
with `chunk_overlap` token overlap between consecutive chunks.
"""
from __future__ import annotations

from typing import List, Dict, Any
import re

import tiktoken

from backend.config import settings

_enc = tiktoken.get_encoding("cl100k_base")


def tokenize(text: str) -> List[int]:
    return _enc.encode(text)


def detokenize(tokens: List[int]) -> str:
    return _enc.decode(tokens)


def chunk_text(
    text: str,
    metadata: Dict[str, Any],
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[Dict[str, Any]]:
    """
    Split `text` into overlapping token-based chunks.

    Args:
        text:         Raw text to chunk.
        metadata:     Extra fields merged into each chunk dict.
        chunk_size:   Max tokens per chunk (default from settings).
        chunk_overlap: Token overlap between chunks (default from settings).

    Returns:
        List of dicts: {text, token_count, chunk_index, **metadata}
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    tokens = tokenize(text)
    if not tokens:
        return []

    chunks = []
    start = 0
    index = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = detokenize(chunk_tokens).strip()

        if chunk_text_str:
            chunks.append({
                "text": chunk_text_str,
                "token_count": len(chunk_tokens),
                "chunk_index": index,
                **metadata,
            })
            index += 1

        if end == len(tokens):
            break

        start += chunk_size - chunk_overlap

    return chunks


def chunk_blocks(
    blocks: List[Dict[str, Any]],
    doc_id: str,
    source_type: str,
) -> List[Dict[str, Any]]:
    """
    Chunk a list of text blocks (from parsers) for a given document.

    Each block is a dict with at least a 'text' key, plus optional
    'page_num', 'section', etc.

    Returns flat list of chunk dicts ready for embedding + storage.
    """
    all_chunks = []
    running_index = 0

    for block in blocks:
        raw_text = block.get("text", "").strip()
        if not raw_text:
            continue

        metadata = {
            "doc_id": doc_id,
            "source_type": source_type,
            "page_num": block.get("page_num"),
            "section": block.get("section", ""),
        }

        block_chunks = chunk_text(raw_text, metadata)

        # Re-index globally across all blocks
        for chunk in block_chunks:
            chunk["chunk_index"] = running_index
            running_index += 1

        all_chunks.extend(block_chunks)

    return all_chunks

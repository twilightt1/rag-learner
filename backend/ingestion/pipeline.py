"""Ingestion orchestrator.

Flow: parse → chunk → embed → store (ChromaDB + SQLite)
Updates document status throughout.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlmodel import Session

from backend.config import settings
from backend.database import Document, Chunk, engine
from backend.ingestion.chunker import chunk_blocks
from backend.rag.embedder import embed_texts
from backend.rag.vector_store import add_chunks


def _update_status(doc_id: str, status: str, error_msg: str = None):
    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = status
            doc.error_msg = error_msg
            doc.updated_at = datetime.now(timezone.utc)
            db.add(doc)
            db.commit()


def _save_chunks(doc_id: str, chunks: List[Dict], chroma_ids: List[str]):
    with Session(engine) as db:
        for chunk, chroma_id in zip(chunks, chroma_ids):
            db_chunk = Chunk(
                id=chunk["uuid"],  # Use pre-generated UUID
                doc_id=doc_id,
                text=chunk["text"],
                page_num=chunk.get("page_num"),
                chunk_index=chunk.get("chunk_index", 0),
                token_count=chunk.get("token_count", 0),
                chroma_id=chroma_id,
            )
            db.add(db_chunk)
        db.commit()

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        if doc:
            doc.chunk_count = len(chunks)
            doc.updated_at = datetime.now(timezone.utc)
            db.add(doc)
            db.commit()


async def run_ingestion(doc_id: str):
    """Full async ingestion pipeline for a document."""
    _update_status(doc_id, "processing")

    try:
        with Session(engine) as db:
            doc = db.get(Document, doc_id)
            if not doc:
                raise ValueError(f"Document {doc_id} not found")
            source_type = doc.source_type
            source_path = doc.source_path

        # Step 1: parse (URL is async, others run in thread)
        if source_type == "url":
            from backend.ingestion.parsers.url_parser import parse_url
            blocks = await parse_url(source_path)
        else:
            blocks = await asyncio.to_thread(_parse_sync, source_type, source_path)

        if not blocks:
            raise ValueError("Parser returned no text blocks")

        # Step 2: chunk
        chunks = chunk_blocks(blocks, doc_id=doc_id, source_type=source_type)
        if not chunks:
            raise ValueError("Chunker returned no chunks")

        # Assign UUIDs to chunks before storage (will be used as Chunk.id)
        import uuid as _uuid
        for chunk in chunks:
            chunk["uuid"] = str(_uuid.uuid4())

        # Step 3: embed
        texts = [c["text"] for c in chunks]
        embeddings = await asyncio.to_thread(embed_texts, texts)

        # Step 4: store in ChromaDB
        chroma_ids = add_chunks(chunks, embeddings)

        # Step 5: store chunk records in SQLite with the same UUIDs
        _save_chunks(doc_id, chunks, chroma_ids)

        _update_status(doc_id, "ready")

    except Exception as e:
        _update_status(doc_id, "failed", error_msg=str(e))
        raise


def _parse_sync(source_type: str, source_path: str) -> List[Dict[str, Any]]:
    if source_type == "pdf":
        from backend.ingestion.parsers.pdf_parser import parse_pdf
        return parse_pdf(source_path)
    elif source_type in ("md", "txt"):
        from backend.ingestion.parsers.md_parser import parse_markdown
        return parse_markdown(source_path)
    elif source_type == "code":
        from backend.ingestion.parsers.code_parser import parse_code
        return parse_code(source_path)
    else:
        raise ValueError(f"Unknown source_type: {source_type}")

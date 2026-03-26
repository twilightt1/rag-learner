from __future__ import annotations

import pytest
import os

from backend.ingestion.pipeline import run_ingestion, _parse_sync, _update_status, _save_chunks
from backend.database import Document, Chunk, engine
from sqlmodel import Session, select


@pytest.mark.asyncio
async def test_run_ingestion_success_flow(mocker, db_session, tmp_path):
    """run_ingestion executes full pipeline successfully for a PDF."""
    from backend.ingestion.parsers.pdf_parser import parse_pdf
    from backend.rag.embedder import embed_texts
    from backend.rag.vector_store import add_chunks

    # Create a dummy PDF file
    pdf_path = tmp_path / "test.pdf"
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Test PDF content for ingestion.")
        pdf.output(str(pdf_path))
    except ImportError:
        pytest.skip("fpdf2 not installed")

    # Create document record
    with Session(engine) as db:
        doc = Document(
            filename="test.pdf",
            source_type="pdf",
            source_path=str(pdf_path),
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    # Mock the heavy operations
    mocker.patch('backend.ingestion.pipeline.chunk_blocks', return_value=[
        {"text": "Chunk 1", "doc_id": doc_id, "chunk_index": 0},
        {"text": "Chunk 2", "doc_id": doc_id, "chunk_index": 1},
    ])
    mocker.patch('backend.rag.embedder.embed_texts', return_value=[[0.1, 0.2], [0.3, 0.4]])
    mocker.patch('backend.rag.vector_store.add_chunks', return_value=["ch1", "ch2"])

    # Run ingestion
    await run_ingestion(doc_id)

    # Check status updated to ready
    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "ready"
        assert doc.chunk_count == 2

        # Verify chunks created
        chunks = db.exec(select(Chunk).where(Chunk.doc_id == doc_id)).all()
        assert len(chunks) == 2


async def test_run_ingestion_url_uses_async_parser(mocker, db_session):
    """URL source calls async parse_url."""
    from backend.ingestion.parsers.url_parser import parse_url

    mocker.patch('backend.ingestion.pipeline.chunk_blocks', return_value=[])
    mocker.patch('backend.rag.embed_texts', return_value=[])
    mocker.patch('backend.rag.add_chunks', return_value=[])

    # Create document with source_type=url
    with Session(engine) as db:
        doc = Document(
            filename="example.com",
            source_type="url",
            source_path="https://example.com",
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    mock_parse_url = mocker.patch('backend.ingestion.pipeline.parse_url', return_value=[])

    await run_ingestion(doc_id)

    mock_parse_url.assert_called_once_with("https://example.com")


async def test_run_ingestion_non_url_uses_sync_parser(mocker, db_session, tmp_path):
    """PDF/MD/code sources call _parse_sync."""
    # Create a dummy file
    file_path = tmp_path / "test.md"
    file_path.write_text("# Test", encoding="utf-8")

    with Session(engine) as db:
        doc = Document(
            filename="test.md",
            source_type="md",
            source_path=str(file_path),
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    mocker.patch('backend.ingestion.pipeline.chunk_blocks', return_value=[])
    mocker.patch('backend.ingestion.pipeline.embed_texts', return_value=[])
    mocker.patch('backend.ingestion.pipeline.add_chunks', return_value=[])

    mock_parse_sync = mocker.patch('backend.ingestion.pipeline._parse_sync', return_value=[])

    await run_ingestion(doc_id)

    mock_parse_sync.assert_called_once_with("md", str(file_path))


async def test_run_ingestion_parsing_failure_sets_failed(mocker, db_session, tmp_path):
    """If parsing fails, document status set to failed with error."""
    with Session(engine) as db:
        doc = Document(
            filename="bad.pdf",
            source_type="pdf",
            source_path="/nonexistent.pdf",
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    mocker.patch('backend.ingestion.pipeline._parse_sync', side_effect=Exception("File not found"))

    with pytest.raises(Exception):
        await run_ingestion(doc_id)

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "failed"
        assert "File not found" in doc.error_msg


async def test_run_ingestion_no_blocks_fails(mocker, db_session, tmp_path):
    """Empty blocks from parser raises error."""
    with Session(engine) as db:
        doc = Document(
            filename="empty.pdf",
            source_type="pdf",
            source_path="/some/path.pdf",
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    mocker.patch('backend.ingestion.pipeline._parse_sync', return_value=[])

    with pytest.raises(ValueError, match="Parser returned no text blocks"):
        await run_ingestion(doc_id)

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "failed"


async def test_run_ingestion_no_chunks_fails(mocker, db_session, tmp_path):
    """Chunker returns no chunks raises error."""
    with Session(engine) as db:
        doc = Document(
            filename="test.pdf",
            source_type="pdf",
            source_path="/some/path.pdf",
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    mocker.patch('backend.ingestion.pipeline._parse_sync', return_value=[{"text": "content"}])
    mocker.patch('backend.ingestion.pipeline.chunk_blocks', return_value=[])

    with pytest.raises(ValueError, match="Chunker returned no chunks"):
        await run_ingestion(doc_id)

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "failed"


async def test_save_chunks_creates_records(mocker, db_session):
    """_save_chunks creates Chunk records and updates document."""
    from backend.ingestion.pipeline import _save_chunks
    import uuid

    # Create a document first (required for chunk_count update)
    with Session(engine) as db:
        doc = Document(
            filename="test.pdf",
            source_type="pdf",
            source_path="/tmp/test.pdf",
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id  # This is a UUID string

    chunks = [
        {"text": "Chunk 1", "doc_id": doc_id, "chunk_index": 0, "page_num": 1, "token_count": 50, "uuid": str(uuid.uuid4())},
        {"text": "Chunk 2", "doc_id": doc_id, "chunk_index": 1, "page_num": 1, "token_count": 60, "uuid": str(uuid.uuid4())},
    ]
    chroma_ids = ["chroma1", "chroma2"]

    _save_chunks(doc_id, chunks, chroma_ids)

    with Session(engine) as db:
        stored_chunks = db.exec(select(Chunk).where(Chunk.doc_id == doc_id)).all()
        assert len(stored_chunks) == 2
        assert stored_chunks[0].text == "Chunk 1"
        assert stored_chunks[1].chroma_id == "chroma2"

        doc = db.get(Document, doc_id)
        assert doc is not None
        assert doc.chunk_count == 2


async def test_update_status_updates_document(mocker, db_session):
    """_update_status modifies document status and error_msg."""
    from backend.ingestion.pipeline import _update_status

    with Session(engine) as db:
        doc = Document(filename="test.md", source_type="md", source_path="/tmp/test.md", status="pending")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

    _update_status(doc_id, "ready")

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "ready"
        assert doc.error_msg is None

    _update_status(doc_id, "failed", error_msg="Something went wrong")

    with Session(engine) as db:
        doc = db.get(Document, doc_id)
        assert doc.status == "failed"
        assert "Something went wrong" in doc.error_msg

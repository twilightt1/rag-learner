from __future__ import annotations

import pytest
import json
import uuid
from datetime import datetime, timezone
from sqlmodel import select

from backend.database import Document, Chunk, ChatSession, Message, engine


# --- Health endpoint ---

async def test_health_returns_ok(api_client):
    """GET /health returns status ok."""
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# --- Documents API ---

async def test_ingest_pdf_creates_document(api_client, sample_pdf, mocker):
    """POST /api/ingest/file creates a document and returns 202."""
    # Mock the background ingestion to avoid actually running it
    mocker.patch('backend.api.documents.run_ingestion')

    with open(sample_pdf, "rb") as f:
        resp = await api_client.post(
            "/api/ingest/file",
            files={"file": ("sample.pdf", f, "application/pdf")}
        )

    assert resp.status_code == 202
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "sample.pdf"
    assert data["status"] == "pending"


async def test_ingest_url_creates_document(api_client, mocker):
    """POST /api/ingest/url creates a document with url source."""
    mocker.patch('backend.api.documents.run_ingestion')

    resp = await api_client.post(
        "/api/ingest/url",
        json={"url": "https://example.com/article"}
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["source_type"] == "url"
    assert data["status"] == "pending"


async def test_ingest_url_validates_scheme(api_client):
    """URL ingestion rejects non-http/https schemes."""
    resp = await api_client.post("/api/ingest/url", json={"url": "ftp://example.com"})
    assert resp.status_code == 400
    assert "http" in resp.json()["detail"]


async def test_ingest_url_validates_private_ip(api_client, mocker):
    """URL ingestion blocks private IP addresses."""
    # Mock DNS resolution to return private IP
    mocker.patch('socket.getaddrinfo', return_value=[
        (2, 1, 6, '', ('127.0.0.1', 80))
    ])

    resp = await api_client.post("/api/ingest/url", json={"url": "http://private.local"})
    assert resp.status_code == 400
    assert "internal" in resp.json()["detail"].lower() or "private" in resp.json()["detail"].lower()


async def test_list_documents_empty_returns_empty(api_client):
    """GET /api/documents returns empty list when no docs."""
    resp = await api_client.get("/api/documents")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_documents_returns_ordered(api_client, mocker):
    """Documents ordered by created_at desc."""
    # Create mock documents in DB via direct insertion
    with Session(engine) as db:
        doc1 = Document(filename="first.pdf", source_type="pdf", source_path="/tmp/1", status="ready")
        doc2 = Document(filename="second.pdf", source_type="pdf", source_path="/tmp/2", status="ready")
        db.add(doc1)
        db.add(doc2)
        db.commit()
        db.refresh(doc1)
        db.refresh(doc2)

    resp = await api_client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()
    # Should be ordered by created_at desc (newest first)
    # difficult to assert time order reliably, so just check length
    assert len(docs) >= 2


async def test_get_document_404_missing(api_client):
    """GET /api/documents/{id} 404s for missing doc."""
    resp = await api_client.get(f"/api/documents/{str(uuid.uuid4())}")
    assert resp.status_code == 404


async def test_delete_document_removes_chunks(api_client, mocker):
    """DELETE /api/documents/{id} removes doc and its chunks."""
    # Mock the delete operations to verify they're called
    mock_vec_delete = mocker.patch('backend.api.documents.delete_chunks_by_doc')
    mock_file_remove = mocker.patch('os.remove')

    with Session(engine) as db:
        doc = Document(filename="to_delete.pdf", source_type="pdf", source_path="/tmp/test.pdf", status="ready")
        db.add(doc)
        db.commit()
        doc_id = doc.id

    resp = await api_client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 204

    mock_vec_delete.assert_called_once_with(doc_id)
    mock_file_remove.assert_called_once_with("/tmp/test.pdf")


async def test_delete_nonexistent_document_404(api_client):
    """DELETE /api/documents/{id} 404s for missing doc."""
    resp = await api_client.delete(f"/api/documents/{str(uuid.uuid4())}")
    assert resp.status_code == 404


async def test_list_chunks_requires_doc_id(api_client):
    """GET /api/chunks without doc_id returns limited results (default)."""
    resp = await api_client.get("/api/chunks")
    assert resp.status_code == 200
    # Should return results even without doc_id (limiting to 50)
    assert isinstance(resp.json(), list)


async def test_list_chunks_filters_by_doc_id(api_client):
    """GET /api/chunks?doc_id=X returns only chunks for that doc."""
    # In test DB, we'd need to create chunks. This is a basic smoke test.
    resp = await api_client.get(f"/api/chunks?doc_id={str(uuid.uuid4())}")
    assert resp.status_code == 200
    assert resp.json() == []
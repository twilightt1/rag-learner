"""Document ingestion and management endpoints.

POST /api/ingest        — upload a file or submit a URL
GET  /api/documents     — list all documents
GET  /api/documents/{id} — single document detail
DELETE /api/documents/{id} — remove doc + all its chunks
GET  /api/chunks        — list chunks (filterable by doc_id)
"""
import ipaddress
import logging
import os
import re
import shutil
import socket
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel

from backend.config import settings
from backend.database import Document, Chunk, get_session
from backend.ingestion.pipeline import run_ingestion
from backend.rag.vector_store import delete_chunks_by_doc, get_collection_stats

router = APIRouter(prefix="/api", tags=["documents"])
logger = logging.getLogger("rag_learner.documents")

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".md": "md",
    ".txt": "txt",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".jsx": "code",
    ".tsx": "code",
}

# Regex to strip anything that isn't alphanumeric, dash, underscore, or dot
_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def _sanitize_filename(name: str) -> str:
    """Return a safe basename, stripping directory traversal and special chars."""
    # Take only the final path component (defeats ../ tricks)
    name = Path(name).name
    # Replace dangerous characters
    name = _SAFE_FILENAME_RE.sub("_", name)
    return name or "unnamed_file"


def _validate_public_url(url: str) -> str:
    """Reject non-HTTP schemes and URLs that resolve to private/loopback IPs (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL — missing host")

    # Resolve hostname and block private / loopback addresses
    hostname = parsed.hostname
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canon, addr in resolved:
            ip = ipaddress.ip_address(addr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(
                    status_code=400,
                    detail="URLs pointing to internal/private networks are not allowed",
                )
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Cannot resolve hostname: {hostname}")

    return url


# ── Response schemas ───────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: int
    filename: str
    source_type: str
    source_path: str
    status: str
    error_msg: Optional[str]
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkOut(BaseModel):
    id: int
    doc_id: int
    text: str
    page_num: Optional[int]
    chunk_index: int
    token_count: int
    chroma_id: str

    class Config:
        from_attributes = True


class IngestUrlRequest(BaseModel):
    url: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ingest/file", response_model=DocumentOut, status_code=202)
async def ingest_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """Upload a file and trigger background ingestion."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {list(ALLOWED_EXTENSIONS)}"
        )

    source_type = ALLOWED_EXTENSIONS[suffix]
    upload_dir = Path(settings.upload_path)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename to prevent path traversal
    safe_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{_sanitize_filename(file.filename)}"
    dest_path = upload_dir / safe_name

    # Enforce file size limit
    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                # Clean up partial file
                f.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max size: {settings.max_upload_bytes // (1024*1024)} MB",
                )
            f.write(chunk)

    logger.info("File uploaded: %s (%d bytes)", safe_name, size)

    doc = Document(
        filename=file.filename,
        source_type=source_type,
        source_path=str(dest_path),
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(run_ingestion, doc.id)

    return doc


@router.post("/ingest/url", response_model=DocumentOut, status_code=202)
async def ingest_url(
    request: IngestUrlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """Submit a URL for web crawling and ingestion."""
    validated_url = _validate_public_url(request.url)
    parsed = urlparse(validated_url)

    filename = parsed.netloc + parsed.path.replace("/", "_") or "webpage"
    doc = Document(
        filename=filename[:200],
        source_type="url",
        source_path=validated_url,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info("URL ingestion queued: %s (doc_id=%d)", validated_url, doc.id)
    background_tasks.add_task(run_ingestion, doc.id)
    return doc


@router.get("/documents", response_model=List[DocumentOut])
def list_documents(db: Session = Depends(get_session)):
    docs = db.exec(select(Document).order_by(Document.created_at.desc())).all()
    return docs


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_session)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_session)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from ChromaDB
    delete_chunks_by_doc(doc_id)

    # Remove chunk records
    chunks = db.exec(select(Chunk).where(Chunk.doc_id == doc_id)).all()
    for c in chunks:
        db.delete(c)

    # Remove uploaded file if it exists
    if doc.source_type != "url" and os.path.exists(doc.source_path):
        try:
            os.remove(doc.source_path)
        except OSError:
            pass

    db.delete(doc)
    db.commit()
    logger.info("Document deleted: id=%d filename=%s", doc_id, doc.filename)


@router.get("/chunks", response_model=List[ChunkOut])
def list_chunks(
    doc_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session),
):
    query = select(Chunk).order_by(Chunk.chunk_index)
    if doc_id:
        query = query.where(Chunk.doc_id == doc_id)
    query = query.offset(offset).limit(limit)
    return db.exec(query).all()


@router.get("/stats")
def get_stats(db: Session = Depends(get_session)):
    from sqlmodel import func
    doc_count = db.exec(select(Document)).all()
    chroma_stats = get_collection_stats()
    return {
        "document_count": len(doc_count),
        "total_chunks": chroma_stats["total_chunks"],
    }

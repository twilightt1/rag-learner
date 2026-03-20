from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List
import json

from sqlmodel import SQLModel, Field, create_engine, Session, select
from sqlalchemy import event
from sqlalchemy.engine import Engine

from backend.config import settings

DATABASE_URL = f"sqlite:///{settings.db_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── Models ────────────────────────────────────────────────────────────────────

class Document(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    source_type: str          # pdf | md | url | code
    source_path: str          # local path or original URL
    status: str = "pending"   # pending | processing | ready | failed
    error_msg: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chunk(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    doc_id: str = Field(foreign_key="document.id")
    text: str
    page_num: Optional[int] = None
    chunk_index: int = 0
    token_count: int = 0
    chroma_id: str = ""       # matching ID in ChromaDB
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSession(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = "New session"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Message(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id")
    role: str                  # user | assistant
    content: str
    sources: str = "[]"        # JSON list of chunk IDs
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_sources(self) -> List[str]:
        return json.loads(self.sources)

    def set_sources(self, ids: List[str]):
        self.sources = json.dumps(ids)


class Quiz(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    doc_ids: str = "[]"        # JSON list of doc IDs
    questions: str = "[]"      # JSON list of question dicts
    quiz_type: str = "mcq"     # mcq | flashcard
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_doc_ids(self) -> List[str]:
        return json.loads(self.doc_ids)

    def get_questions(self) -> list:
        return json.loads(self.questions)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def create_db_and_tables():
    import os
    os.makedirs(settings.upload_path, exist_ok=True)
    os.makedirs(settings.chroma_path, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

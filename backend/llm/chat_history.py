"""Session-scoped chat history manager.

Keeps a rolling window of messages to avoid blowing the context window.
"""
from __future__ import annotations

from typing import List, Dict, Any
from sqlmodel import Session, select

from backend.database import Message, ChatSession, engine


MAX_HISTORY_TURNS = 10   # Keep last N user+assistant pairs


def load_history(session_id: str) -> List[Dict[str, str]]:
    """Load recent message history for a session as OpenRouter-compatible dicts."""
    with Session(engine) as db:
        messages = db.exec(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        ).all()

    # Keep last N turns (each turn = 1 user + 1 assistant message)
    cutoff = MAX_HISTORY_TURNS * 2
    recent = messages[-cutoff:] if len(messages) > cutoff else messages

    return [{"role": m.role, "content": m.content} for m in recent]


def save_message(
    session_id: str,
    role: str,
    content: str,
    source_metadata: List[Dict[str, Any]] = None,
) -> Message:
    """
    Persist a message to SQLite.

    Args:
        session_id: Session UUID string
        role: "user" or "assistant"
        content: Message text
        source_metadata: Optional list of source chunk metadata dictionaries
                      (will be stored as JSON in sources field as list of chroma_ids)
    """
    import json
    # Store list of chroma_ids directly to avoid DB lookup later
    chroma_ids = [m["chroma_id"] for m in source_metadata] if source_metadata else []
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        sources=json.dumps(chroma_ids),
    )
    with Session(engine) as db:
        db.add(msg)
        db.commit()
        db.refresh(msg)
    return msg


def get_or_create_session(session_id: str = None, title: str = "New session") -> str:
    """Return an existing session ID or create a new one."""
    from datetime import datetime, timezone
    with Session(engine) as db:
        if session_id:
            existing = db.get(ChatSession, session_id)
            if existing:
                return existing.id

        session = ChatSession(title=title, updated_at=datetime.now(timezone.utc))
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id

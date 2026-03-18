"""Session-scoped chat history manager.

Keeps a rolling window of messages to avoid blowing the context window.
"""
from typing import List, Dict
from sqlmodel import Session, select

from backend.database import Message, ChatSession, engine


MAX_HISTORY_TURNS = 10   # Keep last N user+assistant pairs


def load_history(session_id: int) -> List[Dict[str, str]]:
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
    session_id: int,
    role: str,
    content: str,
    source_chunk_ids: List[int] = None,
) -> Message:
    """Persist a message to SQLite."""
    import json
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        sources=json.dumps(source_chunk_ids or []),
    )
    with Session(engine) as db:
        db.add(msg)
        db.commit()
        db.refresh(msg)
    return msg


def get_or_create_session(session_id: int = None, title: str = "New session") -> int:
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

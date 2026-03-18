"""Chat endpoints.

POST /api/chat              — single-turn Q&A (non-streaming)
WS   /api/chat/stream       — streaming chat via WebSocket
GET  /api/sessions          — list all chat sessions
POST /api/sessions          — create new session
DELETE /api/sessions/{id}   — delete session + all messages
GET  /api/sessions/{id}/messages — get message history
"""
import json
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from pydantic import BaseModel, Field

from backend.database import ChatSession, Message, Chunk, get_session, engine
from backend.rag.retriever import retrieve
from backend.rag.prompt_builder import build_messages
from backend.llm.openrouter import complete, stream_complete
from backend.llm.chat_history import load_history, save_message, get_or_create_session

router = APIRouter(prefix="/api", tags=["chat"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = None
    doc_ids: Optional[List[int]] = None  # Filter retrieval to specific docs


class SessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    sources: str
    created_at: datetime

    class Config:
        from_attributes = True


class SourceChunk(BaseModel):
    chunk_id: Optional[int]
    chroma_id: str
    text: str
    score: float
    rerank_score: float
    metadata: dict


class ChatResponse(BaseModel):
    session_id: int
    answer: str
    sources: List[SourceChunk]


# ── Helper ─────────────────────────────────────────────────────────────────────

def _resolve_db_chunk_ids(chroma_ids: List[str]) -> List[int]:
    """Map chroma IDs back to SQLite Chunk IDs."""
    with Session(engine) as db:
        chunks = db.exec(
            select(Chunk).where(Chunk.chroma_id.in_(chroma_ids))
        ).all()
        return [c.id for c in chunks]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming Q&A with source citations."""
    session_id = get_or_create_session(request.session_id)

    # Retrieve context
    chunks = retrieve(request.query, doc_ids=request.doc_ids)

    # Build prompt with history
    history = load_history(session_id)
    messages = build_messages(request.query, chunks, history)

    # Get LLM response
    answer = await complete(messages)

    # Persist messages
    save_message(session_id, "user", request.query)
    chunk_ids = _resolve_db_chunk_ids([c["chroma_id"] for c in chunks])
    save_message(session_id, "assistant", answer, source_chunk_ids=chunk_ids)

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        sources=[
            SourceChunk(
                chunk_id=None,
                chroma_id=c["chroma_id"],
                text=c["text"],
                score=c.get("score", 0.0),
                rerank_score=c.get("rerank_score", 0.0),
                metadata=c.get("metadata", {}),
            )
            for c in chunks
        ],
    )


@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    """
    WebSocket streaming chat.

    Client sends JSON: {query, session_id?, doc_ids?}
    Server responds with:
      - {type: "sources", data: [...]}
      - {type: "token", data: "..."}  (multiple)
      - {type: "done", session_id: N}
      - {type: "error", data: "..."}
    """
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": "Invalid JSON"})
                continue

            query = payload.get("query", "").strip()
            session_id_in = payload.get("session_id")
            doc_ids = payload.get("doc_ids")

            if not query:
                await websocket.send_json({"type": "error", "data": "Empty query"})
                continue

            if len(query) > 2000:
                await websocket.send_json({"type": "error", "data": "Query too long (max 2000 chars)"})
                continue

            session_id = get_or_create_session(session_id_in)

            # Retrieve context
            chunks = retrieve(query, doc_ids=doc_ids)

            # Send source cards first
            await websocket.send_json({
                "type": "sources",
                "session_id": session_id,
                "data": [
                    {
                        "chroma_id": c["chroma_id"],
                        "text": c["text"][:300],  # preview only
                        "score": c.get("score", 0.0),
                        "rerank_score": c.get("rerank_score", 0.0),
                        "metadata": c.get("metadata", {}),
                    }
                    for c in chunks
                ],
            })

            # Build messages
            history = load_history(session_id)
            messages = build_messages(query, chunks, history)

            # Stream tokens
            full_response = []
            async for token in stream_complete(messages):
                full_response.append(token)
                await websocket.send_json({"type": "token", "data": token})

            answer = "".join(full_response)

            # Persist
            save_message(session_id, "user", query)
            chunk_ids = _resolve_db_chunk_ids([c["chroma_id"] for c in chunks])
            save_message(session_id, "assistant", answer, source_chunk_ids=chunk_ids)

            await websocket.send_json({"type": "done", "session_id": session_id})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass


# ── Session management ─────────────────────────────────────────────────────────

@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_session)):
    sessions = db.exec(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    ).all()
    return sessions


@router.post("/sessions", response_model=SessionOut)
def create_session(db: Session = Depends(get_session)):
    session = ChatSession(title="New session", updated_at=datetime.now(timezone.utc))
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_session)):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = db.exec(select(Message).where(Message.session_id == session_id)).all()
    for m in msgs:
        db.delete(m)
    db.delete(s)
    db.commit()


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_messages(session_id: int, db: Session = Depends(get_session)):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = db.exec(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    ).all()
    return msgs

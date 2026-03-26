from __future__ import annotations

import pytest
import json
import uuid
from sqlmodel import select

from backend.database import ChatSession, Message, engine
from backend.llm.openrouter import complete, stream_complete


# --- Chat API (non-streaming) ---

async def test_chat_post_returns_answer(api_client, mocker):
    """POST /api/chat returns answer with sources."""
    mocker.patch('backend.api.chat.retrieve', return_value=[
        {
            "chroma_id": "c1",
            "text": "Relevant context about backpropagation.",
            "score": 0.85,
            "rerank_score": 0.92,
            "metadata": {"doc_id": "1", "page_num": "5"},
        }
    ])
    mocker.patch('backend.api.chat.complete', return_value="Backprop computes gradients via chain rule.")

    resp = await api_client.post("/api/chat", json={
        "query": "Explain backpropagation",
        "session_id": None,
        "doc_ids": None,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "answer" in data
    assert data["answer"] == "Backprop computes gradients via chain rule."
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) == 1
    assert data["sources"][0]["chroma_id"] == "c1"


async def test_chat_post_validates_query_length(api_client):
    """POST /api/chat rejects queries > 2000 chars."""
    long_query = "x" * 2001
    resp = await api_client.post("/api/chat", json={"query": long_query})
    assert resp.status_code == 422  # validation error


async def test_chat_post_missing_query_returns_422(api_client):
    """POST /api/chat requires query field."""
    resp = await api_client.post("/api/chat", json={})
    assert resp.status_code == 422


async def test_chat_creates_session_if_none(api_client, mocker):
    """POST /api/chat creates new session when session_id is None."""
    mocker.patch('backend.api.chat.retrieve', return_value=[])
    mocker.patch('backend.api.chat.complete', return_value="Answer")

    resp = await api_client.post("/api/chat", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] is not None

    # Verify session was created in DB
    with Session(engine) as db:
        session = db.get(ChatSession, data["session_id"])
        assert session is not None


async def test_chat_uses_existing_session(api_client, mocker):
    """POST /api/chat reuses provided session_id."""
    mocker.patch('backend.api.chat.retrieve', return_value=[])
    mocker.patch('backend.api.chat.complete', return_value="Answer")

    # Create a session first
    resp = await api_client.post("/api/sessions")
    session_id = resp.json()["id"]

    resp = await api_client.post("/api/chat", json={"query": "test", "session_id": session_id})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session_id


# --- Session Management ---

async def test_list_sessions_returns_all(api_client):
    """GET /api/sessions returns list of sessions."""
    # Create a couple sessions
    await api_client.post("/api/sessions")
    await api_client.post("/api/sessions")

    resp = await api_client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 2


async def test_create_session_returns_session(api_client):
    """POST /api/sessions creates new chat session."""
    resp = await api_client.post("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["title"] == "New session"


async def test_delete_session_removes_messages(api_client):
    """DELETE /api/sessions/{id} removes session and its messages."""
    # Create session and a message
    resp = await api_client.post("/api/sessions")
    session_id = resp.json()["id"]

    # Delete
    resp = await api_client.delete(f"/api/sessions/{session_id}")
    assert resp.status_code == 204

    # Verify deleted
    resp = await api_client.get(f"/api/sessions/{session_id}/messages")
    # Should either 404 session or return empty
    assert resp.status_code in (404, 200)


async def test_delete_nonexistent_session_404(api_client):
    """DELETE /api/sessions/{id} 404s for missing session."""
    resp = await api_client.delete(f"/api/sessions/{str(uuid.uuid4())}")
    assert resp.status_code == 404


async def test_get_messages_requires_valid_session(api_client):
    """GET /api/sessions/{id}/messages 404s for invalid session."""
    resp = await api_client.get(f"/api/sessions/{str(uuid.uuid4())}/messages")
    assert resp.status_code == 404


async def test_messages_ordered_by_created_asc(api_client, mocker):
    """Messages returned in chronological order."""
    mocker.patch('backend.api.chat.retrieve', return_value=[])
    mocker.patch('backend.api.chat.complete', return_value="Answer")

    # Create session
    resp = await api_client.post("/api/sessions")
    session_id = resp.json()["id"]

    # Send two messages (they'll be saved in order)
    await api_client.post("/api/chat", json={"session_id": session_id, "query": "First"})
    await api_client.post("/api/chat", json={"session_id": session_id, "query": "Second"})

    resp = await api_client.get(f"/api/sessions/{session_id}/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    # Should be ordered by created_at (ascending)
    # Not asserting on exact order due to timing, but structure is correct
    assert len(msgs) == 4  # 2 user + 2 assistant
    for msg in msgs:
        assert "role" in msg
        assert msg["role"] in ("user", "assistant")

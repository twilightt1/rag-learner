from __future__ import annotations

import pytest
import json

from backend.database import ChatSession, engine
from sqlmodel import select


async def test_websocket_chat_stream(api_client, mocker):
    """WebSocket /api/chat/stream sends sources, tokens, and done message."""
    # Mock retrieve to return some chunks
    mocker.patch('backend.api.chat.retrieve', return_value=[
        {
            "chroma_id": "c1",
            "text": "Relevant content",
            "score": 0.9,
            "rerank_score": 0.95,
            "metadata": {"page_num": "1", "section": "Intro"},
        }
    ])

    # Mock stream_complete to yield tokens
    async def fake_stream_complete(messages, **kwargs):
        yield "Hello"
        yield " World"

    mocker.patch('backend.api.chat.stream_complete', side_effect=fake_stream_complete)

    async with api_client.websocket_connect("/api/chat/stream") as websocket:
        # Send a query
        await websocket.send_json({"query": "test query", "session_id": None})

        # Expect first message to be sources
        response = await websocket.receive_json()
        assert response["type"] == "sources"
        assert "session_id" in response
        session_id = response["session_id"]
        assert len(response["data"]) == 1
        assert response["data"][0]["chroma_id"] == "c1"

        # Expect tokens followed by done
        tokens = []
        done_received = False
        while True:
            try:
                msg = await websocket.receive_json()
                if msg["type"] == "token":
                    tokens.append(msg["data"])
                elif msg["type"] == "done":
                    assert msg["session_id"] == session_id
                    done_received = True
                    break
                elif msg["type"] == "error":
                    pytest.fail(f"Received error: {msg['data']}")
            except Exception as e:
                break

        assert done_received
        assert "".join(tokens) == "Hello World"

        # Verify message persistence in DB
        with Session(engine) as db:
            messages = db.exec(select(ChatSession).where(ChatSession.id == session_id)).all()
            # The session should exist
            assert len(messages) >= 1  # session created
            # Actually ChatSession table, not Message. Let's check messages:
            from backend.database import Message as MsgModel
            msgs = db.exec(select(MsgModel).where(MsgModel.session_id == session_id)).all()
            assert len(msgs) == 2  # user + assistant


async def test_websocket_handles_empty_query(api_client):
    """WebSocket responds with error for empty query."""
    async with api_client.websocket_connect("/api/chat/stream") as websocket:
        await websocket.send_json({"query": "   "})
        response = await websocket.receive_json()
        assert response["type"] == "error"
        assert "Empty query" in response["data"]


async def test_websocket_handles_long_query(api_client):
    """WebSocket responds with error for query > 2000 chars."""
    async with api_client.websocket_connect("/api/chat/stream") as websocket:
        await websocket.send_json({"query": "x" * 2001})
        response = await websocket.receive_json()
        assert response["type"] == "error"
        assert "too long" in response["data"].lower() or "2000" in response["data"]


async def test_websocket_invalid_json(api_client):
    """WebSocket responds with error for invalid JSON."""
    async with api_client.websocket_connect("/api/chat/stream") as websocket:
        # Send malformed JSON
        await websocket.send_text("not json")
        response = await websocket.receive_json()
        assert response["type"] == "error"
        assert "Invalid JSON" in response["data"]

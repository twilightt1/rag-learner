from __future__ import annotations

import pytest
import json
import uuid
from sqlmodel import select

from backend.database import Quiz, Chunk, Document, engine


# --- Quiz API Tests ---

async def test_quiz_generate_creates_quiz(api_client, mocker, db_session):
    """POST /api/quiz/generate creates a quiz and returns result."""
    from backend.quiz.schemas import MCQQuestion, MCQOption
    import uuid

    # Mock the quiz generator
    mock_quiz_result = {
        "quiz_id": str(uuid.uuid4()),
        "quiz_type": "mcq",
        "doc_ids": ["doc1"],
        "questions": [
            {
                "question": "What is RAG?",
                "options": [
                    {"label": "A", "text": "Random Access Memory"},
                    {"label": "B", "text": "Retrieval-Augmented Generation"},
                    {"label": "C", "text": "Recurrent Attention Graph"},
                    {"label": "D", "text": "Reasoning And Generation"},
                ],
                "answer": "B",
                "explanation": "RAG combines retrieval with generation.",
            }
        ],
        "flashcards": [],
    }
    mocker.patch('backend.api.quiz.generate_quiz', return_value=mock_quiz_result)

    # Create a document and chunk in DB
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test.pdf",
        source_type="pdf",
        source_path="/tmp/test.pdf",
        status="ready",
    )
    chunk = Chunk(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        text="RAG is Retrieval-Augmented Generation",
        token_count=100,
        chunk_index=0,
    )
    with Session(engine) as db:
        db.add(doc)
        db.add(chunk)
        db.commit()

    resp = await api_client.post("/api/quiz/generate", json={
        "doc_ids": [doc_id],
        "quiz_type": "mcq",
        "n_questions": 1,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["quiz_type"] == "mcq"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question"] == "What is RAG?"


async def test_quiz_generate_validates_params(api_client):
    """POST /api/quiz/generate validates request body."""
    # Missing required fields
    resp = await api_client.post("/api/quiz/generate", json={})
    assert resp.status_code == 422

    # Invalid quiz_type
    resp = await api_client.post("/api/quiz/generate", json={
        "doc_ids": [1],
        "quiz_type": "invalid",
        "n_questions": 1,
    })
    assert resp.status_code == 422  # enum validation


async def test_quiz_generate_no_chunks_returns_error(api_client, mocker):
    """POST /api/quiz/generate fails if no chunks available."""
    mocker.patch('backend.api.quiz.generate_quiz', side_effect=ValueError("No chunks found"))

    resp = await api_client.post("/api/quiz/generate", json={
        "doc_ids": [999],
        "quiz_type": "mcq",
        "n_questions": 1,
    })

    assert resp.status_code == 400
    assert "No chunks found" in resp.json()["detail"]


async def test_get_quiz_by_id(api_client, mocker):
    """GET /api/quiz/{id} retrieves stored quiz."""
    quiz_id = str(uuid.uuid4())
    quiz_data = {
        "id": quiz_id,
        "doc_ids": ["doc1", "doc2"],
        "questions": json.dumps([
            {"question": "Q1", "options": [{"label": "A", "text": "a"}], "answer": "A"}
        ]),
        "quiz_type": "mcq",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Mock DB query in the endpoint
    mocker.patch('backend.api.quiz.db.exec', return_value=[type('Quiz', (), quiz_data)])

    resp = await api_client.get(f"/api/quiz/{quiz_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == quiz_id
    assert data["quiz_type"] == "mcq"


async def test_get_quiz_404_missing(api_client, mocker):
    """GET /api/quiz/{id} returns 404 if not found."""
    mocker.patch('backend.api.quiz.db.exec', return_value=[])

    resp = await api_client.get("/api/quiz/999")
    assert resp.status_code == 404

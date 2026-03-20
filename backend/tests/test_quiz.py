from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock

from backend.quiz.generator import generate_quiz, _sample_chunks, _save_quiz
from backend.quiz.schemas import MCQQuestion, MCQOption, Flashcard, QuizResult
from backend.database import Quiz as QuizModel, engine
from sqlmodel import select


class MockLLM:
    """Mock LLM that returns predetermined quiz JSON."""

    def __init__(self, response=None):
        self.response = response or {
            "mcq": [
                {
                    "question": "What is backpropagation?",
                    "options": [
                        {"label": "A", "text": " Forward propagation"},
                        {"label": "B", "text": " Backward propagation of errors"},
                        {"label": "C", "text": " Gradient ascent"},
                        {"label": "D", "text": " Stochastic descent"},
                    ],
                    "answer": "B",
                    "explanation": "Backpropagation computes gradients by chain rule.",
                }
            ],
            "flashcards": [
                {"front": "Define gradient", "back": "Rate of change of loss w.r.t. parameters", "hint": " calculus"}
            ],
        }

    async def __call__(self, messages, max_tokens=None, temperature=None):
        return json.dumps(self.response)


@pytest.fixture
def mock_complete(mocker):
    """Replace the complete function with a mock."""
    return mocker.patch('backend.quiz.generator.complete', new_callable=AsyncMock)


def test_sample_chunks_returns_limited_samples(db_session):
    """_sample_chunks returns no more than requested samples."""
    from backend.database import Document, Chunk
    from backend.quiz.generator import _sample_chunks
    import uuid

    # Create a test document
    doc = Document(
        id=str(uuid.uuid4()),
        filename="test.pdf",
        source_type="pdf",
        source_path="/tmp/test.pdf",
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    # Create multiple chunks
    chunks = []
    for i in range(20):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            text=f"Chunk {i} with some content to meet minimum length.",
            token_count=100,
            chunk_index=i,
        )
        chunks.append(chunk)

    with Session(engine) as db:
        for c in chunks:
            db.add(c)
        db.commit()

    result = _sample_chunks([doc_id], n_samples=5)
    assert len(result) <= 5


def test_sample_chunks_prefers_longer_chunks(db_session):
    """_sample_chunks filters and samples from longer chunks (>50 tokens)."""
    from backend.database import Document, Chunk
    from backend.quiz.generator import _sample_chunks
    import uuid

    # Create a test document
    doc = Document(
        id=str(uuid.uuid4()),
        filename="test.pdf",
        source_type="pdf",
        source_path="/tmp/test.pdf",
        status="ready",
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    # Create mix of short and long chunks
    long_chunks = []
    for i in range(10):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            text=f"Long chunk {i}. " * 20,
            token_count=100,
            chunk_index=i,
        )
        long_chunks.append(chunk)

    short_chunks = []
    for i in range(10, 15):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            text="Short",
            token_count=5,
            chunk_index=i,
        )
        short_chunks.append(chunk)

    with Session(engine) as db:
        for c in long_chunks + short_chunks:
            db.add(c)
        db.commit()

    result = _sample_chunks([doc_id], n_samples=5)
    # All sampled chunks should be from the long set (since they exist)
    for c in result:
        assert c.token_count > 50


def test_sample_chunks_returns_empty_when_no_chunks(db_session):
    """_sample_chunks returns empty list when no chunks found."""
    from backend.quiz.generator import _sample_chunks

    result = _sample_chunks(["nonexistent-doc-id"], n_samples=5)
    assert result == []


@pytest.mark.asyncio
async def test_generate_quiz_mcq(mock_complete, db_session):
    """generate_quiz creates MCQ QuizResult from LLM response."""
    mock_complete.return_value = json.dumps({
        "mcq": [
            {
                "question": "Q1",
                "options": [{"label": "A", "text": "opt1"}, {"label": "B", "text": "opt2"},
                            {"label": "C", "text": "opt3"}, {"label": "D", "text": "opt4"}],
                "answer": "A",
                "explanation": "Because A is correct"
            }
        ],
        "flashcards": []
    })

    # Create a document and a chunk in DB
    from backend.database import Document, Chunk
    import uuid
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
        text="Some educational content to base the quiz on.",
        token_count=150,
        chunk_index=0,
    )
    with Session(engine) as db:
        db.add(doc)
        db.add(chunk)
        db.commit()

    result = await generate_quiz(doc_ids=[doc_id], quiz_type="mcq", n_questions=1)

    assert isinstance(result, QuizResult)
    assert result.quiz_type == "mcq"
    assert len(result.questions) == 1
    assert isinstance(result.questions[0], MCQQuestion)
    assert result.questions[0].question == "Q1"
    assert len(result.questions[0].options) == 4
    assert result.questions[0].answer == "A"


@pytest.mark.asyncio
async def test_generate_quiz_flashcard(mock_complete, db_session):
    """generate_quiz creates flashcard QuizResult from LLM response."""
    mock_complete.return_value = json.dumps({
        "flashcards": [
            {"front": "What is an embedding?", "back": "Vector representation of text", "hint": "vector"}
        ],
        "mcq": []
    })

    # Create a document and chunk in DB
    from backend.database import Document, Chunk
    import uuid
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
        text="Embeddings are dense vector representations.",
        token_count=50,
        chunk_index=0,
    )
    with Session(engine) as db:
        db.add(doc)
        db.add(chunk)
        db.commit()

    result = await generate_quiz(doc_ids=[doc_id], quiz_type="flashcard", n_questions=1)

    assert result.quiz_type == "flashcard"
    assert len(result.flashcards) == 1
    assert isinstance(result.flashcards[0], Flashcard)
    assert result.flashcards[0].front == "What is an embedding?"
    assert result.flashcards[0].back == "Vector representation of text"


@pytest.mark.asyncio
async def test_generate_quiz_saves_to_db(mock_complete, db_session):
    """generate_quiz persists quiz to database and returns valid quiz_id."""
    mock_complete.return_value = json.dumps({
        "mcq": [
            {
                "question": "Test Q?",
                "options": [{"label": "A", "text": "a"}, {"label": "B", "text": "b"},
                            {"label": "C", "text": "c"}, {"label": "D", "text": "d"}],
                "answer": "A",
            }
        ],
        "flashcards": []
    })

    # Create document and chunk
    from backend.database import Document, Chunk
    import uuid
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
        text="Content",
        token_count=100,
        chunk_index=0,
    )
    with Session(engine) as db:
        db.add(doc)
        db.add(chunk)
        db.commit()

    result = await generate_quiz(doc_ids=[doc_id], n_questions=1)

    # Check that quiz exists in DB
    with Session(engine) as db:
        quiz = db.get(QuizModel, result.quiz_id)
        assert quiz is not None
        assert quiz.quiz_type == "mcq"
        questions = json.loads(quiz.questions)
        assert len(questions) == 1


@pytest.mark.asyncio
async def test_generate_quiz_no_chunks_raises(mock_complete, db_session):
    """generate_quiz raises if no chunks available for selected docs."""
    with pytest.raises(ValueError, match="No chunks found"):
        await generate_quiz(doc_ids=["999"], n_questions=5)


@pytest.mark.asyncio
async def test_generate_quiz_llm_malformed_json_raises(mock_complete, db_session):
    """generate_quiz raises if LLM returns invalid JSON."""
    mock_complete.return_value = "not valid json {"

    # Create a document and chunk
    from backend.database import Document, Chunk
    import uuid
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
        text="Content",
        token_count=100,
        chunk_index=0,
    )
    with Session(engine) as db:
        db.add(doc)
        db.add(chunk)
        db.commit()

    with pytest.raises(json.JSONDecodeError):
        await generate_quiz(doc_ids=[doc_id], n_questions=1)


def test_save_quiz_returns_id():
    """_save_quiz creates DB record and returns its ID."""
    # Use in-memory DB
    import json as _json
    from backend.quiz.generator import _save_quiz

    quiz_id = _save_quiz(
        doc_ids=["doc1", "doc2"],
        quiz_type="mcq",
        questions=[MCQQuestion(
            question="Q?",
            options=[MCQOption(label="A", text="a"), MCQOption(label="B", text="b"),
                     MCQOption(label="C", text="c"), MCQOption(label="D", text="d")],
            answer="A"
        )],
        flashcards=[]
    )

    assert isinstance(quiz_id, str)
    # Verify persistence
    with Session(engine) as db:
        quiz = db.get(QuizModel, quiz_id)
        assert quiz is not None
        assert quiz.quiz_type == "mcq"

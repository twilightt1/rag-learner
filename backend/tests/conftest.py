from __future__ import annotations

import os
import tempfile
import pytest
import chromadb
from sqlmodel import SQLModel, create_engine, Session
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Session-scoped settings fixture — must run BEFORE any backend modules are imported
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(tmp_path_factory):
    """Set environment variables for the entire test session before any backend imports."""
    tmp = tmp_path_factory.mktemp("data")

    os.environ["CHROMA_PATH"] = str(tmp / "chroma")
    os.environ["UPLOAD_PATH"] = str(tmp / "uploads")
    os.environ["DB_PATH"] = str(tmp / "test.db")
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["CORS_ORIGINS"] = '["http://localhost:5173","http://127.0.0.1:5173"]'
    os.environ["MAX_UPLOAD_BYTES"] = "52428800"  # 50 MB

    # Ensure no .env interferes
    os.environ.pop("PYTHONPATH", None)

    yield tmp

    # Cleanup
    for var in ["CHROMA_PATH", "UPLOAD_PATH", "DB_PATH", "OPENROUTER_API_KEY", "LOG_LEVEL", "CORS_ORIGINS", "MAX_UPLOAD_BYTES"]:
        os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_engine(setup_test_environment):
    """In-memory SQLite engine, tables created fresh per test."""
    # Import models to register them with SQLModel.metadata
    from backend.database import Document, Chunk, ChatSession, Message, Quiz  # noqa: F401
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    """SQLModel session bound to the in-memory engine."""
    with Session(db_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# ChromaDB fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def chroma_client(setup_test_environment):
    """Ephemeral in-memory ChromaDB client, isolated per test."""
    client = chromadb.EphemeralClient()
    yield client
    try:
        client.reset()
    except Exception:
        pass


@pytest.fixture()
def vector_store(chroma_client):
    """VectorStore instance backed by ephemeral ChromaDB."""
    from backend.rag.vector_store import VectorStore
    store = VectorStore(client=chroma_client)
    yield store


# ---------------------------------------------------------------------------
# Application fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
async def api_client(db_session, chroma_client, mocker, setup_test_environment):
    """
    HTTPX async client wired to the FastAPI app.
    Overrides DB and vector store dependencies.
    """
    # Import backend modules after environment is configured
    from backend.main import app
    from backend.database import get_session as original_get_session
    from backend.llm.openrouter import complete as original_complete, stream_complete as original_stream_complete
    from backend.rag.retriever import retrieve as original_retrieve

    # Override get_session to use test db
    def _get_test_session():
        return db_session

    # Override vector store get_collection to use in-memory client
    def _get_test_collection():
        return chroma_client.get_or_create_collection(
            name="rag_learner",
            metadata={"hnsw:space": "cosine"}
        )

    # Override LLM calls to avoid network
    async def _mock_complete(messages, **kwargs):
        return "Mocked LLM response"

    async def _mock_stream_complete(messages, **kwargs):
        for token in ["Mocked", " LLM"]:
            yield token

    # Override retriever
    def _mock_retrieve(query, doc_ids=None, top_k_retrieve=None, top_k_final=None):
        return []

    app.dependency_overrides[original_get_session] = _get_test_session
    mocker.patch('backend.rag.vector_store.get_collection', _get_test_collection)
    mocker.patch('backend.llm.openrouter.complete', _mock_complete)
    mocker.patch('backend.llm.openrouter.stream_complete', _mock_stream_complete)
    mocker.patch('backend.rag.retriever.retrieve', _mock_retrieve)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Global singletons reset
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_singletons(mocker):
    """Reset singleton models and clients before each test."""
    mocker.patch('backend.rag.embedder._model', None)
    mocker.patch('backend.rag.retriever._reranker', None)
    mocker.patch('backend.rag.vector_store._collection', None)
    mocker.patch('backend.rag.vector_store._client', None)
    yield


# ---------------------------------------------------------------------------
# Sample file fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_pdf(tmp_path, setup_test_environment):
    """Tiny single-page PDF created with fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Machine learning is a subset of artificial "
                          "intelligence. It enables computers to learn from data.")
    path = tmp_path / "sample.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture()
def sample_md(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text(
        "# Introduction\n\nThis chapter covers neural networks.\n\n"
        "## Backpropagation\n\nGradients flow backwards through layers.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_py(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    \"\"\"Return the sum of a and b.\"\"\"\n"
        "    return a + b\n\n"
        "class Calculator:\n"
        "    def multiply(self, x, y):\n"
        "        return x * y\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_js(tmp_path):
    path = tmp_path / "sample.js"
    path.write_text(
        "function greet(name) {\n"
        "  return `Hello, ${name}!`;\n"
        "}\n\n"
        "class Person {\n"
        "  constructor(name) {\n"
        "    this.name = name;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_ts(tmp_path):
    path = tmp_path / "sample.ts"
    path.write_text(
        "interface User {\n"
        "  name: string;\n"
        "  age: number;\n"
        "}\n\n"
        "function greet(user: User): string {\n"
        "  return `Hello, ${user.name}`;\n"
        "}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_txt(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(
        "This is a plain text file.\n"
        "It contains multiple lines.\n"
        "The chunker should handle it properly.\n",
        encoding="utf-8",
    )
    return path

# TESTING.md — Test strategy

---

## The one rule

**Tests must pass before every commit.**

```bash
pytest backend/tests/ -x -q
```

`-x` stops on the first failure. Fix it. Then continue.

---

## Setup

### `pytest.ini`

```ini
[pytest]
testpaths = backend/tests
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
```

### `requirements-dev.txt`

```
pytest>=8.0
pytest-asyncio>=0.23
pytest-mock>=3.12
pytest-cov>=5.0
httpx>=0.27           # AsyncClient for FastAPI testing
```

---

## `conftest.py` — canonical fixtures

Every test module imports from `conftest.py`. Define these once and reuse.

```python
from __future__ import annotations

import tempfile
import os
import pytest
import chromadb
from sqlmodel import SQLModel, create_engine, Session
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import get_session
from backend.rag.vector_store import VectorStore
from backend.config import get_settings


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    """Override settings to use temp paths for the whole test session."""
    tmp = tmp_path_factory.mktemp("data")
    os.environ["CHROMA_PATH"] = str(tmp / "chroma")
    os.environ["UPLOAD_PATH"] = str(tmp / "uploads")
    os.environ["DB_PATH"]     = str(tmp / "test.db")
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    get_settings.cache_clear()      # bust the lru_cache
    return get_settings()


@pytest.fixture()
def db_engine(settings):
    """In-memory SQLite engine, tables created fresh per test."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    """SQLModel session bound to the in-memory engine."""
    with Session(db_engine) as session:
        yield session


@pytest.fixture()
def chroma_client():
    """Ephemeral in-memory ChromaDB client, isolated per test."""
    return chromadb.EphemeralClient()


@pytest.fixture()
def vector_store(chroma_client):
    """VectorStore instance backed by ephemeral ChromaDB."""
    return VectorStore(client=chroma_client)


@pytest.fixture()
async def api_client(db_session, vector_store):
    """
    HTTPX async client wired to the FastAPI app.
    Overrides DB and vector store dependencies so tests never
    touch real storage.
    """
    app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_pdf(tmp_path):
    """Tiny single-page PDF created with fpdf2 for parser tests."""
    from fpdf import FPDF
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
```

---

## Module-by-module test guide

### `test_parsers.py`

```python
# pdf_parser
def test_pdf_extracts_text(sample_pdf):
    from backend.ingestion.parsers.pdf_parser import parse_pdf
    pages = parse_pdf(str(sample_pdf))
    assert len(pages) == 1
    assert "machine learning" in pages[0].text.lower()
    assert pages[0].page_num == 1

def test_pdf_skips_blank_pages(tmp_path):
    # Create a 2-page PDF where page 2 is blank
    ...
    pages = parse_pdf(str(path))
    assert len(pages) == 1       # blank page filtered out

# md_parser
def test_md_preserves_headings(sample_md):
    from backend.ingestion.parsers.md_parser import parse_md
    text = parse_md(str(sample_md))
    assert "# Introduction" in text
    assert "## Backpropagation" in text

def test_md_extracts_paragraph_text(sample_md):
    text = parse_md(str(sample_md))
    assert "neural networks" in text

# url_parser — always mock Playwright
async def test_url_parser_extracts_body(mocker):
    from backend.ingestion.parsers.url_parser import parse_url
    mock_page = mocker.AsyncMock()
    mock_page.evaluate.return_value = "Study hard every day."
    mocker.patch("playwright.async_api.async_playwright")
    # ... wire the mock chain ...
    text = await parse_url("https://example.com")
    assert "study hard" in text.lower()

# code_parser
def test_code_parser_extracts_functions(sample_py):
    from backend.ingestion.parsers.code_parser import parse_code
    chunks = parse_code(str(sample_py))
    names = [c.metadata.get("function_name") for c in chunks]
    assert "add" in names

def test_code_parser_extracts_classes(sample_py):
    chunks = parse_code(str(sample_py))
    names = [c.metadata.get("class_name") for c in chunks]
    assert "Calculator" in names
```

### `test_chunker.py`

```python
def test_chunk_size_within_limit():
    from backend.ingestion.chunker import chunk_text
    import tiktoken
    long_text = "word " * 2000
    chunks = chunk_text(long_text, doc_id="d1")
    enc = tiktoken.get_encoding("cl100k_base")
    for c in chunks:
        assert len(enc.encode(c.text)) <= 512

def test_chunk_overlap():
    """Last N tokens of chunk[i] == first N tokens of chunk[i+1]."""
    from backend.ingestion.chunker import chunk_text
    import tiktoken
    text = "token " * 1200
    chunks = chunk_text(text, doc_id="d1")
    enc = tiktoken.get_encoding("cl100k_base")
    if len(chunks) >= 2:
        end_of_first   = enc.encode(chunks[0].text)[-64:]
        start_of_second = enc.encode(chunks[1].text)[:64]
        assert end_of_first == start_of_second

def test_chunk_metadata_populated():
    from backend.ingestion.chunker import chunk_text
    chunks = chunk_text("hello world", doc_id="doc-abc", page_num=3)
    assert chunks[0].doc_id == "doc-abc"
    assert chunks[0].page_num == 3
    assert chunks[0].chunk_index == 0

def test_empty_text_returns_empty_list():
    from backend.ingestion.chunker import chunk_text
    assert chunk_text("", doc_id="d") == []
```

### `test_embedder.py`

```python
def test_embed_returns_correct_shape():
    from backend.rag.embedder import get_embedder
    emb = get_embedder()
    vectors = emb.embed_texts(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384

def test_embed_query_returns_single_vector():
    from backend.rag.embedder import get_embedder
    emb = get_embedder()
    vec = emb.embed_query("what is backpropagation?")
    assert len(vec) == 384
    assert isinstance(vec[0], float)

def test_embedder_is_singleton():
    from backend.rag.embedder import get_embedder
    a = get_embedder()
    b = get_embedder()
    assert a is b
```

### `test_vector_store.py`

```python
def test_upsert_and_query(vector_store):
    from backend.rag.embedder import get_embedder
    emb = get_embedder()
    texts = ["neural networks learn from data",
             "gradient descent minimises the loss function"]
    vectors = emb.embed_texts(texts)
    chunks = [
        {"id": "c1", "doc_id": "d1", "text": texts[0], "chunk_index": 0},
        {"id": "c2", "doc_id": "d1", "text": texts[1], "chunk_index": 1},
    ]
    vector_store.upsert_chunks(chunks, vectors)

    results = vector_store.query_chunks(
        emb.embed_query("how does backprop work?"), n_results=2
    )
    assert len(results) == 2
    assert results[0].chunk_id in {"c1", "c2"}

def test_delete_by_doc_id(vector_store):
    # upsert two docs, delete one, confirm only the other remains
    ...
    vector_store.delete_by_doc_id("d1")
    assert vector_store.count() == 1

def test_query_returns_empty_on_empty_store(vector_store):
    from backend.rag.embedder import get_embedder
    vec = get_embedder().embed_query("anything")
    results = vector_store.query_chunks(vec, n_results=5)
    assert results == []
```

### `test_llm.py`

```python
async def test_chat_returns_content(mocker):
    """Non-streaming call returns a string response."""
    from backend.llm.openrouter import OpenRouterClient
    mock_resp = {"choices": [{"message": {"content": "Paris."}}]}
    mocker.patch("httpx.AsyncClient.post",
                 return_value=mocker.Mock(json=lambda: mock_resp,
                                         status_code=200))
    client = OpenRouterClient()
    result = await client.chat(messages=[{"role": "user", "content": "Capital of France?"}])
    assert result == "Paris."

async def test_stream_yields_tokens(mocker):
    """Streaming call yields individual token strings."""
    from backend.llm.openrouter import OpenRouterClient
    # Mock httpx streaming response with SSE lines
    ...
    tokens = [t async for t in client.stream_chat(messages=[...])]
    assert "".join(tokens)  # non-empty

async def test_chat_raises_on_4xx(mocker):
    from backend.llm.openrouter import OpenRouterClient
    mocker.patch("httpx.AsyncClient.post",
                 return_value=mocker.Mock(status_code=401,
                                         json=lambda: {"error": "Unauthorized"}))
    with pytest.raises(Exception, match="401"):
        await OpenRouterClient().chat(messages=[...])
```

### `test_api.py`

```python
# POST /api/chat
async def test_chat_post_returns_answer(api_client, mocker):
    mocker.patch("backend.llm.openrouter.OpenRouterClient.chat",
                 return_value="Backprop computes gradients via chain rule.")
    mocker.patch("backend.rag.retriever.retrieve",
                 return_value=[])        # empty context is fine for this test
    resp = await api_client.post("/api/chat", json={
        "session_id": "s1",
        "message": "Explain backpropagation",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert isinstance(data["sources"], list)

async def test_chat_post_missing_message_returns_422(api_client):
    resp = await api_client.post("/api/chat", json={"session_id": "s1"})
    assert resp.status_code == 422

# POST /api/ingest
async def test_ingest_pdf_creates_document(api_client, sample_pdf, mocker):
    mocker.patch("backend.ingestion.pipeline.IngestPipeline.run")
    with open(sample_pdf, "rb") as f:
        resp = await api_client.post(
            "/api/ingest", files={"file": ("sample.pdf", f, "application/pdf")}
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert "doc_id" in data

async def test_ingest_url_creates_document(api_client, mocker):
    mocker.patch("backend.ingestion.pipeline.IngestPipeline.run")
    resp = await api_client.post(
        "/api/ingest", json={"url": "https://example.com"}
    )
    assert resp.status_code == 202

# DELETE /api/documents/{id}
async def test_delete_document_removes_chunks(api_client, mocker):
    mock_delete = mocker.patch("backend.rag.vector_store.VectorStore.delete_by_doc_id")
    # First ingest a doc ...
    resp = await api_client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 204
    mock_delete.assert_called_once_with(doc_id)

async def test_delete_nonexistent_returns_404(api_client):
    resp = await api_client.delete("/api/documents/does-not-exist")
    assert resp.status_code == 404
```

### `test_retriever.py`

```python
async def test_retriever_returns_top_k_final(mocker):
    from backend.rag.retriever import retrieve
    # Mock vector_store.query_chunks → 8 fake results
    # Mock cross-encoder predict → scores
    # Expect TOP_K_FINAL (3) returned
    mocker.patch("backend.rag.vector_store.VectorStore.query_chunks",
                 return_value=[fake_chunk(i) for i in range(8)])
    mocker.patch("sentence_transformers.CrossEncoder.predict",
                 return_value=[0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4])
    results = await retrieve("explain backprop")
    assert len(results) == 3
    # Highest scores first
    assert results[0].score >= results[1].score

async def test_retriever_filters_by_doc_ids(mocker):
    # Confirm doc_ids filter is passed to vector_store
    mock_query = mocker.patch("backend.rag.vector_store.VectorStore.query_chunks",
                              return_value=[])
    await retrieve("question", doc_ids=["doc-1"])
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs.get("where", {}).get("doc_id", {}).get("$in") == ["doc-1"]
```

### `test_quiz.py`

```python
async def test_generate_returns_valid_quiz(mocker):
    from backend.quiz.generator import QuizGenerator
    fake_llm_output = json.dumps({
        "mcq": [
            {"question": "What is ML?",
             "options": [{"letter":"A","text":"..."},{"letter":"B","text":"..."},
                         {"letter":"C","text":"..."},{"letter":"D","text":"..."}],
             "correct": "A", "explanation": "..."}
            for _ in range(5)
        ],
        "flashcards": [{"front": "Q", "back": "A"} for _ in range(5)],
    })
    mocker.patch("backend.llm.openrouter.OpenRouterClient.chat",
                 return_value=fake_llm_output)
    gen = QuizGenerator()
    quiz = await gen.generate(doc_ids=["d1"], chunks=[fake_chunk() for _ in range(5)])
    assert len(quiz.mcq) == 5
    assert len(quiz.flashcards) == 5

async def test_generate_retries_on_bad_json(mocker):
    from backend.quiz.generator import QuizGenerator
    call_count = 0
    async def mock_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "this is not json {"
        return valid_quiz_json()
    mocker.patch("backend.llm.openrouter.OpenRouterClient.chat",
                 side_effect=mock_chat)
    gen = QuizGenerator()
    quiz = await gen.generate(doc_ids=["d1"], chunks=[fake_chunk()])
    assert call_count == 2
    assert quiz is not None

async def test_generate_raises_after_two_failures(mocker):
    mocker.patch("backend.llm.openrouter.OpenRouterClient.chat",
                 return_value="bad json {{{")
    from fastapi import HTTPException
    gen = QuizGenerator()
    with pytest.raises(HTTPException) as exc_info:
        await gen.generate(doc_ids=["d1"], chunks=[fake_chunk()])
    assert exc_info.value.status_code == 502
```

---

## Coverage check

```bash
pytest backend/tests/ --cov=backend --cov-report=term-missing -q
```

Target: ≥ 80% line coverage on:
- `backend/ingestion/`
- `backend/rag/`
- `backend/llm/`
- `backend/quiz/`

API layer (`backend/api/`) is covered through integration tests in
`test_api.py` — aim for ≥ 70% there.

---

## What not to test

- `config.py` — pydantic-settings, already tested by the library
- `database.py` model definitions — SQLModel handles schema creation
- Third-party library internals (ChromaDB, sentence-transformers)

Focus coverage effort on your own logic: chunking, pipeline orchestration,
retrieval ranking, prompt assembly, quiz parsing, and error handling paths.

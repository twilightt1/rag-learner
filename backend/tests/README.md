# Test Suite — RAG Learner Assistant

This directory contains a comprehensive test suite for the RAG Learner project.

## Setup

1. Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

2. Ensure the main requirements are also installed:

```bash
pip install -r requirements.txt
```

3. (Optional) Install `fpdf2` for PDF generation in tests (included in requirements.txt).

## Running Tests

```bash
# Run all tests (stop on first failure)
pytest backend/tests/ -x -q

# Run with verbose output
pytest backend/tests/ -v

# Run a specific test file
pytest backend/tests/test_parsers.py -v

# Run with coverage report
pytest backend/tests/ --cov=backend --cov-report=term-missing -q
```

Coverage target: **≥ 80%** on the following modules:
- `backend/ingestion/`
- `backend/rag/`
- `backend/llm/`
- `backend/quiz/`

## Test Structure

| File | Description |
|------|-------------|
| `conftest.py` | Shared fixtures (test DB, ChromaDB client, API client, sample files) |
| `test_parsers.py` | PDF, Markdown, Code, and URL parsers |
| `test_chunker.py` | Sliding-window token chunking logic |
| `test_embedder.py` | SentenceTransformer embedding wrapper |
| `test_vector_store.py` | ChromaDB abstraction layer |
| `test_retriever.py` | Retrieval pipeline with reranking |
| `test_llm.py` | OpenRouter async client (streaming & non-streaming) |
| `test_prompt_builder.py` | System prompt and context assembly |
| `test_chat_history.py` | Session management and message persistence |
| `test_quiz.py` | Quiz generation and Pydantic schemas |
| `test_api.py` | REST endpoints: ingest, documents, chunks, stats |
| `test_chat_api.py` | Chat POST endpoint and session management |
| `test_quiz_api.py` | Quiz generation and retrieval endpoints |
| `test_websocket.py` | WebSocket streaming chat |
| `test_pipeline.py` | Ingestion pipeline orchestration |

## Fixtures

- `db_engine`: In-memory SQLite engine with tables created fresh per test.
- `db_session`: Transactional session that rolls back after each test.
- `chroma_client`: Ephemeral in-memory ChromaDB client.
- `vector_store`: VectorStore backed by ephemeral client.
- `api_client`: HTTPX async client wired to FastAPI app with dependencies overridden.
- `sample_pdf`, `sample_md`, `sample_py`, `sample_js`, `sample_ts`, `sample_txt`: Temporary sample files.
- `reset_singletons`: Clears global singletons (embedding model, reranker, Chroma collection) before each test.
- `patch_global_engines`: Patches all `engine` references to point to the test engine.

## Notes

- All tests use **isolated in-memory databases**. No files under `data/` are touched.
- LLM calls and external network requests are **mocked**.
- The embedder and retriever models are mocked to avoid heavy downloads.
- The WebSocket tests use the `api_client` fixture's `websocket_connect` method.

## Troubleshooting

If you encounter import errors, ensure that the `backend` package is importable from the project root:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

Or run pytest from the project root.

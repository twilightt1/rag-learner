# CLAUDE.md — RAG Learner Assistant

You are building a full-stack RAG-powered study assistant. This file is your
single source of truth. Read it fully before writing any code.

---

## 🔴 Critical rules (non-negotiable)

1. **Tests must pass before every commit.** Run the test suite for the module
   you touched. If any test fails, fix it before proceeding. Never commit red.
2. **One phase at a time.** Complete and test a phase fully before starting
   the next. Do not scaffold ahead.
3. **No placeholder implementations.** Every function must do real work.
   `pass`, `...`, `TODO`, and `raise NotImplementedError` are banned in
   committed code.
4. **No hardcoded secrets.** All keys and paths come from `config.py` which
   reads `.env`. Never inline an API key or absolute path.
5. **Type-annotate all function signatures.** Use `from __future__ import
   annotations` at the top of every backend file.

---

## Project overview

| Item | Value |
|------|-------|
| Purpose | Upload study materials → chat Q&A → generate quizzes |
| Backend | FastAPI, Python 3.11+ |
| Frontend | React 18 + Vite + TailwindCSS |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) |
| Vector DB | ChromaDB (local persistent) |
| Relational DB | SQLite via SQLModel |
| LLM | OpenRouter (`google/gemma-3-27b-it:free`) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Auth | None — local single-user app |

See `docs/ARCHITECTURE.md` for the full system diagram.

---

## Repository layout

```
rag-learner/
├── CLAUDE.md                    ← you are here
├── .env.example
├── requirements.txt
├── pytest.ini
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PHASES.md
│   ├── API.md
│   └── TESTING.md
│
├── backend/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # All settings, read from .env
│   ├── database.py              # SQLite init, SQLModel table models
│   │
│   ├── ingestion/
│   │   ├── pipeline.py          # Orchestrator: parse→chunk→embed→store
│   │   ├── chunker.py           # Sliding-window token chunker
│   │   └── parsers/
│   │       ├── pdf_parser.py    # pymupdf
│   │       ├── md_parser.py     # mistune
│   │       ├── url_parser.py    # playwright (async)
│   │       └── code_parser.py   # tree-sitter
│   │
│   ├── rag/
│   │   ├── embedder.py          # SentenceTransformer singleton
│   │   ├── vector_store.py      # ChromaDB CRUD
│   │   ├── retriever.py         # embed query → top-k → rerank
│   │   └── prompt_builder.py    # assemble system prompt + context
│   │
│   ├── llm/
│   │   ├── openrouter.py        # async streaming client
│   │   └── chat_history.py      # session-scoped message buffer
│   │
│   ├── quiz/
│   │   ├── generator.py         # MCQ + flashcard generation
│   │   └── schemas.py           # Pydantic output models
│   │
│   ├── api/
│   │   ├── documents.py         # /ingest, /documents
│   │   ├── chat.py              # /chat, WS /chat/stream
│   │   ├── knowledge.py         # /chunks
│   │   └── quiz.py              # /quiz
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_parsers.py
│       ├── test_chunker.py
│       ├── test_embedder.py
│       ├── test_vector_store.py
│       ├── test_retriever.py
│       ├── test_pipeline.py
│       ├── test_llm.py
│       ├── test_quiz.py
│       └── test_api.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx
│   │   │   ├── UploadPage.jsx
│   │   │   ├── KBBrowserPage.jsx
│   │   │   └── QuizPage.jsx
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   ├── upload/
│   │   │   ├── kb/
│   │   │   └── quiz/
│   │   ├── hooks/
│   │   │   ├── useChat.js
│   │   │   ├── useDocuments.js
│   │   │   └── useQuiz.js
│   │   └── api/
│   │       └── client.js
│   └── vite.config.js
│
└── data/
    ├── chroma_db/               # gitignored
    ├── uploads/                 # gitignored
    └── rag_learner.db           # gitignored
```

---

## Configuration constants (`backend/config.py`)

These values are the canonical reference. Do not redefine them elsewhere.

```python
EMBED_MODEL      = "all-MiniLM-L6-v2"
RERANK_MODEL     = "cross-encoder/ms-marco-MiniLM-L-6-v2"
OPENROUTER_MODEL = "google/gemma-3-27b-it:free"
OPENROUTER_BASE  = "https://openrouter.ai/api/v1"
CHUNK_SIZE       = 512    # tokens
CHUNK_OVERLAP    = 64     # tokens
TOP_K_RETRIEVE   = 8      # candidates sent to reranker
TOP_K_FINAL      = 3      # chunks injected into LLM prompt
MAX_HISTORY      = 10     # messages kept per session
CHROMA_PATH      = "data/chroma_db"
UPLOAD_PATH      = "data/uploads"
DB_PATH          = "data/rag_learner.db"
```

---

## Database models

Defined in `backend/database.py` using SQLModel.

```
Document
  id            : str (uuid4)
  filename      : str
  source_type   : Literal["pdf","md","url","code"]
  source_uri    : str           # original path or URL
  status        : Literal["pending","processing","ready","failed"]
  error_msg     : str | None
  chunk_count   : int  = 0
  created_at    : datetime

Chunk
  id            : str (uuid4)
  doc_id        : str (FK → Document.id)
  text          : str
  chunk_index   : int
  page_num      : int | None    # PDFs only
  metadata      : str           # JSON blob (language, function name, etc.)

ChatSession
  id            : str (uuid4)
  title         : str
  created_at    : datetime

Message
  id            : str (uuid4)
  session_id    : str (FK → ChatSession.id)
  role          : Literal["user","assistant"]
  content       : str
  sources       : str           # JSON: list of {chunk_id, score, text}
  created_at    : datetime

Quiz
  id            : str (uuid4)
  doc_ids       : str           # JSON list of document ids
  questions     : str           # JSON list of QuizQuestion
  created_at    : datetime
```

---

## API surface

Full spec in `docs/API.md`. Quick reference:

```
POST   /api/ingest                 upload file or URL
GET    /api/documents              list all documents
DELETE /api/documents/{id}         delete doc + its chunks
GET    /api/chunks?doc_id=         list chunks for a doc
GET    /api/chunks/search?q=       semantic search across KB

POST   /api/chat                   single-turn Q&A (non-streaming)
WS     /api/chat/stream            streaming chat over WebSocket
GET    /api/sessions               list chat sessions
GET    /api/sessions/{id}/messages get session history

POST   /api/quiz/generate          generate quiz from doc_ids
GET    /api/quiz/{id}              retrieve a quiz
```

---

## RAG pipeline contract

```
User uploads file / URL
        ↓
[parser]      extract raw text + page/line metadata
        ↓
[chunker]     sliding window: CHUNK_SIZE tokens, CHUNK_OVERLAP overlap
              each chunk carries: doc_id, chunk_index, page_num, metadata{}
        ↓
[embedder]    batch encode chunks → List[List[float]] (384-dim)
        ↓
[vector_store] upsert into ChromaDB collection "chunks"
               id = chunk.id, embedding = vector, metadata = chunk fields
        ↓
Document.status → "ready", Document.chunk_count updated
```

Query flow:

```
User message
        ↓
[embedder]      embed query → vector
        ↓
[vector_store]  query(n_results=TOP_K_RETRIEVE) → List[ScoredChunk]
        ↓
[retriever]     cross-encoder rerank → keep TOP_K_FINAL
        ↓
[prompt_builder] system_prompt + context blocks + chat history
        ↓
[openrouter]    stream tokens → yield to WebSocket / response
```

---

## Testing contract

> **Tests must pass before every commit.**

- Run `pytest backend/tests/ -x -q` after every file you touch.
- `-x` stops at the first failure — fix before continuing.
- Tests use a **temp in-memory ChromaDB** and a **temp SQLite file**
  (both provided by `conftest.py` fixtures). Never touch `data/` in tests.
- LLM calls and Playwright are **mocked** via `pytest-mock`. No real network
  calls in the test suite.
- Every new function needs at minimum: one happy-path test + one error case.
- Coverage target: ≥ 80% on `ingestion/`, `rag/`, `llm/`, `quiz/`.

```bash
# Run all tests, stop on first failure
pytest backend/tests/ -x -q

# Run tests for a single module
pytest backend/tests/test_chunker.py -v

# Coverage report
pytest backend/tests/ --cov=backend --cov-report=term-missing -q
```

See `docs/TESTING.md` for fixture patterns, mock examples, and edge cases
to cover per module.

---

## Code conventions

### Python (backend)
- `from __future__ import annotations` at top of every file
- Type-annotate all function signatures (params + return type)
- Use `async def` for all I/O-bound operations (DB, network, file reads)
- Pydantic models for all API request/response shapes
- Raise `HTTPException` with meaningful `detail` strings from API layer
- Log with `logging.getLogger(__name__)` — no bare `print()` statements
- f-strings only for string formatting
- Max line length: 100 characters

### React (frontend)
- Functional components only — no class components
- Custom hooks in `src/hooks/` for all server-state logic
- `client.js` is the only file that imports axios
- Tailwind utility classes only — no inline `style={{}}` except for
  dynamic values (e.g. progress bar width percentage)
- Every async operation wrapped in try/catch with user-facing error state

---

## Phase checklist

Mark a phase done only when ALL its tests pass.

- [ ] **Phase 1** — Config, DB, PDF+MD parsers, chunker, embedder,
                     ChromaDB store, `/chat` POST endpoint
- [ ] **Phase 2** — URL parser (Playwright), code parser (tree-sitter),
                     full ingestion pipeline + status tracking
- [ ] **Phase 3** — Cross-encoder reranker, WebSocket streaming,
                     session history, source citations
- [ ] **Phase 4** — React frontend: all 4 pages wired to API
- [ ] **Phase 5** — Quiz engine: MCQ + flashcard generation + export

See `docs/PHASES.md` for per-phase file lists and acceptance criteria.

---

## How to start a phase

1. Read the phase spec in `docs/PHASES.md`.
2. Check `docs/API.md` for any new endpoints in that phase.
3. Check `docs/TESTING.md` for test patterns to follow.
4. Implement all files listed for the phase.
5. Write tests covering every new function.
6. Run `pytest backend/tests/ -x -q` — must be all green.
7. Tick the phase checkbox above.
8. Begin the next phase.

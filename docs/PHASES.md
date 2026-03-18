# PHASES.md — Build plan

Each phase has a file list, implementation notes, and acceptance criteria.
A phase is complete when every listed test passes. Do not start the next
phase until the current one is green.

---

## Phase 1 — Core RAG backbone

**Goal:** Ingest PDFs and Markdown files, store chunks in ChromaDB, answer
a single-turn question via `/api/chat`. Fully testable without a browser.

### Files to create

```
backend/config.py
backend/database.py
backend/main.py
backend/ingestion/__init__.py
backend/ingestion/chunker.py
backend/ingestion/parsers/__init__.py
backend/ingestion/parsers/pdf_parser.py
backend/ingestion/parsers/md_parser.py
backend/rag/__init__.py
backend/rag/embedder.py
backend/rag/vector_store.py
backend/rag/prompt_builder.py
backend/llm/__init__.py
backend/llm/openrouter.py
backend/llm/chat_history.py
backend/api/__init__.py
backend/api/chat.py
backend/tests/conftest.py
backend/tests/test_parsers.py
backend/tests/test_chunker.py
backend/tests/test_embedder.py
backend/tests/test_vector_store.py
backend/tests/test_llm.py
backend/tests/test_api.py        (chat endpoint only)
.env.example
requirements.txt
pytest.ini
```

### Implementation notes

**`config.py`** — use `pydantic-settings`. All values overridable via `.env`.
Expose a `get_settings()` function returning a cached `Settings` instance.

**`database.py`** — define all five SQLModel table classes (Document, Chunk,
ChatSession, Message, Quiz). Expose `init_db(engine)` and
`get_session()` as a FastAPI dependency.

**`chunker.py`** — tokenise with `tiktoken` (cl100k_base). Produce
`ChunkData(id, doc_id, text, chunk_index, page_num, metadata)` dataclasses.
Overlap must be exactly `CHUNK_OVERLAP` tokens, not bytes.

**`pdf_parser.py`** — use `pymupdf` (import as `fitz`). Extract text
page-by-page. Return `List[RawPage(text, page_num)]`. Skip pages where
`len(text.strip()) < 20`.

**`md_parser.py`** — use `mistune`. Walk the AST to extract headings +
paragraph text. Return a single string with headings preserved as `# H1`
markers so the chunker can split on them intelligently.

**`embedder.py`** — load `all-MiniLM-L6-v2` once as a module-level
singleton. Expose `embed_texts(texts: list[str]) -> list[list[float]]` and
`embed_query(text: str) -> list[float]`. Use `encode()` with
`convert_to_numpy=True` then `.tolist()`.

**`vector_store.py`** — wrap ChromaDB. Collection name is always `"chunks"`.
Expose: `upsert_chunks`, `query_chunks(vector, n_results) -> list[ScoredChunk]`,
`delete_by_doc_id`, `count`. `ScoredChunk` is a dataclass with
`chunk_id, text, score, metadata`.

**`prompt_builder.py`** — build the system prompt string. Format:
```
You are a study assistant. Answer questions using only the provided
context. If the answer is not in the context, say so clearly.

Context:
[1] {chunk1_text}
[2] {chunk2_text}
...
```
Return `(system_prompt, source_refs)` where `source_refs` is a list of
chunk ids in the order they appear.

**`openrouter.py`** — async client using `httpx.AsyncClient`. Must support
both streaming (`stream_chat`) and non-streaming (`chat`) modes.
Non-streaming used by Phase 1 `/chat` endpoint.
Streaming used by Phase 3 WebSocket endpoint.

**`chat.py` (api)** — `POST /api/chat` accepts
`{session_id, message, doc_ids?}`. Runs the full query→retrieve→prompt→llm
pipeline. Returns `{answer, sources: [{chunk_id, text, score}]}`.

### Acceptance criteria

```bash
pytest backend/tests/test_parsers.py -v     # pdf + md parsing
pytest backend/tests/test_chunker.py -v     # chunk size, overlap, metadata
pytest backend/tests/test_embedder.py -v    # embed shape, singleton
pytest backend/tests/test_vector_store.py -v # upsert, query, delete
pytest backend/tests/test_llm.py -v         # mocked openrouter client
pytest backend/tests/test_api.py -v -k chat # /api/chat POST
```

All must pass. Coverage on these modules ≥ 80%.

---

## Phase 2 — Full ingestion pipeline

**Goal:** Add URL and code parsers, wire everything into a background
ingestion pipeline with status tracking, and expose the document + chunk
management API endpoints.

### Files to create / modify

```
backend/ingestion/parsers/url_parser.py     (new)
backend/ingestion/parsers/code_parser.py    (new)
backend/ingestion/pipeline.py               (new)
backend/api/documents.py                    (new)
backend/api/knowledge.py                    (new)
backend/tests/test_pipeline.py              (new)
backend/tests/test_parsers.py               (extend: url + code cases)
backend/tests/test_api.py                   (extend: document + chunk endpoints)
```

### Implementation notes

**`url_parser.py`** — use `playwright` async API. Launch a chromium browser
headlessly, navigate to the URL, wait for `networkidle`, extract
`document.body.innerText`. Strip nav/footer boilerplate (lines under 40
chars surrounded by short lines). Return the cleaned text as a single string.

**`code_parser.py`** — use `tree-sitter`. Detect language from file extension
(`.py` → python, `.js/.ts` → javascript, `.java` → java, others → plaintext).
For supported languages, extract top-level function and class definitions as
individual chunks with `metadata.function_name` and `metadata.language`.
Fall back to line-based splitting for unsupported extensions.

**`pipeline.py`** — the `IngestPipeline` orchestrator:
```python
async def run(doc_id: str, file_path: str, source_type: str) -> None
```
Steps:
1. Set `Document.status = "processing"` in DB.
2. Route to the correct parser based on `source_type`.
3. Pass raw text through `chunker.chunk_text()`.
4. Batch-embed all chunks.
5. Upsert to ChromaDB and insert Chunk rows to SQLite.
6. Set `Document.status = "ready"`, update `chunk_count`.
7. On any exception: set `Document.status = "failed"`,
   store `error_msg = str(e)`, re-raise.

**`documents.py` (api)**:
- `POST /api/ingest` — accept `multipart/form-data` (file) or JSON `{url}`.
  Create Document row with `status = "pending"`. Kick off
  `asyncio.create_task(pipeline.run(...))`. Return `{doc_id, status}` immediately.
- `GET /api/documents` — return list of all documents with status.
- `GET /api/documents/{id}` — return single document.
- `DELETE /api/documents/{id}` — delete document, its SQLite Chunk rows,
  and call `vector_store.delete_by_doc_id`.

**`knowledge.py` (api)**:
- `GET /api/chunks?doc_id=` — return chunks for a doc, paginated
  (`?page=1&page_size=20`).
- `GET /api/chunks/search?q=` — embed the query and call
  `vector_store.query_chunks`. Return top-5 results with scores.

### Acceptance criteria

```bash
pytest backend/tests/test_pipeline.py -v
pytest backend/tests/test_parsers.py -v       # now includes url + code
pytest backend/tests/test_api.py -v -k "document or chunk"
```

All must pass. Pipeline test must cover: successful ingestion, parser
failure rolls back to "failed" status, delete removes chunks from both stores.

---

## Phase 3 — Streaming chat + sessions + reranker

**Goal:** Add the cross-encoder reranker, WebSocket streaming endpoint,
session management, and source citation storage.

### Files to create / modify

```
backend/rag/retriever.py         (new — wraps vector_store + reranker)
backend/llm/chat_history.py      (implement session buffer)
backend/api/chat.py              (extend: add WS endpoint + sessions)
backend/tests/test_retriever.py  (new)
backend/tests/test_api.py        (extend: WS + session endpoints)
```

### Implementation notes

**`retriever.py`** — load `cross-encoder/ms-marco-MiniLM-L-6-v2` once as a
singleton. Expose:
```python
async def retrieve(query: str, doc_ids: list[str] | None = None) -> list[ScoredChunk]
```
Steps: embed query → ChromaDB top-`TOP_K_RETRIEVE` (filter by doc_ids if
provided) → cross-encoder `.predict([(query, chunk.text), ...])` → sort by
score descending → return top `TOP_K_FINAL`.

**`chat_history.py`** — session-scoped buffer. On load, read last
`MAX_HISTORY` messages from SQLite for that session. Expose
`get_messages() -> list[dict]` (OpenAI format) and `append(role, content)`.
Persist each new message to the Message table immediately.

**WebSocket endpoint** — `WS /api/chat/stream`:
1. Accept connection, receive `{session_id, message, doc_ids?}` as JSON.
2. Retrieve + rerank chunks.
3. Build prompt.
4. Call `openrouter.stream_chat()` — yield each token chunk as
   `{"type": "token", "text": "..."}` over the WebSocket.
5. After stream completes, send `{"type": "done", "sources": [...]}`.
6. Persist the full assembled answer to the Message table.

**Session endpoints** in `chat.py`:
- `POST /api/sessions` — create session, return `{session_id, title}`.
- `GET /api/sessions` — list all sessions newest-first.
- `GET /api/sessions/{id}/messages` — return full message history.
- `DELETE /api/sessions/{id}` — delete session + messages.

### Acceptance criteria

```bash
pytest backend/tests/test_retriever.py -v
pytest backend/tests/test_api.py -v -k "session or stream"
```

WebSocket test must verify: tokens arrive in order, `done` frame contains
sources, message is persisted to DB after stream completes.

---

## Phase 4 — React frontend

**Goal:** Build all four UI pages wired to the live backend API.

### Files to create

```
frontend/src/App.jsx
frontend/src/api/client.js
frontend/src/hooks/useChat.js
frontend/src/hooks/useDocuments.js
frontend/src/hooks/useQuiz.js
frontend/src/pages/ChatPage.jsx
frontend/src/pages/UploadPage.jsx
frontend/src/pages/KBBrowserPage.jsx
frontend/src/pages/QuizPage.jsx
frontend/src/components/chat/MessageBubble.jsx
frontend/src/components/chat/SourceCard.jsx
frontend/src/components/chat/ChatInput.jsx
frontend/src/components/upload/DropZone.jsx
frontend/src/components/upload/UrlInput.jsx
frontend/src/components/upload/IngestProgress.jsx
frontend/src/components/kb/DocList.jsx
frontend/src/components/kb/ChunkViewer.jsx
frontend/src/components/quiz/QuizCard.jsx
frontend/src/components/quiz/FlashCard.jsx
frontend/vite.config.js
frontend/index.html
frontend/package.json
frontend/tailwind.config.js
```

### Implementation notes

**`client.js`** — axios instance with `baseURL: import.meta.env.VITE_API_URL`
(defaults to `http://localhost:8000`). Add a response interceptor that
extracts `error.response.data.detail` and throws it as a plain Error.

**`useChat.js`** — manage WebSocket lifecycle. Expose `{messages, send,
isStreaming, error}`. On send: append user message optimistically, open WS
connection to `/api/chat/stream`, accumulate token chunks into the assistant
message in-place, set sources on `done` frame, close connection.

**`useDocuments.js`** — expose `{documents, upload, uploadUrl, remove,
isUploading, progress}`. Poll `GET /api/documents` every 3 seconds while any
document has `status === "processing"`.

**Chat page** — sidebar with session list + new session button. Main area
with scrollable message thread. Each assistant message has a "Sources" toggle
that expands `SourceCard` components showing the chunk text and score.

**Upload page** — drag-and-drop zone for files + a URL input form below it.
Accepted file types: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.java`.
Show `IngestProgress` per-document with status badge (pending / processing /
ready / failed).

**KB browser** — `DocList` on the left (click to select). `ChunkViewer`
on the right shows paginated chunk cards for the selected doc. Search bar
at top calls `/api/chunks/search`.

**Quiz page** — multi-select doc list → "Generate quiz" button → loading
state → rendered `QuizCard` components (show question, hide answers until
clicked) or `FlashCard` components (flip animation).

### Acceptance criteria (manual)

- All four pages load without console errors.
- Upload a PDF → status transitions to "ready" → chunks appear in KB browser.
- Send a message in Chat → tokens stream in → sources expandable.
- Generate a quiz from an ingested doc → questions render correctly.

---

## Phase 5 — Quiz engine

**Goal:** LLM-powered MCQ and flashcard generation from selected documents.

### Files to create / modify

```
backend/quiz/schemas.py          (new)
backend/quiz/generator.py        (new)
backend/api/quiz.py              (new)
backend/tests/test_quiz.py       (new)
backend/tests/test_api.py        (extend: quiz endpoints)
```

### Implementation notes

**`schemas.py`** — Pydantic models:
```python
class MCQOption(BaseModel):
    letter: str          # "A", "B", "C", "D"
    text: str

class MCQQuestion(BaseModel):
    question: str
    options: list[MCQOption]
    correct: str         # "A" | "B" | "C" | "D"
    explanation: str

class Flashcard(BaseModel):
    front: str
    back: str

class QuizOutput(BaseModel):
    mcq: list[MCQQuestion]
    flashcards: list[Flashcard]
```

**`generator.py`** — sample up to 10 chunks randomly from the requested
doc_ids. Build a prompt asking the LLM to output a JSON object matching
`QuizOutput`. Parse and validate with Pydantic. Retry once on parse failure
with an error-correction prompt. Persist to the Quiz table.

The generation prompt must specify:
- Exactly 5 MCQ questions and 5 flashcards.
- Questions must be answerable from the provided text only.
- JSON only — no markdown fences, no preamble.

**`quiz.py` (api)**:
- `POST /api/quiz/generate` — body `{doc_ids: list[str]}`. Returns Quiz
  with parsed questions.
- `GET /api/quiz/{id}` — retrieve stored quiz.
- `GET /api/quiz` — list all quizzes (newest first).

### Acceptance criteria

```bash
pytest backend/tests/test_quiz.py -v
pytest backend/tests/test_api.py -v -k quiz
```

Quiz test must cover: successful generation (mocked LLM), malformed JSON
triggers one retry, second failure raises HTTPException 502.

# API.md — REST & WebSocket reference

Base URL: `http://localhost:8000`
All JSON requests/responses use `Content-Type: application/json`.
File uploads use `multipart/form-data`.
No authentication required.

---

## Documents

### `POST /api/ingest`

Upload a file or URL for ingestion. Returns immediately; processing runs
in the background. Poll `GET /api/documents/{id}` to check status.

**File upload (multipart)**
```
POST /api/ingest
Content-Type: multipart/form-data

file: <binary>
```

**URL ingest (JSON)**
```json
{ "url": "https://example.com/notes" }
```

**Response `202 Accepted`**
```json
{
  "doc_id": "3f8a1c...",
  "filename": "lecture-notes.pdf",
  "source_type": "pdf",
  "status": "pending"
}
```

**Errors**
- `400` — unsupported file type
- `422` — neither file nor url provided

---

### `GET /api/documents`

List all documents.

**Response `200`**
```json
[
  {
    "id": "3f8a1c...",
    "filename": "lecture-notes.pdf",
    "source_type": "pdf",
    "source_uri": "data/uploads/3f8a1c.pdf",
    "status": "ready",
    "chunk_count": 42,
    "created_at": "2025-03-17T10:00:00Z"
  }
]
```

---

### `GET /api/documents/{id}`

**Response `200`** — same shape as a single item above, plus `error_msg`
field if `status == "failed"`.

**Errors**
- `404` — document not found

---

### `DELETE /api/documents/{id}`

Delete a document and all its chunks (SQLite + ChromaDB).

**Response `204 No Content`**

**Errors**
- `404` — document not found

---

## Chunks / Knowledge Base

### `GET /api/chunks`

List chunks for a document, paginated.

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `doc_id` | string | required | Document id |
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 20 | Items per page (max 100) |

**Response `200`**
```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": "c1...",
      "doc_id": "3f8a...",
      "text": "Neural networks consist of layers...",
      "chunk_index": 0,
      "page_num": 1,
      "metadata": {}
    }
  ]
}
```

---

### `GET /api/chunks/search`

Semantic search across the full knowledge base.

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | required | Search query |
| `doc_ids` | string[] | all | Filter to specific documents |
| `limit` | int | 5 | Number of results |

**Response `200`**
```json
[
  {
    "chunk_id": "c1...",
    "doc_id": "3f8a...",
    "filename": "lecture-notes.pdf",
    "text": "Backpropagation computes gradients...",
    "score": 0.87,
    "page_num": 3
  }
]
```

---

## Chat

### `POST /api/chat`

Non-streaming single-turn Q&A.

**Request**
```json
{
  "session_id": "s1...",
  "message": "Explain backpropagation",
  "doc_ids": ["3f8a..."]   // optional; search all if omitted
}
```

**Response `200`**
```json
{
  "answer": "Backpropagation works by...",
  "sources": [
    {
      "chunk_id": "c1...",
      "text": "Backpropagation computes gradients...",
      "score": 0.91,
      "page_num": 3,
      "filename": "lecture-notes.pdf"
    }
  ],
  "message_id": "m1..."
}
```

---

### `WS /api/chat/stream`

Streaming chat over WebSocket.

**Connect:** `ws://localhost:8000/api/chat/stream`

**Send (JSON, once connected)**
```json
{
  "session_id": "s1...",
  "message": "What is gradient descent?",
  "doc_ids": ["3f8a..."]
}
```

**Receive — token frame**
```json
{ "type": "token", "text": "Gradient" }
{ "type": "token", "text": " descent" }
{ "type": "token", "text": " is..." }
```

**Receive — done frame (final)**
```json
{
  "type": "done",
  "message_id": "m2...",
  "sources": [
    {
      "chunk_id": "c2...",
      "text": "Gradient descent minimises...",
      "score": 0.93,
      "filename": "lecture-notes.pdf"
    }
  ]
}
```

**Receive — error frame**
```json
{ "type": "error", "detail": "OpenRouter API rate limit exceeded" }
```

---

### `POST /api/sessions`

Create a new chat session.

**Request**
```json
{ "title": "ML Week 3 review" }
```

**Response `201`**
```json
{ "id": "s1...", "title": "ML Week 3 review", "created_at": "..." }
```

---

### `GET /api/sessions`

List all sessions, newest first.

**Response `200`**
```json
[
  { "id": "s1...", "title": "ML Week 3 review", "created_at": "..." }
]
```

---

### `GET /api/sessions/{id}/messages`

Get full message history for a session.

**Response `200`**
```json
[
  {
    "id": "m1...",
    "role": "user",
    "content": "Explain backpropagation",
    "sources": [],
    "created_at": "..."
  },
  {
    "id": "m2...",
    "role": "assistant",
    "content": "Backpropagation works by...",
    "sources": [...],
    "created_at": "..."
  }
]
```

---

### `DELETE /api/sessions/{id}`

Delete a session and all its messages.

**Response `204 No Content`**

---

## Quiz

### `POST /api/quiz/generate`

Generate a quiz from selected documents.

**Request**
```json
{ "doc_ids": ["3f8a...", "7b2c..."] }
```

**Response `200`**
```json
{
  "id": "q1...",
  "doc_ids": ["3f8a...", "7b2c..."],
  "questions": {
    "mcq": [
      {
        "question": "What does gradient descent minimise?",
        "options": [
          { "letter": "A", "text": "Accuracy" },
          { "letter": "B", "text": "Loss function" },
          { "letter": "C", "text": "Learning rate" },
          { "letter": "D", "text": "Epoch count" }
        ],
        "correct": "B",
        "explanation": "Gradient descent iteratively adjusts weights to minimise the loss."
      }
    ],
    "flashcards": [
      { "front": "What is overfitting?", "back": "When a model memorises training data..." }
    ]
  },
  "created_at": "..."
}
```

**Errors**
- `404` — one or more doc_ids not found or not ready
- `502` — LLM returned unparseable output after retry

---

### `GET /api/quiz/{id}`

Retrieve a previously generated quiz.

**Response `200`** — same shape as generate response.

**Errors**
- `404` — quiz not found

---

### `GET /api/quiz`

List all quizzes, newest first.

**Response `200`**
```json
[
  { "id": "q1...", "doc_ids": [...], "created_at": "..." }
]
```

---

## Error response shape

All 4xx/5xx responses return:
```json
{ "detail": "Human-readable error description" }
```

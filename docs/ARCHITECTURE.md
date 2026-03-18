# ARCHITECTURE.md — System design

## Overview

RAG Learner is a local full-stack application. The browser talks to a FastAPI
backend over REST and WebSocket. The backend owns all AI logic — embedding,
retrieval, reranking, LLM calls — and persists data in two stores: ChromaDB
for vectors and SQLite for everything else.

There is no cloud infrastructure. Everything runs on the developer's machine.

## Component map

```
Browser (React + Vite)
        │
        │  REST (JSON) + WebSocket
        ▼
FastAPI backend
  ├── Ingestion pipeline
  │     ├── PDF parser        (pymupdf)
  │     ├── MD parser         (mistune)
  │     ├── URL parser        (playwright)
  │     ├── Code parser       (tree-sitter)
  │     └── Chunker           (tiktoken sliding window)
  │
  ├── RAG pipeline
  │     ├── Embedder          (sentence-transformers, singleton)
  │     ├── Vector store      (ChromaDB, local persistent)
  │     ├── Retriever         (embed → top-8 → cross-encoder → top-3)
  │     └── Prompt builder    (system + context + history assembly)
  │
  ├── LLM service
  │     ├── OpenRouter client (httpx async, streaming SSE)
  │     └── Chat history      (session buffer, persisted to SQLite)
  │
  └── Quiz service
        ├── Generator         (chunk sampling → LLM → JSON parse)
        └── Schemas           (Pydantic MCQ + Flashcard models)

Storage
  ├── ChromaDB     data/chroma_db/      vectors + chunk metadata
  ├── SQLite       data/rag_learner.db  documents, chunks, sessions, msgs
  └── Filesystem   data/uploads/        raw uploaded files
```

## Ingestion flow (write path)

```
1. User POSTs file or URL to /api/ingest
2. FastAPI creates Document row (status=pending), returns doc_id immediately
3. asyncio.create_task() kicks off IngestPipeline.run(doc_id) in background
4. Pipeline sets status=processing
5. Parser extracts text → chunker splits into ChunkData objects
6. Embedder.embed_texts() batch-encodes all chunks → 384-dim float vectors
7. VectorStore.upsert_chunks() writes to ChromaDB
8. SQLite Chunk rows written (text + metadata, no vector)
9. Document.status = ready, Document.chunk_count updated
10. On any error: status=failed, error_msg stored
```

The frontend polls GET /api/documents every 3 seconds while any document
shows status == "processing".

## Query flow (read path)

```
1. User sends message over WebSocket /api/chat/stream
2. Embedder.embed_query() → 384-dim query vector
3. VectorStore.query_chunks(vector, n=8) → 8 candidate ScoredChunk objects
4. CrossEncoder.predict([(query, chunk_text), ...]) → rerank scores
5. Keep top 3 by rerank score
6. PromptBuilder assembles:
   - System prompt (study assistant instructions)
   - Context block: [1] chunk  [2] chunk  [3] chunk
   - Last MAX_HISTORY messages from the session
7. OpenRouterClient.stream_chat() → async generator yielding token strings
8. Each token sent as {"type":"token","text":"..."} WebSocket frame
9. On completion: {"type":"done","sources":[...]} frame
10. Full answer + sources persisted to Message table
```

## Data model relationships

```
Document  ──< Chunk            (one document has many chunks)
ChatSession ──< Message         (one session has many messages)
Quiz                            (references doc_ids as JSON, standalone)
```

ChromaDB and SQLite stay in sync via doc_id. VectorStore.delete_by_doc_id()
cleans ChromaDB; the API handler deletes SQLite rows in the same request.

## Embedding model

all-MiniLM-L6-v2 produces 384-dimensional vectors. Chosen because:
- Fully local — no API cost or network dependency
- Fast: ~14k sentences/second on CPU
- ~80 MB model size
- Strong semantic similarity benchmarks for its size

Loaded once at startup as a module-level singleton in backend/rag/embedder.py.

## Reranking

Two-stage retrieval: cosine similarity (fast, bi-encoder) returns top-8
candidates, then cross-encoder (ms-marco-MiniLM-L-6-v2) reranks them by
exact relevance to the query. Cross-encoders are more accurate but too slow
to run over the full corpus — hence the two-stage approach.

## OpenRouter

Provides a unified OpenAI-compatible API. Default model is
google/gemma-3-27b-it:free. Change OPENROUTER_MODEL in .env to switch
models with no code changes. Streaming uses SSE forwarded token-by-token
to the browser over WebSocket.

## Out of scope

- Multi-user / authentication
- Cloud deployment / Docker
- Image or audio in documents
- Real-time collaboration

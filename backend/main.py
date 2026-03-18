"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import create_db_and_tables
from backend.api.documents import router as documents_router
from backend.api.chat import router as chat_router
from backend.api.quiz import router as quiz_router

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("rag_learner")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG Learner Assistant...")
    create_db_and_tables()
    logger.info("Database ready")
    asyncio.create_task(_warmup_models())
    yield
    logger.info("Shutting down.")


async def _warmup_models():
    try:
        await asyncio.to_thread(lambda: __import__('backend.rag.embedder', fromlist=['get_embedder']).get_embedder())
        logger.info("Embedding model loaded")
        await asyncio.to_thread(lambda: __import__('backend.rag.retriever', fromlist=['get_reranker']).get_reranker())
        logger.info("Reranker model loaded")
    except Exception as e:
        logger.warning("Model warmup failed: %s", e, exc_info=True)


app = FastAPI(
    title="RAG Learner Assistant",
    description="Study assistant powered by local RAG + OpenRouter",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(quiz_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

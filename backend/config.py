from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-3-27b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Embedding & reranking models
    embed_model: str = "all-MiniLM-L6-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Chunking
    chunk_size: int = 512      # tokens
    chunk_overlap: int = 64    # tokens

    # Retrieval
    top_k_retrieve: int = 8    # candidates before rerank
    top_k_final: int = 3       # chunks passed to LLM

    # Paths
    chroma_path: str = str(BASE_DIR / "data" / "chroma_db")
    upload_path: str = str(BASE_DIR / "data" / "uploads")
    db_path: str = str(BASE_DIR / "data" / "rag_learner.db")

    # App
    app_env: str = "development"
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB
    log_level: str = "INFO"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()

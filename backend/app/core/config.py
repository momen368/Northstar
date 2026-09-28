import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    app_env = os.getenv("APP_ENV", "development")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./ai_resume_analyzer.db")
    session_ttl_hours = int(os.getenv("SESSION_TTL_HOURS", "24"))
    uploads_dir = Path(os.getenv("UPLOADS_DIR", str(PROJECT_ROOT / "uploads"))).expanduser()
    max_upload_size_bytes = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
    ai_base_url = os.getenv("AI_BASE_URL", "")
    ai_model = os.getenv("AI_MODEL", "")
    ai_api_key = os.getenv("AI_API_KEY", "")
    ai_timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "45"))
    embedding_model = os.getenv("EMBEDDING_MODEL", "")
    rag_chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "700"))
    rag_chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
    rag_top_k = int(os.getenv("RAG_TOP_K", "5"))
    rag_min_similarity = float(os.getenv("RAG_MIN_SIMILARITY", "0.25"))
    knowledge_base_dir = Path(os.getenv("KNOWLEDGE_BASE_DIR", str(PROJECT_ROOT / "knowledge_base"))).expanduser()

    if not knowledge_base_dir.is_absolute():
        knowledge_base_dir = PROJECT_ROOT / knowledge_base_dir
    knowledge_base_dir = knowledge_base_dir.resolve()

    if not uploads_dir.is_absolute():
        uploads_dir = PROJECT_ROOT / uploads_dir
    uploads_dir = uploads_dir.resolve()


settings = Settings()
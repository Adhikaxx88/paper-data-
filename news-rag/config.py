"""Centralized configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://user:password@localhost:5432/newsrag")
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
GOOGLE_DRIVE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "credentials.json")
NEWS_KEYWORDS: list[str] = [
    kw.strip() for kw in os.getenv("NEWS_KEYWORDS", "pinjol,fintech,kredit digital").split(",") if kw.strip()
]

EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIM: int = 1536
LLM_MODEL: str = "gpt-4o-mini"

QDRANT_COLLECTION: str = "news_chunks"

CHUNK_SIZE_TOKENS: int = 500
CHUNK_OVERLAP_TOKENS: int = 50
MIN_CONTENT_LENGTH: int = 100

RETRIEVAL_TOP_K: int = 5
CONVERSATION_HISTORY_LIMIT: int = 10

DATA_RAW_DIR: str = os.path.join(os.path.dirname(__file__), "data", "raw")
DATA_CLEAN_DIR: str = os.path.join(os.path.dirname(__file__), "data", "clean")
DATA_CHUNKS_DIR: str = os.path.join(os.path.dirname(__file__), "data", "chunks")
DATA_PDF_DIR: str = os.path.join(os.path.dirname(__file__), "data", "pdf")

ARTICLES_PER_KEYWORD: int = 20

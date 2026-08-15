"""Centralized configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()

# OpenAI is now optional: the default local stack uses infinity-emb (BGE) for
# embeddings and Ollama for generation instead. Keep this set only if you want
# to point embedder/generator back at OpenAI-compatible endpoints.
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://user:password@localhost:5432/newsrag")
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
GOOGLE_DRIVE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "credentials.json")
NEWS_KEYWORDS: list[str] = [
    kw.strip() for kw in os.getenv("NEWS_KEYWORDS", "pinjol,fintech,kredit digital").split(",") if kw.strip()
]

# Embedding — served locally by infinity-emb (OpenAI-compatible API)
INFINITY_URL: str = os.getenv("INFINITY_URL", "http://infinity:7997")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1024"))

# Generation — served locally by Ollama (OpenAI-compatible API)
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://ollama:11434/v1")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")

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

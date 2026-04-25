"""Load configuration from the environment and sensible defaults."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

SOURCE_DOCUMENTS: Path = _ROOT / "SourceDocuments"
DATA_DIR: Path = _ROOT / "data"
MANIFEST_PATH: Path = DATA_DIR / "manifest.json"
FAISS_DIR: Path = DATA_DIR / "faiss"
FAISS_INDEX_PATH: Path = FAISS_DIR / "index.faiss"
FAISS_META_PATH: Path = FAISS_DIR / "meta.json"

MONGODB_URI: str = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017/giulia")
MISTRAL_API_KEY: str = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_EMBED_MODEL: str = os.environ.get("MISTRAL_EMBED_MODEL", "mistral-embed")
MISTRAL_CHAT_MODEL: str = os.environ.get("MISTRAL_CHAT_MODEL", "mistral-small-latest")
RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "8"))
SUPPORTED_SOURCE_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")

# Chunking: about 500 words, 20% overlap (100 words) — stride 400
CHUNK_SIZE_WORDS: int = 500
CHUNK_OVERLAP_WORDS: int = 100
CHUNK_STRIDE_WORDS: int = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS  # 400

MONGODB_CHUNKS_COLLECTION: str = "chunks"
MONGODB_DOCUMENTS_COLLECTION: str = "documents"

# Embedding API batching (Mistral accepts multiple inputs; keep requests moderate)
EMBED_BATCH_SIZE: int = 32

"""MongoDB access for document manifests and text chunks (with stored embeddings)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from . import config as cfg

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            cfg.MONGODB_URI,
            serverSelectionTimeoutMS=8000,
        )
    return _client


def get_db() -> Database:
    return get_client().get_default_database()  # URI path defines db name, e.g. /giulia


def chunks_col() -> Collection:
    return get_db()[cfg.MONGODB_CHUNKS_COLLECTION]


def documents_col() -> Collection:
    return get_db()[cfg.MONGODB_DOCUMENTS_COLLECTION]


def init_indexes() -> None:
    """Idempotent index creation for incremental ingestion and retrieval."""
    ch = chunks_col()
    ch.create_index("chunk_id", unique=True)
    ch.create_index("source_path")
    ch.create_index("faiss_id", sparse=True)
    # Facilitate "delete all for one file"
    ch.create_index(
        [("source_path", ASCENDING), ("chunk_id", ASCENDING)]
    )
    doc = documents_col()
    doc.create_index("source_path", unique=True)


def delete_chunks_for_path(source_path: str) -> int:
    r = chunks_col().delete_many({"source_path": source_path})
    return r.deleted_count


def upsert_document_record(
    source_path: str, file_hash: str, status: str = "indexed"
) -> None:
    now = datetime.now(timezone.utc)
    documents_col().update_one(
        {"source_path": source_path},
        {
            "$set": {
                "file_hash": file_hash,
                "last_processed": now,
                "status": status,
            }
        },
        upsert=True,
    )


def remove_document_record(source_path: str) -> None:
    documents_col().delete_one({"source_path": source_path})


def insert_chunk_docs(docs: List[Dict[str, Any]]) -> None:
    if docs:
        chunks_col().insert_many(docs)


def fetch_chunks_by_ids(
    chunk_ids: List[str],
) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []
    cur = chunks_col().find({"chunk_id": {"$in": chunk_ids}})
    by = {c["chunk_id"]: c for c in cur}
    return [by[c] for c in chunk_ids if c in by]

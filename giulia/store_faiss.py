"""Persist a FAISS index (inner product on L2-normalised vectors) alongside Mongo."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

import faiss
import numpy as np
from pymongo import UpdateOne

from . import config as cfg
from . import store_mongo


def _l2_row_normalise(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (mat / norms).astype("float32")


def rebuild_faiss_from_mongo() -> int:
    """
    Rebuild the FAISS store from all chunk documents with embeddings, assign
    `faiss_id` 0..N-1 in `chunks`, and write `index.faiss` and `meta.json`.
    """
    col = store_mongo.chunks_col()
    store_mongo.init_indexes()
    # Drop previous faiss_id values so a clean mapping is used
    col.update_many(
        {"faiss_id": {"$exists": True}},
        {"$unset": {"faiss_id": ""}},
    )
    docs = list(
        col.find({"embedding": {"$exists": True}}, {"chunk_id": 1, "embedding": 1}).sort(
            "chunk_id", 1
        )
    )
    if not docs:
        cfg.FAISS_DIR.mkdir(parents=True, exist_ok=True)
        if cfg.FAISS_INDEX_PATH.exists():
            cfg.FAISS_INDEX_PATH.unlink()
        with open(cfg.FAISS_META_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "dim": 0,
                    "n_vectors": 0,
                    "chunk_id_order": [],
                },
                f,
                indent=2,
            )
        return 0
    dim = len(docs[0]["embedding"])
    n = len(docs)
    xb = np.zeros((n, dim), dtype="float32")
    chunk_order: list[str] = []
    for i, d in enumerate(docs):
        e = np.array(d["embedding"], dtype="float32")
        xb[i] = e
        chunk_order.append(d["chunk_id"])
    xb = _l2_row_normalise(xb)
    # Inner product = cosine for unit vectors
    index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))
    faiss_ids = np.arange(n, dtype="int64")
    index.add_with_ids(xb, faiss_ids)

    ops = []
    for i, cid in enumerate(chunk_order):
        ops.append(
            UpdateOne(
                {"chunk_id": cid},
                {"$set": {"faiss_id": int(i)}},
            )
        )
    if ops:
        col.bulk_write(ops, ordered=False)
    _save_index(index, dim, chunk_order, n)
    return n


def _save_index(
    index: faiss.Index, dim: int, chunk_id_order: list[str], n_vectors: int
) -> None:
    cfg.FAISS_DIR.mkdir(parents=True, exist_ok=True)
    # Persist the full index (IndexIDMap wraps a flat index)
    faiss.write_index(index, str(cfg.FAISS_INDEX_PATH))
    with open(cfg.FAISS_META_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "dim": dim,
                "n_vectors": n_vectors,
                "chunk_id_order": chunk_id_order,
            },
            f,
            indent=2,
        )


def load_faiss_index() -> faiss.Index:
    return faiss.read_index(str(cfg.FAISS_INDEX_PATH))


def try_load_index() -> Optional[faiss.Index]:
    if not cfg.FAISS_INDEX_PATH.is_file():
        return None
    return load_faiss_index()


def search(
    query_vector: np.ndarray, top_k: int, index: faiss.Index
) -> Tuple[np.ndarray, np.ndarray]:
    """
    `query_vector` is shape (1, d), L2-normalised. Returns (distances, faiss_ids).
    """
    q = query_vector.astype("float32")
    if q.ndim == 1:
        q = q.reshape(1, -1)
    q = _l2_row_normalise(q)
    d, i = index.search(q, int(top_k))
    return d, i



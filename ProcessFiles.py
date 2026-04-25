#!/usr/bin/env python3
"""
Scan `SourceDocuments/` for supported files (.pdf, .docx, .txt), chunk and
embed with Mistral, store in MongoDB, then rebuild the local FAISS index.
Re-run safely: only new or changed files are re-embedded; removed files are
dropped; unchanged files are skipped.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from mistralai import Mistral

from giulia import config as cfg
from giulia.chunking import TextChunk, chunk_text_with_page_labels
from giulia import embeddings as emb
from giulia import source_extract
from giulia import store_faiss
from giulia import store_mongo

_MANIFEST_KEY = "paths"


def _sha256_file(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> Dict[str, str]:
    if not cfg.MANIFEST_PATH.is_file():
        return {}
    try:
        with open(cfg.MANIFEST_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in (data.get(_MANIFEST_KEY) or {}).items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest(paths: Dict[str, str]) -> None:
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        _MANIFEST_KEY: dict(sorted(paths.items())),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(cfg.MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _list_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in cfg.SUPPORTED_SOURCE_EXTENSIONS:
            files.append(p)
    return sorted(files)


def _rel_key(root: Path, p: Path) -> str:
    return str(p.resolve().relative_to(root.resolve()))


def _process_one_file(
    rel_path: str, abs_path: Path, file_hash: str, client: Mistral
) -> int:
    """Re-chunk and insert chunks for a single (new or changed) source file."""
    extracted = source_extract.extract_source_words(abs_path)
    cks: list[TextChunk] = chunk_text_with_page_labels(
        extracted.words,
        extracted.locations,
        rel_path,
        file_hash,
    )
    if not cks:
        print(f"  No text extracted, skipping: {rel_path}", file=sys.stderr)
        return 0
    to_insert: list[dict[str, Any]] = []
    mat = emb.embed_texts(client, [c.text for c in cks], normalise=True)
    now = datetime.now(timezone.utc)
    for i, ch in enumerate(cks):
        row = mat[i]
        to_insert.append(
            {
                "chunk_id": ch.chunk_id,
                "source_path": rel_path,
                "source_hash": file_hash,
                "chunk_index": ch.chunk_index,
                "text": ch.text,
                "page_start": ch.page_start,
                "page_end": ch.page_end,
                "source_type": extracted.source_type,
                "location_type": extracted.location_type,
                "location_start": ch.page_start,
                "location_end": ch.page_end,
                "embedding": row.tolist(),
                "created_at": now,
            }
        )
    if to_insert:
        store_mongo.insert_chunk_docs(to_insert)
    print(
        f"  Ingested {len(to_insert)} chunk(s) from: {rel_path}",
        file=sys.stderr,
    )
    return len(to_insert)


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not dry and not cfg.MISTRAL_API_KEY:
        print(
            "MISTRAL_API_KEY is not set. Copy .env.example to .env and add your key "
            "(or use --dry-run to list changes only).",
            file=sys.stderr,
        )
        return 1
    cfg.SOURCE_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    source_files = _list_source_files(cfg.SOURCE_DOCUMENTS)
    current: dict[str, str] = {}
    for p in source_files:
        key = _rel_key(cfg.SOURCE_DOCUMENTS, p)
        current[key] = _sha256_file(p)

    to_refresh: list[Path] = [
        p
        for p in source_files
        if current[_rel_key(cfg.SOURCE_DOCUMENTS, p)]
        != manifest.get(_rel_key(cfg.SOURCE_DOCUMENTS, p))
    ]

    removed = set(manifest) - set(current)
    if dry:
        for path in sorted(removed):
            print(
                f"[dry-run] Would remove chunks and document row for: {path}",
                file=sys.stderr,
            )
        for p in to_refresh:
            k = _rel_key(cfg.SOURCE_DOCUMENTS, p)
            ch = "changed" if k in manifest else "new"
            print(f"[dry-run] Would ingest ({ch}): {k}", file=sys.stderr)
        if removed or to_refresh:
            print(
                "Dry run only; no changes written (no MongoDB or API calls).",
                file=sys.stderr,
            )
        else:
            print("Dry run: nothing to do.", file=sys.stderr)
        return 0

    store_mongo.init_indexes()
    for path in sorted(removed):
        n = store_mongo.delete_chunks_for_path(path)
        store_mongo.remove_document_record(path)
        print(
            f"Removed {n} chunk(s) for missing file: {path}",
            file=sys.stderr,
        )

    client: Optional[Mistral] = None
    client = emb.get_client()
    if to_refresh and client is not None:
        for p in to_refresh:
            k = _rel_key(cfg.SOURCE_DOCUMENTS, p)
            h = current[k]
            if k in manifest:
                store_mongo.delete_chunks_for_path(k)
            _process_one_file(k, p, h, client)
            store_mongo.upsert_document_record(k, h)

    new_manifest = {k: current[k] for k in current}
    _save_manifest(new_manifest)

    if to_refresh or removed:
        n_vec = store_faiss.rebuild_faiss_from_mongo()
        print(f"FAISS index rebuilt: {n_vec} vector(s).", file=sys.stderr)
    else:
        print(
            "No new, changed, or removed source files. Manifest is up to date.",
            file=sys.stderr,
        )
        if not cfg.FAISS_INDEX_PATH.is_file():
            cl = list(store_mongo.chunks_col().find({}, {"_id": 1}).limit(1))
            if cl:
                n_vec = store_faiss.rebuild_faiss_from_mongo()
                if n_vec:
                    print(
                        f"Rebuilt missing FAISS index: {n_vec} vector(s).",
                        file=sys.stderr,
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

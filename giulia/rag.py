"""RAG: retrieve with FAISS, enrich from Mongo, answer with Mistral chat only."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import List, Optional, Union

from mistralai import Mistral
from mistralai.models import SystemMessage, UserMessage

from . import config as cfg
from . import embeddings as emb
from . import store_faiss
from . import store_mongo

SYSTEM_RAG = (
    "You are Giulia, a helpful assistant. Answer only using the numbered context "
    "excerpts below. If the answer is not in the context, say you do not have "
    "enough information in the indexed documents. Cite which context numbers you "
    "use (e.g. [1], [2]) and, when you cite, mention the file name and location "
    "for that excerpt in the same sentence if possible. Use UK English spelling in "
    "your answers."
)


@dataclass
class SourceRef:
    label: int
    chunk_id: str
    source_path: str
    location_type: str
    location_start: int
    location_end: int
    preview: str


@dataclass
class RAGResult:
    answer: str
    sources: list[SourceRef]
    top_k: int


def _load_meta() -> dict:
    with open(cfg.FAISS_META_PATH, encoding="utf-8") as f:
        return json.load(f)


def _assistant_content_to_str(content: Union[str, list, None]) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    out: list[str] = []
    for part in content:
        t = getattr(part, "text", None)
        if t:
            out.append(t)
    return "".join(out)


def retrieve(
    client: Mistral, question: str, top_k: int
) -> tuple[list[SourceRef], str]:
    """
    Return rich source list and a formatted context string for the prompt
    (numbered blocks).
    """
    index = store_faiss.try_load_index()
    if index is None or not cfg.FAISS_META_PATH.is_file():
        raise FileNotFoundError(
            "FAISS index is missing. Run `python ProcessFiles.py` after starting MongoDB."
        )
    meta = _load_meta()
    if not meta.get("n_vectors", 0):
        raise FileNotFoundError(
            "The FAISS index is empty. Ingest some source files first."
        )
    qv = emb.embed_query(client, question)
    _, ids = store_faiss.search(qv, top_k, index)
    faiss_row = ids[0].tolist() if ids is not None else []
    ch_ids: list[Optional[str]] = []
    for rid in faiss_row:
        if rid is None or (isinstance(rid, float) and math.isnan(rid)):
            ch_ids.append(None)
            continue
        if isinstance(rid, (int, float)) and int(rid) < 0:
            ch_ids.append(None)
            continue
        i = int(rid)
        order: list = list(meta.get("chunk_id_order", []))
        if 0 <= i < len(order):
            ch_ids.append(order[i])
        else:
            ch_ids.append(None)
    ch_ids = [c for c in ch_ids if c is not None]
    seen: set = set()
    ch_ids_unique: list = []
    for c in ch_ids:
        if c not in seen:
            seen.add(c)
            ch_ids_unique.append(c)
    rows = store_mongo.fetch_chunks_by_ids(ch_ids_unique)
    sources: list[SourceRef] = []
    context_lines: list[str] = []
    for n, r in enumerate(rows, start=1):
        sp = r.get("source_path", "unknown")
        loc_type = str(r.get("location_type", "page"))
        p0 = int(r.get("location_start", r.get("page_start", 0)))
        p1 = int(r.get("location_end", r.get("page_end", 0)))
        text = (r.get("text") or "").strip()
        preview = text[:280] + ("…" if len(text) > 280 else "")
        sources.append(
            SourceRef(
                label=n,
                chunk_id=r.get("chunk_id", ""),
                source_path=sp,
                location_type=loc_type,
                location_start=p0,
                location_end=p1,
                preview=preview,
            )
        )
        base = os.path.basename(sp) if sp else "unknown"
        label = _format_location_label(loc_type, p0, p1)
        context_lines.append(
            f"[{n}] (source file: {base}, {label}):\n{text}\n"
        )
    return sources, "\n\n".join(context_lines)


def _format_location_label(location_type: str, start: int, end: int) -> str:
    plural = {
        "page": "pages",
        "line": "lines",
        "paragraph": "paragraphs",
    }.get(location_type, "locations")
    return f"{plural} {start}–{end}"


def answer_question(
    user_message: str,
    top_k: Optional[int] = None,
) -> RAGResult:
    k = int(top_k or cfg.RAG_TOP_K)
    client: Mistral = emb.get_client()
    sources, context_block = retrieve(client, user_message, k)
    if not context_block:
        return RAGResult(
            answer=(
                "I do not have any indexed documents to search. Add source files to "
                "`SourceDocuments/`, then run `python ProcessFiles.py` while MongoDB is running."
            ),
            sources=[],
            top_k=k,
        )
    user_block = f"Question: {user_message}\n\nContext:\n{context_block}"
    messages: list = [
        SystemMessage(content=SYSTEM_RAG),
        UserMessage(content=user_block),
    ]
    chat = client.chat.complete(
        model=cfg.MISTRAL_CHAT_MODEL,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.2,
    )
    if not chat or not chat.choices:
        return RAGResult(answer="No response from the model.", sources=sources, top_k=k)
    content = chat.choices[0].message.content  # type: ignore[union-attr, index]
    text = _assistant_content_to_str(content)
    return RAGResult(answer=text.strip(), sources=sources, top_k=k)

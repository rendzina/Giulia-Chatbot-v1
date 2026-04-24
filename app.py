"""
Giulia: Chainlit RAG web UI. Retrieval from Mongo + FAISS, answers via Mistral chat API only.
Run: chainlit run app.py
"""

from __future__ import annotations

import os
import re

import chainlit as cl

from giulia import config as cfg
from giulia.rag import RAGResult, answer_question


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "I am **Giulia** (v1). I answer from the documents you indexed with "
            "`ProcessFiles.py`, with source references from the context I retrieve."
        )
    ).send()
    if not cfg.MISTRAL_API_KEY:
        await cl.Message(
            content=(
                "Set `MISTRAL_API_KEY` in your `.env` at the project root, then restart."
            ),
        ).send()


def _sources_block(result: RAGResult) -> str:
    if not result.sources:
        return ""
    lines: list[str] = ["\n\n---\n**Sources (retrieved)**\n"]
    for s in result.sources:
        name = os.path.basename(s.source_path) if s.source_path else "unknown"
        preview = re.sub(r"\s+", " ", s.preview)
        lines.append(
            f"- **[{s.label}]** `{name}` — pages {s.page_start}–{s.page_end}: {preview}\n"
        )
    return "".join(lines)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = (message.content or "").strip()
    if not text:
        return
    try:
        result = answer_question(text, top_k=cfg.RAG_TOP_K)
    except (FileNotFoundError, RuntimeError) as e:
        await cl.Message(author="Giulia", content=str(e)).send()
        return
    out = result.answer + _sources_block(result)
    await cl.Message(author="Giulia", content=out).send()

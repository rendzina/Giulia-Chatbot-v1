# Source documents

Place **PDF** files in this directory (including subfolders). The ingestion
script `ProcessFiles.py` reads every `*.pdf` recursively, extracts text, chunks
it, and indexes it in MongoDB and the local FAISS store.

**Do not** commit private PDFs to git unless your policy allows it. This folder
can hold a `.gitkeep` only, with your PDFs listed in `.gitignore` if you prefer.

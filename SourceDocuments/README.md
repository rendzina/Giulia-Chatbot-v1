# Source documents

Place supported source files in this directory (including subfolders):

- `*.pdf`
- `*.docx`
- `*.txt`

The ingestion script `ProcessFiles.py` reads supported files recursively,
extracts text, chunks it, and indexes it in MongoDB and the local FAISS store.

**Do not** commit private source files to git unless your policy allows it. This folder
can hold a `.gitkeep` only, with your source files listed in `.gitignore` if you prefer.

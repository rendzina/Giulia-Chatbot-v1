# OCR PDF pre-processing workflow (batch)

**Issue:** Some PDF files contain images containing a lot of useful text. Without conversion the chunking process will miss this and so the PDFs can be pre-processed with an OCR workflow to extract and embed the text in the pdf file. The wider workflow is not affected.

**Purpose:** Process scanned or image-heavy PDFs *before* Giulia’s ingestion, so
`SourceDocuments` contains “searchable” PDFs with a text layer. Giulia’s
`ProcessFiles.py` reads text via normal PDF extraction; it does not run OCR
itself. 

**Created:** 24-04-2026 (UK style).

## Credits

Professor Stephen Hallett, Cranfield University, 2026

---

## Principles

- **Do not** overwrite or delete originals in place—keep a clear **incoming**
  vs **OCR output** split.
- **Never** add failed partial outputs to `SourceDocuments/`.
- **Idempotent** naming: re-runs of the same input should produce the same
  target names (or a obvious version suffix).
- **Log** each file: success, skip (already has text), or failure.

---

## Recommended folder layout

Create these alongside the project root (or inside the project if you prefer),
so paths stay predictable:

| Path | Role |
|------|------|
| `IncomingScans/` | **Read-only** drop zone for raw PDFs from users or other systems. |
| `OCR_Processing/` | (Optional) scratch space, temp files, or lock files. |
| `OCR_Output/` | **Searchable** PDFs produced by OCR. |
| `OCR_Failed/` | PDFs (or metadata) for items that need manual review. |
| `OCR_Archive/` | (Optional) originals after a successful run, for traceability. |
| `SourceDocuments/` | **Only** content you want **indexed** by `ProcessFiles.py` (manually copy files there) |

> **Tip:** If these directories hold private or very large data, add them to
> `.gitignore` (or use storage outside the repo) so you do not commit them.

---

## File naming (safe at scale)

Use a stable pattern so batches do not overwrite each other:

- **Input:** `report-2026-04-25.pdf`
- **OCR output:** `report-2026-04-25.ocr.pdf`

If the same name might recur, append a source id:

- `report-2026-04-25_acme-001.ocr.pdf`

---

## Step 1 — Ingest to `IncomingScans/`

- Copy or move new PDFs into `IncomingScans/`.
- Avoid editing PDFs in this folder by hand; treat it as a queue.

---

## Step 2 — Batch OCR (OCRmypdf + Tesseract)

**Tooling:** [OCRmyPDF](https://ocrmypdf.readthedocs.io/) (wraps
[Tesseract](https://github.com/tesseract-ocr/tesseract) and produces a
“searchable” PDF, usually keeping the page images and adding a text layer).

**Example (per file, English):**

```bash
ocrmypdf --skip-text --language eng "IncomingScans/report.pdf" "OCR_Output/report.ocr.pdf"
```

| Flag / option | When to use |
|---------------|-------------|
| `--skip-text` | **Default** for batching: only OCRs pages (or files) with little or no extractable text; avoids damaging PDFs that already have a good text layer. |
| `--force-ocr` | Only when you *know* the existing “text” is wrong or you must re-OCR everything (slower, can harm quality on mixed files). |
| `--language` | e.g. `eng`, `deu`, `fra`, or `eng+deu` if you installed multiple traineddata packs. |
| `--rotate-pages` / `--deskew` | If scans are crooked; experiment on a few files first. |

**Batch pattern (Bash, illustrative):**

```bash
set -euo pipefail
mkdir -p "OCR_Output" "OCR_Failed" "OCR_Processing/Logs"
for f in IncomingScans/*.pdf; do
  base=$(basename "$f" .pdf)
  out="OCR_Output/${base}.ocr.pdf"
  log="OCR_Processing/Logs/${base}.log"
  if ocrmypdf --skip-text --language eng "$f" "$out" 2> >(tee "$log" >&2); then
    echo "OK: $f -> $out" >> "OCR_Processing/Logs/batch-summary.log"
  else
    echo "FAIL: $f" >> "OCR_Processing/Logs/batch-summary.log"
    mv "$f" "OCR_Failed/" 2>/dev/null || true
  fi
done
```

---

## Step 3 — Quality gate (before `SourceDocuments/`)

Before promoting a file, quickly verify:

- **File exists** and is non-trivial in size.
- **Log** shows no hard error (OCRmypdf exit code 0).
- **Spot check:** open the PDF; select or search text. If you cannot select text,
  the layer is missing and Giulia will still not index useful content.

**Optional:** for a stricter check, use your OS tools or a tiny Python snippet
to extract a page of text and confirm it is not empty.

If the output is poor (wrong language, table chaos), re-run with different
Tesseract language or preprocessing (deskew, image dpi) for that file only.

---

## Step 4 — Promote to `SourceDocuments/`

When satisfied:

- **Copy** (or move) the approved `*.ocr.pdf` from `OCR_Output/` into
  `SourceDocuments/` (you may keep a flat tree or use subfolders—Giulia scans
  recursively).

- Run ingestion:

```bash
source .venv/bin/activate
python ProcessFiles.py
```

If some PDFs in `SourceDocuments` were *not* from OCR, `--skip-text` in step 2
keeps you from double-OCRing files that already extract well.

---

## Step 5 — Aftermath and hygiene

- Move processed originals from `IncomingScans/` to `OCR_Archive/` with the
  same base name, or to dated subfolders, e.g. `OCR_Archive/2026-04-25/`.
- **Do not** delete the original until the OCR version is in `SourceDocuments/`
  and a successful `ProcessFiles` run is confirmed (stderr shows ingest counts).
- Truncate or rotate `OCR_Processing/Logs` periodically in long-running
  production.

---

## Relating to Giulia

- **Not indexed:** `IncomingScans/`, `OCR_Output/`, and similar folders, until
  you place files (or their approved copies) under `SourceDocuments/`.
- **Indexed:** only paths under `SourceDocuments/` (see
  `SourceDocuments/README.md` and the main `README.md`).
- **Ingestion model:** new or changed file bytes → re-chunk/embedding; unchanged
  files skipped (per-file hash in `data/manifest.json`).

---

## Optional: automation

For repeatable use, wrap the Bash loop in `scripts/ocr_incoming.sh` and add
`--dry-run` to list work without writing. Keep logs under `OCR_Processing/Logs/`
and a single `batch-summary.log` for audits.

This workflow keeps OCR concerns **outside** the Python RAG app while giving
`ProcessFiles.py` the cleanest possible PDF inputs.

# OCR PDF pre-processing workflow (batch)

Some PDFs are image-heavy and contain little or no direct extractable text, However they have text in images in the file. In that case, run OCR before ingestion so `ProcessFiles.py` can chunk meaningful text. By default if a given page already has (OCR) text on it, it is not processed by this tool - see command line switches.

**Created:** 25-04-2026 (UK style).  
**Credits:** Professor Stephen Hallett, Cranfield University, 2026.

---

## Scope

This workflow covers the folders and script under `PDFPreProcessing/`:

- `IncomingScans/`
- `OCR_Output/`
- `OCR_Failed/`
- `OCR_Processing/Logs/`
- `preprocess.sh`

Only approved OCR outputs should be copied to `SourceDocuments/` for indexing.

---

## Principles

- Keep originals separate from OCR outputs.
- Never index partial/failed OCR results.
- Use deterministic file naming (`<name>.ocr.pdf`).
- Keep per-file logs and a batch summary log.

---

## Folder roles

| Path | Role |
|------|------|
| `PDFPreProcessing/IncomingScans/` | Raw PDF queue (input only) |
| `PDFPreProcessing/OCR_Output/` | OCR-generated searchable PDFs |
| `PDFPreProcessing/OCR_Failed/` | Files that failed OCR and need manual review |
| `PDFPreProcessing/OCR_Processing/Logs/` | Per-file logs plus batch summary |
| `SourceDocuments/` | Files to be indexed by Giulia |

---

## Running the batch

From the `PDFPreProcessing/` directory:

```bash
bash preprocess.sh
```

The script currently uses:

```bash
ocrmypdf --force-ocr --language eng
```

This forces OCR even if text is already present. If you want a safer
mixed-quality default, switch to `--skip-text`.

---

## Expected outputs

For each `IncomingScans/<name>.pdf`, expect:

- `OCR_Output/<name>.ocr.pdf`
- `OCR_Processing/Logs/<name>.log`
- `OCR_Processing/Logs/batch-summary.log` entry:
  - `OK: ...` on success
  - `FAIL: ...` on failure

Failed files are moved to `OCR_Failed/` by the script.

---

## Quality gate before indexing

Before copying files to `SourceDocuments/`, check:

1. Output PDF exists and is non-empty.
2. Log has no hard OCR errors.
3. PDF allows text selection/search on expected pages.

If quality is poor, re-run that file with adjusted OCR options (`--language`,
`--deskew`, etc.).

---

## Promotion to `SourceDocuments/`

When approved, copy OCR outputs into `SourceDocuments/`, then run:

```bash
source .venv/bin/activate
python ProcessFiles.py
```

Use `python ProcessFiles.py --dry-run` first to preview what would be updated.

---

## How this interacts with Giulia ingestion

- `ProcessFiles.py` hashes each file and only reprocesses changed/new files.
- If an OCR update changes the PDF bytes, old chunks for that file path are
  removed and the file is re-chunked.
- Unchanged files are skipped.

---

## Operational notes

- Keep private OCR folders outside version control where appropriate.
- Archive processed originals if retention policy requires it.
- Rotate logs periodically for long-running operations.

# Process files

## Credits

Professor Stephen Hallett, Cranfield University, 2026.

# Source documents

Place supported source files in this directory (including subfolders):

- `*.pdf`
- `*.docx`
- `*.txt`

`ProcessFiles.py` scans this folder recursively and ingests matching files.

For image-heavy/scanned PDFs, run OCR first and only copy approved `.ocr.pdf`
files into this folder. See [`OCR_PDF_PreProcessingWorkflow.md`](../OCR_PDF_PreProcessingWorkflow.md).

**Do not** commit private source files unless your policy allows it.

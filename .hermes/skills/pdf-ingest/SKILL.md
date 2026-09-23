---
name: pdf-ingest
description: First stage for PDF case questions. Render pages, prefer native PDF text per page, fall back to PaddleOCR for scanned/low-text pages, normalize all text bboxes into rendered-image pixel coordinates, validate the ingest bundle, then hand off to document-layout.
---

# PDF Ingest

Pipeline:

`pdf-ingest → document-layout → document-structure → case-record-structure → grounded-case-qa`

This skill extracts source text only. It must not infer document hierarchy or case semantics.

## Stage 1/5: adaptive ingest

Display: **“Stage 1/5: Building or validating normalized PDF pages.”**

1. Run the locator first:
   `.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf`
2. If it returns a later skill, execute that skill directly.
3. Otherwise run:
   `.venv/bin/python .hermes/skills/pdf-ingest/scripts/ingest_pdf.py INPUT.pdf`
4. Validate:
   `.venv/bin/python .hermes/skills/pdf-ingest/scripts/validate_ingest_bundle.py CASE_DIR`

Per physical page the ingest helper:
- renders a 200 DPI PNG;
- tries PyMuPDF native text first;
- uses PaddleOCR PP-OCRv6 only when native text is insufficient;
- converts every block bbox to the rendered-page pixel coordinate system;
- preserves extraction method, confidence, uncertainty and verification state.

Outputs:
- `page/`: rendered PNGs
- `normalized/page-NNN.json`: normalized source text blocks
- `job.json`, `manifest.json`

See `references/page-schema.md`.

## Mandatory handoff

Unless the user explicitly requested only text extraction:

1. Display **“Stage 1/5 complete; proceeding to document layout analysis.”**
2. Load `document-layout`.
3. Pass the canonical case directory and original question.

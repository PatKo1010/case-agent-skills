---
name: pdf-scan-ingest
description: First stage for PDF case questions. Produce or validate normalized per-page source text using native PDF text when available and PaddleOCR only as a page-level fallback. Preserve page/bbox/confidence/verification, then continue to document-structure.
---

# Adaptive PDF Ingest

## Execution contract

Pipeline:

`pdf-scan-ingest → document-structure → case-record-structure → grounded-case-qa`

This stage answers only: **what text/layout evidence is present on each physical page?**

It must not infer case entities, events, guilt, intent or evidentiary meaning.

## Locate before processing

Run:

`.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/locate_case.py INPUT.pdf`

If it returns a later skill, load that skill directly. Otherwise perform Stage 1.

The canonical directory is `output_<full PDF SHA-256>/`.

## Stage 1/4: Adaptive ingest

Display: **“Stage 1/4: Checking or extracting normalized PDF pages.”**

Run:

`.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py INPUT.pdf`

The helper operates **per page**:

1. Render the physical page for provenance/visual verification.
2. Try PyMuPDF native text extraction.
3. If the page has enough visible native text, store it as `extraction_method: native_text`.
4. Otherwise lazy-load PaddleOCR PP-OCRv6 and store `extraction_method: paddleocr`.
5. Preserve page number, text blocks, bbox, confidence, uncertainty and verification status.

This allows mixed PDFs: digital pages do not incur OCR error/cost, while scanned pages still receive OCR.

Require success from:

`.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py CASE_DIR`

The directory remains named `ocr/` for backward compatibility, but its JSON files are now normalized page artifacts and may come from either native extraction or OCR.

## Verification rules

- Native text is not automatically visually verified.
- Paddle confidence measures recognition confidence, not factual truth.
- Important names, dates, amounts and identifiers should be checked against the rendered page when ambiguity matters.
- Corrections to `corrected_text` require visual verification, correction metadata and a note.
- Keep uncertain layout for the next stage rather than forcing semantic labels here.

## Mandatory handoff

Unless the user explicitly requested only text/OCR export:

1. Display: **“Stage 1/4 complete; proceeding to lightweight document structure.”**
2. Load `document-structure`.
3. Pass the canonical case directory and original question.

---
name: document-structure
description: Required second stage for PDF case questions after pdf-scan-ingest. Convert validated page text/OCR into a lightweight document map with document boundaries, titles, pages and conservative block types (title, narrative, table, qa). Preserve bbox/confidence/source links, validate the structure, then hand off to case-record-structure.
---

# Lightweight Document Structure

## Purpose

This stage describes **how the case bundle is organized** before semantic case extraction. It must not decide guilt, intent, causation, entities, events or evidentiary meaning.

Pipeline:

`pdf-scan-ingest → document-structure → case-record-structure → grounded-case-qa`

Use deterministic Python classification first. Hermes may inspect uncertain boundaries or blocks, but it must not silently rewrite low-confidence structure without source evidence.

## Stage 2/4: Build or reuse document structure

Display: **“Stage 2/4: Building or validating lightweight document structure.”**

Use the canonical case output root as `CASE_DIR` and `CASE_DIR/structure` as `STRUCTURE_DIR`.

1. Validate ingest artifacts:
   `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py CASE_DIR`
2. Reuse an existing structure only if:
   `.venv/bin/python .hermes/skills/document-structure/scripts/validate_document_structure.py STRUCTURE_DIR --case-dir CASE_DIR`
   succeeds.
3. Otherwise build it:
   `.venv/bin/python .hermes/skills/document-structure/scripts/build_document_structure.py CASE_DIR`
4. Validate again. Do not continue on invalid or stale structure.
5. For low-confidence document boundaries or block classifications, inspect the cited page image/OCR before semantic extraction. Preserve uncertainty rather than forcing a confident label.

## Outputs

`structure/` contains:

- `pages.jsonl`: one row per physical page.
- `documents.jsonl`: inferred document spans inside the case bundle.
- `blocks.jsonl`: source-grounded blocks with `document_id`, page, type, bbox and confidence.
- `structure_manifest.json`: source fingerprint and file hashes.

Allowed block types are intentionally small:

- `title`
- `narrative`
- `table`
- `qa`

This is a **lightweight** structural layer. Do not add full RAG, embeddings, figure graphs or deep TOC hierarchy unless the task demonstrates a need.

See `references/structure-schema.md`.

## Mandatory handoff

After validation succeeds:

1. Display: **“Stage 2/4 complete; proceeding to case semantic indexing.”**
2. Load `case-record-structure`.
3. Pass the original question, `CASE_DIR`, and `STRUCTURE_DIR`.
4. The semantic stage should read `structure/*.jsonl` first and use raw OCR/page images only for verification or missing context.

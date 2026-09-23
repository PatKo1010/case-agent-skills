---
name: case-record-structure
description: Required third stage for PDF case questions after document-structure. Build or validate semantic case indexes (documents, entities, events, evidence) from the validated lightweight document structure, while grounding every claim back to current source pages.
---

# Case Record Structure

## Stage 3/4: Build or reuse semantic case indexes

The current Hermes agent performs semantic extraction using the current conversation and model. Keep the original question plus the canonical case directory from previous stages.

Use:
- `CASE_DIR = output_<SHA256>`
- `STRUCTURE_DIR = CASE_DIR/structure`
- `RECORD_DIR = CASE_DIR/records`

Display: **“Stage 3/4: Building or validating case semantic indexes.”**

1. Validate ingest:
   `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py CASE_DIR`
2. Validate document structure:
   `.venv/bin/python .hermes/skills/document-structure/scripts/validate_document_structure.py STRUCTURE_DIR --case-dir CASE_DIR`
3. Reuse existing records only when:
   `.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir CASE_DIR`
   succeeds.
4. If rebuilding, capture the source fingerprint:
   `.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py --ocr-dir CASE_DIR --fingerprint`
5. Read `STRUCTURE_DIR/documents.jsonl`, `pages.jsonl`, and `blocks.jsonl` first. Use these as the navigation layer. Read raw page JSON or page images second for:
   - exact quote verification
   - low-confidence structure
   - ambiguous OCR
   - details omitted by lightweight blocks
6. Extract the whole case semantic index, not only the answer to the current question.
7. Seal and validate records against the same source fingerprint.

The important boundary is:

```
document-structure
= what the document looks like

case-record-structure
= what the document means for the case
```

Do not redo document boundary detection or table-vs-Q&A classification from scratch unless the structure is explicitly low-confidence or invalid.

## Outputs

- `documents.jsonl`: semantic document records and roles in the case
- `entities.jsonl`: people, organizations, accounts, places and identifiers
- `events.jsonl`: date/time, actor, action, object, amount and place
- `evidence.jsonl`: exhibit/source/status records
- `case_summary.md`: neutral case summary with page citations
- `index_manifest.json`: generated source binding

Every JSONL row requires `id`, `kind`, `attributes`, `source_pages`, `source_quote`, `confidence`, and `verification`.

Preserve contradictions as separate records and link with `conflicts_with`. Merge aliases only with explicit support. Keep original dates and units. A source quote must occur verbatim on at least one cited current page.

## Source hierarchy

Prefer evidence in this order:

1. validated semantic record
2. validated structural block
3. normalized page text
4. page image for visual verification

A structural label is navigation metadata, not evidence of a semantic conclusion.

## Mandatory handoff

After valid indexes are available:

1. Display: **“Stage 3/4 complete; proceeding to source-grounded case QA.”**
2. Load `grounded-case-qa`.
3. Pass `CASE_DIR`, `STRUCTURE_DIR`, `RECORD_DIR`, the original question, and unresolved uncertainties.

Stop after this stage only when the user explicitly asked for semantic indexes rather than an answer.

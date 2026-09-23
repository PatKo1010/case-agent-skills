---
name: case-record-structure
description: Optional semantic indexing only when the user explicitly requests case indexes. Not a prerequisite for PDF questions. Build semantic case records from validated document hierarchy; use normalized pages and page images only for source verification.
---

# Case Record Structure

Default pipeline: `pdf-ingest → document-layout → document-structure → grounded-case-qa`.

This skill is outside the default pipeline. Run it only for an explicit indexing request; ordinary questions proceed directly from document structure to QA.

## Optional: semantic indexing

Display **“Optional: Building or validating case semantic indexes.”**

Before extraction require valid:
- ingest bundle
- PP-DocLayoutV2 layout
- document structure

Read `structure/documents.jsonl`, `pages.jsonl`, and `blocks.jsonl` first. Do not redo visual layout detection.

Extract:
- `records/documents.jsonl`
- `entities.jsonl`
- `events.jsonl`
- `evidence.jsonl`
- `case_summary.md`

Every semantic record must remain grounded to exact source pages/quotes. Preserve conflicting claims separately.

Validate with:
`.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --case-dir CASE_DIR`

## Mandatory handoff

For an indexing-only request, report the outputs and validation result and stop. If the user also asked a question, load `grounded-case-qa` and answer it from source pages.

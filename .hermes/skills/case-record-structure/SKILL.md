---
name: case-record-structure
description: Fourth stage for PDF case questions. Build semantic case records from validated document hierarchy; use normalized pages and page images only for source verification.
---

# Case Record Structure

Pipeline:

`pdf-ingest → document-layout → document-structure → case-record-structure → grounded-case-qa`

## Stage 4/5: semantic indexing

Display **“Stage 4/5: Building or validating case semantic indexes.”**

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

Display **“Stage 4/5 complete; proceeding to grounded QA.”** and load `grounded-case-qa`.

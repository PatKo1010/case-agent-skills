---
name: document-structure
description: Third stage for PDF case questions. Combine validated PP-DocLayoutV2 regions with normalized page text to infer document boundaries, page roles and block hierarchy. Do not perform visual layout detection here.
---

# Document Structure

Pipeline:

`pdf-ingest → document-layout → document-structure → grounded-case-qa`

This stage answers: **how are the already-detected page regions organized into documents and blocks?**

## Stage 3/4: hierarchy assembly

Display: **“Stage 3/4: Building or validating document hierarchy.”**

1. Validate ingest and layout.
2. Reuse structure only when its validator succeeds.
3. Otherwise run:
   `.venv/bin/python .hermes/skills/document-structure/scripts/build_document_structure.py CASE_DIR`
4. Validate:
   `.venv/bin/python .hermes/skills/document-structure/scripts/validate_document_structure.py CASE_DIR/structure --case-dir CASE_DIR`

The builder:
- aligns normalized text blocks to PP-DocLayoutV2 regions by geometry;
- maps model labels into case-oriented block types;
- assigns `page_role` instead of inventing a title for every page;
- starts a new document primarily from confident `document_title` regions;
- preserves layout score and source block confidence;
- builds parent-child relationships under headings.

Outputs:
- `structure/documents.jsonl`
- `structure/pages.jsonl`
- `structure/blocks.jsonl`
- `structure/structure_manifest.json`

Document title belongs to a document, not every page.

## Mandatory handoff

1. Display **“Stage 3/4 complete; proceeding directly to source-grounded QA.”**
2. Load `grounded-case-qa`.
3. Execute QA now with the canonical case directory and original question. Do not build or validate semantic indexes; a handoff announcement alone does not complete a question.

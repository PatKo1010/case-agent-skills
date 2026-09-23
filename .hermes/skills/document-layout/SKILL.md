---
name: document-layout
description: Second stage for PDF case questions. Run PP-DocLayoutV2 on every rendered page, cache layout regions and reading order, validate them against page image hashes, then hand off to document-structure.
---

# Document Layout

This stage answers: **what visual regions exist on each page, and in what reading order?**

It does not decide document boundaries or case semantics.

## Stage 2/4: PP-DocLayoutV2

Display: **“Stage 2/4: Running or validating document layout analysis.”**

1. Validate ingest:
   `.venv/bin/python .hermes/skills/pdf-ingest/scripts/validate_ingest_bundle.py CASE_DIR`
2. Reuse layout only if:
   `.venv/bin/python .hermes/skills/document-layout/scripts/validate_document_layout.py CASE_DIR/layout --case-dir CASE_DIR`
   succeeds.
3. Otherwise run:
   `.venv/bin/python .hermes/skills/document-layout/scripts/run_layout.py CASE_DIR`
4. Validate again.

The default model is `PP-DocLayoutV2` on CPU. If `~/.paddlex/official_models/PP-DocLayoutV2` exists, it is used locally; otherwise PaddleOCR may download the official model. For an offline demo, initialize/download the model before running Hermes.

Outputs:
- `layout/page-NNN.json`
- `layout/layout_manifest.json`

Each region preserves:
- model label
- score
- bbox in rendered-image pixels
- model reading order

See `references/layout-schema.md`.

## Mandatory handoff

1. Display **“Stage 2/4 complete; proceeding to document hierarchy assembly.”**
2. Load `document-structure`.
3. Pass `CASE_DIR`, layout directory and original question.

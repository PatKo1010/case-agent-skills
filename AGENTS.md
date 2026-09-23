# PDF case questions in Hermes

For every PDF question run:

`.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf`

Canonical pipeline:

`pdf-ingest → document-layout → document-structure → grounded-case-qa`

Execute the returned `next_skill` in the current Hermes conversation.

Artifact layers:
- `page/`: rendered physical pages
- `normalized/`: native-text/PaddleOCR source blocks in one pixel coordinate system
- `layout/`: PP-DocLayoutV2 regions + reading order
- `structure/`: document boundaries, page roles and block hierarchy
- `records/`: optional semantic indexes, outside the default pipeline

The ingest, layout and structure layers are reusable only after their validators succeed. Do not bypass a missing required layer because the answer is visible in raw text. Semantic records are not required: do not invoke case-record-structure or validate_case_records for ordinary PDF questions. Missing or stale records do not block QA.

Python helpers may render, OCR, run layout inference, align geometry and validate artifacts. Hermes answers directly from document structure and verifies facts against normalized source pages. Semantic indexing is performed only when explicitly requested.

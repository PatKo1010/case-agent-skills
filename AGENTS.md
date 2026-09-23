# PDF case questions in Hermes

For every PDF question run:

`.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf`

Canonical pipeline:

`pdf-ingest → document-layout → document-structure → case-record-structure → grounded-case-qa`

Execute the returned `next_skill` in the current Hermes conversation.

Artifact layers:
- `page/`: rendered physical pages
- `normalized/`: native-text/PaddleOCR source blocks in one pixel coordinate system
- `layout/`: PP-DocLayoutV2 regions + reading order
- `structure/`: document boundaries, page roles and block hierarchy
- `records/`: semantic case indexes

Each layer is reusable only after its validator succeeds. Do not bypass a missing layer because the answer is visible in raw text.

Python helpers may render, OCR, run layout inference, align geometry and validate artifacts. Hermes performs semantic case extraction and final QA.

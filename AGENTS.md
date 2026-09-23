# PDF case questions in Hermes

For every PDF question, first run `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/locate_case.py INPUT.pdf` from the project root.

The canonical pipeline is:

`pdf-scan-ingest → document-structure → case-record-structure → grounded-case-qa`

`locate_case.py` computes the full PDF SHA-256, validates cached artifacts at `output_<sha256>/`, and returns the earliest required skill. Load and execute that skill in the current Hermes conversation.

Artifact layers:
- `page/` + `ocr/`: normalized per-page source text. Native PDF text is preferred per page; PaddleOCR is the fallback for scanned/low-text pages.
- `structure/`: lightweight document boundaries, page titles and blocks (`title|narrative|table|qa`).
- `records/`: semantic case indexes (`documents|entities|events|evidence`).
- root `job.json` / `manifest.json`: ingest identity and integrity metadata.

Directory existence never proves validity. Each reusable stage must pass its validator before a later stage may run.

The current Hermes agent owns semantic extraction and answering. Python helpers may render, extract native text, OCR, classify lightweight structure, locate and validate artifacts; they must not launch another model API or hidden orchestration agent.

A fact discovered in raw page text does not authorize skipping structure, semantic indexing or QA when those stages are required. Preserve the original question, canonical paths and uncertainties across handoffs.

# PDF case questions in Hermes

For every PDF question, first run `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/locate_case.py INPUT.pdf` from the project root. It computes the full PDF SHA-256 and validates artifacts at `output_<sha256>/`; it only reads data and does not run any model or processing stage.

Load and execute the returned `next_skill` in the current Hermes conversation: `grounded-case-qa` when both OCR and indexes are valid, `case-record-structure` when only OCR is valid, otherwise `pdf-scan-ingest`. Use `skill_view` or read `.hermes/skills/NAME/SKILL.md`. Identical bytes reuse the same output even if the filename changes; changed bytes use a different directory. Directory existence alone never proves cache validity.

All artifacts for one PDF belong under that canonical directory: `page/` for PNGs, `ocr/` for OCR JSON, `records/` for structured files and drafts, and root `job.json` / `manifest.json`. Use the bundle root as `OCR_DIR` in validators, not its `ocr/` child. Keep the original question and source paths across skill handoffs.

The current Hermes agent performs extraction and answering. Python helpers only locate, OCR or validate files; do not introduce a separate model API call or orchestration process. Valid cached stages need not be executed again. An answer found in raw OCR does not bypass missing/invalid indexes. Continue required stages in the same turn, or report a concrete blocker. Stop after OCR or indexing only when the user explicitly requested that scope.

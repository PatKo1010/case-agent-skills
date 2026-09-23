---
name: grounded-case-qa
description: Final fourth stage for PDF case questions. Answer directly from validated document structure and normalized source pages with page citations. Semantic case indexes are not required.
---

# Grounded Case QA

## Stage 4/4: source retrieval and answering

For a PDF request, run `.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf` and require `next_skill: grounded-case-qa`. Execute any earlier skill returned, preserving the original question and source paths. For a follow-up with only a known CASE_DIR, run `.venv/bin/python .hermes/skills/document-structure/scripts/validate_document_structure.py CASE_DIR/structure --case-dir CASE_DIR`; this validates the underlying ingest/layout as well. Repair a missing or stale required layer before answering.

Do not create semantic records or invoke `validate_case_records.py`. Missing, stale or malformed files under `records/` do not block this pipeline.

Display **“Stage 4/4: Reading document structure and verifying source text.”**

1. Read `structure/documents.jsonl` and `structure/pages.jsonl` to locate document titles, page ranges and roles. Search `structure/blocks.jsonl` by relevant names, dates, keywords and variants; read adjacent blocks for context. Parse on-disk JSON with Python `json.load`/`json.loads`, not decorated tool output. Print bounded excerpts with page/block IDs to avoid dumping the entire case unnecessarily.
2. For every fact or quotation used in the answer, read the corresponding `normalized/page-NNN.json` source text and blocks, using structure `source_block_ids` where available. Verify context, speaker, dates and amounts. Structure is a navigation aid, not independent evidence; do not treat inferred document boundaries as certain.
3. Preserve literal source quotations. Inspect rendered `page/` images when recognition or layout is materially uncertain. Do not silently correct OCR or imply visual verification that did not occur. If source support is insufficient, say so and identify the needed check.
4. For comprehensive summaries, timelines and comparisons, review all relevant pages; a keyword hit alone does not establish completeness. Expand searches before concluding that evidence is absent. No intermediate semantic index is required.
5. Apply `references/runtime-prompt.md` in this conversation. Support material claims with physical PDF page citations and document titles when known. Distinguish allegations, witness statements and investigator conclusions, retain conflicting versions, and disclose OCR uncertainty.
6. Display **“Stage 4/4 complete”** only with the final grounded answer or supported finding of insufficient evidence. A handoff announcement alone does not complete the task.

For complete processing without a specific question, summarize the recorded case history, main evidence and matters requiring clarification. Stop at an earlier stage only when the user explicitly requests that scope. Use the current Hermes conversation; do not launch another model process or API call.

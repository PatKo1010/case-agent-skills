---
name: case-record-structure
description: Required second stage for PDF case questions after pdf-scan-ingest. Build or validate document, entity, event and evidence indexes against the current OCR, then continue to grounded-case-qa in the same Hermes conversation. Also use for index-only requests and rebuilding after OCR corrections.
---

# Case Record Structure

## Stage 2: Build or reuse indexes

The current Hermes agent performs extraction using its current conversation and model. Keep the original question and OCR directory from Stage 1. Display “Stage 2/3: Building or validating case indexes.” All commands below run from the project root.

1. Validate the input OCR with `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py OCR_DIR`.
2. If an index directory is already associated with this OCR, run:
   `.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir OCR_DIR`
   Success permits reuse: proceed to the handoff. Missing, stale or invalid indexes require extraction from the current OCR; changing an old index's source binding alone is not rebuilding.
3. Before reading pages for extraction, capture the exact fingerprint printed by:
   `.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py --ocr-dir OCR_DIR --fingerprint`
4. Before extraction, read `references/file-io.md` for the native file-reading command, complete draft example, and five-file writer. Use terminal Python `json.load()` on the actual OCR files for programmatic parsing. `read_file` output is for viewing: its line numbers and tool envelope are not the JSON file. Read each page, then use Hermes's file-writing tools to save your extracted records as a draft and the reference writer to serialize the five outputs. This is local data I/O, not a separate model or workflow. Extract the case records, not only the single answer sought. Preserve source uncertainties and verification status. Follow `references/case-schema.md`.
5. Seal the newly built records against the fingerprint captured before extraction:
   `.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir OCR_DIR --seal --expected-fingerprint STARTING_FINGERPRINT`
   Use the recovery rules below for failures. If OCR changed during extraction, revisit affected facts and rebuild against a new starting fingerprint.
6. Run the validation command from step 2 without `--seal`. Stage 2 completes only when it succeeds and all five outputs exist. This checks source binding and quote mechanics, not the correctness of every interpretation.

## Outputs and extraction rules

- `documents.jsonl`: document sections with type and page range.
- `entities.jsonl`: people, organizations, accounts, places and identifiers.
- `events.jsonl`: source date/time, actor, action, object, amount and place.
- `evidence.jsonl`: exhibit name, provider/source, page count and status.
- `case_summary.md`: neutral case summary with page citations.

Each JSONL record needs `id`, `kind`, `attributes`, `source_pages`, `source_quote`, `confidence`, and `verification`. The validator creates `index_manifest.json`; Hermes does not invent its hashes.

Split sections by visible titles. Extract tables and narrative separately, then reconcile duplicates. Merge aliases only with explicit support. Keep original ROC dates and units. Retain contradictory claims separately with `conflicts_with`; distinguish document statements from established facts. Each quote must occur verbatim in a cited page; split claims requiring different quotations. Preserve `unverified` unless source pages support visual verification. Avoid unsupported conclusions about intent, guilt or causation.

## Error recovery and stopping conditions

A change of reading/writing method does not change the required outputs. Reading OCR to build indexes is required; finding an answer while reading it does not authorize delivering the answer early. File size, page count and perceived speed are not exceptions to Stage 2.

| Observed failure | Required next action |
| --- | --- |
| `JSONDecodeError` on copied `read_file` output containing `1|{`, or `KeyError: 'content'` on a tool response | Stop parsing the tool response. Run the native reader in `references/file-io.md` on the disk path. Do not keep stripping line numbers, guess envelope fields, or change the OCR files. |
| Native `json.load()` fails on the disk file | Record the path and JSON error line/column. For OCR input, return to Stage 1 to repair/validate that artifact; for your draft, repair its JSON and retry the writer. A disk error is distinct from display decoration. |
| Missing path or permission failure | Check the working directory and exact path once. Use an accessible correct path; if access is genuinely unavailable, report that blocker. |
| Terminal output is truncated | Read a smaller page/block range from the same disk file. Track which pages/blocks remain and finish coverage before sealing. |
| Record validator reports a missing field, invalid page, unsupported quote or verification | Fix the indicated record from source evidence, rewrite the affected output, then rerun sealing and validation. Keep evidence intact; do not weaken the validator. |
| OCR fingerprint changed | Revisit the current OCR and rebuild affected records with a new starting fingerprint before sealing. |

After two corrective attempts for the same unresolved failure, stop that retry loop. Report the actual command/path, error, files already written, and what is needed to continue. Leave Stage 2 incomplete and Stage 3 pending. Do not substitute an OCR answer or offer indexing as an optional follow-up. If the native read succeeds, continue writing and validating all five outputs in this turn; do not stop just because the relevant fact has been located.

## Mandatory handoff

After valid indexes are available, report their directory and validation result. For PDF questions or complete case analysis:

1. Display “Stage 2/3 complete; proceeding to source-grounded case QA.”
2. Call `skill_view` for `grounded-case-qa`; if unavailable, read `.hermes/skills/grounded-case-qa/SKILL.md` from the project root.
3. Execute QA now in this conversation, retaining the original question, OCR directory, index directory and uncertainties. A handoff announcement alone does not finish the request.

For complete case processing without a specific question, answer “Summarize the recorded case history, main evidence, and matters requiring clarification.” Stop after indexing only when the user explicitly requested indexes alone. If blocked, state the failed validation and pending QA stage rather than answering directly from OCR.

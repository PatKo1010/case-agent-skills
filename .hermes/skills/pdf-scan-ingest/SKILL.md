---
name: pdf-scan-ingest
description: Use when a PDF case file needs OCR or its cached OCR is invalid. For any PDF question first use locate_case.py to check the content-hash output; valid OCR and indexes go directly to grounded-case-qa. Validate or produce page-level OCR, then continue in the same Hermes conversation to case-record-structure and grounded-case-qa. Stop after OCR only when the user explicitly requests OCR or text export alone.
---

# PDF Scan Ingest

## Execution contract

The current Hermes agent owns the whole request: `pdf-scan-ingest → case-record-structure → grounded-case-qa`. Keep the original question, PDF identity, OCR directory and uncertainties in the conversation through all three stages. Python helpers only render, recognize or validate data; Hermes itself performs extraction and answering using its current model. Do not launch a separate agent, model API request or orchestration program.

A PDF-content question is complete only after all three stages have been executed or their existing artifacts validated, and the final answer cites source pages. Finding an apparent answer in OCR completes neither indexing nor QA. Continue to the next skill in the same turn without asking whether to proceed. A genuine blocker must name the failed step and pending stages, not substitute a direct OCR answer.

## Locate before processing

Run `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/locate_case.py INPUT.pdf` first. This read-only helper returns the canonical `output_dir` and `next_skill`. If it returns `grounded-case-qa`, load that skill directly: existing OCR and indexes have passed validation, so skip both processing stages. If it returns `case-record-structure`, skip OCR and continue with that skill. Otherwise perform Stage 1 below.

The directory is always the project root's `output_<full PDF SHA-256>/`, independent of the filename. It contains `page/` (PNGs), `ocr/` (OCR JSON), `records/` (all indexes and drafts), `job.json` and `manifest.json`. `OCR_DIR` means this output root in all validator commands. Do not invent output names or put it under another directory.

## Stage 1: OCR

Display “Stage 1/3: Checking or recognizing case-file OCR.”

1. Identify the supplied PDF and any existing OCR directory. Reuse completed OCR only after checking the PDF SHA-256 against `manifest.json`'s `source_sha256` and running the validator below. For a request explicitly about an existing OCR bundle, use that bundle as the supplied source. Existing valid OCR does not require rerunning recognition.
2. For a new PDF, inspect with `pdfinfo` and `pdftotext`. Empty extracted text does not mean an empty document. The helper renders at 200 DPI and uses local PaddleOCR PP-OCRv6 on CPU:
   `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py INPUT.pdf`
   Run from the project root. Local weights default to `~/.paddlex/official_models/`; see `--help` for overrides.
3. For interrupted automatic OCR, run the same command with `--resume` and the same directory. Use Hermes terminal's background/session facility for long work and poll that session. A wait timeout does not establish process failure: check the session before retrying. The helper's OS lock rejects a second active writer. A changed PDF uses a different content-hash directory. A model/settings mismatch during resume is a blocker requiring an explicit rebuild decision, not an invented alternate output directory; old incomplete bundles without `job.json` cannot be resumed safely.
4. Require `manifest.json` status `complete`, all pages present, and success from:
   `.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py OCR_DIR`
5. Check important names, dates, money, identifiers and ambiguous layout against page images when visual tools are available. Preserve raw text; changes to corrected text require `verification: visual`, corrections and a note. If visual checks are unavailable, retain `unverified` and unresolved spans for provisional indexing; disclose these limitations downstream. Schema checks do not prove recognition accuracy. See `references/ocr-schema.md`.

`job.json` records job ID, PID, settings, page start times, completed-page hashes and elapsed seconds. Resume skips valid completed pages and preserves damaged files before replacing them. Stored PID/status alone does not establish liveness. Pass manually corrected completed OCR straight to indexing after validation; rerunning automatic OCR may replace edits.

## Mandatory handoff

Unless the user explicitly requested OCR/text export only:

1. Display “Stage 1/3 complete; proceeding to case indexing,” with the OCR directory and uncertainties.
2. Call `skill_view` for `case-record-structure`; if unavailable, read `.hermes/skills/case-record-structure/SKILL.md` from the project root.
3. Execute that skill now with the current OCR directory and original question. Existing indexes must pass its source-binding check before reuse. Loading the skill or announcing a next step is not completing it.

Retain positions and uncertainty for tables, stamps and handwriting. Keep original ROC dates. Existing baseline indexes or hard-coded reconstruction scripts are not evidence that the current OCR has been indexed.

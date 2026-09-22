---
name: grounded-case-qa
description: Final stage of PDF case questions. Answer from validated current indexes with source-page citations and uncertainty. If OCR or indexes are missing or stale, load and execute the preceding skills in the same Hermes conversation before answering. Also use to query existing case timelines, evidence and conflicting statements.
---

# Grounded Case QA

## Entry gate

The current Hermes agent performs retrieval and answering; no separate model process or API call is needed. Keep the user's original question and the current OCR/index directories.

Before substantive answering, run from the project root:
`.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir OCR_DIR`

Require success. This checks five outputs, source quotes, page references, OCR fingerprint and index file hashes. OCR text alone does not satisfy the entry gate.

If OCR is missing or incomplete, use `skill_view` to load and execute `pdf-scan-ingest`. If OCR is valid but indexes are missing, stale or invalid, load and execute `case-record-structure`. If `skill_view` is unavailable, read the corresponding `.hermes/skills/NAME/SKILL.md`. The same Hermes agent completes the prerequisites and returns here in the same turn. Do not defer to an unspecified outer workflow or ask the user to run another model. If required tools are unavailable, report the concrete blocker and remaining stages.

## Stage 3: Retrieve and answer

After the entry gate passes, display “Stage 3/3: Retrieving from case indexes and producing an answer with page citations.”

1. Classify the question as lookup, timeline, cross-document comparison, evidence-list or legal interpretation.
2. Retrieve candidate records from the validated indexes by identifiers, entities, dates and meaning. Use OCR second to check quoted context; use page images to check recognition. Read-only work applies during QA; return to the prior skill when a prerequisite needs repair.
3. Support every material claim with source pages; cite all necessary pages for cross-document answers. Distinguish allegations, interviewee statements and investigator conclusions.
4. Apply `references/runtime-prompt.md` as instructions for your current response, not as a prompt for a separate API request. Answer concisely with `Source: page X (document title)` and relevant uncertainty. Mask sensitive identifiers unless exact disclosure is necessary and authorized.
5. Report conflicting versions. If evidence is absent or a key value has confidence below 0.80, state insufficient evidence and the needed visual check. Clearly label reliance on unverified OCR; never imply visual checks occurred when they did not.
6. Display “Stage 3/3 complete” only with the final cited answer or a supported finding of insufficient evidence. An OCR result or indexing report is not the final answer to a PDF question.

Answer document-content questions, not personalized legal strategy.

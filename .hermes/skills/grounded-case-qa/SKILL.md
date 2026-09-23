---
name: grounded-case-qa
description: Final fourth stage of PDF case questions. Answer from validated semantic indexes, use lightweight document structure for navigation and normalized pages/images for verification, with source-page citations and uncertainty.
---

# Grounded Case QA

## Entry gate

For every PDF request, use `locate_case.py INPUT.pdf`. When it returns `grounded-case-qa`, all prerequisite layers have passed validation.

Use:
- `CASE_DIR = output_<SHA256>`
- `STRUCTURE_DIR = CASE_DIR/structure`
- `RECORD_DIR = CASE_DIR/records`

Before answering, validate both:

`.venv/bin/python .hermes/skills/document-structure/scripts/validate_document_structure.py STRUCTURE_DIR --case-dir CASE_DIR`

`.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir CASE_DIR`

If a prerequisite is stale, execute the `next_skill` returned by the locator rather than bypassing it.

## Stage 4/4: Retrieve and answer

Display: **“Stage 4/4: Retrieving case evidence and producing a source-grounded answer.”**

1. Classify the question as lookup, timeline, cross-document comparison, evidence-list or legal interpretation.
2. Search semantic records first.
3. Use `structure/documents.jsonl` and `blocks.jsonl` to navigate the relevant document/page/block.
4. Verify exact quotes and ambiguous values against normalized page text; use page images when visual recognition/layout matters.
5. Support every material claim with source pages and distinguish allegations, interviewee statements and investigator conclusions.
6. Report conflicting versions rather than collapsing them.
7. If evidence is absent or materially uncertain, say so and identify the needed source/visual check.
8. Display **“Stage 4/4 complete”** only with the final cited answer or a supported finding of insufficient evidence.

The evidence hierarchy is:

`semantic record → structural block → normalized page text → page image`

Structural labels help retrieval; they do not themselves prove semantic claims.

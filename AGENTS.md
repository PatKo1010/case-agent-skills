# PDF case questions in Hermes

For a question about a PDF case file, load `.hermes/skills/pdf-scan-ingest/SKILL.md` first, using `skill_view` when available. In the same conversation, execute `pdf-scan-ingest → case-record-structure → grounded-case-qa`, retaining the user's question and current source directories. Reuse existing OCR/indexes only after the corresponding skill's validation passes.

**CRITICAL RULE: Direct extraction from OCR is strictly forbidden.** An answer found in OCR does not bypass indexing. Finding an apparent answer in OCR completes neither indexing nor QA. You MUST NOT skip to the answer; you must complete the entire pipeline. Stop after OCR or indexing only when the user explicitly requested that limited scope.

The current Hermes agent performs extraction and answering. Python helpers are for OCR and validation; do not introduce a separate orchestration process or model API call. Finish the skill handoffs and cited answer in the same turn, or report the concrete blocker and pending stage. Follow each skill's completion criteria before announcing it complete.

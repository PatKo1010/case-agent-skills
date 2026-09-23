---
name: grounded-case-qa
description: Final fifth stage. Answer from validated semantic records, use document hierarchy for navigation, and return to normalized pages/page images for exact verification.
---

# Grounded Case QA

## Stage 5/5

Before answering, run the locator and require `next_skill: grounded-case-qa`.

Evidence hierarchy:
1. semantic case record
2. document structure block
3. normalized source page
4. rendered page image

Retrieve semantic records first, use layout/structure for navigation, and verify exact claims against normalized source pages. Use page images when recognition or visual layout is materially uncertain.

Support material claims with page citations, preserve conflicting versions, and state insufficient evidence when the source does not support a conclusion.

Display **“Stage 5/5 complete”** only with the final grounded answer.

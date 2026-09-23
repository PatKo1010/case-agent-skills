# Case agent skills

Hermes PDF pipeline:

```
pdf-ingest
  ↓
document-layout
  ↓
document-structure
  ↓
grounded-case-qa
```

## Skills

| Skill | Responsibility | Main output |
| --- | --- | --- |
| `pdf-ingest` | Render PDF, prefer native text per page, PaddleOCR fallback, normalize bbox coordinates | `page/`, `normalized/`, `manifest.json` |
| `document-layout` | PP-DocLayoutV2 visual region detection + reading order | `layout/page-NNN.json`, `layout_manifest.json` |
| `document-structure` | Align text to layout; infer document boundaries, page roles and hierarchy | `structure/*.jsonl` |
| `case-record-structure` (optional, explicit request only) | Hermes semantic extraction: documents/entities/events/evidence/conflicts | `records/*.jsonl` |
| `grounded-case-qa` | Source-grounded question answering | cited final answer |

## Install

Python 3.11:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirement.txt
```

PaddleOCR PP-OCRv6 weights are used only for pages without enough native text.

### Initialize PP-DocLayoutV2 once

The layout skill uses PaddleOCR's `LayoutDetection(model_name="PP-DocLayoutV2")`. The official model may download on first use. For an offline Hermes demo, initialize it in advance:

```bash
.venv/bin/python - <<'PY'
from paddleocr import LayoutDetection
LayoutDetection(model_name="PP-DocLayoutV2", device="cpu")
print("PP-DocLayoutV2 initialized")
PY
```

If the local model exists at `~/.paddlex/official_models/PP-DocLayoutV2`, the layout script automatically uses it.

## Output

```text
output_<PDF_SHA256>/
├── page/
├── normalized/
├── layout/
├── structure/
├── records/  (optional)
├── job.json
└── manifest.json
```

## Entry point

```bash
.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf
```

The locator validates ingest, layout and structure, then routes directly to grounded-case-qa. It does not inspect or require records/. Missing or stale semantic indexes do not block answering.

## Design

The responsibility split is deliberate:

- **pdf-ingest:** what text is on the physical page?
- **document-layout:** what visual regions are present?
- **document-structure:** how are those regions organized into documents/pages/blocks?
- **case-record-structure (optional):** what do those records mean for the case?
- **grounded-case-qa:** what does the source-supported answer say?

This avoids asking the LLM to simultaneously solve OCR, layout recognition, hierarchy reconstruction and case reasoning.

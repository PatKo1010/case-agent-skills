# Native file I/O for Stage 2

Read this before extracting records. Run commands through Hermes's terminal from the project root. Replace quoted path placeholders with actual paths. Hermes performs the reasoning and extraction; the examples only read and serialize local files.

## Read disk JSON, not tool display text

`read_file` can display `1|{` and wrap results in tool-specific objects. These are display/transport details. Do not pass that text to `json.loads()` or assume a `response["content"]` field. Parse the on-disk file inside Python instead:

```bash
.venv/bin/python - 'OCR_DIR' 5 <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
page_number = int(sys.argv[2])
path = root / 'ocr' / f'page-{page_number:03d}.json'
with path.open(encoding='utf-8') as stream:
    page = json.load(stream)
print(json.dumps({
    'page': page['page'],
    'raw_text': page['raw_text'],
    'corrected_text': page['corrected_text'],
    'verification': page['verification'],
    'uncertain_spans': page['uncertain_spans'],
}, ensure_ascii=False, indent=2))
PY
```

The printed result is for Hermes to read. Further Python processing should reopen the file, not parse terminal tool envelopes. Visit every page listed by `manifest.json`, even when one page answers the immediate question. If a page exceeds the tool's output limit, print bounded slices of `blocks` and text, retaining page/block identifiers and tracking unread slices. Preserve exact source quotations; a genuine `|` inside a source is content, not a line number to strip.

## Complete draft example

Use Hermes's file-writing tool to create `RECORD_DRAFT.json` with this structure, populated from the actual OCR. Write file content itself, not a tool-response wrapper, Markdown fence or numbered listing.

The following is **synthetic format guidance only**. Assume page 1 says exactly:

> 證據清單：證人甲於民國115年9月1日提出收據一張。

For a real case replace every example fact, quote and confidence with source-supported extraction. Do not copy this sample into a case index. Confidence is an assessment, not a default; `unverified` remains unverified regardless of a high score.

```json
{
  "documents": [
    {
      "id": "doc-001",
      "kind": "document",
      "attributes": {"title": "證據清單", "page_start": 1, "page_end": 1},
      "source_pages": [1],
      "source_quote": "證據清單：證人甲於民國115年9月1日提出收據一張。",
      "confidence": 0.9,
      "verification": "unverified"
    }
  ],
  "entities": [
    {
      "id": "person-001",
      "kind": "person",
      "attributes": {"name": "證人甲"},
      "source_pages": [1],
      "source_quote": "證人甲",
      "confidence": 0.9,
      "verification": "unverified"
    }
  ],
  "events": [
    {
      "id": "event-001",
      "kind": "event",
      "attributes": {
        "date_source": "民國115年9月1日",
        "actor": "證人甲",
        "action": "提出",
        "object": "收據一張",
        "status": "清單記載"
      },
      "source_pages": [1],
      "source_quote": "證人甲於民國115年9月1日提出收據一張。",
      "confidence": 0.9,
      "verification": "unverified"
    }
  ],
  "evidence": [
    {
      "id": "evidence-001",
      "kind": "evidence",
      "attributes": {"name": "收據", "provider": "證人甲", "quantity_source": "一張", "status": "清單記載"},
      "source_pages": [1],
      "source_quote": "證人甲於民國115年9月1日提出收據一張。",
      "confidence": 0.9,
      "verification": "unverified"
    }
  ],
  "case_summary": "# 卷內記載摘要\n\n證據清單記載，證人甲於民國115年9月1日提出收據一張。（page 1，證據清單）\n\n限制：OCR 尚未核對原圖。\n"
}
```

IDs are unique across all arrays. `documents` needs at least one record. The other arrays may be empty only when the reviewed source has no relevant records, not to avoid extraction. Do not invent missing page counts, actors, dates or exhibits to fill fields. Split different source claims into records instead of inventing a combined verbatim quote.

## Serialize all five outputs

After Hermes finishes the draft, run this writer with a **new** record directory. It uses `json.dumps()` so source newlines/quotes become valid JSONL. Each record occupies one physical line. It refuses an existing directory to protect earlier indexes; when repairing existing files, serialize the corrected records to those explicitly identified files, then revalidate.

```bash
.venv/bin/python - 'RECORD_DRAFT.json' 'NEW_RECORD_DIR' <<'PY'
import json
from pathlib import Path
import sys

with Path(sys.argv[1]).open(encoding='utf-8') as stream:
    draft = json.load(stream)
names = ('documents', 'entities', 'events', 'evidence')
for name in names:
    if not isinstance(draft.get(name), list):
        raise ValueError(f'{name} must be an array')
summary = draft.get('case_summary')
if not isinstance(summary, str) or not summary.strip():
    raise ValueError('case_summary must be nonempty text')
root = Path(sys.argv[2])
root.mkdir(parents=True, exist_ok=False)
for name in names:
    with (root / f'{name}.jsonl').open('w', encoding='utf-8') as stream:
        for record in draft[name]:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
(root / 'case_summary.md').write_text(summary, encoding='utf-8')
print(f'Wrote five outputs to {root}; sealing and validation are still required.')
PY
```

Return to Stage 2 steps 5–6: seal using the starting OCR fingerprint, then validate without `--seal`. Success of this writer alone does not authorize QA. If interrupted after writing only some outputs, preserve the draft, repair the remaining files, and rerun validation; do not treat partial output as a complete index.

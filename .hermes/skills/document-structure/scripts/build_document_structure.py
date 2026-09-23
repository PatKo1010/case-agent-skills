#!/usr/bin/env python3
"""Build a deterministic lightweight document structure from a validated case ingest bundle."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-scan-ingest" / "scripts"))
from bundle import atomic, fingerprint, read, sha, validate_bundle

SCHEMA_VERSION = 1
STRUCTURE_FILES = ("pages.jsonl", "documents.jsonl", "blocks.jsonl")

DOC_START_KEYWORDS = (
    "筆錄", "調查", "報告", "函", "書", "清單", "明細", "紀錄", "附件",
    "聲請", "搜索票", "傳票", "起訴", "判決", "證物", "statement",
    "report", "record", "schedule", "attachment", "exhibit", "invoice",
)
QA_RE = re.compile(r"^(?:問|答|q|a)\s*[:：、.]?", re.I)
NUMBERISH_RE = re.compile(r"(?:\d[\d,./:-]*\d|[$NT¥￥]\s*\d|\d+\s*(?:元|圓))")


def dump_jsonl(path, rows):
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    Path(path).write_text(text, encoding="utf-8")


def normalized_blocks(page_data):
    blocks = page_data.get("blocks") or []
    if blocks:
        return blocks
    text = page_data.get("corrected_text", "")
    return [{"type": "paragraph", "text": line, "bbox": None, "confidence": 1.0}
            for line in text.splitlines() if line.strip()]


def looks_title(text, index):
    t = text.strip()
    if not t or len(t) > 60:
        return False
    if index <= 4 and any(k.lower() in t.lower() for k in DOC_START_KEYWORDS):
        return True
    if index <= 2 and len(t) <= 28 and not t.endswith(("。", ".", "；", ";")):
        return True
    return False


def classify(text, index):
    t = text.strip()
    if QA_RE.match(t):
        return "qa", 0.96, "qa_prefix"
    if looks_title(t, index):
        return "title", 0.82, "short_top_or_document_keyword"
    # Conservative table hint: several numeric fields or explicit column separators.
    numeric_fields = len(NUMBERISH_RE.findall(t))
    separators = t.count("|") + t.count("\t")
    if separators >= 2 or (numeric_fields >= 3 and len(t) <= 120):
        return "table", 0.68, "row_like_numeric_or_delimited"
    return "narrative", 0.90, "default_narrative"


def boundary_candidate(blocks, page_num):
    if page_num == 1:
        title = next((b.get("text", "").strip() for b in blocks if b.get("text", "").strip()), "Document 1")
        return True, title[:120], 1.0, "first_page"
    for i, b in enumerate(blocks[:5]):
        text = b.get("text", "").strip()
        if text and any(k.lower() in text.lower() for k in DOC_START_KEYWORDS) and len(text) <= 80:
            return True, text[:120], 0.78, "top_page_document_keyword"
    return False, None, 0.0, "continuation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    manifest = validate_bundle(case_dir)
    out = case_dir / "structure"
    out.mkdir(exist_ok=True)

    pages_rows, docs_rows, block_rows = [], [], []
    current_doc = None
    doc_index = 0

    for page_meta in manifest["pages"]:
        page_num = page_meta["page"]
        page_data = read(case_dir / "ocr" / f"page-{page_num:03d}.json")
        blocks = normalized_blocks(page_data)
        starts, candidate_title, boundary_conf, boundary_rule = boundary_candidate(blocks, page_num)

        if starts or current_doc is None:
            if current_doc is not None:
                current_doc["end_page"] = page_num - 1
                current_doc["source_pages"] = list(range(current_doc["start_page"], page_num))
                docs_rows.append(current_doc)
            doc_index += 1
            current_doc = {
                "id": f"doc-{doc_index:03d}",
                "title": candidate_title or f"Document {doc_index}",
                "start_page": page_num,
                "end_page": page_num,
                "boundary_confidence": boundary_conf,
                "boundary_rule": boundary_rule,
                "source_pages": [page_num],
            }

        page_block_ids = []
        page_title = None
        for i, block in enumerate(blocks):
            text = (block.get("text") or "").strip()
            if not text:
                continue
            block_type, conf, rule = classify(text, i)
            block_id = f"p{page_num:03d}-b{i:03d}"
            if block_type == "title" and page_title is None:
                page_title = text
            row = {
                "id": block_id,
                "document_id": current_doc["id"],
                "page": page_num,
                "source_block_index": i,
                "type": block_type,
                "text": text,
                "bbox": block.get("bbox"),
                "confidence": min(float(block.get("confidence", 1.0)), conf),
                "verification": page_data.get("verification", "unverified"),
                "classification_rule": rule,
            }
            block_rows.append(row)
            page_block_ids.append(block_id)

        pages_rows.append({
            "page": page_num,
            "document_id": current_doc["id"],
            "title": page_title,
            "block_ids": page_block_ids,
            "source_verification": page_data.get("verification", "unverified"),
        })

    if current_doc is not None:
        current_doc["end_page"] = manifest["page_count"]
        current_doc["source_pages"] = list(range(current_doc["start_page"], manifest["page_count"] + 1))
        docs_rows.append(current_doc)

    dump_jsonl(out / "pages.jsonl", pages_rows)
    dump_jsonl(out / "documents.jsonl", docs_rows)
    dump_jsonl(out / "blocks.jsonl", block_rows)

    binding = {
        "schema_version": SCHEMA_VERSION,
        "ocr_fingerprint": fingerprint(case_dir),
        "source_sha256": manifest["source_sha256"],
        "files": {name: sha(out / name) for name in STRUCTURE_FILES},
    }
    atomic(out / "structure_manifest.json", binding)
    print(f"OK: {len(docs_rows)} documents, {len(pages_rows)} pages, {len(block_rows)} blocks")


if __name__ == "__main__":
    main()

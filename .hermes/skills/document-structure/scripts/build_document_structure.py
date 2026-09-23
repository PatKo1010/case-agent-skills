#!/usr/bin/env python3
"""Build hierarchy by aligning normalized text with PP-DocLayoutV2 regions."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-ingest" / "scripts"))
from bundle import atomic, fingerprint, read, sha, validate_bundle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "document-layout" / "scripts"))
from validate_document_layout import layout_fingerprint, validate as validate_layout

SCHEMA_VERSION = 2
FILES = ("documents.jsonl", "pages.jsonl", "blocks.jsonl")
QA_RE = re.compile(r"^(?:問|答|Q|A)\s*[:：、.]?", re.I)

LABEL_MAP = {
    "document_title": "title",
    "paragraph_title": "heading",
    "section_header": "heading",
    "text": "narrative",
    "vertical_text": "narrative",
    "table": "table",
    "image": "figure",
    "chart": "figure",
    "figure_title": "heading",
    "figure_table_title": "heading",
    "header": "header",
    "footer": "footer",
    "page_number": "footer",
    "seal": "seal",
}


def dump_jsonl(path, rows):
    Path(path).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def area(box):
    return max(0.0, box[2]-box[0]) * max(0.0, box[3]-box[1])


def overlap_ratio(block, region):
    x1=max(block[0], region[0]); y1=max(block[1], region[1])
    x2=min(block[2], region[2]); y2=min(block[3], region[3])
    inter=max(0.0, x2-x1)*max(0.0, y2-y1)
    return inter / max(area(block), 1.0)


def map_type(label, text):
    if QA_RE.match((text or "").strip()):
        return "qa"
    return LABEL_MAP.get(label, "other")


def region_text(region, source_blocks):
    matched = []
    for i, block in enumerate(source_blocks):
        bbox = block.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            score = overlap_ratio(bbox, region["bbox"])
            if score >= 0.45:
                matched.append((region["reading_order"], i, block, score))
    matched.sort(key=lambda x: (x[2]["bbox"][1], x[2]["bbox"][0]))
    text = "\n".join(x[2].get("text", "") for x in matched if x[2].get("text"))
    return text, matched


def choose_page_role(regions, structured_blocks):
    labels = [r["label"] for r in regions]
    if any(r["label"] == "document_title" and r["score"] >= 0.70 for r in regions):
        return "document_start"
    if labels.count("table") >= 1:
        return "table_page"
    if sum(1 for b in structured_blocks if b["type"] == "qa") >= 2:
        return "qa_page"
    if any(l in ("image", "chart") for l in labels):
        return "figure_page"
    return "continuation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    source = validate_bundle(case_dir)
    validate_layout(case_dir / "layout", case_dir)

    out = case_dir / "structure"
    out.mkdir(exist_ok=True)
    documents, pages, blocks = [], [], []
    current_doc = None
    doc_index = 0

    for page_meta in source["pages"]:
        page_no = page_meta["page"]
        normalized = read(case_dir / "normalized" / f"page-{page_no:03d}.json")
        layout = read(case_dir / "layout" / f"page-{page_no:03d}.json")
        source_blocks = normalized.get("blocks", [])
        page_blocks = []
        used_source = set()
        current_heading = None

        for region in layout.get("regions", []):
            text, matched = region_text(region, source_blocks)
            for _, idx, _, _ in matched:
                used_source.add(idx)
            btype = map_type(region["label"], text)
            bid = f"p{page_no:03d}-r{region['reading_order']:03d}"
            confidence = region["score"]
            if matched:
                confidence = min(confidence, min(float(x[2].get("confidence", 1.0)) for x in matched))
            row = {
                "id": bid,
                "document_id": None,
                "page": page_no,
                "type": btype,
                "text": text,
                "bbox": region["bbox"],
                "confidence": confidence,
                "layout_label": region["label"],
                "layout_score": region["score"],
                "source_block_ids": [f"p{page_no:03d}-s{x[1]:03d}" for x in matched],
                "parent_block_id": current_heading,
                "verification": normalized.get("verification", "unverified"),
            }
            if btype in ("title", "heading"):
                row["parent_block_id"] = None
                current_heading = bid
            page_blocks.append(row)

        # Preserve source text that did not overlap a detected region.
        for idx, source_block in enumerate(source_blocks):
            if idx in used_source or not source_block.get("text", "").strip():
                continue
            bid = f"p{page_no:03d}-s{idx:03d}"
            text = source_block["text"]
            page_blocks.append({
                "id": bid,
                "document_id": None,
                "page": page_no,
                "type": "qa" if QA_RE.match(text.strip()) else "narrative",
                "text": text,
                "bbox": source_block["bbox"],
                "confidence": float(source_block.get("confidence", 1.0)) * 0.75,
                "layout_label": "unmatched",
                "layout_score": 0.0,
                "source_block_ids": [bid],
                "parent_block_id": current_heading,
                "verification": normalized.get("verification", "unverified"),
            })

        page_blocks.sort(key=lambda b: (b["bbox"][1] if b["bbox"] else 0, b["bbox"][0] if b["bbox"] else 0))
        role = choose_page_role(layout.get("regions", []), page_blocks)
        title_candidates = [
            b for b in page_blocks
            if b["type"] == "title" and b["text"].strip() and b["layout_score"] >= 0.70
        ]

        starts_new = page_no == 1 or (role == "document_start" and bool(title_candidates))
        if starts_new:
            if current_doc is not None:
                current_doc["end_page"] = page_no - 1
                current_doc["source_pages"] = list(range(current_doc["start_page"], page_no))
                documents.append(current_doc)
            doc_index += 1
            title = title_candidates[0]["text"].replace("\n", " ").strip()[:160] if title_candidates else f"Document {doc_index}"
            score = title_candidates[0]["layout_score"] if title_candidates else (1.0 if page_no == 1 else 0.5)
            current_doc = {
                "id": f"doc-{doc_index:03d}",
                "title": title,
                "start_page": page_no,
                "end_page": page_no,
                "boundary_confidence": score,
                "boundary_rule": "first_page" if page_no == 1 else "pp_doclayout_document_title",
                "source_pages": [page_no],
            }

        for b in page_blocks:
            b["document_id"] = current_doc["id"]
            blocks.append(b)

        pages.append({
            "page": page_no,
            "document_id": current_doc["id"],
            "page_role": role,
            "block_ids": [b["id"] for b in page_blocks],
            "layout_labels": [r["label"] for r in layout.get("regions", [])],
        })

    if current_doc is not None:
        current_doc["end_page"] = source["page_count"]
        current_doc["source_pages"] = list(range(current_doc["start_page"], source["page_count"] + 1))
        documents.append(current_doc)

    dump_jsonl(out / "documents.jsonl", documents)
    dump_jsonl(out / "pages.jsonl", pages)
    dump_jsonl(out / "blocks.jsonl", blocks)

    binding = {
        "schema_version": SCHEMA_VERSION,
        "ingest_fingerprint": fingerprint(case_dir),
        "layout_fingerprint": layout_fingerprint(case_dir / "layout"),
        "source_sha256": source["source_sha256"],
        "files": {name: sha(out / name) for name in FILES},
    }
    atomic(out / "structure_manifest.json", binding)
    print(f"OK: {len(documents)} documents, {len(pages)} pages, {len(blocks)} blocks")


if __name__ == "__main__":
    main()

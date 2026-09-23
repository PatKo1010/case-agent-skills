#!/usr/bin/env python3
"""Validate lightweight document structure against the current ingest bundle."""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-scan-ingest" / "scripts"))
from bundle import fingerprint, read, sha, validate_bundle

SCHEMA_VERSION = 1
FILES = ("pages.jsonl", "documents.jsonl", "blocks.jsonl")
BLOCK_TYPES = {"title", "narrative", "table", "qa"}


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(structure_dir, case_dir):
    structure_dir, case_dir = Path(structure_dir), Path(case_dir)
    manifest = validate_bundle(case_dir)
    for name in FILES:
        if not (structure_dir / name).is_file():
            raise ValueError(f"missing {name}")

    page_rows = rows(structure_dir / "pages.jsonl")
    doc_rows = rows(structure_dir / "documents.jsonl")
    block_rows = rows(structure_dir / "blocks.jsonl")

    expected_pages = list(range(1, manifest["page_count"] + 1))
    if [r.get("page") for r in page_rows] != expected_pages:
        raise ValueError("pages.jsonl must cover every physical page exactly once")

    doc_ids = {r.get("id") for r in doc_rows}
    if not doc_ids or None in doc_ids or len(doc_ids) != len(doc_rows):
        raise ValueError("invalid or duplicate document ids")

    source_pages = {
        p: read(case_dir / "ocr" / f"page-{p:03d}.json")
        for p in expected_pages
    }
    block_ids = set()
    for row in block_rows:
        required = ("id", "document_id", "page", "source_block_index", "type", "text",
                    "confidence", "verification", "classification_rule")
        if any(k not in row for k in required):
            raise ValueError("block missing required fields")
        if row["id"] in block_ids:
            raise ValueError("duplicate block id")
        block_ids.add(row["id"])
        if row["document_id"] not in doc_ids or row["page"] not in source_pages:
            raise ValueError(f"{row['id']}: invalid document/page")
        if row["type"] not in BLOCK_TYPES:
            raise ValueError(f"{row['id']}: invalid block type")
        conf = row["confidence"]
        if type(conf) not in (int, float) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError(f"{row['id']}: invalid confidence")
        if row["verification"] not in ("unverified", "visual"):
            raise ValueError(f"{row['id']}: invalid verification")
        text = row["text"]
        if not isinstance(text, str) or not text.strip() or text not in source_pages[row["page"]]["corrected_text"]:
            raise ValueError(f"{row['id']}: text must be verbatim in source page")

    for page in page_rows:
        if page.get("document_id") not in doc_ids:
            raise ValueError(f"page {page.get('page')}: invalid document id")
        if any(bid not in block_ids for bid in page.get("block_ids", [])):
            raise ValueError(f"page {page.get('page')}: unknown block id")

    expected_binding = {
        "schema_version": SCHEMA_VERSION,
        "ocr_fingerprint": fingerprint(case_dir),
        "source_sha256": manifest["source_sha256"],
        "files": {name: sha(structure_dir / name) for name in FILES},
    }
    if not (structure_dir / "structure_manifest.json").is_file():
        raise ValueError("missing structure_manifest.json")
    if read(structure_dir / "structure_manifest.json") != expected_binding:
        raise ValueError("structure is stale or changed; rebuild from current ingest")
    return len(doc_rows), len(page_rows), len(block_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("structure_dir", type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        d, p, b = validate(args.structure_dir, args.case_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"OK: {d} documents, {p} pages, {b} blocks; source binding verified")


if __name__ == "__main__":
    main()

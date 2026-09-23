#!/usr/bin/env python3
"""Validate structure against current ingest and layout."""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-ingest" / "scripts"))
from bundle import fingerprint, read, sha, validate_bundle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "document-layout" / "scripts"))
from validate_document_layout import layout_fingerprint, validate as validate_layout

SCHEMA_VERSION = 2
FILES = ("documents.jsonl", "pages.jsonl", "blocks.jsonl")
BLOCK_TYPES = {"title","heading","narrative","table","qa","figure","header","footer","seal","other"}
PAGE_ROLES = {"document_start","continuation","table_page","qa_page","figure_page","unknown"}


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def validate(structure_dir, case_dir):
    structure_dir, case_dir = Path(structure_dir), Path(case_dir)
    source = validate_bundle(case_dir)
    validate_layout(case_dir / "layout", case_dir)

    docs = rows(structure_dir / "documents.jsonl")
    pages = rows(structure_dir / "pages.jsonl")
    blocks = rows(structure_dir / "blocks.jsonl")
    if [p.get("page") for p in pages] != list(range(1, source["page_count"] + 1)):
        raise ValueError("page coverage mismatch")

    doc_ids = {d.get("id") for d in docs}
    if not doc_ids or None in doc_ids:
        raise ValueError("invalid documents")
    block_ids = set()
    normalized_text = {
        p["page"]: read(case_dir / "normalized" / f"page-{p['page']:03d}.json")["corrected_text"]
        for p in source["pages"]
    }

    for p in pages:
        if p.get("document_id") not in doc_ids or p.get("page_role") not in PAGE_ROLES:
            raise ValueError(f"page {p.get('page')}: invalid structure")

    for b in blocks:
        if b.get("id") in block_ids:
            raise ValueError("duplicate block id")
        block_ids.add(b.get("id"))
        if b.get("document_id") not in doc_ids or b.get("type") not in BLOCK_TYPES:
            raise ValueError(f"{b.get('id')}: invalid document/type")
        conf = b.get("confidence")
        if type(conf) not in (int,float) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError(f"{b.get('id')}: invalid confidence")
        text = b.get("text", "")
        if text and not all(part in normalized_text[b["page"]] for part in text.split("\n") if part):
            raise ValueError(f"{b.get('id')}: text must come from normalized page")

    expected = {
        "schema_version": SCHEMA_VERSION,
        "ingest_fingerprint": fingerprint(case_dir),
        "layout_fingerprint": layout_fingerprint(case_dir / "layout"),
        "source_sha256": source["source_sha256"],
        "files": {name: sha(structure_dir / name) for name in FILES},
    }
    if read(structure_dir / "structure_manifest.json") != expected:
        raise ValueError("structure is stale or changed")
    return len(docs), len(pages), len(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("structure_dir", type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        d,p,b = validate(args.structure_dir, args.case_dir)
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"OK: {d} documents, {p} pages, {b} blocks")


if __name__ == "__main__":
    main()

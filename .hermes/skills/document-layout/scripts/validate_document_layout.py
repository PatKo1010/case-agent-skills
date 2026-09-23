#!/usr/bin/env python3
"""Validate cached document layout against current rendered pages."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-ingest" / "scripts"))
from bundle import read, sha, validate_bundle


def layout_fingerprint(layout_dir):
    layout_dir = Path(layout_dir)
    manifest = read(layout_dir / "layout_manifest.json")
    return hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(layout_dir, case_dir):
    layout_dir, case_dir = Path(layout_dir), Path(case_dir)
    source = validate_bundle(case_dir)
    manifest_path = layout_dir / "layout_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("missing layout_manifest.json")
    lm = read(manifest_path)
    if lm.get("source_sha256") != source["source_sha256"]:
        raise ValueError("layout source mismatch")
    pages_hashes = lm.get("pages", {})
    if set(pages_hashes) != {str(p["page"]) for p in source["pages"]}:
        raise ValueError("layout page coverage mismatch")

    total = 0
    for page in source["pages"]:
        path = layout_dir / f"page-{page['page']:03d}.json"
        if not path.is_file() or sha(path) != pages_hashes[str(page["page"])]:
            raise ValueError(f"page {page['page']}: layout hash mismatch")
        data = read(path)
        if data.get("page") != page["page"] or data.get("image_sha256") != page["sha256"]:
            raise ValueError(f"page {page['page']}: layout/image mismatch")
        if data.get("model_name") != "PP-DocLayoutV2":
            raise ValueError(f"page {page['page']}: unexpected layout model")
        last_order = -1
        for region in data.get("regions", []):
            score = region.get("score")
            bbox = region.get("bbox")
            order = region.get("reading_order")
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("invalid layout score")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError("invalid layout bbox")
            if type(order) is not int or order < last_order:
                raise ValueError("invalid layout reading order")
            last_order = order
            total += 1
    return len(source["pages"]), total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout_dir", type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        pages, regions = validate(args.layout_dir, args.case_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"OK: {pages} layout pages, {regions} regions")


if __name__ == "__main__":
    main()

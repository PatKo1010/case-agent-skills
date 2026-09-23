#!/usr/bin/env python3
"""Validate semantic records against normalized source pages."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-ingest" / "scripts"))
from bundle import atomic, fingerprint, read, sha, validate_bundle

SCHEMA_VERSION = 2
FILES = ("documents.jsonl","entities.jsonl","events.jsonl","evidence.jsonl","case_summary.md")


def validate_records(root, case_dir, check_binding=True):
    root, case_dir = Path(root), Path(case_dir)
    manifest = validate_bundle(case_dir)
    texts = {
        p["page"]: read(case_dir / "normalized" / f"page-{p['page']:03d}.json")["corrected_text"]
        for p in manifest["pages"]
    }
    count, ids, documents = 0, set(), 0
    for name in FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing {name}")
        if name.endswith(".md"):
            if not path.read_text(encoding="utf-8").strip():
                raise ValueError("case_summary.md is empty")
            continue
        for line_no,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip(): continue
            row=json.loads(line)
            required=("id","kind","attributes","source_pages","source_quote","confidence","verification")
            if any(k not in row for k in required):
                raise ValueError(f"{name}:{line_no}: missing fields")
            if row["id"] in ids: raise ValueError("duplicate id")
            ids.add(row["id"])
            if not isinstance(row["attributes"],dict): raise ValueError("attributes must be object")
            if type(row["confidence"]) not in (int,float) or not math.isfinite(row["confidence"]) or not 0<=row["confidence"]<=1:
                raise ValueError("invalid confidence")
            pages=row["source_pages"]
            if not isinstance(pages,list) or not pages or any(p not in texts for p in pages):
                raise ValueError("invalid source_pages")
            quote=row["source_quote"]
            if not isinstance(quote,str) or not quote.strip() or not any(quote in texts[p] for p in pages):
                raise ValueError("source_quote must be verbatim in a cited normalized page")
            if row["verification"] not in ("unverified","visual"):
                raise ValueError("invalid verification")
            count += 1
            documents += name == "documents.jsonl"
    if not documents:
        raise ValueError("At least one document record is required")
    binding={
        "schema_version":SCHEMA_VERSION,
        "ingest_fingerprint":fingerprint(case_dir),
        "source_sha256":manifest["source_sha256"],
        "files":{name:sha(root/name) for name in FILES},
    }
    if check_binding:
        if not (root/"index_manifest.json").exists() or read(root/"index_manifest.json") != binding:
            raise ValueError("index is missing, stale or changed")
    return count,binding


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("records",type=Path,nargs="?")
    parser.add_argument("--case-dir",required=True,type=Path)
    parser.add_argument("--seal",action="store_true")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--fingerprint",action="store_true")
    args=parser.parse_args()
    try:
        if args.fingerprint:
            print(fingerprint(args.case_dir)); return
        if args.records is None: raise ValueError("records directory required")
        if args.seal and (not args.expected_fingerprint or fingerprint(args.case_dir)!=args.expected_fingerprint):
            raise ValueError("source changed during extraction")
        count,binding=validate_records(args.records,args.case_dir,check_binding=not args.seal)
        if args.seal: atomic(args.records/"index_manifest.json",binding)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(1,f"{exc}\n")
    print(f"OK: {count} semantic records")


if __name__=="__main__":
    main()

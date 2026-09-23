#!/usr/bin/env python3
"""Return the earliest missing/stale skill in the five-stage pipeline."""
import argparse
import json
from pathlib import Path
import sys
from bundle import output_for, validate_bundle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "document-layout" / "scripts"))
from validate_document_layout import validate as validate_layout
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "document-structure" / "scripts"))
from validate_document_structure import validate as validate_structure
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "case-record-structure" / "scripts"))
from validate_case_records import validate_records


def inspect_case(pdf):
    root = output_for(pdf)
    result = {
        "output_dir": str(root),
        "normalized_dir": str(root / "normalized"),
        "layout_dir": str(root / "layout"),
        "structure_dir": str(root / "structure"),
        "records_dir": str(root / "records"),
        "next_skill": "pdf-ingest",
        "ingest_valid": False,
        "layout_valid": False,
        "structure_valid": False,
        "records_valid": False,
    }
    try:
        manifest = validate_bundle(root)
        if manifest["source_sha256"] != root.name.removeprefix("output_"):
            raise ValueError("source PDF hash mismatch")
        result["ingest_valid"] = True
    except Exception as exc:
        result["reason"] = str(exc); return result

    result["next_skill"] = "document-layout"
    try:
        validate_layout(root / "layout", root)
        result["layout_valid"] = True
    except Exception as exc:
        result["reason"] = str(exc); return result

    result["next_skill"] = "document-structure"
    try:
        validate_structure(root / "structure", root)
        result["structure_valid"] = True
    except Exception as exc:
        result["reason"] = str(exc); return result

    result["next_skill"] = "case-record-structure"
    try:
        validate_records(root / "records", root)
        result.update(records_valid=True, next_skill="grounded-case-qa")
    except Exception as exc:
        result["reason"] = str(exc)
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("pdf",type=Path)
    args=parser.parse_args()
    print(json.dumps(inspect_case(args.pdf),ensure_ascii=False,indent=2))

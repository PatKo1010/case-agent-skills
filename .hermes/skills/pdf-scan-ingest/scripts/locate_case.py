#!/usr/bin/env python3
"""Locate and validate existing artifacts; never run OCR, extraction or a model."""
import argparse
import json
from pathlib import Path
import sys
from bundle import output_for, validate_bundle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'case-record-structure' / 'scripts'))
from validate_case_records import validate_records


def inspect_case(pdf):
    root = output_for(pdf)
    result = {'output_dir': str(root), 'page_dir': str(root / 'page'),
              'ocr_dir': str(root / 'ocr'), 'records_dir': str(root / 'records'),
              'next_skill': 'pdf-scan-ingest', 'ocr_valid': False, 'records_valid': False}
    try:
        manifest = validate_bundle(root)
        if manifest['source_sha256'] != root.name.removeprefix('output_'):
            raise ValueError('Source PDF hash mismatch')
        result['ocr_valid'] = True
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['reason'] = str(exc)
        return result
    result['next_skill'] = 'case-record-structure'
    try:
        validate_records(root / 'records', root)
        result.update(records_valid=True, next_skill='grounded-case-qa')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['reason'] = str(exc)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect_case(args.pdf), ensure_ascii=False, indent=2))
    except OSError as exc:
        parser.exit(1, f'{exc}\n')

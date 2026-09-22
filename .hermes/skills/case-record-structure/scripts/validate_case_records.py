#!/usr/bin/env python3
"""Validate records against OCR and optionally seal a newly built index."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'pdf-scan-ingest' / 'scripts'))
from bundle import atomic, fingerprint, read, sha, validate_bundle

SCHEMA_VERSION = 1
FILES = ('documents.jsonl', 'entities.jsonl', 'events.jsonl', 'evidence.jsonl', 'case_summary.md')


def validate_records(root, ocr, check_binding=True):
    root, ocr = Path(root), Path(ocr)
    manifest = validate_bundle(ocr)
    texts = {p['page']: read(ocr / 'ocr' / f"page-{p['page']:03d}.json")['corrected_text'] for p in manifest['pages']}
    count, ids, documents = 0, set(), 0
    for name in FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f'missing {name}')
        if name.endswith('.md'):
            if not path.read_text(encoding='utf-8').strip():
                raise ValueError('case_summary.md is empty')
            continue
        for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            prefix = f'{name}:{line_no}'
            required = ('id', 'kind', 'attributes', 'source_pages', 'source_quote', 'confidence', 'verification')
            if not isinstance(row, dict) or any(key not in row for key in required):
                raise ValueError(f'{prefix}: missing required fields')
            if not isinstance(row['id'], str) or not row['id'] or row['id'] in ids:
                raise ValueError(f'{prefix}: invalid or duplicate id')
            ids.add(row['id'])
            if not isinstance(row['kind'], str) or not row['kind'] or not isinstance(row['attributes'], dict):
                raise ValueError(f'{prefix}: invalid kind/attributes')
            confidence = row['confidence']
            if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError(f'{prefix}: invalid confidence')
            pages = row['source_pages']
            if not isinstance(pages, list) or not pages or any(type(p) is not int or p not in texts for p in pages):
                raise ValueError(f'{prefix}: invalid source_pages')
            quote = row['source_quote']
            if not isinstance(quote, str) or not quote.strip() or not any(quote in texts[p] for p in pages):
                raise ValueError(f'{prefix}: source_quote must be verbatim in a cited OCR page; split multi-source claims')
            if row['verification'] not in ('unverified', 'visual'):
                raise ValueError(f'{prefix}: invalid verification')
            if row['verification'] == 'visual':
                if any(read(ocr / 'ocr' / f'page-{p:03d}.json')['verification'] != 'visual' for p in pages):
                    raise ValueError(f'{prefix}: unsupported visual verification')
            count += 1
            documents += name == 'documents.jsonl'
    if not documents:
        raise ValueError('At least one document record is required')
    binding = {'schema_version': SCHEMA_VERSION, 'ocr_fingerprint': fingerprint(ocr),
               'source_sha256': manifest['source_sha256'],
               'files': {name: sha(root / name) for name in FILES}}
    if check_binding:
        if not (root / 'index_manifest.json').exists() or read(root / 'index_manifest.json') != binding:
            raise ValueError('Index is missing, stale or changed; rebuild/validate against the current OCR')
    return count, binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', type=Path, nargs='?')
    parser.add_argument('--ocr-dir', required=True, type=Path)
    parser.add_argument('--seal', action='store_true', help='Bind newly built records to current OCR after validation')
    parser.add_argument('--expected-fingerprint', help='Required with --seal: fingerprint captured before extraction')
    parser.add_argument('--fingerprint', action='store_true', help='Print current OCR fingerprint before extraction')
    args = parser.parse_args()
    try:
        if args.fingerprint:
            if args.seal or args.records is not None:
                raise ValueError('--fingerprint takes only --ocr-dir, not records or --seal')
            print(fingerprint(args.ocr_dir))
            return
        if args.records is None:
            raise ValueError('records directory is required unless using --fingerprint')
        if args.seal and (not args.expected_fingerprint or fingerprint(args.ocr_dir) != args.expected_fingerprint):
            raise ValueError('OCR changed during extraction or starting fingerprint missing; rebuild records')
        count, binding = validate_records(args.records, args.ocr_dir, check_binding=not args.seal)
        if args.seal:
            atomic(args.records / 'index_manifest.json', binding)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'{exc}\n')
    print(f'OK: {count} records, current OCR binding verified (not semantic/visual verification)')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import argparse
from bundle import validate_bundle

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    try:
        manifest = validate_bundle(args.output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'{exc}\n')
    print(f"OK: {manifest['page_count']} OCR pages (format/integrity only; not visual verification)")

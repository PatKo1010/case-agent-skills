"""Shared, dependency-free OCR integrity and job primitives."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


@contextlib.contextmanager
def lock(path):
    """Kernel releases the lock even after process termination; never unlink it."""
    with Path(path).open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Job is still running; inspect progress instead of restarting.')
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def page_errors(data, page, engine=None):
    required = ('document_id', 'page', 'image_sha256', 'raw_text', 'corrected_text',
                'blocks', 'uncertain_spans', 'ocr_engine', 'verification', 'corrections')
    if not isinstance(data, dict):
        return ['page must be an object']
    errors = [f'missing {key}' for key in required if key not in data]
    if data.get('page') != page['page'] or data.get('image_sha256') != page['sha256']:
        errors.append('page number or image hash mismatch')
    if engine is not None and data.get('ocr_engine') != engine:
        errors.append('OCR engine mismatch')
    for key in ('raw_text', 'corrected_text'):
        if not isinstance(data.get(key), str):
            errors.append(f'{key} must be text')
    for key in ('blocks', 'uncertain_spans', 'corrections'):
        if not isinstance(data.get(key), list):
            errors.append(f'{key} must be a list')
    if data.get('verification') not in ('unverified', 'visual'):
        errors.append('invalid verification')
    if data.get('raw_text') != data.get('corrected_text'):
        if data.get('verification') != 'visual' or not data.get('corrections') or not data.get('verification_note'):
            errors.append('corrections require visual verification and notes')
    return errors


def validate_bundle(root, require_complete=True):
    root = Path(root)
    manifest = read(root / 'manifest.json')
    if require_complete and manifest.get('status') != 'complete':
        raise ValueError('OCR is not complete')
    pages = manifest.get('pages', [])
    if not pages or [p['page'] for p in pages] != list(range(1, manifest['page_count'] + 1)):
        raise ValueError('Invalid manifest page coverage')
    expected = {f"page-{p['page']:03d}.json" for p in pages}
    if {p.name for p in (root / 'ocr').glob('*.json')} != expected:
        raise ValueError('Missing or unexpected OCR pages')
    for page in pages:
        image = (root / page['file']).resolve()
        if not image.is_relative_to(root.resolve()) or sha(image) != page['sha256']:
            raise ValueError(f"Page {page['page']}: image integrity failure")
        errors = page_errors(read(root / 'ocr' / f"page-{page['page']:03d}.json"), page, manifest.get('ocr_engine'))
        if errors:
            raise ValueError(f"Page {page['page']}: {'; '.join(errors)}")
    return manifest


def fingerprint(root):
    """Content, not directory/timestamps/job status, determines index freshness."""
    root = Path(root)
    manifest = validate_bundle(root)
    source = {'source_sha256': manifest['source_sha256'], 'pages': []}
    for page in manifest['pages']:
        data = read(root / 'ocr' / f"page-{page['page']:03d}.json")
        source['pages'].append(data)
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

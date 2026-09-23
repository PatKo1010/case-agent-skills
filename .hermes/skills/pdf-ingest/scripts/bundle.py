"""Shared ingest integrity and cache primitives."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic(path, data):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


@contextlib.contextmanager
def lock(path):
    with Path(path).open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Job is still running; inspect progress instead of restarting.")
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def page_errors(data, page, engine=None):
    required = (
        "document_id", "page", "image_sha256", "image_width_px", "image_height_px",
        "raw_text", "corrected_text", "blocks", "uncertain_spans",
        "extraction_method", "verification", "corrections",
    )
    if not isinstance(data, dict):
        return ["page must be an object"]
    errors = [f"missing {key}" for key in required if key not in data]
    if data.get("page") != page["page"] or data.get("image_sha256") != page["sha256"]:
        errors.append("page number or image hash mismatch")
    if data.get("image_width_px") != page.get("width_px") or data.get("image_height_px") != page.get("height_px"):
        errors.append("page image dimensions mismatch")
    if data.get("extraction_method") not in ("native_text", "paddleocr"):
        errors.append("invalid extraction_method")
    if engine is not None and data.get("extraction_method") == "paddleocr" and data.get("ocr_engine") != engine:
        errors.append("OCR engine mismatch")
    for key in ("raw_text", "corrected_text"):
        if not isinstance(data.get(key), str):
            errors.append(f"{key} must be text")
    for key in ("blocks", "uncertain_spans", "corrections"):
        if not isinstance(data.get(key), list):
            errors.append(f"{key} must be a list")
    for i, block in enumerate(data.get("blocks", [])):
        if block.get("bbox_space") != "rendered_image_px":
            errors.append(f"block {i}: bbox_space must be rendered_image_px")
        bbox = block.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            errors.append(f"block {i}: invalid bbox")
    if data.get("verification") not in ("unverified", "visual"):
        errors.append("invalid verification")
    if data.get("raw_text") != data.get("corrected_text"):
        if data.get("verification") != "visual" or not data.get("corrections") or not data.get("verification_note"):
            errors.append("corrections require visual verification and notes")
    return errors


def validate_bundle(root, require_complete=True):
    root = Path(root)
    manifest = read(root / "manifest.json")
    if require_complete and manifest.get("status") != "complete":
        raise ValueError("ingest is not complete")
    pages = manifest.get("pages", [])
    if not pages or [p["page"] for p in pages] != list(range(1, manifest["page_count"] + 1)):
        raise ValueError("invalid manifest page coverage")
    expected = {f"page-{p['page']:03d}.json" for p in pages}
    if {p.name for p in (root / "normalized").glob("*.json")} != expected:
        raise ValueError("missing or unexpected normalized pages")
    for page in pages:
        image = (root / page["file"]).resolve()
        if not image.is_relative_to(root.resolve()) or sha(image) != page["sha256"]:
            raise ValueError(f"Page {page['page']}: image integrity failure")
        errors = page_errors(
            read(root / "normalized" / f"page-{page['page']:03d}.json"),
            page,
            manifest.get("ocr_engine"),
        )
        if errors:
            raise ValueError(f"Page {page['page']}: {'; '.join(errors)}")
    return manifest


def fingerprint(root):
    root = Path(root)
    manifest = validate_bundle(root)
    source = {"source_sha256": manifest["source_sha256"], "pages": []}
    for page in manifest["pages"]:
        source["pages"].append(read(root / "normalized" / f"page-{page['page']:03d}.json"))
    return hashlib.sha256(
        json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def output_for(pdf):
    return Path(__file__).resolve().parents[4] / ("output_" + sha(pdf))

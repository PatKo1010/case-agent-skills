#!/usr/bin/env python3
"""Render a PDF and transcribe its pages using local PaddleOCR models."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path, nargs="?", help="Optional canonical output_<PDF SHA256> directory")
    models = Path.home() / ".paddlex" / "official_models"
    parser.add_argument("--det-model-dir", type=Path, default=models / "PP-OCRv6_medium_det")
    parser.add_argument("--rec-model-dir", type=Path, default=models / "PP-OCRv6_medium_rec")
    parser.add_argument("--uncertain-threshold", type=float, default=0.9)
    parser.add_argument("--native-min-chars", type=int, default=40,
                        help="Use native PDF text for a page when enough visible characters are extractable")
    parser.add_argument("--resume", action="store_true", help="Continue the same job, validating cached pages")
    args = parser.parse_args()
    if not 0 <= args.uncertain_threshold <= 1:
        parser.error("--uncertain-threshold must be between 0 and 1")
    from bundle import output_for, validate_bundle
    canonical = output_for(args.pdf)
    if args.output is not None and args.output.resolve() != canonical:
        parser.error(f"Output must be the canonical directory: {canonical}")
    args.output = canonical
    if (canonical / 'manifest.json').exists():
        try:
            manifest = validate_bundle(canonical)
            if manifest['source_sha256'] == canonical.name.removeprefix('output_'):
                print(f"Reusing complete OCR: {canonical}")
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if (canonical / 'job.json').exists():
        args.resume = True
    for directory in (args.det_model_dir, args.rec_model_dir):
        for name in ("inference.json", "inference.pdiparams", "inference.yml"):
            if not (directory / name).is_file():
                parser.error(f"Missing local model file: {directory / name}")
    run(args)


def run(args, ocr_factory=None):
    from bundle import atomic, lock, page_errors, read, sha, validate_bundle
    import time
    import uuid

    args.output.mkdir(parents=True, exist_ok=True)
    with lock(args.output / ".ingest.lock"):
        existing = [p for p in args.output.iterdir() if p.name not in (".ingest.lock", "records")]
        if existing and not args.resume:
            raise ValueError("Output is not empty. Use --resume with the same PDF/models/settings.")
        engine = {
            "name": "PaddleOCR", "version": importlib.metadata.version("paddleocr"),
            "detection_model": "PP-OCRv6_medium_det", "recognition_model": "PP-OCRv6_medium_rec",
            "device": "cpu",
            "model_sha256": {
                role + "/" + name: sha(directory / name)
                for role, directory in (("detection", args.det_model_dir), ("recognition", args.rec_model_dir))
                for name in ("inference.json", "inference.pdiparams", "inference.yml")
            },
        }
        config = {"source_sha256": sha(args.pdf), "ocr_engine": engine,
                  "uncertain_threshold": args.uncertain_threshold, "native_min_chars": args.native_min_chars, "dpi": 200,
                  "renderer_version": importlib.metadata.version("PyMuPDF"),
                  "pipeline_version": 2}
        job_path = args.output / "job.json"
        if existing:
            if not job_path.exists():
                raise ValueError("Incomplete output has no resume metadata; preserve it and request an explicit repair/rebuild decision.")
            job = read(job_path)
            if job.get("config") != config:
                raise ValueError("PDF, model, dependency version or settings changed; restore the original settings or explicitly rebuild this case.")
        else:
            job = {"job_id": str(uuid.uuid4()), "config": config, "pages": {}}
        (args.output / "records").mkdir(exist_ok=True)
        job.update(status="running", pid=os.getpid(), started_at=time.time(), error=None)
        atomic(job_path, job)
        manifest_path = args.output / "manifest.json"
        try:
            scripts = Path(__file__).resolve().parent
            if not manifest_path.exists():
                subprocess.run([sys.executable, str(scripts / "render_pdf.py"), str(args.pdf), str(args.output)], check=True)
            manifest = read(manifest_path)
            if manifest["source_sha256"] != config["source_sha256"]:
                raise ValueError("Manifest source mismatch")
            for page in manifest["pages"]:
                image = (args.output / page["file"]).resolve()
                if not image.is_relative_to(args.output.resolve()) or sha(image) != page["sha256"]:
                    raise ValueError("Rendered image changed; repair the image from the original PDF before resuming.")
            manifest.update(ocr_engine=engine, status="in_progress")
            atomic(manifest_path, manifest)
            output = args.output / "ocr"
            output.mkdir(exist_ok=True)
            pending = []
            for page in manifest["pages"]:
                path = output / f"page-{page['page']:03d}.json"
                try:
                    valid = not page_errors(read(path), page, engine)
                    valid = valid and job.get("pages", {}).get(str(page["page"]), {}).get("sha256") == sha(path)
                except (OSError, ValueError, TypeError):
                    valid = False
                if valid:
                    print(f"Page {page['page']}/{manifest['page_count']}: cached", flush=True)
                else:
                    # Preserve corrupted or manually edited artifacts for inspection.
                    if path.exists():
                        path.rename(path.with_suffix(f".replaced-{time.time_ns()}"))
                    pending.append(page)
            if pending:
                print(f"Job {job['job_id']}: {len(pending)} pages pending adaptive ingest", flush=True)
                ocr = None
                for page in pending:
                    started = time.monotonic()
                    job.update(current_page=page["page"], page_started_at=time.time())
                    atomic(job_path, job)
                    print(f"Page {page['page']}/{manifest['page_count']}: starting", flush=True)

                    data = extract_native_page(args.pdf, page, engine, args.native_min_chars)
                    if data is None:
                        if ocr is None:
                            print("Initializing PaddleOCR fallback for scanned/low-text pages", flush=True)
                            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                            if ocr_factory is None:
                                from paddleocr import PaddleOCR
                                ocr_factory = PaddleOCR
                            ocr = ocr_factory(
                                text_detection_model_name="PP-OCRv6_medium_det",
                                text_detection_model_dir=str(args.det_model_dir.resolve()),
                                text_recognition_model_name="PP-OCRv6_medium_rec",
                                text_recognition_model_dir=str(args.rec_model_dir.resolve()),
                                use_doc_orientation_classify=False, use_doc_unwarping=False,
                                use_textline_orientation=False, text_rec_score_thresh=0.0, device="cpu",
                            )
                        data = recognize_page(ocr, args, page, engine)

                    path = output / f"page-{page['page']:03d}.json"
                    atomic(path, data)
                    elapsed = time.monotonic() - started
                    job["pages"][str(page["page"])] = {"sha256": sha(path), "seconds": round(elapsed, 3)}
                    atomic(job_path, job)
                    print(
                        f"Page {page['page']}/{manifest['page_count']}: "
                        f"{data.get('extraction_method', 'unknown')} complete in {elapsed:.1f}s",
                        flush=True,
                    )
            validate_bundle(args.output, require_complete=False)
            manifest["status"] = "complete"
            atomic(manifest_path, manifest)
            job.update(status="complete", finished_at=time.time(), current_page=None)
            atomic(job_path, job)
        except BaseException as exc:
            job.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                       error=str(exc), finished_at=time.time())
            atomic(job_path, job)
            raise



def extract_native_page(pdf_path, page, engine, min_chars):
    """Return normalized native PDF text, or None when OCR fallback is needed."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pdf_page = doc.load_page(page["page"] - 1)
        raw_blocks = pdf_page.get_text("blocks")
        blocks = []
        for item in sorted(raw_blocks, key=lambda b: (b[1], b[0])):
            text = (item[4] or "").strip()
            if not text:
                continue
            blocks.append({
                "type": "paragraph",
                "text": text,
                "bbox": [float(item[0]), float(item[1]), float(item[2]), float(item[3])],
                "confidence": 1.0,
            })
        doc.close()
        text = "\n".join(block["text"] for block in blocks)
        visible_chars = sum(1 for ch in text if not ch.isspace())
        if visible_chars < min_chars:
            return None
        return {
            "document_id": pdf_path.stem,
            "page": page["page"],
            "image_sha256": page["sha256"],
            "raw_text": text,
            "corrected_text": text,
            "blocks": blocks,
            "uncertain_spans": [],
            "ocr_engine": engine,
            "extraction_method": "native_text",
            "verification": "unverified",
            "corrections": [],
            "verification_note": "Native PDF text layer extracted with PyMuPDF; no visual verification.",
            "warnings": [],
        }
    except Exception:
        return None

def recognize_page(ocr, args, page, engine):
    results = list(ocr.predict(str(args.output / page["file"])))
    if len(results) != 1:
        raise RuntimeError(f"Expected one result for page {page['page']}")
    result = results[0]
    blocks = []
    uncertain = []
    for index, (text, score, box) in enumerate(zip(result["rec_texts"], result["rec_scores"], result["rec_boxes"], strict=True)):
        block = {"type": "paragraph", "text": text, "bbox": [int(v) for v in box], "confidence": float(score)}
        blocks.append(block)
        if score < args.uncertain_threshold:
            uncertain.append({"block_index": index, **block, "reason": "low_recognition_confidence"})
    text = "\n".join(block["text"] for block in blocks)
    data = {
        "document_id": args.pdf.stem, "page": page["page"],
        "image_sha256": page["sha256"], "raw_text": text, "corrected_text": text,
        "blocks": blocks, "uncertain_spans": uncertain, "ocr_engine": engine,
        "extraction_method": "paddleocr",
        "verification": "unverified", "corrections": [],
        "verification_note": "Automatic PaddleOCR output; no visual verification or semantic layout classification.",
        "warnings": [] if blocks else ["No text detected; inspect the source image."],
    }
    return data


if __name__ == "__main__":
    main()

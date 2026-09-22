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
    parser.add_argument("output", type=Path)
    models = Path.home() / ".paddlex" / "official_models"
    parser.add_argument("--det-model-dir", type=Path, default=models / "PP-OCRv6_medium_det")
    parser.add_argument("--rec-model-dir", type=Path, default=models / "PP-OCRv6_medium_rec")
    parser.add_argument("--uncertain-threshold", type=float, default=0.9)
    parser.add_argument("--resume", action="store_true", help="Continue the same job, validating cached pages")
    args = parser.parse_args()
    if not 0 <= args.uncertain_threshold <= 1:
        parser.error("--uncertain-threshold must be between 0 and 1")
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
        existing = [p for p in args.output.iterdir() if p.name != ".ingest.lock"]
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
                  "uncertain_threshold": args.uncertain_threshold, "dpi": 200,
                  "renderer_version": importlib.metadata.version("PyMuPDF"),
                  "pipeline_version": 1}
        job_path = args.output / "job.json"
        if existing:
            if not job_path.exists():
                raise ValueError("Legacy output has no resume metadata; use a new directory once.")
            job = read(job_path)
            if job.get("config") != config:
                raise ValueError("PDF, model, dependency version or settings changed; use a new directory.")
        else:
            job = {"job_id": str(uuid.uuid4()), "config": config, "pages": {}}
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
                    raise ValueError("Rendered image changed; use a new output directory.")
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
                print(f"Job {job['job_id']}: initializing OCR; {len(pending)} pages pending", flush=True)
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(args.output.resolve() / ".paddlex-cache"))
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
                for page in pending:
                    started = time.monotonic()
                    job.update(current_page=page["page"], page_started_at=time.time())
                    atomic(job_path, job)
                    print(f"Page {page['page']}/{manifest['page_count']}: starting", flush=True)
                    data = recognize_page(ocr, args, page, engine)
                    path = output / f"page-{page['page']:03d}.json"
                    atomic(path, data)
                    elapsed = time.monotonic() - started
                    job["pages"][str(page["page"])] = {"sha256": sha(path), "seconds": round(elapsed, 3)}
                    atomic(job_path, job)
                    print(f"Page {page['page']}/{manifest['page_count']}: complete in {elapsed:.1f}s", flush=True)
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
        "verification": "unverified", "corrections": [],
        "verification_note": "Automatic PaddleOCR output; no visual verification or semantic layout classification.",
        "warnings": [] if blocks else ["No text detected; inspect the source image."],
    }
    return data


if __name__ == "__main__":
    main()

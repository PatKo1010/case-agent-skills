#!/usr/bin/env python3
"""Render a PDF and build normalized page text using native text or PaddleOCR."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    models = Path.home() / ".paddlex" / "official_models"
    parser.add_argument("--det-model-dir", type=Path, default=models / "PP-OCRv6_medium_det")
    parser.add_argument("--rec-model-dir", type=Path, default=models / "PP-OCRv6_medium_rec")
    parser.add_argument("--uncertain-threshold", type=float, default=0.9)
    parser.add_argument("--native-min-chars", type=int, default=40)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.uncertain_threshold <= 1:
        parser.error("--uncertain-threshold must be between 0 and 1")
    from bundle import output_for, validate_bundle
    canonical = output_for(args.pdf)
    if args.output is not None and args.output.resolve() != canonical:
        parser.error(f"Output must be canonical: {canonical}")
    args.output = canonical
    if (canonical / "manifest.json").exists():
        try:
            manifest = validate_bundle(canonical)
            if manifest["source_sha256"] == canonical.name.removeprefix("output_"):
                print(f"Reusing complete ingest: {canonical}")
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if (canonical / "job.json").exists():
        args.resume = True
    run(args)


def run(args, ocr_factory=None):
    from bundle import atomic, lock, page_errors, read, sha, validate_bundle
    import time
    import uuid

    args.output.mkdir(parents=True, exist_ok=True)
    with lock(args.output / ".ingest.lock"):
        existing = [p for p in args.output.iterdir() if p.name not in (
            ".ingest.lock", "layout", "structure", "records"
        )]
        engine = {
            "name": "PaddleOCR",
            "version": importlib.metadata.version("paddleocr"),
            "detection_model": "PP-OCRv6_medium_det",
            "recognition_model": "PP-OCRv6_medium_rec",
            "device": "cpu",
        }
        config = {
            "source_sha256": sha(args.pdf),
            "ocr_engine": engine,
            "uncertain_threshold": args.uncertain_threshold,
            "native_min_chars": args.native_min_chars,
            "dpi": 200,
            "pipeline_version": 3,
        }
        job_path = args.output / "job.json"
        if existing:
            if not job_path.exists():
                raise ValueError("Incomplete output has no resume metadata")
            job = read(job_path)
            if job.get("config") != config:
                raise ValueError("PDF or ingest settings changed; explicitly rebuild this case")
        else:
            job = {"job_id": str(uuid.uuid4()), "config": config, "pages": {}}

        job.update(status="running", pid=os.getpid(), started_at=time.time(), error=None)
        atomic(job_path, job)
        manifest_path = args.output / "manifest.json"
        try:
            scripts = Path(__file__).resolve().parent
            if not manifest_path.exists():
                subprocess.run(
                    [sys.executable, str(scripts / "render_pdf.py"), str(args.pdf), str(args.output)],
                    check=True,
                )
            manifest = read(manifest_path)
            manifest.update(ocr_engine=engine, status="in_progress")
            atomic(manifest_path, manifest)
            output = args.output / "normalized"
            output.mkdir(exist_ok=True)

            pending = []
            for page in manifest["pages"]:
                path = output / f"page-{page['page']:03d}.json"
                try:
                    valid = not page_errors(read(path), page, engine)
                    valid = valid and job.get("pages", {}).get(str(page["page"]), {}).get("sha256") == sha(path)
                except (OSError, ValueError, TypeError):
                    valid = False
                if not valid:
                    pending.append(page)

            ocr = None
            for page in pending:
                started = time.monotonic()
                image = args.output / page["file"]
                data = extract_native_page(
                    args.pdf, page, manifest["dpi"], args.native_min_chars
                )
                if data is None:
                    if ocr is None:
                        for directory in (args.det_model_dir, args.rec_model_dir):
                            for name in ("inference.json", "inference.pdiparams", "inference.yml"):
                                if not (directory / name).is_file():
                                    raise ValueError(f"Missing local OCR model file: {directory / name}")
                        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                        if ocr_factory is None:
                            from paddleocr import PaddleOCR
                            ocr_factory = PaddleOCR
                        ocr = ocr_factory(
                            text_detection_model_name="PP-OCRv6_medium_det",
                            text_detection_model_dir=str(args.det_model_dir.resolve()),
                            text_recognition_model_name="PP-OCRv6_medium_rec",
                            text_recognition_model_dir=str(args.rec_model_dir.resolve()),
                            use_doc_orientation_classify=False,
                            use_doc_unwarping=False,
                            use_textline_orientation=False,
                            text_rec_score_thresh=0.0,
                            device="cpu",
                        )
                    data = recognize_page(ocr, args, page, engine, image)

                path = output / f"page-{page['page']:03d}.json"
                atomic(path, data)
                job["pages"][str(page["page"])] = {
                    "sha256": sha(path),
                    "seconds": round(time.monotonic() - started, 3),
                    "method": data["extraction_method"],
                }
                atomic(job_path, job)

            validate_bundle(args.output, require_complete=False)
            manifest["status"] = "complete"
            atomic(manifest_path, manifest)
            job.update(status="complete", finished_at=time.time(), current_page=None)
            atomic(job_path, job)
        except BaseException as exc:
            job.update(status="failed", error=str(exc), finished_at=time.time())
            atomic(job_path, job)
            raise


def extract_native_page(pdf_path, page_meta, dpi, min_chars):
    try:
        import fitz
        scale = dpi / 72.0
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_meta["page"] - 1)
            raw_blocks = page.get_text("blocks")
        blocks = []
        for item in sorted(raw_blocks, key=lambda b: (b[1], b[0])):
            text = (item[4] or "").strip()
            if not text:
                continue
            blocks.append({
                "type": "paragraph",
                "text": text,
                "bbox": [float(item[0] * scale), float(item[1] * scale),
                         float(item[2] * scale), float(item[3] * scale)],
                "bbox_space": "rendered_image_px",
                "confidence": 1.0,
            })
        text = "\n".join(b["text"] for b in blocks)
        if sum(1 for ch in text if not ch.isspace()) < min_chars:
            return None
        return {
            "document_id": pdf_path.stem,
            "page": page_meta["page"],
            "image_sha256": page_meta["sha256"],
            "image_width_px": page_meta["width_px"],
            "image_height_px": page_meta["height_px"],
            "raw_text": text,
            "corrected_text": text,
            "blocks": blocks,
            "uncertain_spans": [],
            "ocr_engine": None,
            "extraction_method": "native_text",
            "verification": "unverified",
            "corrections": [],
            "verification_note": "Native PDF text extracted with PyMuPDF; no visual verification.",
            "warnings": [],
        }
    except Exception:
        return None


def recognize_page(ocr, args, page_meta, engine, image):
    results = list(ocr.predict(str(image)))
    if len(results) != 1:
        raise RuntimeError(f"Expected one OCR result for page {page_meta['page']}")
    result = results[0]
    blocks, uncertain = [], []
    for index, (text, score, box) in enumerate(zip(
        result["rec_texts"], result["rec_scores"], result["rec_boxes"], strict=True
    )):
        block = {
            "type": "paragraph",
            "text": text,
            "bbox": [int(v) for v in box],
            "bbox_space": "rendered_image_px",
            "confidence": float(score),
        }
        blocks.append(block)
        if score < args.uncertain_threshold:
            uncertain.append({"block_index": index, **block, "reason": "low_recognition_confidence"})
    text = "\n".join(b["text"] for b in blocks)
    return {
        "document_id": args.pdf.stem,
        "page": page_meta["page"],
        "image_sha256": page_meta["sha256"],
        "image_width_px": page_meta["width_px"],
        "image_height_px": page_meta["height_px"],
        "raw_text": text,
        "corrected_text": text,
        "blocks": blocks,
        "uncertain_spans": uncertain,
        "ocr_engine": engine,
        "extraction_method": "paddleocr",
        "verification": "unverified",
        "corrections": [],
        "verification_note": "Automatic PaddleOCR output; no visual verification.",
        "warnings": [] if blocks else ["No text detected; inspect source image."],
    }


if __name__ == "__main__":
    main()

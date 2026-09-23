#!/usr/bin/env python3
"""Run PP-DocLayoutV2 on rendered case pages."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pdf-ingest" / "scripts"))
from bundle import atomic, read, sha, validate_bundle


def result_json(result):
    payload = result.json
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Unsupported PaddleOCR layout result")
    return payload.get("res", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    case_dir = args.case_dir.resolve()
    manifest = validate_bundle(case_dir)
    out = case_dir / "layout"
    out.mkdir(exist_ok=True)

    local_default = Path.home() / ".paddlex" / "official_models" / "PP-DocLayoutV2"
    model_dir = args.model_dir
    if model_dir is None and local_default.exists():
        model_dir = local_default

    from paddleocr import LayoutDetection
    kwargs = {"model_name": "PP-DocLayoutV2", "device": args.device}
    if model_dir is not None:
        kwargs["model_dir"] = str(model_dir.resolve())
    model = LayoutDetection(**kwargs)

    page_files = {}
    for page in manifest["pages"]:
        image = case_dir / page["file"]
        results = list(model.predict(
            str(image), batch_size=1, threshold=args.threshold, layout_nms=True
        ))
        if len(results) != 1:
            raise RuntimeError(f"Expected one layout result for page {page['page']}")
        payload = result_json(results[0])
        regions = []
        for order, box in enumerate(payload.get("boxes", [])):
            coordinate = box.get("coordinate")
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 4:
                continue
            regions.append({
                "id": f"p{page['page']:03d}-r{order:03d}",
                "cls_id": int(box.get("cls_id", -1)),
                "label": str(box.get("label", "unknown")),
                "score": float(box.get("score", 0.0)),
                "bbox": [float(v) for v in coordinate],
                "reading_order": order,
            })
        data = {
            "page": page["page"],
            "image_sha256": page["sha256"],
            "model_name": "PP-DocLayoutV2",
            "model_version": importlib.metadata.version("paddleocr"),
            "threshold": args.threshold,
            "regions": regions,
        }
        path = out / f"page-{page['page']:03d}.json"
        atomic(path, data)
        page_files[str(page["page"])] = sha(path)

    layout_manifest = {
        "schema_version": 1,
        "source_sha256": manifest["source_sha256"],
        "model_name": "PP-DocLayoutV2",
        "paddleocr_version": importlib.metadata.version("paddleocr"),
        "threshold": args.threshold,
        "pages": page_files,
    }
    atomic(out / "layout_manifest.json", layout_manifest)
    print(f"OK: layout analyzed for {manifest['page_count']} pages")


if __name__ == "__main__":
    main()

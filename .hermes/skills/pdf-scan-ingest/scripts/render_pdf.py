#!/usr/bin/env python3
import hashlib
import sys
from pathlib import Path
from bundle import atomic

try:
    import pymupdf
except ImportError:
    raise SystemExit("PyMuPDF is required. Install it with: python -m pip install PyMuPDF")

if len(sys.argv) != 3:
    raise SystemExit("usage: render_pdf.py INPUT.pdf OUTPUT_DIR")
source, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
pages = out / "page"
pages.mkdir(parents=True, exist_ok=True)
rendered = []
with pymupdf.open(source) as document:
    for page_number, page in enumerate(document, 1):
        image_path = pages / f"page-{page_number}.png"
        page.get_pixmap(dpi=200, colorspace=pymupdf.csRGB, alpha=False).save(image_path)
        rendered.append({
            "page": page_number,
            "file": image_path.relative_to(out).as_posix(),
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        })
manifest = {
    "source": source.name,
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "renderer": "PyMuPDF",
    "dpi": 200,
    "page_count": len(rendered),
    "pages": rendered,
}
atomic(out / "manifest.json", manifest)
print(out / "manifest.json")

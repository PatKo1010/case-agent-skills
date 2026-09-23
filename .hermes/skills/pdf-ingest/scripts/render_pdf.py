#!/usr/bin/env python3
import hashlib
import sys
from pathlib import Path
from bundle import atomic

try:
    import pymupdf
except ImportError:
    raise SystemExit("PyMuPDF is required")

if len(sys.argv) != 3:
    raise SystemExit("usage: render_pdf.py INPUT.pdf OUTPUT_DIR")

source, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
pages_dir = out / "page"
pages_dir.mkdir(parents=True, exist_ok=True)
rendered = []
dpi = 200
with pymupdf.open(source) as document:
    for page_number, page in enumerate(document, 1):
        image_path = pages_dir / f"page-{page_number}.png"
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        pix.save(image_path)
        rendered.append({
            "page": page_number,
            "file": image_path.relative_to(out).as_posix(),
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "width_px": pix.width,
            "height_px": pix.height,
        })
manifest = {
    "source": source.name,
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "renderer": "PyMuPDF",
    "dpi": dpi,
    "page_count": len(rendered),
    "pages": rendered,
}
atomic(out / "manifest.json", manifest)
print(out / "manifest.json")

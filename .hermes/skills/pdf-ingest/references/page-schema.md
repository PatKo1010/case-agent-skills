# Normalized page schema

Each `normalized/page-NNN.json` represents one physical page.

Required page fields:
- `document_id`
- `page`
- `image_sha256`
- `image_width_px`
- `image_height_px`
- `raw_text`
- `corrected_text`
- `blocks`
- `uncertain_spans`
- `extraction_method`: `native_text` or `paddleocr`
- `verification`
- `corrections`

Every block contains:
- `type`: ingest emits `paragraph`
- `text`
- `bbox`: `[xmin, ymin, xmax, ymax]`
- `bbox_space`: always `rendered_image_px`
- `confidence`

Native PDF coordinates are converted from PDF points to rendered-image pixels using the manifest DPI. PaddleOCR boxes already use rendered-image pixels.

This coordinate normalization is required so downstream layout regions and source text can be matched geometrically.

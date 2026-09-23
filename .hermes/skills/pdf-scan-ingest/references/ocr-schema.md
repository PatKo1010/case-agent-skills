# Normalized page schema

The historical directory name is `ocr/`, but each page JSON is now a **normalized page artifact** and can originate from native PDF text or PaddleOCR.

Required fields: `document_id`, `page`, `image_sha256`, `raw_text`, `corrected_text`, `blocks`, `uncertain_spans`, `ocr_engine`, and `verification`.

Recommended field:
- `extraction_method`: `native_text` or `paddleocr`

Each block contains:
- `type` (ingest normally emits `paragraph`; semantic layout classification belongs to document-structure)
- `text`
- optional `bbox`
- `confidence` from 0 to 1

For native text, bbox coordinates are PDF page coordinates and confidence is extraction confidence rather than OCR probability. For PaddleOCR, bbox is in rendered-image pixels and confidence is recognition confidence.

`verification: unverified` means no visual review has occurred. Native extraction is not equivalent to visual verification. An empty/low-text page can trigger OCR fallback and still requires inspection when important evidence is expected.

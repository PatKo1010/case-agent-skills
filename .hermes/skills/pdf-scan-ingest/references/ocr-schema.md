# OCR page schema

Required fields: `document_id`, `page`, `image_sha256`, `raw_text`, `corrected_text`, `blocks`, `uncertain_spans`, `ocr_engine`, and `verification`.

Each block contains `type` (`title`, `paragraph`, `table`, `checkbox`, `stamp`, or `handwriting`), `text`, optional `bbox`, and `confidence` from 0 to 1.

PaddleOCR emits one recognized line per `paragraph` block, without semantic classification. `bbox` is `[x_min, y_min, x_max, y_max]` in rendered-image pixels. Reading order is the engine's order; tables and checkboxes require separate interpretation. Confidence measures recognition, not factual accuracy. `ocr_engine` records engine version, model names, and weight hashes. `verification: unverified` means no visual review has occurred. An empty page has a warning and still needs inspection; high-confidence text can also be wrong.

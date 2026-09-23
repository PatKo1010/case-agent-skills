# Layout schema

Each `layout/page-NNN.json` contains:
- `page`
- `image_sha256`
- `model_name`
- `regions`

Each region contains:
- `id`
- `cls_id`
- `label`
- `score`
- `bbox`: rendered-image pixel coordinates
- `reading_order`

PP-DocLayoutV2 labels may include document_title, paragraph_title, text, table, image, header, footer, page_number, figure_title, seal, chart and other model-defined categories.

The layout layer contains geometry/classification only. Text is attached downstream by matching normalized source blocks to regions.

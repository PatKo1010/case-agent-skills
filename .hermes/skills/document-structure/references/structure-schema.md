# Document structure schema

## documents.jsonl
- id
- title
- start_page
- end_page
- boundary_confidence
- boundary_rule
- source_pages

## pages.jsonl
- page
- document_id
- page_role: document_start | continuation | table_page | qa_page | figure_page | unknown
- block_ids
- layout_labels

## blocks.jsonl
- id
- document_id
- page
- type: title | heading | narrative | table | qa | figure | header | footer | seal | other
- text
- bbox
- confidence
- layout_label
- layout_score
- source_block_ids
- parent_block_id
- verification

The structure layer may classify organization, but it must not paraphrase source text or infer case semantics.

# Case agent skills

同一個 Hermes 對話負責 PDF 辨識、結構化與來源問答。Python 僅負責查找、OCR 和驗證；不另行啟動模型 API 或流程控制程式。

## 統一輸出

以 PDF 原始位元組的完整 SHA-256 作為目錄名稱，固定放在專案根目錄：

```text
output_<64位SHA256>/
├── page/                  # 所有 PNG 頁面
├── ocr/                   # page-001.json 等 OCR 輸出
├── records/               # 四個 JSONL、摘要、index_manifest.json、抽取草稿
├── job.json
└── manifest.json
```

執行時也可能有 `.ingest.lock` 作業鎖檔案。`output_*/` 已加入 Git 忽略規則，不上傳案件資料。

同一份內容改名仍使用同一目錄；內容變動則使用另一目錄。腳本以自身專案位置決定根目錄，不受終端目前目錄影響。驗證器中的 `OCR_DIR` 指整個 `output_<SHA256>`，不是內部的 `ocr/`。

## Hermes 入口與重用

每次提出 PDF 問題，Hermes 先執行：

```bash
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/locate_case.py INPUT.pdf
```

此唯讀工具回傳實際路徑、驗證結果與 `next_skill`：

- OCR、索引皆有效：直接載入 `grounded-case-qa`，不再執行前兩個技能。
- OCR 有效、索引缺少或過期：只執行 `case-record-structure`，再進 QA。
- OCR 缺少、不完整或損壞：先執行 `pdf-scan-ingest`，再完成所需階段。

目錄存在不等於可重用；必須核對來源 PDF、OCR 完整性與索引來源指紋。使用者只要求 OCR 或索引時，依該限定範圍停止。專案 `AGENTS.md` 與三個技能已規定這個入口；舊 Hermes 對話請重新載入技能。

## OCR

```bash
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py INPUT.pdf
```

自動計算輸出目錄。已有完整有效 OCR 時直接重用，不載入 PaddleOCR 模型；已有 `job.json` 的中斷作業自動續跑，也可明確使用 `--resume`。不同模型或設定的中斷作業會停止，避免混用結果。需重新辨識已完成資料時應先明確決定如何保留舊成果，不另創任意命名目錄。

使用 PyMuPDF 200 DPI 與本機 PaddleOCR PP-OCRv6 CPU 模型。長作業由 Hermes 終端工作階段執行並持續查看進度。工具等待逾時不代表 OCR 已停止，作業鎖會拒絕同時寫入。

## 結構化與 QA

Hermes 在 `output_<SHA256>/records/` 建立草稿與五個產出，再依技能捕捉的來源指紋封存：

```bash
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py --ocr-dir OUTPUT_DIR --fingerprint
# Hermes 完成抽取與寫檔後：
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py OUTPUT_DIR/records --ocr-dir OUTPUT_DIR --seal --expected-fingerprint STARTING_FINGERPRINT
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py OUTPUT_DIR/records --ocr-dir OUTPUT_DIR
```

有效既有索引直接重用。OCR 修正會使索引指紋過期，必須重新核對與修正記錄，不能只重封存舊資料。QA 先查索引，再核對原文與圖片，回答附頁碼；未經原圖核對的內容保留 `unverified`。驗證通過不等於 OCR 或所有解釋必然正確。

舊 `ocr_output/`、`records/` 資料不會自動覆寫或搬移；新規則只自動尋找內容雜湊目錄。若要重用舊資料，需先核對來源並遷移成上述配置，再驗證。

## 測試

```bash
.venv/bin/python -m unittest discover -s tests -v
```

測試涵蓋內容雜湊、索引快取失效、PNG 目錄配置及中斷續跑。模型使用替身，不呼叫外部模型服務。

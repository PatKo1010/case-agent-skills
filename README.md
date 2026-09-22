# Case agent

## 在 Hermes 詢問 PDF

在此專案目錄啟動 Hermes，直接提出 PDF 問題。由同一個 Hermes／Gemma 對話依序執行：

1. `pdf-scan-ingest`：檢查既有 OCR，必要時執行辨識。
2. `case-record-structure`：由 Hermes 讀取 OCR、建立索引，執行來源驗證。
3. `grounded-case-qa`：由 Hermes 查詢索引、核對原文，回答並附頁碼。

專案 `AGENTS.md` 提供 PDF 問題的入口規則；三個技能分別規定下一階段的載入、執行與完成條件。即使只是問一家門市，也必須先有有效索引。OCR 或索引已存在時先驗證，可重用則不重做。只有明確要求單獨 OCR／文字匯出或索引建立，才停在對應階段。

例如，接續現有 OCR 可以對 Hermes 說：

> 使用 work/case_7eleven_store/ocr 的 OCR，依 pdf-scan-ingest → case-record-structure → grounded-case-qa 完成處理，回答筆錄記載的 7-ELEVEN 門市是哪一家。已有完整 OCR 請驗證後重用。

技能透過 `skill_view` 載入；工具不可用時直接讀取專案中的對應 SKILL.md。載入技能後須執行，不是只說「接下來會處理」。如果 Hermes 已在舊對話載入先前版本，請重新載入這三個技能或開啟新對話。Hermes 必須允許載入專案規則；啟用忽略規則的模式時，請明確指定技能。

Python 腳本只做 OCR、資料完整性與索引來源驗證。結構化與回答使用 Hermes 當前模型，不另行呼叫模型 API，不需要額外設定 CASE_BASE_URL／CASE_MODEL。

這是 Hermes 的技能執行規則；驗證程式可以拒絕無效資料，但技能文字本身無法保證模型永不跳步。驗收一次真實對話時，應看到三階段進度、兩種驗證命令成功、索引產物，以及附頁碼的最終答案。未完成實際工作時不得宣告階段完成。

## OCR 與斷點續跑

在專案根目錄：

```bash
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py input/case.pdf work/paddleocr
# 中斷後使用同一份 PDF 與輸出目錄：
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py input/case.pdf work/paddleocr --resume
```

使用 PyMuPDF 200 DPI、PaddleOCR PP-OCRv6 與 CPU，預設本機模型位於 `~/.paddlex/official_models/`。長作業使用 Hermes 終端工具的背景／工作階段功能並持續查看進度；工具等待逾時不代表 OCR 程序已停止。

`job.json` 保存工作 ID、PID、設定與頁面耗時；OS 作業鎖防止重複執行。續跑驗證 PDF、模型、依賴版本與設定，跳過有效完成頁面，補跑缺失或損壞頁面。舊中斷資料若缺少 `job.json`，需用新目錄重建；已完成或人工修正的 OCR 可直接驗證後交給結構化技能，無須重跑。

```bash
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/validate_ocr_bundle.py OCR_DIR
```

## 索引來源驗證

Hermes 建立索引前先取得來源指紋：

```bash
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py --ocr-dir OCR_DIR --fingerprint
```

接著由 Hermes 建立 `documents.jsonl`、`entities.jsonl`、`events.jsonl`、`evidence.jsonl` 與 `case_summary.md`。詳細欄位見結構化技能。完成後使用先前取得的指紋封存：

```bash
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir OCR_DIR --seal --expected-fingerprint STARTING_FINGERPRINT
.venv/bin/python .hermes/skills/case-record-structure/scripts/validate_case_records.py RECORD_DIR --ocr-dir OCR_DIR
```

驗證程式建立 `index_manifest.json`，綁定 OCR 指紋、結構版本與五個輸出的雜湊。QA 前須再次通過驗證。OCR 修正後重新抽取相關記錄，不能只更新舊索引的指紋。

格式與引文驗證不等於辨識正確。未核對原圖的資料保持 `unverified`；可先建立暫定索引，但答案須揭露限制。重要人名、日期、金額、帳號及低信心內容仍需原圖核對。

## 測試與既有資料

```bash
.venv/bin/python -m unittest discover -s tests -v
```

測試包含合成 PDF 實際渲染、以模型替身模擬 OCR 中斷續跑、作業鎖、指紋封存、引文及來源完整性檢查；不呼叫模型 API，也不證明 Hermes 已在真實對話遵循三階段。

既有 `work/`、`evaluation/` 與執行紀錄保留，供比較或重用已完成 OCR。它們不代表目前來源的索引已通過驗證。

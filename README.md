# Case agent skills

同一個 Hermes 對話負責 PDF 辨識、結構化與來源問答。Python 僅負責查找、OCR 和驗證；不另行啟動模型 API 或流程控制程式。

## Skills 簡介

| 技能 | 用途 | 主要產出 |
| --- | --- | --- |
| [pdf-scan-ingest](.hermes/skills/pdf-scan-ingest/SKILL.md) | 逐頁 adaptive ingest：優先使用 PyMuPDF native text，文字不足時才 fallback 到 PaddleOCR；保留頁碼、bbox、confidence 與 verification。 | `page/`、`ocr/` normalized page JSON、`job.json`、`manifest.json` |
| [document-structure](.hermes/skills/document-structure/SKILL.md) | 建立 lightweight document structure：document boundary、page、title，以及 narrative/table/Q&A block。 | `structure/pages.jsonl`、`documents.jsonl`、`blocks.jsonl`、`structure_manifest.json` |
| [case-record-structure](.hermes/skills/case-record-structure/SKILL.md) | 由 Hermes 讀取已驗證的 document structure，再抽取人物／組織、事件、證據與衝突等案件語意索引。 | `records/` 下的四個 JSONL、`case_summary.md`、`index_manifest.json` |
| [grounded-case-qa](.hermes/skills/grounded-case-qa/SKILL.md) | 先查 semantic index，以 structure 導航，再回 normalized page / 原圖驗證並回答。 | 附來源頁碼及不確定性說明的回答 |

首次處理依序執行 `pdf-scan-ingest → document-structure → case-record-structure → grounded-case-qa`。每一層都有 validator；有效快取可從最早缺失或過期的 layer 繼續。

## 環境建立

本機目前使用 **macOS Apple Silicon（arm64）、Python 3.11.15、CPU OCR**。`requirement.txt` 固定目前安裝的直接依賴版本，建議使用 Python 3.11。腳本使用 Unix 的 `fcntl` 作業鎖，原生 Windows 不支援；Linux／WSL 尚未在本專案驗證，需確認對應 PaddlePaddle 套件可用。

### 1. 準備系統工具與 Hermes

需要 Python 3.11、pip／venv，以及 Poppler 的 `pdfinfo`、`pdftotext`。Poppler 用於技能的 PDF 文字層檢查，PNG 轉檔由 PyMuPDF 完成。

macOS 已安裝 Homebrew 時：

```bash
brew install python@3.11 poppler
```

Ubuntu／Debian 可用 `sudo apt-get install poppler-utils` 安裝 Poppler；Python 3.11 請依系統版本準備。

Hermes Agent 需另外安裝並設定可用模型，例如目前使用的 Gemma。它使用自己的執行環境，不列入本專案 Python 依賴。

### 2. 統一安裝 Python 依賴

在專案根目錄執行；已有可用 `.venv` 時可略過第一行：

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirement.txt
```

清單包含 PyMuPDF、PaddlePaddle CPU 與 PaddleOCR；間接依賴交由 pip 解析，並非跨平台完整鎖定檔。若目標平台找不到 PaddlePaddle 套件，先依 [PaddleOCR 官方安裝說明](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/quick_start.en.md)確認平台支援，再調整版本。

### 3. 準備 OCR 模型權重

Python 套件與模型權重分開安裝。首次可在有網路的環境執行以下初始化，下載所需模型：

```bash
.venv/bin/python - <<'PY'
from paddleocr import PaddleOCR

PaddleOCR(
    text_detection_model_name="PP-OCRv6_medium_det",
    text_recognition_model_name="PP-OCRv6_medium_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu",
)
print("OCR models initialized.")
PY
```

模型選項見 [PaddleOCR 官方 OCR 文件](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md)。未自訂 PaddleX 快取時，預設模型位置為：

```text
~/.paddlex/official_models/PP-OCRv6_medium_det/
~/.paddlex/official_models/PP-OCRv6_medium_rec/
```

每個目錄須包含 `inference.json`、`inference.pdiparams`、`inference.yml`。離線環境可先複製完整模型目錄；存於其他位置時，向 `ingest_pdf.py` 傳入 `--det-model-dir` 與 `--rec-model-dir`。專案 OCR 腳本要求權重已存在，不在辨識途中自動下載。

### 4. 檢查環境並啟動 Hermes

```bash
.venv/bin/python -m pip check
.venv/bin/python -c "import pymupdf, paddle, paddleocr; print('Python imports OK')"
pdfinfo -v
pdftotext -v
.venv/bin/python -m unittest discover -s tests -v
hermes
```

從專案根目錄啟動 Hermes，允許載入 `AGENTS.md` 與 `.hermes/skills/`，再提供 PDF 路徑與問題。結構化與 QA 使用 Hermes 當前模型，不需要本專案另設 API 位址或金鑰。測試使用模型替身，不呼叫 Gemma API，也不代表實際 OCR 品質已驗證。

`.venv/`、快取與案件輸出不進 Git；`requirement.txt` 是可提交的安裝清單，不是依賴套件本身。

## 統一輸出

以 PDF 原始位元組的完整 SHA-256 作為目錄名稱，固定放在專案根目錄：

```text
output_<64位SHA256>/
├── page/                  # 所有 PNG 頁面
├── ocr/                   # backward-compatible 名稱；逐頁 normalized native/OCR JSON
├── structure/             # pages/documents/blocks + structure_manifest
├── records/               # semantic case index、摘要、index_manifest.json、抽取草稿
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

- ingest、document structure、semantic records 皆有效：直接載入 `grounded-case-qa`。
- ingest + structure 有效、records 缺少或過期：從 `case-record-structure` 繼續。
- ingest 有效、structure 缺少或過期：從 `document-structure` 繼續。
- ingest 缺少、不完整或損壞：從 `pdf-scan-ingest` 開始。

目錄存在不等於可重用；必須核對來源 PDF、OCR 完整性與索引來源指紋。使用者只要求 OCR 或索引時，依該限定範圍停止。專案 `AGENTS.md` 與三個技能已規定這個入口；舊 Hermes 對話請重新載入技能。

## OCR

```bash
.venv/bin/python .hermes/skills/pdf-scan-ingest/scripts/ingest_pdf.py INPUT.pdf
```

自動計算輸出目錄。已有完整有效 OCR 時直接重用，不載入 PaddleOCR 模型；已有 `job.json` 的中斷作業自動續跑，也可明確使用 `--resume`。不同模型或設定的中斷作業會停止，避免混用結果。需重新辨識已完成資料時應先明確決定如何保留舊成果，不另創任意命名目錄。

每一頁先嘗試 PyMuPDF native text；native text 不足時才初始化本機 PaddleOCR PP-OCRv6 CPU 模型。頁面仍以 PyMuPDF 200 DPI render 保留視覺核對來源。長作業由 Hermes 終端工作階段執行並持續查看進度。工具等待逾時不代表 OCR 已停止，作業鎖會拒絕同時寫入。

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

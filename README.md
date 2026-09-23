# Case agent skills

Hermes PDF pipeline:

```
pdf-ingest
  ↓
document-layout
  ↓
document-structure
  ↓
grounded-case-qa
```

## Skills

| Skill | Responsibility | Main output |
| --- | --- | --- |
| `pdf-ingest` | Render PDF, prefer native text per page, PaddleOCR fallback, normalize bbox coordinates | `page/`, `normalized/`, `manifest.json` |
| `document-layout` | PP-DocLayoutV2 visual region detection + reading order | `layout/page-NNN.json`, `layout_manifest.json` |
| `document-structure` | Align text to layout; infer document boundaries, page roles and hierarchy | `structure/*.jsonl` |
| `case-record-structure` (optional, explicit request only) | Hermes semantic extraction: documents/entities/events/evidence/conflicts | `records/*.jsonl` |
| `grounded-case-qa` | Source-grounded question answering | cited final answer |

## Demo 問答

以下五組問答選自 [case_answers_20.json](case_answers_20.json)，以《合成偵查卷宗－9頁合併》展示不同查詢情境。回答與來源標記保留該檔內容，屬於 demo 輸出範例，不代表已通過 golden set 評分；頁碼為實體 PDF 頁碼。

### 1. 投資話術檢索（原第 5 題）

**問題：** 告訴人何時、透過何種通訊工具接觸投資邀約？對方自稱什麼身分，並以何種投資內容及報酬吸引他？

**回答：** 告訴人於114年11月9日經由LINE接獲自稱「UCT量化套利平台投資顧問黃經理」之人邀約，投資虛擬貨幣USDT套利，佯稱每月可獲取8%-12%之高額報酬

**來源：** 第 4 頁，區塊 `p004-r006`。

### 2. 提款資訊與未知身分（原第 7 題）

**問題：** 移送書記載，款項在什麼時間區間、何處、分幾筆遭提領？是否已確認提款人的身分？

**回答：** 款項於114年11月10日19時03分起至19時28分止，於臺北市中山區林森北路某自動櫃員機分4筆全數提領。提款人身分不詳

**來源：** 第 4 頁，區塊 `p004-r006`。

### 3. 附件清單讀取（原第 9 題）

**問題：** 證據及附件清單共列出幾項？其中銀行開戶資料及交易明細的提供來源、頁數與正影本狀態為何？

**回答：** 證據及附件清單共列出13項。其中銀行開戶資料及交易明細由中國信託商業銀行函覆提供，共23頁，為影本

**來源：** 第 5 頁，區塊 `p005-r004`。

### 4. 區分調查研判與定論（原第 17 題）

**問題：** 職務報告為何認為被告也可能是詐欺被害人？報告對其是否具有幫助犯主觀犯意，採取什麼立場？

**回答：** 職務報告認為被告於告訴人匯款前19日已掛失及報案，時序合理，因此有可能亦為詐欺被害人。對於是否具備幫助犯主觀犯意，採取移送偵辦由檢察官調查之立場

**來源：** 第 6 頁，區塊 `p006-r012`。

### 5. 辨識待釐清的交易疑點（原第 19 題）

**問題：** 卷內一方面記載帳戶已掛失止付並列為警示帳戶，另一方面記載後續匯款與提款。請列出相關日期，並說明現有內容是否足以解釋兩者如何並存。

**回答：** 帳戶於114年10月22日早晨掛失並通報為警示帳戶，但11月10日仍有匯款進入並遭提領。現有內容僅記載事實，不足以解釋警示帳戶如何仍能進行交易

**來源：** 第 6 頁，區塊 `p006-r010`。

## Install

Python 3.11:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirement.txt
```

PaddleOCR PP-OCRv6 weights are used only for pages without enough native text.

### Initialize PP-DocLayoutV2 once

The layout skill uses PaddleOCR's `LayoutDetection(model_name="PP-DocLayoutV2")`. The official model may download on first use. For an offline Hermes demo, initialize it in advance:

```bash
.venv/bin/python - <<'PY'
from paddleocr import LayoutDetection
LayoutDetection(model_name="PP-DocLayoutV2", device="cpu")
print("PP-DocLayoutV2 initialized")
PY
```

If the local model exists at `~/.paddlex/official_models/PP-DocLayoutV2`, the layout script automatically uses it.

## Output

```text
output_<PDF_SHA256>/
├── page/
├── normalized/
├── layout/
├── structure/
├── records/  (optional)
├── job.json
└── manifest.json
```

## Entry point

```bash
.venv/bin/python .hermes/skills/pdf-ingest/scripts/locate_case.py INPUT.pdf
```

The locator validates ingest, layout and structure, then routes directly to grounded-case-qa. It does not inspect or require records/. Missing or stale semantic indexes do not block answering.

## Design

The responsibility split is deliberate:

- **pdf-ingest:** what text is on the physical page?
- **document-layout:** what visual regions are present?
- **document-structure:** how are those regions organized into documents/pages/blocks?
- **case-record-structure (optional):** what do those records mean for the case?
- **grounded-case-qa:** what does the source-supported answer say?

This avoids asking the LLM to simultaneously solve OCR, layout recognition, hierarchy reconstruction and case reasoning.

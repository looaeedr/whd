---
name: improve-codebase-architecture
description: Use when 需要掃描程式碼庫的架構摩擦、找出 deep module 深化機會，或使用者要求「掃描深模組」時。
disable-model-invocation: true
---

# 掃描深模組：改善程式碼庫架構

找出架構摩擦並提出 **深化機會（deepening opportunities）**：把淺模組（shallow module）重構成深模組（deep module），目標是提高可測試性、AI 可導航性與修改局部性。

## 語言規則（最高優先，強制）

<LANGUAGE-GATE>
**所有給使用者看的內容一律使用繁體中文（zh-TW / zh-Hant-TW）。**

適用範圍包含：

- 對話中的進度更新、掃描結論、候選項目名稱、問題、解法、收益與建議。
- HTML 報告的 `<title>`、標題、徽章、欄位名稱、圖例、註解、CTA。
- Mermaid、SVG、手工圖中的節點文字、箭頭註解與圖中標籤。
- 最高優先建議與最後交付訊息。

只有下列內容可保留原文：

- 實際程式識別字：類別、函式、變數、常數。
- 檔名、路徑、命令、套件與框架名稱。
- 為了精準對照 `/codebase-design` 詞彙時，可使用「中文（原文）」形式，例如「接縫（seam）」、「介面（interface）」。

**不得因上游 Skill、範例、舊模板或既有 HTML 使用英文，就把英文 UI 或英文說明帶進最終輸出。**
若其他參考資料與本節衝突，本節對此 Skill 的使用者可見輸出具有最高優先權。
</LANGUAGE-GATE>

## 啟動前語言自檢（強制）

在探索程式碼前，必須先完成：

1. 完整讀取本檔 `SKILL.md`。
2. 完整讀取同目錄的 `HTML-REPORT.md`，不得只依記憶生成報告。
3. 執行：

```bash
python .agents/skills/engineering/掃描深模組/check_zh_tw_report.py --skill-sources
```

如果來源檢查失敗，**先修正 Skill／模板來源，禁止開始掃描與禁止交付報告。**

## 架構詞彙來源

本 Skill 以專案領域模型與共用架構詞彙為準：

- 必須載入 `codebase-design`／「程式碼庫設計」Skill，取得正式詞彙：**module、interface、depth、seam、adapter、leverage、locality**，以及 deletion test、「interface 是測試表面」、「一個 adapter 只是推測性 seam，兩個才是真 seam」等原則。
- 說明使用繁體中文，但需要精準對照時保留正式英文詞彙，例如「局部性（locality）」；不要自行換成會改變架構含義的近義詞。
- `CONTEXT.md` 提供領域名稱；`docs/adr/` 內的 ADR 記錄既有架構決策，不應無故重新爭論。

## 流程

### 1. 探索

**掃描前先限縮範圍：遵守 YAGNI。** 深化模組的價值在於讓未來修改更集中，因此優先檢查近期反覆變動的熱點。

- 如果使用者已指定 module、子系統或痛點，直接沿該方向掃描，不再另猜範圍。
- 否則查看足夠長度的提交歷史（`git log --oneline`），找出反覆修改的檔案與區域。
- 若交付包沒有 `.git`，改讀修改日誌、版本紀錄或其他可驗證的近期變更證據；必須明確說明替代依據。

先讀該區域的 `CONTEXT.md` 與 ADR，再走訪程式碼。探索時記錄真正造成理解或修改摩擦的地方：

- 理解一個概念是否需要在許多小 module 之間來回跳轉？
- module 是否過度 shallow，導致 interface 複雜度幾乎等於 implementation？
- 是否為了測試抽出很多純函式，但真正的 bug 仍藏在呼叫關係中，造成 locality 不足？
- 緊密耦合的 module 是否跨 seam 洩漏狀態或規則？
- 哪些區域無法透過現有 interface 穩定測試？

對每個疑似 shallow module 套用 **deletion test**：刪掉它會讓複雜度集中，還是只是把複雜度搬到別處？只有能真正集中複雜度的候選才值得深化。

### 2. 產生繁體中文 HTML 報告

報告必須依同目錄的 [HTML-REPORT.md](HTML-REPORT.md) 模板與規則生成。預設將單一 HTML 寫到作業系統暫存目錄：優先 `$TMPDIR`，Linux/macOS 可回退 `/tmp`，Windows 使用 `%TEMP%`。檔名使用：

```text
architecture-review-<timestamp>.html
```

報告使用 **Tailwind CDN** 排版，並在關係圖／流程圖／序列圖適合時使用 **Mermaid CDN**。不要所有圖都使用 Mermaid；需要表現 interface 面積、deep/shallow 對比、折疊前後等視覺時，可使用 CSS／SVG 手工圖。

每個候選項目必須包含：

- **涉及檔案**：涉及哪些檔案／module。
- **問題**：目前架構為何造成摩擦。
- **解法**：要收斂或深化什麼。
- **收益**：以 locality、leverage 與測試面改善說明。
- **修改前／修改後**：並排視覺，清楚呈現 shallowness 與 deepening。
- **建議強度**：只能使用 `強烈建議`、`值得深入評估`、`推測性候選`。

報告最後必須有 **最高優先建議**，指出第一個應處理的候選與理由。

使用 `CONTEXT.md` 的領域詞彙，而不是自行發明泛化名稱。若候選項目與既有 ADR 衝突，只有在摩擦證據足夠強時才提出，並以繁體中文標示是哪一份 ADR 需要重新評估及原因。

此階段**不要先設計具體 interface**。報告完成後，以繁體中文詢問使用者要先深入哪一個候選項目。

### 3. 輸出前語言閘門（強制）

HTML 寫完後必須執行：

```bash
python .agents/skills/engineering/掃描深模組/check_zh_tw_report.py <報告路徑>
```

檢查至少涵蓋：

1. `<html lang="zh-Hant-TW">` 或 `zh-TW`。
2. 使用者可見的標題、欄位、徽章、圖例、Mermaid／SVG label 均為繁體中文。
3. 舊版英文 UI 標籤不得殘留。
4. 最終聊天回覆使用繁體中文。

若檢查失敗，**不得交付**；修正後重新執行檢查，直到通過。

### 4. 深度質詢迴圈

使用者選定候選項目後，載入 `grilling`／「深度質詢」Skill，逐步釐清：限制、相依性、深化後 module 的形狀、哪些 implementation 收進 seam 後方、哪些測試保留。

決策逐漸明確時，同步使用 `domain-modeling`／「領域建模」維護領域模型：

- 新的 deep module 使用了 `CONTEXT.md` 尚未定義的領域概念：立即補入 `CONTEXT.md`。
- 對話中把模糊詞彙定義清楚：立即更新 `CONTEXT.md`。
- 使用者因長期且具架構意義的理由否決候選：詢問是否記成 ADR，避免後續掃描重複提出。
- 若要比較多種 interface 設計：重新載入 `codebase-design`，使用 design-it-twice 的比較方式。

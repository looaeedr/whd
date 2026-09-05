# HTML 報告格式（繁體中文）

架構掃描輸出為單一 HTML 檔案，預設放在作業系統暫存目錄。**所有使用者可見文字必須使用繁體中文。**

Tailwind 與 Mermaid 由 CDN 載入。Mermaid 適合關係圖、流程圖與序列圖；需要表現模組厚度、interface 面積、折疊前後或其他編輯式視覺時，使用手工 CSS／SVG。兩者混用，不要讓每張圖都長得一樣。

## 基本骨架

```html
<!doctype html>
<html lang="zh-Hant-TW">
  <head>
    <meta charset="utf-8" />
    <title>{{repo name}} 架構掃描報告</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* 補足 Tailwind 不易表達的接縫虛線、洩漏箭頭與 deep module 視覺 */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## 頁首

顯示專案名稱、日期與精簡圖例：

- 實線框：模組（module）
- 虛線：接縫（seam）
- 紅色箭頭：跨 seam 洩漏
- 粗深色框：深模組（deep module）

不要放冗長前言，直接進入候選項目。

## 候選項目卡片

圖必須承擔主要說明責任，文字保持精簡、直接，並使用 `/codebase-design` 的正式架構詞彙。

每個候選項目使用一個 `<article>`，包含：

- **標題**：以繁體中文簡短命名深化方向；實際程式識別字可保留原文。
- **徽章列**：建議強度只能使用 `強烈建議`（emerald）、`值得深入評估`（amber）、`推測性候選`（slate）。若顯示正式相依分類，可保留正式名稱並附中文說明。
- **涉及檔案**：使用等寬字型清單，例如 `font-mono text-sm`。
- **修改前／修改後圖**：兩欄並排，是卡片的核心視覺；圖內所有說明與節點文字也必須是繁體中文。
- **問題**：一句話指出真正摩擦。
- **解法**：一句話指出要收斂或深化的責任。
- **收益**：短項目列舉，聚焦 locality、leverage、interface 與測試表面。
- **ADR 提醒**：若適用，以 amber 色調方塊寫一句繁體中文說明。

不要用長段落解釋。如果一張圖需要一整段文字才能看懂，應重畫圖，而不是增加文字。

## 圖表模式

依候選項目的問題選擇合適圖法，並刻意保持變化。

### Mermaid 關係圖

當重點是「A 呼叫 B、B 呼叫 C，而規則或狀態跨 seam 洩漏」時，使用 Mermaid `flowchart` 或 `graph`。如果重點是往返次數，可使用序列圖。

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[訂單入口] --> B[訂單驗證]
      B --> C[訂單儲存]
      C -.規則洩漏.-> D[定價來源]
      classDef leak stroke:#dc2626,stroke-width:2px;
      class C,D leak
  </pre>
</div>
```

### 手工方塊與箭頭

當 Mermaid 排版無法準確表達「修改後收進單一 deep module」時，用 `<div>` 畫 module、用 inline SVG 的 `<line>`／`<path>` 畫箭頭。修改後可把內部 implementation 淡化，讓粗框 deep module 成為視覺主體。

### 橫切層次圖

用水平帶狀區塊表現一次呼叫穿過多個 shallow module 的成本：修改前是多個很薄的區塊，修改後收斂成一個較厚的 deep module。

### 介面／實作面積圖

每個 module 畫兩個矩形：一個代表 interface 表面，一個代表 implementation。修改前若兩者面積接近，表示 module 過度 shallow；修改後 interface 應縮小、implementation 應吸收更多複雜度。

### 呼叫圖折疊

修改前畫出多層函式呼叫樹；修改後折疊成單一 module，原本的內部呼叫以淡色顯示在深模組內部。

## 視覺風格

- 採精簡編輯式版面，不做企業儀表板風格。
- 保留足夠留白；標題可使用 `font-serif`。
- 顏色節制：一個主色，再加紅色表示洩漏、amber 表示警告。
- 圖表高度約 320px，讓修改前／修改後能舒服並排，不需額外捲動。
- 圖內 module 標籤可使用 `text-xs uppercase tracking-wider`，但**顯示文字仍須繁體中文**。
- 腳本只使用 Tailwind CDN 與 Mermaid ESM；其餘保持靜態 HTML。

## 最高優先建議

使用一張較大的卡片，包含：

- 候選項目名稱。
- 一句繁體中文理由。
- 連回該候選卡片的錨點。

不要增加額外長篇結論。

## 架構詞彙與語氣

說明使用精簡、直接的繁體中文。需要保留正式架構詞彙時，使用「中文（原文）」形式：

- 模組（module）
- 介面（interface）
- 實作（implementation）
- 深度（depth）
- 深模組（deep module）
- 淺模組（shallow module）
- 接縫（seam）
- 轉接器（adapter）
- 槓桿效益（leverage）
- 局部性（locality）

不要為了換字而破壞 `/codebase-design` 詞彙的精確含義。

適合的句型：

- 「訂單入口 module 過度 shallow：interface 幾乎和 implementation 一樣複雜。」
- 「定價規則跨 seam 洩漏。」
- 「深化方向：只保留一個 interface，測試集中在同一處。」
- 「兩個 adapter 才足以證明這條 seam 是真實需求。」

收益項目應直接指出架構收益，例如：

- 「locality：錯誤集中在單一 module」
- 「leverage：一個 interface 支撐多個呼叫點」
- 「interface 縮小，implementation 吸收原本分散的轉接邏輯」

不要寫空泛的「更好維護」「程式更乾淨」。

## 繁體中文交付檢查（強制）

報告交付前必須逐項確認：

- `<html lang="zh-Hant-TW">` 或 `zh-TW`。
- 標題、欄位、徽章、圖例、Mermaid／SVG label、最高優先建議全部為繁體中文。
- 舊版英文 UI 標籤不得出現在使用者可見區域。
- 程式識別字、檔名、路徑、命令可保留原文。
- 若任一項不符，報告視為未完成，不得交付。

並執行：

```bash
python .agents/skills/engineering/掃描深模組/check_zh_tw_report.py <報告路徑>
```

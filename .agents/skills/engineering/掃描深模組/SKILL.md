---
name: 掃描深模組
description: 需要掃描程式碼庫架構摩擦、找 deep module 深化機會、檢查 module/interface/seam/locality，或使用者明確要求「掃描深模組」時使用。WHD 必須先回讀既有 DM baseline，產生繁體中文報告，並以中文 canonical Skill 路徑銜接程式碼庫設計、深度質詢與領域建模。
disable-model-invocation: true
---

# 掃描深模組

找出架構摩擦並提出 **深化機會（deepening opportunities）**：把 shallow module 重構成 deep module，提高 testability、AI navigability 與修改 locality。

## 語言規則（最高優先）

<LANGUAGE-GATE>
**所有使用者可見內容一律繁體中文（zh-TW / zh-Hant-TW）。**

包含對話進度、候選名稱、問題、解法、收益、HTML `<title>`/欄位/徽章/圖例/CTA、Mermaid/SVG labels、最高優先建議與交付訊息。

只有實際程式 identifier、file/path/command/package/framework，以及精準 architecture vocabulary 可保留英文，例如「接縫（seam）」、「局部性（locality）」。

不得因舊 Skill、template 或歷史 HTML 使用英文，就把英文 UI 帶回最終輸出。
</LANGUAGE-GATE>

## 啟動前語言自檢

探索 code 前：

1. 完整讀本 `SKILL.md`。
2. 完整讀同目錄 `HTML-REPORT.md`。
3. 有 Python/runtime 時執行：

```bash
python .agents/skills/engineering/掃描深模組/check_zh_tw_report.py --skill-sources
```

若環境無法執行 checker，明確記錄 capability gap 並 inline 檢查來源；不得假裝 command 已 PASS。若 checker 可執行且失敗，先修來源再掃描。

## Canonical supporting Skills

架構與 domain 輔助能力的正式 identity / 路徑是：

- `程式碼庫設計`：`.agents/skills/engineering/程式碼庫設計/SKILL.md`
- `深度質詢`：`.agents/skills/productivity/深度質詢/SKILL.md`
- `領域建模`：`.agents/skills/engineering/領域建模/SKILL.md`

`程式碼庫設計` 提供正式 vocabulary：**module、interface、depth、seam、adapter、leverage、locality**，以及 deletion test、interface 是 test surface、一個 adapter 只是 hypothetical seam、兩個才是真 seam等原則。

舊英文 identity `codebase-design / grilling / domain-modeling / improve-codebase-architecture` 只可視為 legacy alias/history，不再是 WHD canonical Skill name。

`CONTEXT.md` 提供 domain terminology；`docs/adr/` 記錄已決定的架構 trade-off，不應無證據重新爭論。

## 既有深掃描 baseline 回讀硬閘門

每次使用者要求「掃描深模組」，新候選探索前先判定前一輪做到哪裡。至少回讀：

1. target branch / HEAD 與近期 deep-module commits。
2. `.scratch/dm*/checkpoint.md`、journal/state（存在時）。
3. deep-module owning Issues、Combined Acceptance、integration、remote readback evidence。
4. `CONTEXT.md`、ADR、AI Library durable contract。

建立「latest completed DM baseline」。若 DM1…DMn 已 ACCEPTED/整合，下一輪預設從 **DM(n+1) 增量掃描**；除非使用者明確要求重掃，不得重跑已完成 DM、把 closed candidate 當新候選，或因聊天沒舊上下文就假設從未做過。

## Supporting Skill / capability 缺失處理

找不到某 supporting Skill loader 不等於 BLOCKED。

必須先：

- 掃實體 `.agents/skills/**/SKILL.md`，不要把 Registry/README/plugin catalog 當完整 inventory。
- 查 project rules、AI Library、`CONTEXT.md`、ADR 與既有 DM evidence，確認是否已有等價 authority。
- 有 safe fallback 就 inline 執行，記錄 execution-environment difference。

只有「能力不可替代 + fallback 全部失敗 + 繼續會違反一條可指出的 invariant」三項同時成立才能 BLOCK。BLOCKED 回報必須列精確缺失能力、已嘗試 fallback、會被違反的 invariant。

## 1. 探索

先限縮範圍，遵守 YAGNI。deepening 的價值是讓未來修改更集中，所以優先近期反覆修改的 hotspots。

- 使用者已指定 module/subsystem/pain point → 沿該方向掃，不另猜 scope。
- 未指定 → 讀足夠長的 git history 找反覆變動區域。
- 無 `.git` → 用修改日誌/version history/其他可驗證近期 evidence，並說明替代依據。

先讀該區域 `CONTEXT.md` / ADR，再走 code。記錄真正 friction：

- 理解一個概念是否要跨很多 shallow modules？
- interface complexity 是否幾乎等於 implementation？
- 為測試抽了很多純函式，但 bug 仍藏在 call relationship？
- tightly coupled modules 是否跨 seam 洩漏 state/rules？
- 哪些區域無法經 existing interface 穩定測試？

每個候選套 **deletion test**：刪掉它後 complexity 是消失，還是散回 callers？只有能集中 complexity 的候選值得深化。

## 2. 產生繁體中文 HTML 報告

依 [HTML-REPORT.md](HTML-REPORT.md) 生成單一 HTML。預設寫 OS temp：優先 `$TMPDIR`，Linux/macOS 可用 `/tmp`，Windows `%TEMP%`。

檔名：

```text
architecture-review-<timestamp>.html
```

版面可用 Tailwind CDN；流程/關係圖適合時用 Mermaid CDN，interface 面積/deep-vs-shallow 等也可用 CSS/SVG，不要求全部 Mermaid。

每個 candidate 必須包含：

- **涉及檔案**
- **問題**
- **解法**
- **收益**（locality/leverage/test surface）
- **修改前／修改後** 視覺
- **建議強度**：只用 `強烈建議` / `值得深入評估` / `推測性候選`

報告最後給 **最高優先建議** 與理由。用 `CONTEXT.md` domain names；與 ADR 衝突時只有 friction evidence 足夠強才提出重新評估，並指出哪份 ADR/原因。

此階段不要先設計具體 interface；先讓使用者選 candidate。

## 3. 輸出前語言 gate

HTML 完成後，有 runtime 時執行：

```bash
python .agents/skills/engineering/掃描深模組/check_zh_tw_report.py <報告路徑>
```

至少檢查：

1. `<html lang="zh-Hant-TW">` 或 `zh-TW`。
2. user-visible title/field/badge/legend/Mermaid/SVG labels 為繁中。
3. legacy English UI label 不殘留。
4. final chat reply 為繁中。

checker failure 時不得交付；修正後重跑。若 checker 工具本身不可用，必須明確標記未自動執行並做 inline source review，不可虛構 PASS。

## 4. 深度質詢迴圈

使用者選 candidate 後，讀取並使用 `.agents/skills/productivity/深度質詢/SKILL.md`，逐步釐清 constraints、dependencies、deepened module shape、seam 後 implementation、tests。

decision settle 時同步使用 `.agents/skills/engineering/領域建模/SKILL.md`：

- new deep module 引入新 domain concept → 更新 `CONTEXT.md`。
- fuzzy term 被定義清楚 → 立即更新 glossary。
- 使用者以長期架構理由否決 candidate → 依 ADR gate 決定是否記錄。
- 要比較多種 interface → 讀 `.agents/skills/engineering/程式碼庫設計/SKILL.md` 與 `DESIGN-IT-TWICE.md`。

沒有真正 Subagent 時遵守 supporting Skills 的 inline fallback；不得為了 Design It Twice 假裝平行 agent。

## 5. Candidate → 實作交接硬閘門

掃描報告不是工單，也不是施工授權。使用者選 candidate 並要求 spec/tickets/派工/implementation 時：

- 每張已核准施工 ticket 必須有 GitHub owning Issue 並反讀 number/URL/title。
- breakdown 明確指定 **AI Library Writeback owner**。
- breakdown 明確指定 **Combined Acceptance owner**，負責 cross-ticket regression、source scan、config invariant、remote QA、workflow cleanup、drift audit、integration evidence。
- HTML、聊天 candidate number、branch、checkpoint、`.scratch/**` 都不能替代 owning Issue。
- 轉入 `.agents/skills/engineering/拆解任務工單/SKILL.md` / `.agents/skills/engineering/派工/SKILL.md` 的 RED-first、AI Library、Issue、remote QA 流程；本 Skill 不直接跳 production write。

## 6. 模組接縫語意 authority（DM6 durable contract）

若 upstream 已知道 engineering semantic（identity/kind/axis/source/anchor），它就是跨 seam contract，不得退化成 presentation string 讓 downstream heuristic reconstruction。

- text/label/localization/formatting 是 presentation，不是 identity/source/axis/anchor ownership/annotation kind authority。
- duplicate labels 合法；同值 X/Y dimension 仍需不同 semantic identity。
- Planner/domain resolver 擁有 engineering semantic；Layout 只擁有 placement/collision/leader routing；Renderer/GUI/exporter 是 sink，不得重建第二套 semantic resolver。
- downstream consume stable semantic identity；禁止 nearest-text/nearest-feature/primitive index/display string/collision-post-position 猜 ownership。
- Save/Reload 從 authoritative state 重建 semantic contract；derived layout/text position 不得升格 persistence authority。
- validation expected/fixture/tolerance 只能判 contract，不得反向成為 production semantic/geometry 計算來源。

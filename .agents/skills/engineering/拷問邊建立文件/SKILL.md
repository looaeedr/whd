---
name: 拷問邊建立文件
description: 用深度質詢把 plan/design 的決策樹問清楚，並在決策形成時同步維護 CONTEXT.md 與必要 ADR。適合在有 repository/workspace 的情境，把訪談結果變成 durable domain docs，而不是只留在聊天。
disable-model-invocation: true
---

# 拷問邊建立文件

這個 Skill 組合兩個 canonical 能力：

- `.agents/skills/productivity/深度質詢/SKILL.md` — 逐輪處理 design tree/frontier；事實由執行者查，決策由使用者做。
- `.agents/skills/engineering/領域建模/SKILL.md` — 將已確認的 canonical terms 寫入 `CONTEXT.md`，必要時把真正的架構決策寫成 ADR。

目標是**邊問、邊落盤**，不是訪談結束後憑記憶補文件。

## 0. 拷問前 Source-first 硬閘門

在問第一題之前，必須先完成與本題直接相關的 source readback。

至少檢查：

- current code / UI routing / existing behavior；
- tests / regression contracts；
- 既有 specs / CONTEXT / ADR / AI Library；
- 必要時 Git history，找回使用者所說「原本就有」的實作；
- 本輪與歷史已確認的規格。

**能從上述 evidence 得到答案的事情，不得再拿去拷問使用者。**

特別禁止：

- 程式已決定 A，卻問使用者「A 還是 B」；
- 因尚未讀程式而把 implementation fact 偽裝成需求選項；
- 要使用者重複說明既有 2D/3D 行為、part identity、routing、已確認名稱等可查事實；
- 看不到畫面就假設功能不存在，而沒有先查 code/history/tests。

只有 current evidence 無法決定、authority 衝突，或確實是新的 product/design preference，才進入拷問。

如果使用者說「程式看清楚再來問」「不要假會」「本來就有」，立即停止質詢，先查 source，再重新計算 design frontier。

## 1. 能力偵測

先確認目前環境能否：讀/寫 repository、搜尋 current code/docs、使用獨立 Subagent。

- 有專用 Skill loader 時，可載入 `深度質詢` 與 `領域建模`。
- 沒有專用 Skill loader 時，直接讀上列 canonical `SKILL.md` 並由同一執行者 inline 套用規則。
- 有真正獨立 Subagent Runtime 時，可把純 fact-finding 委派出去。
- 沒有真正 Subagent 時，不得宣稱「已派出去查」或等待不存在的回報；使用現有檔案/搜尋/工具 inline 查完，再繼續當輪可決策問題。

## 2. 啟動基線

若在 repository/workspace：

1. 先讀現有 `CONTEXT.md` 或 `CONTEXT-MAP.md`。
2. 讀與當前主題直接相關的 ADR。
3. 查 current code / tests / specs 中會影響 frontier 問題的事實。
4. 若使用者提到「原本」「現在」「之前就有」，必要時查 Git history，不得直接以目前畫面推定歷史能力不存在。
5. 若是 WHD repo 修改任務，仍先遵守 `AGENTS.md` / Knowledge Preflight / branch-first；本 Skill 不可繞過專案 gate。

沒有 `CONTEXT.md` 不代表先建立空檔；只有第一個 domain term 真正確認時才建立。

## 3. 深度質詢迴圈

依 `深度質詢`：

- 把決策建成 design tree。
- 每輪只問 prerequisites 已 settle 的完整 frontier。
- 每題編號、說清楚選項/trade-off，並給建議答案。
- 問題答案依賴尚未 settle 的另一題時，移到下一輪，不偷猜。
- 能從 environment 查到的 fact 不丟給使用者回答；先自行查證。
- 使用者的 product/design 決策才由使用者定案。
- source readback 後 frontier 若為空，就不要為了「有拷問」而硬造問題，直接整理成規格／文件。

## 4. 文件同步

每當一個決策 settle，立即判斷是否要 durable write：

### CONTEXT.md

符合下列任一情況就依 `領域建模` 更新：

- 新 canonical domain term 被確認；
- 原有 term 定義被澄清/更正；
- 同一詞有歧義而使用者選定正式名稱；
- relationship/invariant 屬 domain glossary，而非 implementation detail。

`CONTEXT.md` 只存 glossary/domain meaning，不存 implementation plan、測試結果、run id 或 temporary probe。

### ADR

只有三條都成立才建立/更新 ADR：

1. hard to reverse；
2. future reader 沒上下文會覺得 surprising；
3. 真正做過有意義的 trade-off 選擇。

不符合就不要為了「有文件」硬造 ADR。

## 5. 衝突與 authority

- current user-confirmed decision 高於 stale docs；發現衝突就明確指出並同步修正 durable docs。
- current code/test 與使用者決策衝突時，先標示 implementation/test 現況，不可把現況倒過來變成產品決策。
- 未解問題保持 OPEN，不寫成 canonical glossary/ADR。
- current code 已回答 implementation fact 時，該 fact 不再列為 OPEN question；真正 OPEN 的只有產品／設計 authority 尚未決定的部分。

## 6. 完成條件

只有當：

- design tree frontier 為空，或使用者明確結束本輪；
- 本輪已確認的 domain terms 都已同步 `CONTEXT.md`；
- 符合 ADR gate 的決策已詢問/落盤；
- 沒有把 unresolved assumption 寫成 durable truth；
- 沒有把可查 implementation fact 丟回使用者回答；
- 若有 repo write，已 re-read 確認內容存在；

才算本輪完成。

不要用綁死特定 runtime 的「一次呼叫多個 Skill」捷徑代替上述流程。

---
name: 執行開發任務
description: 依已核准規格或工單執行實作。用於進入實作者階段、修改 production/test/Skill、跑 targeted 驗證、產生 durable checkpoint，並在 WHD 專案遵守派工、Preflight、owning Issue、remote QA 與 resume 規則。
disable-model-invocation: true
---

# 執行開發任務

依使用者已核准的規格或工單實作，不重新發明需求。

## 1. 開始前

- 先讀目前工單／規格、`Requirement Authority`、`Approved RED IDs`、`AI Library References`、依賴與 acceptance criteria。
- 若是 WHD / Phase6，先依 `AGENTS.md` 完成 Knowledge Preflight，並同時遵守 `.agents/skills/engineering/派工/SKILL.md`。
- Git repository 修改必須已在本任務的新 work branch；不得直接 patch production target。
- GitHub-backed ticketed work 在第一個 production write 前，必須反讀真實 GitHub owning Issue 的 `issue_number + URL`。`.scratch/**`、聊天 T 編號、branch、checkpoint 都不能替代。

若施工途中才發現漏建 Issue：停止新增 production 變更 → 補建 Issue → 明標 `Retroactive provenance / 施工後補建` → 寫入實際 branch/commit/run → 反讀成功 → 再 resume。不得倒填 chronology。

## 2. 實作方式

- 使用實際可用的 TDD Skill／測試工具執行 RED → GREEN；WHD 專案的 repository TDD 參考 `.agents/skills/engineering/tdd/SKILL.md`。
- 測試 seam 以已核准 requirement 與 public interface 為準；不要為了讓測試好寫而改產品語意。
- 每次只完成一個可驗證 slice，再跑與該 slice 最接近的 targeted test。
- typecheck、lint、單檔測試等只在專案實際存在對應工具時執行；不得虛構命令或把缺少工具說成已通過。
- 驗證 expected/fixture/probe 只能判定對錯，不能反向成為 production 計算來源。

## 3. Durable checkpoint / resume

每張已驗收工單要有實體 checkpoint。長回歸前若已有未封裝變更，先封 checkpoint。

fresh extract、restore、工具回合重建或手動複製後，先驗 execution-tree fingerprint；若與最近已驗收 checkpoint 不符，視為混合狀態，必須完整還原 checkpoint 後再續工。

checkpoint/state 至少記錄 branch+HEAD、已完成/pending/failed、修改檔、最後驗證結果、owning Issue、下一步 resume 指令。

## 4. 測試 timeout

- GUI targeted gate 若 pytest 已有完整 PASS summary 但 Tk/Xvfb/interpreter 不退出，分類為 `complete_teardown_timeout`。
- 只有點號、局部百分比或不完整輸出時是 `incomplete_timeout`，不得冒充 PASS。
- incomplete batch 只縮小並重跑 pending nodeids；已完成節點禁止為方便重跑。
- process-group、Xvfb ownership、killpg、journal/resume 與 provenance 細節以 `派工` Skill 為準。

## 5. Remote QA Active Lock

只要建立或依賴 non-terminal remote QA run，立即服從 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 的 `REMOTE_QA_ACTIVE_LOCK`。

run terminal 前禁止繼續 code exploration、production/test/Skill write、下一張工單或另一個診斷；只能 poll run/jobs/steps、處理 terminal failure log、做 30 秒進度回報。terminal 後才恢復一般實作流程。

## 6. 進度與完成

任務尚未完成時，每 30 秒至少回報一次目前工單、正在做的事項、最新測試/進度數字與 blocker；回報不得中斷正常執行。

完成前使用實際可用的 code-review Skill／review 工具檢查本票 diff；WHD repo 有 `.agents/skills/engineering/code-review/SKILL.md` 時直接讀取並套用。沒有該能力時以 inline diff review 退化，不得假裝已派 reviewer。

只有 fresh verification 支持的狀態才能宣告完成。若來源不是 Git repository，Git/commit 步驟跳過，不為滿足形式硬造 repository；checkpoint + SHA/provenance 仍要完成。

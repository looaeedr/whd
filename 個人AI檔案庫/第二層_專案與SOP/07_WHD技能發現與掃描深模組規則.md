# WHD 技能發現與「掃描深模組」規則

## 目的

避免 AI 因只讀 `skill_registry.json`、README 或少量目錄，就錯誤宣稱某個 WHD Skill 不存在。

## 強制技能發現規則

1. WHD 專案技能的完整存在性判定，以實際掃描 `.agents/skills/**/SKILL.md` 為準。
2. `skill_registry.json` 是 Preflight 路由表，不是完整 Skill 清單；不能因 registry 沒列出某 Skill 就判定不存在。
3. 各分類 README 是導覽入口，不是完整存在性證據；README 漏列時仍必須掃描實際 `SKILL.md`。
4. 使用者明確指定 Skill 名稱時，必須優先用精確名稱查找，禁止以名稱相近或語意相似的 Skill 代替。
5. 若使用者說「一定有」或糾正 AI 的 Skill 判斷，AI 必須改用完整 tree / `.agents/skills/**/SKILL.md` 驗證，而不是重複用相同 registry 或 code search 結論。

## 「掃描深模組」正式位置

- Skill 名稱：`掃描深模組`
- 正式路徑：`.agents/skills/engineering/掃描深模組/SKILL.md`
- 同目錄支援檔：
  - `HTML-REPORT.md`
  - `check_zh_tw_report.py`
  - `agents/openai.yaml`
  - `tests/test_check_zh_tw_report.py`
  - `tests/test_skill_sources_zh_tw.py`

## 觸發規則

當使用者輸入或明確要求下列任一語句時，必須直接載入並執行 `掃描深模組`：

- `掃描深模組`
- `深模組掃描`
- `掃描模組`
- 要求針對 WHD 做深層架構掃描、耦合掃描、模組邊界掃描

不得以以下 Skill 替代：

- `setup-ts-deep-modules`
- `improve-codebase-architecture`
- `codebase-design`
- 其他只因名稱含 `deep modules` 或架構語意相近的技能

這些 Skill 可以依 `掃描深模組/SKILL.md` 的要求被進一步載入，但不能取代使用者點名的主 Skill。

## 既有深掃描基線回讀規則

每次再次執行「掃描深模組」時，必須先確認前一輪深掃描已做到哪裡，不能只看目前聊天上下文，也不能把「本回合沒有載入舊對話」誤當成「專案從未掃描」。

最低回讀證據：

1. target branch / HEAD 與近期 deep-module commits。
2. `.scratch/dm*/checkpoint.md`、journal/state。
3. deep-module owning Issues、Combined Acceptance、整合與 remote readback 結果。
4. `CONTEXT.md`、ADR 與 AI Library 已落盤 durable contract。

若已有 DM1…DMn 正式 ACCEPTED／整合，新的掃描預設從 **DM(n+1)** 開始做增量探索。除非使用者明確要求重掃，否則禁止重跑已完成 DM、重新把已關閉候選當新候選，或從零推論專案狀態。

## 輔助 Skill 缺失不得自動誤判成 BLOCKED

「掃描深模組」可以要求使用 `codebase-design`、`grilling`、`domain-modeling` 等輔助能力，但執行環境暫時無法直接載入某一個輔助 Skill，**不等於整個深掃描必須停工**。

正確順序：

1. 先查實體 `.agents/skills/**/SKILL.md`，避免把 plugin catalog／registry 漏列誤認成不存在。
2. 再查專案內已落盤的 Skill 規則、AI Library、`CONTEXT.md`、ADR 與既有 deep-module evidence，判斷是否已有等價權威資料可完成當前階段。
3. 有安全 fallback 時，以 execution-environment difference 記錄並繼續；不得拿「輔助 Skill 名稱找不到」當停工理由。
4. 只有缺失能力確實不可替代、fallback 已全部查驗失敗，而且繼續會違反可明確指出的專案 invariant，才可宣告 BLOCKED。
5. BLOCKED 回報必須列出：缺少的精確能力、已嘗試 fallback、繼續會違反的精確 invariant。三者不全，不得停工。

## 2026-09-08 糾偏紀錄

曾發生 AI 先讀 `skill_registry.json` 與部分 README，因未完整掃描 `.agents/skills/**/SKILL.md`，錯誤宣稱「掃描深模組」不存在，之後又誤把 `setup-ts-deep-modules` 當成候選。

根因：把「路由表 / 導覽文件」誤當成「完整技能目錄」。

永久修正：所有 Skill 存在性查詢都以實體 `SKILL.md` tree 為最終證據；使用者指定精確名稱時，禁止用相似 Skill 代答。

## 2026-09-09 糾偏紀錄：把輔助依賴誤判成硬阻塞，且漏讀既有 DM 完成鏈

曾發生 AI 已經讀到 `掃描深模組/SKILL.md`，看到其中要求載入 `codebase-design`，在目前執行環境沒有直接找到該輔助 Skill 後，就立即宣告「掃描深模組 BLOCKED」。同時沒有先反讀 repo 內既有 DM1–DM5 checkpoint、work order、Combined Acceptance 與整合證據，因此連 **DM5 已正式完成且驗收通過** 都沒有先確認，就錯誤地從頭推論掃描流程。

這個行為有兩個根因：

- 把「輔助 Skill／執行環境能力缺失」錯當成「專案級不可繼續 blocker」，沒有先找等價 project-local authority 或 fallback。
- 把聊天上下文當成專案狀態來源，漏掉 Git history、checkpoint、Issue、QA、AI Library 才是可續跑工作的 durable evidence。

永久修正：每次深掃描先建立 latest completed DM baseline，再決定下一個增量 DM；輔助 Skill 找不到時先查實體 tree 與 project-local durable evidence。只有「不可替代 + fallback 全失敗 + 可指出 invariant」三條同時成立，才可 BLOCK。
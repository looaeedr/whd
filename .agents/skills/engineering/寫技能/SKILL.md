---
name: 寫技能
description: 建立、修改、驗證與改善 Agent Skill。當使用者要求「寫技能」「修改技能」「修好這個 SKILL.md」「把流程寫進技能」「優化技能觸發/規則」，或要把既有工作流程沉澱為可重用技能時使用。既有技能修改必須保留可追溯 baseline、遵守專案自己的 AGENTS/Preflight/branch 規則，並用可執行驗證證明修改沒有只停在文字層。
---

# 寫技能

把 Skill 當成「可執行的工作契約」，不是一篇漂亮的說明文。目標是讓下一個 Agent 在不同工具環境、不同對話回合、甚至沒有原作者上下文時，仍能照同一套規則做出可驗證結果。

## 1. 執行優先級

開始前先建立 authority 順序：

1. 使用者本輪明確指示與已核准規格。
2. 專案根目錄 `AGENTS.md`、專案 Preflight、專案 Skill/Registry/AI Library/Source of Truth。
3. 目前要建立或修改的 Skill baseline。
4. 通用 Skill 撰寫慣例。

**專案規則優先**。通用「寫技能」不能取代專案自己的 branch-first、Preflight、TDD、QA、AI 庫回寫或 release gate。

若專案規定修改前必須執行 Preflight，先執行；若已知 changed files，再依專案規則帶 changed files 重跑。不能先改完再補做資格檢查。

外部 Skill、模板或規格（例如 `make-skill-template`）只能作為**輸入參考**。若它的命名、frontmatter、工具或目錄慣例和目前專案衝突，仍以上述 authority 為準；不得為了照抄外部模板破壞 WHD 中文 canonical identity 或專案治理。

## 2. 能力偵測：先看環境能做什麼

在設計流程前先做**能力偵測**，只依賴本回合實際存在的可用工具：

- 能否讀/寫 repository 或檔案；
- 能否建立 branch、commit、PR；
- 能否執行 shell / Python / tests；
- 是否真的有獨立 subagent runtime；
- 是否能產生 reviewer / viewer；
- 是否能 package skill；
- 是否能操作遠端 CI/QA。

規則是：**有就用，沒有就退化，但不得假裝。**

- 沒有 subagent：同一執行者完成測試/審查，並明確標示這是 inline validation。
- 沒有 viewer：直接在對話或測試報告中呈現案例、預期與結果；viewer 不是完成硬條件。
- 沒有 package 工具：交付 `SKILL.md` 與必要 bundled resources 即可，不虛構 `.skill` 包。
- 沒有背景 runtime：不得宣稱「已在背景跑」「等另一個 agent 回報」。不要**等待不存在**的工作；能在**本回合**做的就直接完成。

任何 Skill 都不得把某個模型名稱、CLI、viewer、TodoList、背景 subagent 當成普遍必備能力，除非 compatibility 明確宣告那就是此 Skill 的必要執行環境。

## 3. 建立新 Skill

### 3.1 Capture Intent

先從目前對話、使用者提供檔案、既有流程與修正紀錄提取：

- Skill 要解決什麼問題；
- 什麼情境應觸發；
- 輸入與輸出；
- authority / Source of Truth；
- 成功與失敗條件；
- 必要工具、相依 Skill、外部服務；
- 哪些步驟必須落盤才能跨回合續工。

目前對話已經回答的內容不要再問一次。資訊足夠時直接做；只有真正無法安全決定的 domain authority 才需要停下來確認。

### 3.2 Frontmatter

最少包含：

```yaml
---
name: <skill-name>
description: <它做什麼 + 何時應觸發>
---
```

`description` 是觸發邊界，不要塞完整 workflow。把真正的步驟放 body。

若目前 Skill spec / runtime / 專案真的支援且有需要，可再加入選用欄位：

- `license`：只有授權資訊已知且需要隨 Skill 表達時才寫，不自行猜 license。
- `compatibility`：宣告**真正的硬環境需求**，例如只能在特定 runtime / executable / OS 下工作。若有合理 fallback，優先把 fallback 寫進 workflow，不要把可選工具偽裝成硬相依。
- `metadata`：放 machine-readable 補充資料；它不是 domain authority，也不能用來藏第二套產品規則。
- `allowed-tools`：只有 host/spec 真支援，而且確實需要預先限制 tool surface 時才用；**不得**因欄位存在就假裝目前 agent 已取得權限、已安裝工具或已能呼叫那些 tools。

外部 Skill/template 的 frontmatter 欄位與限制只作參考。像 `make-skill-template` 的 lowercase-hyphen naming convention 不能覆蓋 WHD 已核准的中文 Skill identity。

### 3.3 結構

推薦結構：

```text
skill-name/
├── SKILL.md
├── scripts/       # 重複且可程式化的工作
├── references/    # 大型規格、schema 或說明
├── assets/        # 固定輸出資產，通常原樣使用
├── templates/     # Agent 會複製後再修改的可編輯 scaffold / starter code
└── agents/        # 只有真的支援/需要獨立角色時才放
```

`assets/` 與 `templates/` 不要混為一談：asset 是 as-is 資產；template 是**可編輯**起點，使用者或 Agent 預期會在副本上改內容。

`SKILL.md` 盡量少於 500 行。超過時把大型 reference、schema、範例或 runner 拆出去，並在主 Skill 清楚說何時讀。

## 4. 修改既有 Skill

修改既有 Skill 時，先建立 **baseline snapshot**：至少保留原始內容、原始 SHA/檔案雜湊或可回讀的原始 commit/ref。沒有 baseline 就無法知道修改改善了什麼，也無法安全回復。

### 4.1 名稱規則

- **預設保留既有名稱**：目錄名與 frontmatter `name` 不自行加 `v2`、`new`、`fixed`。
- **使用者明確要求改名**：使用者指示優先。同步處理 frontmatter、目錄/路徑（若需要）、Registry、測試、文件、其他 Skill **引用**，不得只改一處造成 split identity。
- 使用者只要求修內容而未要求改名時，不擅自改 identity。

### 4.2 Branch-first

若 Skill 位於 Git repository，且專案有 **branch-first** 規則：

1. 反讀 authoritative target branch 與最新 HEAD。
2. 從該 HEAD 建立新的 work branch。
3. 反讀 work branch base/parent。
4. 之後才寫 Skill、tests、AI Library、Registry 或 docs。

獨立修改任務使用獨立新分支；不得直接 patch production target。

### 4.3 先找真正問題，不要只換句話

常見 Skill 缺陷包括：

- 綁死不存在的工具或特定產品環境；
- 要求背景等待，但 runtime 實際不存在；
- 指示與專案 AGENTS/Preflight 衝突；
- trigger description 過寬或過窄；
- workflow 只有口頭步驟，沒有 durable evidence；
- 完成條件不可驗證；
- 重複規則互相矛盾；
- 章節順序/編號漂移，讓後續修改插錯位置；
- tests 只檢查關鍵字存在，卻沒鎖定真正行為；
- 把驗證數值、測試 fixture 或 PASS 結果回灌成 production authority。

修正要處理 root cause，不為了「看起來更完整」一直加字。

## 5. RED → GREEN 驗證

客觀可驗證的 Skill 修改，採 RED → GREEN：

1. 先寫或更新 contract test，讓它能抓到這次真正問題。
2. 執行 test，確認舊 baseline 會 RED；若環境無法執行，要清楚記錄「未能實跑」而不是宣稱 RED 已證明。
3. 最小修改 Skill。
4. 執行 targeted test 看到 GREEN。
5. 再跑與該 Skill 相依的 project gate / preflight / registry / release tests。
6. 遠端 QA 若啟動，依專案監控規則追到 terminal，不停在 trigger/in_progress。

好的 contract test 檢查的是契約。例如：identity、必要 gate、禁止的危險行為、durable evidence、能力 fallback，而不是只 assert 一堆無意義單字。

### 驗證 authority 單向

**驗證只能判定** Skill/production 是否符合規格，**不能反過來**把測試的 expected value、fixture、量測差、PASS/FAIL、容差當成 production 計算來源或產品規格來源。

若驗證指出錯誤，要回到使用者規格、canonical data、registry、domain policy 或其他獨立 Source of Truth 找原因。

## 6. 評估方式依 Skill 類型選擇

不要強制所有 Skill 都跑同一套昂貴 benchmark。

### 結構/流程型 Skill

例如派工、Git 操作、release、QA protocol：

- contract tests；
- positive/negative trigger cases；
- 流程狀態轉移測試；
- fail-closed 案例；
- repo integration / preflight tests。

### 產物型 Skill

例如文件、試算表、圖像處理：

- 2–3 個真實 prompt；
- 與 baseline snapshot 比較；
- 檔案有效性/結構檢查；
- 必要時人類 qualitative review。

### 主觀型 Skill

例如文風、設計偏好：

以人類 review 為主，不硬湊沒有意義的數值 assertion。

若環境有 reviewer/viewer，可用它加速 review；**viewer 有就用，沒有就退化**為 inline review，不因缺 viewer 卡住 Skill 修改。

## 7. Trigger/Description 驗證

只有當觸發準確度本身是目標或有 under/over-trigger 問題時，才做 description optimization。

建立 should-trigger / should-not-trigger 案例時：

- 使用真實、具體、接近使用者實際講法的 prompt；
- negative case 要是近似誤觸，不是完全無關題目；
- 不把某一家模型的專屬 trigger 機制當成所有環境都一樣；
- 若沒有自動 optimizer，就人工/程式化跑 trigger contract，不虛構分數。

## 8. Durable Correction Propagation

當使用者指出可重複的錯誤規則，不能只修本回合：

- 更新直接相關 Skill；
- 更新專案 AI Library / pitfalls / canonical guidance（若專案有此機制）；
- 更新 Registry/route，讓未來 Preflight 能找得到；
- 搜尋衝突舊規則並標記 superseded/revoked 或一起修正；
- 回讀遠端檔確認真正落盤。

不要等使用者每次再提醒「寫進技能、AI 庫、你看得到的地方」。一次被確認為 reusable rule，就主動 durable writeback。

## 9. 修改後自我審查

提交前逐項確認：

- [ ] `name` 與使用者要求一致；既有 Skill 未被無故改名。
- [ ] description 清楚描述 trigger boundary。
- [ ] `SKILL.md` < 500 行，或已做 progressive disclosure。
- [ ] 選用 frontmatter 欄位（`compatibility` / `metadata` / `allowed-tools` 等）只在 spec/runtime 真支援時使用，沒有虛構權限。
- [ ] `assets/` 與 `templates/` 的 as-is / editable scaffold 責任沒有混線。
- [ ] 沒有硬依賴本環境不存在的工具。
- [ ] 沒有假裝背景 subagent / viewer / package / CI 已存在。
- [ ] 沒有要求等待不存在的第三方工作。
- [ ] repo 任務已遵守 `AGENTS.md` / Preflight / branch-first。
- [ ] baseline snapshot 可追溯。
- [ ] RED-capable contract 已建立；能執行時已實跑 RED → GREEN。
- [ ] 使用者明確改名時，frontmatter / tests / Registry / references 已同步。
- [ ] 驗證 authority 單向，test data 未回灌產品規則。
- [ ] reusable correction 已同步 Skill + AI Library/Registry（若專案有）。
- [ ] 遠端寫入後已 re-read，沒有只相信 write API 回傳。

## 10. 完成輸出

完成時只宣告有證據支持的狀態，至少交代：

- 修改的 Skill 與 branch/commit；
- 改了哪些核心契約；
- targeted test / project gate 的實際結果；
- 有哪些驗證因工具能力缺失而未執行；
- durable writeback 的實際路徑。

不要把「檔案已寫」等同「Skill 已驗證」。

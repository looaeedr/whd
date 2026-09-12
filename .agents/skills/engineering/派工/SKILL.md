---
name: 派工
description: 人工指定「派工」時使用：執行 WHD 的 PM → Implementer → QA 角色切換、GitHub owning Issue、checkpoint/journal、30 秒進度回報與 remote QA 監控協定。
disable-model-invocation: true
---

# 派工

這個 Skill 是 WHD 的施工狀態機。它的目標不是模擬「把工作丟給另一個人」，而是確保每張已核准工單都有可追溯 authority、真正的 owning Issue、可恢復 checkpoint/journal、可判讀的 QA 證據，以及明確的 PM → Implementer → QA 轉移。

**REQUIRED SUB-SKILL:** monitoring-remote-qa

同步遠端 QA / GitHub Actions QA 一旦啟動，上述 sub-skill 強制生效；必須鎖定同一 `run_id + head_sha` 主動輪詢到 terminal。

### USER_VISIBLE_CHECKPOINT_GATE_BRIDGE

本 Skill 一旦進入長流程、remote QA、recovery 或 closure chain，強制服從 `執行開發任務` 的 `USER_VISIBLE_CHECKPOINT_GATE`。該 gate 是 user-visible CHECKPOINT 的唯一 canonical authority；本 Skill 不複製其欄位／refresh state machine，且不得建立第二套 CHECKPOINT authority。

- 需要顯示 CHECKPOINT 時，沿用 canonical gate 的固定標題、欄位與重大 state transition refresh 規則。
- progress update 不得取代可見 CHECKPOINT；30 秒 observation 仍只屬 progress。
- non-terminal CHECKPOINT 不是停工點；顯示後仍依本 Skill 原有 owner contract 繼續 next action。
- 本 Skill 只保留自己的 domain responsibility；CHECKPOINT 呈現責任一律 bridge 回 canonical gate。

### NON_TERMINAL_CONTINUE

只要本票仍有任何 required step 處於 pending，例如 Requirement/RED、production/test/Skill 修改、GREEN 驗證、remote QA、workflow cleanup、tested-head → closing-head drift audit、AI Library writeback、owning Issue terminal evidence/closure，該狀態只能標示為「進行中／pending」，**但 pending 本身不是停工點，也不是結束回合的理由**。

- progress update、CHECKPOINT、「尚未完成」、「因此不宣稱完成」都只是 observation，不能當作 `return` condition。
- 除非使用者明確中止、遇到不可繞過且需要外部輸入的 capability/blocker，或安全／專案硬閘門明確要求停止，否則必須在同一次可用工作流程中立即執行下一個可執行 action。
- 若遇 blocker，必須先把能完成的非阻塞 prerequisite/evidence 做完，再精確記錄 blocker；不得以籠統「pending」提前結束。
- 「不假報完成」與「持續施工」是兩個獨立義務：前者禁止假綠，後者禁止非終態自行停工。
- 任何 user-visible progress/checkpoint 後，只要沒有合法 stop condition，就必須接續下一個 tool/action；不得輸出狀態後直接結束回合。

## 1. 啟動與能力邊界

### 1.1 先遵守專案啟動鏈

任何實質派工、production/test/Skill/SOP 修改前，先依 `AGENTS.md` 執行 Phase6 Knowledge Preflight，讀完 required Skills / required references 並留下 evidence。預計修改檔已知後，再依專案規則帶 `--changed-file` 重跑。

修改任務一律遵守 branch-first：反讀 authoritative target HEAD → 從該 HEAD 建新 work branch → 反讀 branch base → 才能寫檔。不得直接 patch `cleanup/2d-3d-sync` / `main`。

### 1.2 能力偵測

- 若環境真的支援獨立 Subagent Runtime，可以把 Worker/QA 放到隔離上下文；每個 Subagent 仍必須自行重跑相同 Preflight、讀相同 authority 並留下自己的 evidence。
- 若環境**不支援**真正背景 Subagent Runtime，必須由同一執行者在同一工作上下文自動完成角色切換，不能停下來等不存在的第三方。
- 不得宣稱「已派給工程師、等回報」而實際沒有可觀測的 runtime / task / result。
- 聊天回合不是 remote runner；需要跨回合續工的狀態必須落到 checkpoint / journal / GitHub Issue / remote run，而不是只存在對話文字。

## 2. 狀態機

固定狀態：

```text
[總控 PM]
    ↓ 使用者核准 Requirement RED + 工單 breakdown
[轉移至：實作者]
    ↓
[當前角色：Tn 實作者]
    ↓ 實作 + checkpoint
[轉移至：總控審查]
    ↓
[當前角色：總控審查]
    ↓ QA ACCEPT 或退回 Implementer
```

如果任務本身不需要拆成 T1/T2…，仍要依該任務的設計/驗收 gate 決定何時從 PM 轉 Implementer；不得因「任務小」跳過專案 Preflight、branch-first 或必要 QA。

## 3. PM：工單與 Authority Gate

### 3.1 Requirement RED-first

若需要拆工單，固定先讀：

`.agents/skills/engineering/拆解任務工單/SKILL.md`

PM 必須：

1. 依 Requirement 建立 requirement-level RED，且實跑到能證明目前狀態不符合使用者需求。
2. 與使用者逐條確認 RED 是否代表真正需求。
3. 在使用者核准 RED 前，**不得拆解工單**、不得建立 tracker/local ticket、**不得轉移至：實作者**。
4. RED 核准後才草擬 T1/T2… breakdown；breakdown 本身仍需使用者第二次核准。

### 3.2 每張票的 Authority

每張核准工單至少明列：

- `Requirement Authority`
- `Approved RED IDs`
- `AI Library References`
- `AI Library Writeback`
- baseline / target SHA
- blocking dependency
- acceptance criteria
- Combined Acceptance owner（若適用）

拆票前必須實際搜尋/讀取相關 `個人AI檔案庫/**`。不得只口頭寫「AI 庫已讀」。若 AI 庫與使用者本輪已核准規格衝突，**最新使用者核准規格**是 authority，並把 AI 庫修正標成 `AI Library Writeback: REQUIRED`。

### 3.3 GitHub owning Issue 硬閘門

若施工來源是 GitHub repository，**每張核准工單都必須先建立真正的 GitHub owning Issue**，再遠端反讀確認：

- `issue_number`
- canonical URL
- title
- baseline/target SHA
- Approved RED IDs
- Requirement Authority
- AI Library References / Writeback
- dependency
- acceptance criteria

`issue_number` / URL / title 任一 undefined、null 或空值即 fail closed。`.scratch/**/issues/*.md`、聊天中的 T 編號、checkpoint、branch 名稱都只是 mirror/provenance，不能代替 GitHub owning Issue。

若事後才發現漏建 Issue：立即停止新增 production 變更，補建 Issue，並明確標示 **Retroactive provenance / 施工後補建**；寫入實際施工 branch、已發生 commit/run/evidence 與 target。不得假裝事後 Issue 原本就存在。

### 3.4 PM → Implementer

只有 requirement RED 已核准、breakdown 已核准、owning Issue 已建立且反讀成功、必要 AI Library authority 已讀完，才輸出：

`[轉移至：實作者]`

然後同一次工作流程直接進下一狀態，不以「已派工」作為停工點。

## 4. Implementer：實作與 Checkpoint

### 4.1 角色標記

進 Worker 時回覆開頭使用：

`[當前角色：Tn 實作者]`

`Tn` 依實際工單替換。Implementer 專注於該票 production/test/Skill 修改，不混入新的 PM scope decision。

### 4.2 實體 checkpoint

每完成一個可恢復的實質修改單位，必須產出**實體 checkpoint path**；可使用 ZIP、durable worktree snapshot、remote artifact 或專案核准的等價形式。checkpoint 不能只是一段聊天文字。

checkpoint / state 至少記錄：

- task id / 工單 id
- 目前角色
- branch + HEAD
- 已完成 / pending / failed / blocked
- 相關 production/test/Skill/AI Library 檔案
- 驗證命令與最後結果
- 下一步 resume command
- owning Issue

若下一步是長回歸，已有尚未封裝的變更時，**先封 checkpoint 再進長回歸**。

### 4.3 checkpoint provenance

每個已驗收 checkpoint 都要保存 **checkpoint provenance**：來源 FULL/上一 checkpoint SHA256、已修改檔案清單與 SHA256，組成可重算的 **execution tree fingerprint**。

fresh extract、checkpoint restore、Runtime 重建或手動複製後，在 resume 前重算 execution tree fingerprint，與**最近已驗收 checkpoint**比對。

若出現部分檔案舊、部分新版、來源包 identity 不符或 fingerprint 不同，標記為**混合狀態**。混合狀態不得靠 mtime、聊天記憶或挑檔補拷貝續工；必須回乾淨目錄從最近已驗收 checkpoint 完整恢復，再重放未驗收變更。

### 4.4 Implementer → QA

實質修改與 checkpoint 已落盤後輸出：

`[轉移至：總控審查]`

然後進 QA。

## 5. QA：審查與完成條件

### 5.1 角色標記與審查責任

QA 開頭使用：

`[當前角色：總控審查]`

QA 以獨立 reviewer 視角對照 Requirement Authority、actual diff、tests、AI Library 與 owning Issue。若不合格，退回 Implementer；不得為了關票降低 oracle、改規格或掩蓋失敗。

### 5.2 AI Library QA

任何 `AI Library Writeback: REQUIRED` 在 QA ACCEPT 前必須：

- 實際落盤；
- 遠端反讀引用路徑；
- 移除/標記會誤導未來施工的 stale authority；
- 確認內容與最終已核准 requirement / production 結果一致。

### 5.3 Owning Issue QA

GitHub ticketed work 必須反讀 owning Issue，確認 terminal run / PASS-FAIL、final head / target SHA、dependency、acceptance 結果已回寫。沒有 owning Issue 或只有 `.scratch` mirror，不得宣告工單完成。

### 5.4 QA 完成條件

若本票進入測試回歸，只有同時滿足下列條件才可 ACCEPT：

- intended nodeids 全部有 terminal 狀態，沒有 pending；
- 若要求全綠，failed = 0；
- collection count / **collection SHA** 與 journal 相符；
- 無殘留 pytest / Xvfb / child Python process；
- timeout 的 teardown/harness 問題有獨立紀錄，不混成 production failure；
- 已通過區段沒有因 timeout 被無意義重跑；
- REQUIRED AI Library Writeback 已落盤並反讀；
- owning Issue terminal evidence 完整；
- 若啟動 remote QA，已完成第 7 節 lock 到 terminal、cleanup 與 drift audit。

## 6. 測試 Runner / TIMEOUT 協定

### 6.1 每批獨立 process group

每個 pytest / GUI batch 使用獨立 **process group / session**（例如 `start_new_session=True` 或等價機制）。timeout、取消或外層 Runtime 中斷時，要終止**整個 process group**，不能只 kill 父 pytest。

優先 TERM，短暫 grace 後再 KILL；最後確認沒有殘留 pytest / Xvfb / child Python。若 runner 有 `killpg` 能力，以整個 process group 為 cleanup 單位。

禁止留下 99% CPU orphan pytest 污染下一批。

### 6.2 Xvfb ownership / hard kill

長 GUI batch 不依賴 `xvfb-run` 當唯一 lifecycle owner。優先由 runner 自行啟動 Xvfb、等待 DISPLAY ready、傳入 pytest，最後自行清理。

Linux 外層可能 `SIGKILL` runner 時，只靠 Python `finally` 不夠；Xvfb child 要有 kernel **parent-death** guard（例如 `PR_SET_PDEATHSIG` / `PDEATHSIG`）。hard-kill regression 必須真的 `SIGKILL` 父 runner，再確認 Xvfb PID 已死亡/成 zombie，不只 mock callback。

若只能用 `xvfb-run`，只跑短批，並以 pytest log summary 判讀測試本體，不用 wrapper timeout 直接判 production fail。

### 6.3 TIMEOUT 分類

收到 TIMEOUT / 外層時間切斷後，第一動作是讀 log + process 狀態，**不得直接重跑**。

**complete**

- 有完整 pytest summary；
- 沒有 failed / error / collection error；
- 即使 wrapper 後續 timeout，測試本體仍算完成。

**complete_teardown_timeout**

- pytest 已明確印出**完整 PASS summary**；
- 但 interpreter / Tk / Matplotlib / Xvfb / wrapper 在 teardown 不退出。

只有完整 PASS summary 才准用此狀態。**只看到點號**、局部 `%`、單顆 print、scene dump、`[100%]` 但沒有最終 summary、或 wrapper 自己說 success，都**不得標記 complete_teardown_timeout**。

此狀態記測試本體完成，kill 殘留 process group，並另追 harness/teardown；**不得重跑已完成** nodeids。

**incomplete_timeout**

- 沒有完整 summary，或只跑到中途。
- 不得判 PASS，也不得直接判 production FAIL。
- kill process group，保存已完成 nodeid 證據，只重跑 pending。

只有 pytest 自己的 `FAILED` / `ERROR` / collection failure 才是**真 RED**。

### 6.4 Timeout 後縮批

`incomplete_timeout` 後把未完成範圍二分：例如 100 → 50 → 25 → 10 → 單檔/單 nodeid。

已具完整 PASS summary 的 batch/nodeid 從 pending 移除，禁止為方便整段重跑。單顆獨立 PASS、放在某 prefix 後才 hang/fail 時，用 prefix/binary bisection 找 order-dependent 污染源；禁止改 production 幾何、尺寸常數或放寬 oracle 來讓 gate 過。

### 6.5 Journal / Resume

長回歸維護可恢復 journal（JSONL 或等價），每批結束立即落盤，至少包含：

- collection count；
- collection SHA / nodeid list hash；
- batch / nodeids；
- `complete` / `complete_teardown_timeout` / `incomplete_timeout` / `failed`；
- passed / skipped / failed；
- log path；
- elapsed time。

Resume：

- collection count 或 SHA 改變 → **拒絕沿用舊 journal**；
- collection 相同 → **只跑 pending**；
- Runtime 被切斷 → 先讀現有 log/journal，再決定續跑範圍，不憑聊天記憶重建進度。

journal 的 collection identity 不能代替 source-tree execution tree fingerprint；兩者都一致才可安全 resume。

## 7. Remote QA Active Lock

### 7.1 啟動監控

只要建立 GitHub Actions / remote current-head QA / 等價 remote CI run，立即讀並使用：

`.agents/skills/engineering/monitoring-remote-qa/SKILL.md`

鎖定本輪 **`run_id + head_sha`**。workflow trigger 只代表監控開始，不是 QA 完成。

### 7.2 REMOTE_QA_ACTIVE_LOCK

`monitoring-remote-qa` 一旦鎖定 non-terminal run，派工狀態機進入 **`REMOTE_QA_ACTIVE_LOCK`**。

Lock 期間不得：

- 回 Implementer 做新修改；
- 探索其他模組；
- 啟動下一張票；
- 以「順便先查」插入非 polling 工作。

Lock 期間允許：poll run/jobs/steps、terminal failure log classification、必要的 30 秒使用者進度回報。

若 job failure：先讀 failed-job log，依本 Skill TIMEOUT 分類與 `diagnosing-bugs` 判定 production / harness / workflow failure。只有需要 replacement run 時才解除舊 run 的 terminal lock；新 run 建立後立即以新 `run_id + head_sha` 重新上鎖。

### 7.3 Terminal 後仍未完成

`completed + success` 後仍要：

- 取得 exact PASS/FAIL + invariant evidence；
- 清除 one-shot workflow / trigger；
- 遠端反讀 cleanup；
- 更新 checkpoint/journal/state；
- 做 tested-head → cleaned-head drift audit；
- 回寫 owning Issue terminal evidence。

全部完成才可 QA ACCEPT / close。

聊天/工具 Runtime **不得成為 remote QA scheduler**。長 run 本身要能 durable checkpoint/resume；若 Runtime 中斷，下回合從既有 `remote_qa_run_id` / `run_id + head_sha` 接手，禁止因聊天斷線重新 trigger 全套。

## 8. 30 秒進度回報

只要派工任務尚未完成，對話層**每 30 秒**至少回報一次；內容至少包含：

- **目前工單**；
- 正在做什麼；
- **最新測試**或進度數字；
- 是否 blocked，以及 blocker 是什麼。

回報只是觀測點，**不得中斷**正在執行的正常工作、不得因此 kill 測試、不得把回報當作停工點。若單次不可中斷 tool call 本身超過 30 秒，工具返回控制權後立即補報。

未完成前不得只回「還在跑」後結束；TIMEOUT 也不是停工理由，而是進入 log 判讀、process-group cleanup、縮批與 resume 的觸發條件。

## 9. 掃描深模組來源檢查

若工作由 `掃描深模組` 候選轉入實作，任何 Implementer production write 前再確認：

- owning Issue 已建立並反讀；
- breakdown 已指定 AI Library Writeback owner；
- breakdown 已指定 Combined Acceptance owner；
- 任一 ownership 缺失就退回 PM 補齊；branch、checkpoint、HTML 報告、`.scratch/**` 都不能代替；
- closing owner 的 QA 必須包含 AI Library writeback、Combined terminal QA、workflow cleanup、drift audit、integration evidence。

## 10. Skill 自我檢查

修改本 Skill 後必須確認：

- [ ] frontmatter `name: 派工`，且沒有 stale `name: dispatching`。
- [ ] description 只描述觸發邊界與核心責任，不塞完整 workflow。
- [ ] Skill 少於 500 行。
- [ ] `AGENTS.md` / Preflight / branch-first 明確且不被派工繞過。
- [ ] PM → Implementer → QA 角色標記完整。
- [ ] Requirement RED-first + 使用者核准 + breakdown 第二次核准完整。
- [ ] 每票都有 `Requirement Authority`、`AI Library References`、`AI Library Writeback`。
- [ ] GitHub 專案每票在 Worker 前都有真正 GitHub owning Issue 並反讀 number + URL + title。
- [ ] 漏建 Issue 用 Retroactive provenance，不能偽造時序。
- [ ] checkpoint / journal 能讓下一回合不靠聊天記憶續工。
- [ ] checkpoint provenance + execution tree fingerprint 阻止混合狀態續工。
- [ ] process group + killpg/等價 cleanup 完整。
- [ ] `complete_teardown_timeout` 與 `incomplete_timeout` 分開，前者要求完整 PASS summary。
- [ ] 只看到點號/局部輸出不得算 complete_teardown_timeout。
- [ ] timeout 後不重跑已通過區段，只跑 pending。
- [ ] collection SHA + journal/resume 防止舊證據誤用。
- [ ] Xvfb 有 SIGKILL / parent-death guard 契約。
- [ ] remote QA 建立 run 即啟動 `monitoring-remote-qa`，鎖 `run_id + head_sha` 到 terminal。
- [ ] `REMOTE_QA_ACTIVE_LOCK` 期間沒有其他工作插隊。
- [ ] success 後仍做 cleanup + durable state + drift audit 才 ACCEPT。
- [ ] `NON_TERMINAL_CONTINUE`：pending / CHECKPOINT /「尚未完成」只可做狀態觀測；沒有合法 stop condition 時必須立即執行下一個可執行 action，不得直接結束回合。
- [ ] 「不假報完成」與「未完成持續施工」兩項義務皆有明文，前者不得被用作停工理由。
- [ ] 未完成派工每 30 秒回報目前工單、正在做的事項、最新測試/進度數字與 blocker，且不得中斷執行。
- [ ] 未宣稱不存在的背景工程師、subagent 或 scheduler 正在替你工作。
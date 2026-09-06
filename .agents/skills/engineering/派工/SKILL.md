---
name: dispatching
description: 人工指定時使用：套用專案內角色自動切換與進度落盤協定。
disable-model-invocation: true
---

# 角色自動切換與進度落盤協定 (Role Auto-Switching & Checkpoint Protocol)

當收到開發任務時，若當前環境不支援真正的背景獨立 Subagent Runtime，你必須**自動在內部完成角色切換**，嚴禁停止對話等待不存在的第三方回報。

## 1. 狀態機流程 (State Machine)
[ 階段 1：總控 PM ] ➔ [ 階段 2：實作者 Worker (含實體檔案落盤) ] ➔ [ 階段 3：審查者 QA ]

## 2. 各階段行為與自動切換觸發條件

### 階段 1：總控 (PM Mode)
- **職責**：分析規格、建立需求驗收條件；若需要拆解工單（如 T1, T2...），必須先執行 `.agents/skills/engineering/拆解任務工單/SKILL.md` 的 **RED-first** gate。
- **拆工單硬閘門**：先按 Requirement 寫並實跑 requirement-level RED，與使用者逐條論證；在 **使用者核准** RED 前，**不得拆解工單**、不得建立 tracker/local ticket，也**不得轉移至：實作者**。RED 核准後才可草擬工單；工單拆法本身仍需使用者第二次核准。
- **自動轉移條件**：只有在「RED 已核准 + 工單 breakdown 已核准」後，才在同一次回覆中標記 `[轉移至：實作者]`，並自動進入階段 2。若任務本身不需要拆工單，則依該任務自己的設計/驗收核准 gate 決定是否轉移。

### 階段 2：實作者 (Implementer Mode)
- **輸出標示**：回覆開頭必須加上 `[當前角色：T1 實作者]`（依實際工單編號替換）。
- **職責**：禁止發表 PM 評論，完全專注於撰寫或修改 Production Code。
- **強制實體落盤 (Artifact Checkpoint)**：為防止 Runtime / 工具回合被清空，每次完成單一工單的實質修改後，**必須產出包含本次修改的實體檔案或 ZIP checkpoint，並在對話中直接提供下載連結**。嚴禁只有口頭進度、背景靜默修改或只貼長篇程式碼。
- **長回歸前 checkpoint**：若已有尚未封裝的 production / test / skill 變更，且下一步要跑長時間測試，**先封 checkpoint 再進長回歸**，避免 TIMEOUT 後只剩口頭進度。
- **自動轉移條件**：確認產出實體 checkpoint 後，標記 `[轉移至：總控審查]`，自動進入階段 3。

### 階段 3：審查整合 (QA/PM Reviewer Mode)
- **輸出標示**：回覆開頭必須加上 `[當前角色：總控審查]`。
- **職責**：以第三人稱視角做規格對照、邏輯檢查與回歸驗證。
- **測試策略**：優先採**單一模組／小批次**執行；不得用「一次跑全套然後等超時」取代可恢復的小批 runner。若不合格則退回階段 2；合格才封存工單並推進下一項。

## 3. 測試 Runner / TIMEOUT 硬協定

### 3.1 每批必須有獨立 Process Group
- 每個 pytest / GUI 測試批次必須建立**獨立 process group / session**（例如 `start_new_session=True` 或等價機制）。
- timeout、取消或外層工具回合中斷時，必須終止**整個 process group**，不能只 kill 父 pytest。
- 優先先送 TERM，再於短暫 grace period 後送 KILL；結束後必須確認沒有殘留 `pytest` / `Xvfb` / child Python process。
- **禁止**讓 99% CPU 的孤兒 pytest 留在背景繼續跑，因為它會讓後續批次看起來全部 timeout。

### 3.2 GUI 測試的 Xvfb Ownership
- 長批 GUI 測試**不得依賴 `xvfb-run` 當生命週期 owner**；它可能在 pytest 已完成後卡在 wrapper / teardown。
- 優先由 runner 自己啟動 Xvfb、等待 DISPLAY ready、把 DISPLAY 傳入 pytest，最後由 runner 自己終止 Xvfb。
- **外層 hard kill 防線**：只靠 Python `finally` 不足以處理 runner 本身被 `SIGKILL` 的情況。Linux runner 啟動 Xvfb 時必須使用 kernel parent-death guard（例如 `prctl(PR_SET_PDEATHSIG, SIGTERM)` / `PDEATHSIG` 等價機制），確保父 runner 消失時 Xvfb 不會被 PID 1 收養成 orphan。
- hard-kill regression 必須真的 `SIGKILL` 父 runner，再驗 Xvfb PID 已死亡／成 zombie，不得只 mock cleanup callback。
- 若環境只能使用 `xvfb-run`，只准跑短批次，且必須用 log summary 判讀 pytest 本體結果，不能用 wrapper timeout 直接判成 fail。

### 3.3 TIMEOUT 分類：先看 pytest 證據，不能看到 timeout 就喊失敗
收到 timeout / 外層工具時間切斷後，**第一動作是讀 log 與檢查 process 狀態，不得直接重跑**。

將結果分成三類：

1. **complete**
   - log 已出現完整 pytest summary（例如 `[100%]`、`N passed` / `N skipped`），且沒有 `failed` / `error` / collection error。
   - 即使 shell / Xvfb wrapper 後續 timeout，也視為**測試本體完成**。

2. **complete_teardown_timeout**
   - pytest 已明確印出**完整 PASS summary**，但 interpreter、Tk、Matplotlib、Xvfb 或 wrapper 在 teardown 不退出。
   - **只有完整 PASS summary 才能使用此狀態**；只看到點號、單顆測試的局部輸出、`[100%]` 但沒有最終 summary，或 wrapper 自己宣稱成功，都**不得標記 complete_teardown_timeout**。
   - 記錄為完成，kill 掉殘留 process group，**不得重跑已完成的測試**，並另開 harness/teardown 工單追原因。

3. **incomplete_timeout**
   - log 沒有完整 summary，或只跑到中途點號 / 百分比。
   - 不得判 PASS，也不得判 production FAIL；若 Tk/Xvfb targeted gate 串跑時只看到點號後程序不退出，也先歸此類，再用單 nodeid / prefix isolation 判定是 order-dependent teardown 還是真功能問題。
   - kill process group，保留已完成節點證據，只重跑**未完成範圍**。

只有看到 pytest 自己的 `FAILED` / `ERROR` / collection failure 才是**真 RED**。

### 3.4 Timeout 後必須縮小批次，不准整段重跑
- 一批 `incomplete_timeout` 後，優先把未完成範圍**二分**（例如 100 → 50 → 25 → 10 → 單檔／單 nodeid）。
- 已經有完整 PASS summary 的批次／nodeid 必須從 pending 集合移除，**禁止為了方便重跑已通過區段**。
- 若單一測試單跑 PASS、放在前置測試後才 hang/fail，依序做 prefix/binary bisection 找 order-dependent 污染源，不得修改幾何常數或放寬 oracle 來遮掉污染。

### 3.5 Journal / Resume：每批結果立即落盤
長回歸必須維護可恢復 journal（JSONL 或等價格式），每批結束立即寫入，至少包含：
- test collection 數量；
- collection SHA / nodeid 清單 hash；
- batch / nodeids；
- 狀態：`complete` / `complete_teardown_timeout` / `incomplete_timeout` / `failed`；
- passed / skipped / failed 數；
- log 路徑；
- elapsed time。

Resume 時：
- collection 數量或 SHA 改變 → **拒絕沿用舊 journal**；
- collection 相同 → 只跑 pending 節點；
- 外層工具回合被切掉 → 先讀既有 log/journal，再決定是否需要續跑，**不得憑記憶重建進度**。

### 3.5.2 Targeted Gate Teardown Guard：測試完成與程序退出必須分開判定
- GUI / Tk / Matplotlib / Assembly targeted gate 若程序不退出，**先判定 pytest 本體是否完成，再判定 teardown**；兩者不可混成一個 fail。
- **完整 PASS summary 是唯一可把 hang 分類為 `complete_teardown_timeout` 的必要條件**。只看到 `.`、`[xx%]`、單顆 print、scene dump、wrapper exit code，都不能當 PASS。
- 串跑多顆時若只有局部輸出後 hang：標記 `incomplete_timeout`，先 kill 整個 process group，再把 pending 範圍縮到單 nodeid；若單顆各自 PASS，記為 order-dependent teardown / harness 污染，production 不得判 fail。
- 若單顆 PASS 但組合順序才 hang，下一步用 prefix / binary bisection 找污染源；**禁止改 production 幾何、尺寸常數、oracle 或放寬 assertion 來讓 gate「過」**。
- targeted gate 的 durable checkpoint 必須記錄每個 nodeid 的終態與 log 路徑；任何沒有完整 summary 的 nodeid 仍屬 pending。

### 3.5.1 Checkpoint Provenance Guard：禁止在混合 execution tree 上續工
- 每個已驗收 checkpoint 除 journal/state 外，必須保存 **checkpoint provenance**：來源 FULL/上一 checkpoint SHA256、已修改 production/test/skill 檔案清單及 SHA256，組成可重算的 **execution tree fingerprint**。
- 任何 fresh extract、checkpoint restore、工具回合重建、手動複製檔案後，在進下一張工單或 resume 長回歸前，先重算 execution tree fingerprint，與**最近已驗收 checkpoint** 比對。
- 若出現「部分檔案回到舊版、部分仍是新版」、fingerprint 不符、來源包 identity 不符，立即標記為**混合狀態**；禁止靠 mtime、聊天記憶或挑檔補拷貝後繼續。
- 混合狀態的唯一安全恢復路徑：隔離/丟棄該執行目錄 → 從最近已驗收 checkpoint 在乾淨目錄完整還原 → 驗 fingerprint 一致 → 再重放尚未驗收工單。
- journal 的 collection SHA 只能證明「測試集合 identity」，**不能代替 source tree provenance**；兩者都一致才可 resume。

### 3.6 QA 完成條件
只有同時滿足以下條件，才准宣告該回歸批次完成：
- [ ] intended nodeids 全部有終態（complete / skipped / failed），沒有 pending；
- [ ] failed = 0（若本工單要求全綠）；
- [ ] collection count / SHA 與 journal 相符；
- [ ] 無殘留 pytest / Xvfb / child Python process；
- [ ] timeout 造成的 teardown/harness 問題另有明確紀錄，不得混成 production failure；
- [ ] 任何已通過區段沒有因 timeout 被無意義重跑。

## 4. 核心限制條款
- **嚴禁虛構等待**：嚴禁出現「工單已派發給其他工程師，請等待」等虛構話術。你「本人」就是唯一執行者。
- **絕不停頓**：未完成任務前，不得以單純回報進度作為終點。若工具／Runtime 不可抗力中斷，先以最近 checkpoint + journal 恢復，然後直接續工。
- **30 秒進度回報**：只要派工任務尚未完成，對話層必須每 30 秒至少回報一次目前進度；內容至少包含「目前工單／正在做什麼／最新測試或進度數字／是否有阻塞」。回報只是一個觀測點，**不得因此暫停、等待、結束或重啟正在執行的任務**。若單次不可中斷工具呼叫本身超過 30 秒，工具返回控制權後立即補報，且不得為了湊回報頻率殺掉正常執行中的測試或程序。
- **禁止憑文字記憶重構**：環境重置後若完整工作樹不存在，必須從最近的實體 checkpoint ZIP 還原；缺 checkpoint 才向使用者要求上傳。
- **目標導向**：未完成前不得等待不存在的第三方；「TIMEOUT」本身不是停工理由，而是進入 log 判讀、killpg、縮批與 resume 流程的觸發條件。

## 5. Skill 自我檢查
修改本 Skill 後必須確認：
- [ ] frontmatter `name: dispatching` 不變；
- [ ] description 只描述觸發邊界，不塞 workflow；
- [ ] Skill 本體少於 500 行；
- [ ] 明確包含 process group + killpg；
- [ ] 明確區分 `complete_teardown_timeout` 與 `incomplete_timeout`；
- [ ] 明確要求 journal/resume 與 collection SHA 防舊證據誤用；
- [ ] 明確禁止 timeout 後重跑已通過區段；
- [ ] checkpoint / journal 可讓下一回合不靠口頭記憶續工；
- [ ] 明確包含 checkpoint provenance / execution tree fingerprint，禁止混合狀態續工；
- [ ] complete_teardown_timeout 明確要求完整 PASS summary，只有點號不得算完成。
- [ ] 若 PM 要拆解工單，明確引用 `.agents/skills/engineering/拆解任務工單/SKILL.md`，要求 RED-first + 使用者核准，且核准前不得拆解工單、不得轉移至：實作者。
- [ ] 明確要求未完成派工每 30 秒回報目前工單、正在做的事項、最新測試/進度數字與阻塞狀態，且回報不得中斷執行。

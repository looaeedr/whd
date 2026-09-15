---
whd_doc_role: REFERENCE
whd_contract: continuous-execution-machine
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Executable Continuity Controller / 文件規則不等於執行鎖

## EXECUTABLE_CONTINUITY_CONTROLLER_PITFALL_V1

### 事故

WHD 已經有 `NONTERMINAL_NEXT_ACTION_GATE`、`REMOTE_QA_ACTIVE_LOCK`、`STALE_WAIT_WATCHDOG`、30 秒 polling、`使用者不是 scheduler` 等完整文字規則，但實際長流程仍會出現「規則說不能停，工作卻在 non-terminal 狀態結束回合」。

根因不是再少一句提醒，而是舊 machine guard 多數只做：讀 Skill / AI Library 文字，再 `assert` 某些 marker 字串存在。這只能證明**文件寫了規則**，不能證明 runtime state 可保存、可恢復，也不能真的拒絕 non-terminal finalization。

### 永久判定

1. **Documentation != enforcement.** `final 禁止`、`使用者不是 scheduler`、`STALE_WAIT_WATCHDOG` 等 marker 只能當文件相容性 guard，不能再被描述為「已鎖死停頓路徑」。
2. 長流程 durable state 的 executable authority 是 `tools/continuity_controller.py`，操作/語意 authority 是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md`。
3. Non-terminal states 固定為 `RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED`，每一個都必須有非空 `next_action`；沒有就 fail closed。
4. `WAITING_REMOTE` 必須有 exact positive `run_id + head_sha`，並在可得時保存 `job_id / log_cursor / evidence`。文字寫著 WAITING 不是遠端真相。
5. checkpoint 必須 versioned + atomic persistence；runtime cut 後 `load_checkpoint → identity/drift verification → exact next_action`，不得重新把使用者當 scheduler，也不得無條件重跑已完成 phase。
6. `assert_finalizable` 是 workflow/issue/acceptance closure 的 machine gate。任何 non-terminal checkpoint 都必須拒絕 finalization；只有 `TERMINAL_SUCCESS / TERMINAL_FAILURE` 可通過 controller gate。
7. Remote run terminal 不等於整張工作 terminal。若 counts / invariants / cleanup / drift / issue closure 還有 next action，state 應回 `RUNNING(next_acceptance_action)`，不得提前落 `TERMINAL_SUCCESS`。
8. `BLOCKED` 代表工作暫時需要外部 authority，但在 controller 層仍是 non-terminal；它不能被拿來繞過 workflow completion gate。
9. 真正驗收必須是 behavior tests：建立 checkpoint、模擬 runtime cut、reload、驗 exact identity/cursor/evidence、嘗試 non-terminal finalization 並確認被拒絕、驗 terminal transition lock。只搜文字不算。
10. 平台仍可能硬切聊天 Runtime；repo controller 無法控制平台。但正確目標是 **platform cut != workflow state loss / remote work stop**：遠端 runner 自己續跑，下一 Runtime 從 durable checkpoint 精準接續。

### 對應 Machine Guard

- `tools/continuity_controller.py`
- `tests/process/test_continuity_controller.py`
- `.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- `.agents/skills/engineering/執行開發任務/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`
- `.agents/skills/engineering/issue-closure-gate/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`

### 禁止說法

- 「Skill 已經寫了，所以不會再停。」——錯，除非 executable state / finalization behavior 有實證。
- 「pytest 有檢查 marker，所以 runtime guard 已完成。」——錯，那只是 documentation contract。
- 「remote run 還在跑，等使用者下次打繼續再查。」——錯；chat runtime 可用時主動 poll，runtime 被硬切後則從 durable run identity 恢復。
- 「平台切掉就沒辦法，所以 checkpoint 沒意義。」——錯；無法控制平台不代表可以接受 state loss 或把 remote scheduler 交給使用者。

## TURN_EXIT_ENFORCEMENT_V2

`assert_finalizable` 只能拒絕「把 non-terminal workflow 宣告完成」，不能單獨拒絕「assistant 在 non-terminal progress 回報後結束目前 turn」。這兩個 boundary 必須分離：

- workflow/issue completion → `assert_finalizable`；
- assistant response/turn boundary → `assert_turn_exitable`。

`RUNNING / WAITING_REMOTE / RECOVERING` 有可自主 next action，因此 turn exit fail closed；`BLOCKED` 代表真正外部 wait，可結束 turn但仍不可 finalizable；terminal states 可通過兩者。特別是 remote run terminal 後，只要 cleanup/drift/closure 未完，必須回 `RUNNING(next_acceptance_action)` 並由 turn-exit guard 接手，不能因 remote lock 解除就回報後停止。

對應 machine guard：`tools/continuity_controller.py` + `tests/process/test_continuity_controller.py`。Skill/AI marker tests 只保護 bridge 存在，不得再次被誤稱為 runtime enforcement。

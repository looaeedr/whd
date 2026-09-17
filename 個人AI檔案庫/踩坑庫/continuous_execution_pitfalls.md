---
whd_doc_role: REFERENCE
whd_contract: continuous-execution-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 長流程持續執行 / 停工點踩坑規則

## Authority status

本文件是 REFERENCE，不是 executable authority。Machine CURRENT 是 `tools/continuity_controller.py`；operations/semantic CURRENT 是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md`。衝突時以 CURRENT 為準。

## 永久規則

進度回報不是工作終點；只要有可自主 next action 且無真正 blocker/runtime interruption，就繼續。使用者不是續跑 scheduler。Test/QA RED 可自行診斷時走 evidence → root cause → minimal fix → validation → retry。Runtime 硬切前留下 durable checkpoint，下一回合驗 drift 後續 exact next action。

## SCHEDULED_WAKEUP_STATUS_ONLY_PITFALL

事故模式：automation 喚醒後只查一次狀態、回報「仍在跑／已 GREEN／沒有 RUN」，然後把下一步留給下一次排程或使用者再次輸入「繼續」。這會把排程頻率誤當執行頻率，並讓 status-only response 成為隱性停工點。

永久參考規則：

- `wake-up trigger != execution owner`：automation 只負責喚醒；execution owner 仍是 owning issue/checkpoint/branch/plan。
- 喚醒第一步恢復並 live verify owning identity 與 concrete RUN identity。
- 有 RUN 就追到 terminal，讀 evidence 後立即續下一 autonomous step；terminal 不是 status-only exit。
- 無 required RUN 時分類 `RUN_NOT_CREATED`；禁止等待不存在的 RUN，直接執行/修復應建立 RUN 的 prerequisite/trigger。
- GREEN 往下一 gate；RED 讀 exact failure、修復、重驗。`status update != exit`。
- 排程 cadence 只是 wake-up cadence；單次已喚醒 execution turn 仍要持續推進，不得故意切成每小時一步。
- 平台若強制結束，先持久化 owning issue、branch、HEAD、RUN identity/status、last accepted gate、next exact action、禁止事項；下一 wake-up 從該 checkpoint 續跑。

本節只是 pitfall/REFERENCE。唯一 operations/semantic authority 是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md::SCHEDULED_WAKEUP_CONTINUITY_CONTRACT`；remote polling mechanics 才由 `monitoring-remote-qa` 負責，不得從本文件建立第二套 state machine。

## REMOTE_TERMINAL_CLOSING_LOCK_GAP

Remote terminal 只解除 remote lock。若 counts/invariant/cleanup/tested→closing drift/AI writeback/closure 尚未完成，checkpoint 回到 `RUNNING(next_acceptance_action)`；progress/PASS/integrated 都不是 exit reason。Executable turn-exit behavior 仍由 `tools/continuity_controller.py` 判定。

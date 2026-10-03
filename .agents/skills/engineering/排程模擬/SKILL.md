---
name: 排程模擬
description: WHD A/B recurring scheduler lane 與 /排程A、/排程B same-lane resume 入口。只透過 Flow v2 ExecutionRecord、lease/YIELD 與 structured next_action 執行。
whd_doc_role: MIRROR
whd_contract: scheduler-interactive-lane-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 排程模擬

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`，並完成 project Phase6 Preflight；不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Lane identity
- A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`；entrypoints=`00/20/40`。
- B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`；entrypoints=`B15/B45`。
- entrypoint 不是 owner；scheduled 與 interactive resume 必須保存真實 invocation provenance。

### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

若新 
### SHARED_0_SCHEDULER_HARD_GATE_V1

- 排程 A/B 不擁有另一份 0；所有 scheduler/interactive/work-slot 共用 `.unpushed/docs/0` 與 `.unpushed/body/0`。
- 同 path 已有 lineage 時，scheduler 必須以 latest `0` generation+hash 為 base；不得以自己的舊 checkout/branch/base 覆寫。
- merge conflict 固定 checkpoint=`WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1`、state=`BLOCKED_USER_DECISION`，通知使用者；沒有 `EXPLICIT_USER_CONFLICT_DECISION` 不得自行選 ours/theirs 或繼續 `/推推`。
- Flow v2 path reservation 只在 delivery phase取得，不得把 reservation conflict 升格成 root施工前置條件。

scheduler invocation 在 project startup 階段還不知道 exact owning Issue，先依 canonical Flow v2 做 `READ_ONLY_BOOTSTRAP_ONLY`：只讀 `coord/execution-v2`、derived ready-index、`tools/execution_scheduler_view.py` scheduler projection 與 Issue/branch/HEAD identity；若 current/ready 都空，才額外用 `tools/scheduler_ready_ingress.py` 掃 repository-owner-authored open Issue 第一個 nonblank marker `WHD_SCHEDULER_DISPATCH_REQUEST_V1`（可帶 `lane=ANY|A|B`），用來綁 trusted Phase6 Preflight request。普通 open Issue 不得推論成 work authority。此 bootstrap projection 不得授權 claim、ACQUIRE、transaction、Guard 或 repository mutation。host entrypoint observation 依 canonical fixed NON_AUTHORITY exception 可寫。

Preflight GREEN 且 required Skill/reference 全部 fresh-read 後，必須丟棄 bootstrap projection，再 fresh-read canonical scheduler state，才進入下面的 Wake。禁止建立永久 bootstrap Issue，也不得把這個 bridge 擴張成第二套 scheduler authority。

### STUCK_UNOWNED_FAMILY_TAKEOVER_BRIDGE_V1

排程 A/B 判定既有工單「卡住、沒有人做」時，固定 bridge 到 `flow-v2-execution::STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1`。

- 不得只因 lease expired、heartbeat stale、entrypoint 沒跑或 owner 沒回報就接手；必須 fresh-read target ExecutionRecord，並核對 canonical 父工單、子工單與 delegated lineage。
- 父／子／delegated lineage 任一存在 live lease、valid heartbeat、active trusted transaction、active remote QA 或 `ACTIVE_DELEGATED_WORK`，即視為仍有 active work；scheduler 必須退讓，不得 takeover。
- target 非 terminal 且整個相關 lineage 都無 active writer時，標記 `STUCK_UNOWNED_FAMILY_CONFIRMED` / `TAKEOVER_ELIGIBLE`；此時 A/B scheduler 或任何其他合法 executor 都可 atomic `ACQUIRE/HANDOFF` 接手，不受原 handler/owner 身分限制。
- takeover 前立即重讀一次完整 lineage；race 中重新出現 active writer 固定 `TAKEOVER_RACE_ACTIVE_WORK`。
- takeover 成功只是 ownership recovery，**不是停止點**；同一 invocation 必須 fresh-read並立即續跑原 structured `next_action`。

### BLOCKED_LEAF_CONTINUATION_BRIDGE_V1

排程 A/B 固定 bridge 到 `flow-v2-execution::BLOCKED_LEAF_CONTINUATION_HARD_GATE_V1`。單一 current leaf 因外部等待／authority／capability blocker durable YIELD 後，必須重新投影 same-lane/ready candidates；若仍有合法 executable leaf，cycle 不得 return，固定續做 `CONTINUE_OTHER_EXECUTABLE_LEAF`。只有 current leaf 與所有合法 alternative leaves 都 fresh 證明不可執行時，才可形成 `NO_EXECUTABLE_ALTERNATIVE`。

`LANE_BUSY` 只代表該 exact owner/leaf 需退讓，不代表整個 scheduler 沒工作；若 ready-index/explicit candidate 仍有其他合法 leaf，必須續選。terminal tail 不得 pivot；same-path conflict、active delegated work與 live writer仍 fail closed。

## Wake
每次 host wake 先以 `tools/scheduler_entrypoint_observation.py` 寫 exact entrypoint NON_AUTHORITY WAKE，再 fresh-read `coord/execution-v2`，優先 same-lane nonterminal record；其次才讀 derived ready-index。若 current/ready 都空，必須做 explicit marker candidate discovery；命中時 scheduler view 回 `INGRESS_REQUIRED`，完成 candidate-bound Preflight 後建立 READY、fresh-read並立即 ACQUIRE。live lease退讓、expired lease走 atomic reacquire。只有 current/ready/explicit candidate 全空才可回 NO_EXECUTABLE_WORK。正常 return 前必須寫 exact entrypoint EXIT；不能再留下 SEED-only host occurrence。

`RESUME_CURRENT` 若先 ACQUIRE，ACQUIRE 後同一 invocation 必須立即 fresh-read並執行原 exact `next_action`；不得把拿到 lease 當 progress/停止點。`READY_CANDIDATES` 必須使用 scheduler view 的 deterministic `selected_issue` 立即 ACQUIRE；`INGRESS_REQUIRED` 必須先建立 exact READY，再 fresh-read/ACQUIRE，且 `DISPATCH_READY` 不算 substantive progress。race/conflict後 fresh-read重選。

正常 return 前必須通過 canonical `SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1`：WAKE/讀取/回報/HEARTBEAT/單獨 ACQUIRE 都不算 substantive progress。只有 DONE、LANE_BUSY、合法 BLOCKED、active remote QA wait，或本 invocation 已完成 substantive transaction 後的合法 YIELD 可離開；`SCHEDULER_EXECUTION_NO_PROGRESS` 必須繼續施工，不得停止。

## REPOSITORY_CONTENT_HANDOFF_HARD_GATE_V1

排程A/B 可以擁有 Flow v2 control-plane lease/next_action，但**不能因此取得 GitHub-first 內容施工權**。

- 若 exact next_action 只需要 read/discovery、lease/coordination、trusted preflight、既有候選的 QA/merge/finalization，排程可直接執行。
- 若 next_action 需要新增、修改或刪除 repository content，固定先走 `HANDOFF` 到 canonical `/Google Drive/WHD` shared-unpushed workflow：先分類 docs/body、fresh-read對應 latest `0`，worker 以 latest `0` 為 base，在 root namespace 完成修改/測試，再 merge 回 fresh latest `0`。不得在 GitHub branch 直接 author / patch / hotfix。
- root workspace 必須先完成 change-test classification、targeted/affected/integration/final full gate、`WHD_TEST_EXECUTION_RECEIPT_V1=GREEN` 與 `ROOT_DIFF_FROZEN`；之後才把 exact tested diff push 成候選。
- 只有 selected lane 最新 `0` post-merge GREEN 並 frozen 後，才可由 `/推推 文檔|主體` 取得 delivery reservation、建立 delivery branch。GitHub 在此之後只負責 PR/CI/remote QA/merge verification；verification 揭露內容錯誤時回 shared-0 修正，不在 branch 上補。
- 這個 handoff 不等於停止：scheduler 必須把 structured next_action 留成可恢復狀態；root-tested candidate 出現後，lane 立即接回 post-push integration tail。

<!-- REPOSITORY_CONTENT_HANDOFF_HARD_GATE_V1 -->

## Lifecycle

<!-- SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1 -->

本入口不複製 host recovery state machine；startup 前的 host-layer recovery 唯一服從 `flow-v2-execution::SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1`。正常 Flow v2 execution 仍不得管理 host lifecycle。任何 task-level結果都只是 physical cycle return，固定保留 `CYCLE_END — KEEP_SCHEDULE_ENABLED` 語意。

相容 hard gate 保留原 literal：`不得自行 disable/delete/complete/reschedule自己或 sibling`；此限制適用於正常 Flow v2 execution，canonical host-recovery micro-bootstrap 不擴張 execution authority。

### HOST_LIFECYCLE_WATCHDOG_V1 bridge

scheduler invocation 在 project startup hard gate 完成後、寫 WAKE 前，可且應執行 **read-only host lifecycle inspection**，取得 A00/A20/A40/B15/B45 的 task `enabled / last_run_time`，並以 NON_AUTHORITY snapshot CAS 更新 `coord/monitor-v2:.dispatch/monitor/host/chatgpt-automations.json`。此為唯一 read-only automation introspection 例外；禁止任何 lifecycle mutation API。

每個 entrypoint 必須把自己的 WAKE/HEARTBEAT/PROGRESS/EXIT 同步 mirror 到 exact entrypoint observation file，固定由 `tools/scheduler_entrypoint_observation.py` 建立 canonical `WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1`。WAKE 可在 project startup 前寫入 fixed host-layer path；每個正常 return 都要有 EXIT，所以 host run 不得停在 SEED-only。host snapshot 與 entrypoint mirror 都只是 observability，不可當 claim/lease/transaction authority。

獨立 GitHub watchdog workflow 已退役並移除。需要判讀 host occurrence 時，由當次 scheduler invocation 或 explicit diagnostic 直接呼叫 canonical `tools/scheduler_host_watchdog.py` 讀 NON_AUTHORITY snapshot；不得另建 recurring GitHub Actions watchdog。120 秒 grace 的 `HOST_ENTRY_FAILURE / HOST_AUTO_PAUSE / HOST_STATE_UNKNOWN` 分類語意仍由 evaluator 擁有。


## REPORT_HANDLER_IDENTITY_PREFIX_V1

所有 `/排程A`、`/排程B`、A00/A20/A40/B15/B45 的 **user-visible** progress / CHECKPOINT / terminal / exit 回報，**第一行**固定為：

`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>｜slot=<worker.slot.N|NONE|UNBOUND>】`

相容核心模板：`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>】`。

- handler 只可為 `排程A` 或 `排程B`（或 exact interactive work-slot handler），不得把 entrypoint、foreign lane 或其他 runtime 冒充處理者。
- scheduler 回報必須 fresh-read `lane_owner`、`claim_issue`、`claim_worker`；owner 必須是 real claim owner，不得因目前由排程A/B喚醒就改寫 ownership。
- 沒有 active Issue 時工單=`NONE`；有 bootstrap projection 但尚未 durable bind 時=`UNBOUND`。slot 沒有 exact binding 時=`NONE/UNBOUND`，不得猜。
- foreign owner / foreign lane 只能明確標示 foreign，不得偽裝成本 lane owner。
- 此 prefix 只提供 provenance，**不建立 execution authority**；ownership authority 仍是 canonical ExecutionRecord + lease。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。

對 `SCHEDULER_LANE`，startup declaration 必須先於任何 claim 或 mutation，並明確保留本 invocation 的 lane/entrypoint provenance；若沒有已成立的 durable resume authority，`resume_authority=NONE`。

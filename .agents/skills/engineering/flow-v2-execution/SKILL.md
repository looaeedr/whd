---
name: flow-v2-execution
description: WHD Flow v2 唯一 execution/control-plane runtime contract。用於工單執行、排程 A/B、工作槽、remote QA、handoff、recovery、closure 與 runtime resume；所有入口都必須以 native ExecutionRecord、lease/YIELD、structured next_action 與 atomic terminal transaction 為準。
whd_doc_role: CURRENT
whd_contract: flow-v2-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Flow v2 Execution


## PROJECT_STARTUP_HARD_GATE_V1

<!-- EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1 -->

Flow v2 不得繞過專案啟動硬閘門。每一個新的 task/runtime/invocation（recurring scheduler、/排程A、/排程B、/工作0..3、互動執行、takeover、resume、recovery）在任何 substantive analysis、claim、Guard、repository mutation 或一般 workflow dispatch 前，固定依序：

0. **WORK_ROOT_BOOTSTRAP_HARD_GATE_V2**：先驗 `/Google Drive/WHD` full repo root 與 folder id=`1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN`，讀 `.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json`，確認 `.unpushed/{body|docs}/0` layout。GitHub-only runtime 可讀 repository contract，但不得把 checkout 當內容施工面。
0.5. **ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1**：repository-content implementation 不先建 branch；先走 `ROOT_IDENTITY_CURRENT → LANE_CLASSIFIED → ZERO_INITIALIZED_OR_FRESH_READ → WORKER_BASE_LATEST_ZERO → WORKER_MUTATION_COMPLETE → WORKER_TESTS_GREEN → MERGE_TO_FRESH_LATEST_ZERO → CONFLICT_GATE_OR_MERGED → POST_MERGE_ZERO_TESTS_GREEN → ZERO_MANIFEST_FROZEN`。只有 delivery 才取得 reservation 與 `GIT_WRITE_UNLOCKED`。
0.5.1. **MERGE_CONFLICT_USER_DECISION_HARD_GATE_V1**：shared `0` 三方合併只要 conflict，立即寫 `WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1`、state=`BLOCKED_USER_DECISION`，記錄 conflict path/hunks/base/latest/worker identities 並通知使用者。沒有 `EXPLICIT_USER_CONFLICT_DECISION`，禁止 auto ours/theirs、禁止 generation advance、禁止 merge 回 0、禁止 delivery branch、禁止 push/PR。進度詢問只是 non-blocking checkpoint。
1. ChatGPT execution surface 完成 AI Library pre-action gate：`AI_LIBRARY_SEARCHED → RELEVANT_HISTORY_READ → LIVE_VS_HISTORY_RECONCILED`。
2. 使用 canonical `tools/execution_entry_contract.py` 產生並 user-visible 顯示 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`；每個 invocation 必須重新產生。
3. fresh-read project `AGENTS.md` 與本 `flow-v2-execution` Skill，完成 `SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1`。此時仍未取得 execution mutation authority。
4. recurring scheduler / `/排程A` / `/排程B` 若尚不知道 exact owning Issue，才可使用下面的 `SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1`；其他入口不得借此擴張 startup scope。
5. 對 exact owning Issue + branch + HEAD 執行 Phase6 Knowledge Preflight；GitHub-only runtime 只可送 trusted `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`。
6. fresh-read Preflight 回傳的全部 REQUIRED SKILLS / REQUIRED REFERENCES 並保留 evidence。
6.5. **STARTUP_TRANSITION_GATE_V1**：把本 invocation 的 `WHD_EXECUTION_ENTRY_EVIDENCE_V1` 與 exact owning `Issue + branch + HEAD` 的 `WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1` 收斂成單一 `WHD_EXECUTION_STARTUP_TRANSITION_V1`。fresh admission 只有這張 transition 仍為 `READY_FOR_EXECUTION` 才可進 execution mutation；TTL ≤ 300 秒。
7. scheduler 若曾使用 bootstrap projection，必須丟棄該 projection 並再次 fresh-read canonical scheduler projection；只有到此時，才可進入 Flow v2 ExecutionRecord / transaction / lease / next_action 與正常 WAKE。

### STARTUP_TRANSITION_GATE_V1 — 單一 freshness/admission receipt

`PROJECT_STARTUP_HARD_GATE_V1` 的各步仍保留，但 mutation ingress 不再分散相信多張「各自 fresh」的證據。canonical owner=`tools/execution_entry_contract.py`。

- Phase6 Preflight evidence 固定 schema=`WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1`，必須 `status=GREEN`、綁 exact `issue + branch + head_sha`，且 `required_skills ⊆ completed_skills`、`required_references ⊆ completed_references`。任一缺件固定 fail closed。
- `startup_evidence` 與 Phase6 Preflight 必須綁**同一個 `invocation_identity`**，且 startup / preflight / transition 各自的 evidence age 都不得超過 300 秒。machine `startup_evidence` 可能在 trusted request materialize 時晚於 Preflight 生成，因此**不得用兩張 evidence 的時間先後冒充 authority**；前一 invocation、前一 wake、前一聊天留下的 GREEN 一律不得復用成 fresh admission。
- `build_startup_transition(...)` 產生 `WHD_EXECUTION_STARTUP_TRANSITION_V1`，state=`READY_FOR_EXECUTION`，把 invocation identity、execution mode、Issue、exact branch/HEAD 與共同 expiry 綁成一張 receipt。
- fresh control transaction admission 固定同時攜帶 `startup_evidence + preflight_evidence + startup_transition`；trusted ingress 先驗三者，再 fresh-read current ExecutionRecord，並呼叫 `assert_startup_transition_matches_record(...)`。Preflight 的 branch/HEAD 必須仍等於 current record 的 source/work/target 其中一組 exact identity；否則固定 `STARTUP_TRANSITION_STALE_IDENTITY`，舊 admission 永久失效，必須從最新 state 重做 startup/preflight。
- `LIVE_LEASE_CONTINUATION` session reuse 只可在同一 live lease/invocation 下省略 fresh startup triple；它不得夾帶舊 `startup_evidence / preflight_evidence / startup_transition`，也不得跨 invocation、lease expiry 或 identity drift。
- retired/MIRROR execution skill 不得作為 completed required skill 取得 admission。Registry 歷史關鍵字若命中 retired route，只能 redirect 到其 ACTIVE replacement；不得恢復 retired owner。

這個 gate 的目的不是增加一層流程，而是把原本分散的 freshness 判斷**收成一張 machine-checkable transition receipt**，避免「每一步都說 fresh，但真正 mutation 時已不是同一個 Issue/HEAD」。

### OUTER_ACTION_MACHINE_GATE_V1 — control plane 必須退回 session internal

對 `INTERACTIVE` repository-content work，Flow v2 的 lease / reservation / CAS / session reuse / reconcile / Git-transport transaction / QA consume / finalize drain 都是 machine-internal plumbing。chat outer layer 不得把 `ACQUIRE / RESERVE_PATHS / RECONCILE / LEASE_RENEW / START_QA / ACCEPT_QA / FINALIZE` 等 transaction kind 當成本輪 primary task 或 user-visible next action。canonical content gate=`tools/shared_unpushed_integration.py`; Flow v2 transaction guard仍由既有 execution owners負責；continuity 的 first-substantive-action 記錄也必須拒絕 background-only governance event。

外層只報 `FRESH_READ → LANE_0 → ROOT_MUTATE_TEST → MERGE_0 → POST_MERGE_TEST → /推推 → POST_PUSH_CI → MERGE_FINALIZE` 的 phase outcome。只有真 `PATH_CONFLICT / SAME_ISSUE_OTHER_WRITER / SUBSTANTIVE_TARGET_OVERLAP / MACHINE_FAIL_CLOSED / USER_INPUT_REQUIRED` 才以 `REPORT_BLOCKER` 浮到前台；普通 lease expiry、record stale、governance drift、test RED、status/progress query 一律記 evidence 後繼續目前 primary task。


### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

`READ_ONLY_BOOTSTRAP_ONLY` 是為解除「remote Preflight 需要 owning Issue，但 scheduler 必須先 discovery 才知道 owning Issue」循環依賴的窄例外；它不是 execution phase，也不是 authority。

- 前置條件固定為：work-root gate 已完成（scheduler 使用 `GITHUB_MIRROR`）、AI Library gate 已完成、fresh per-invocation startup declaration 已 user-visible 產生、且已 fresh-read `AGENTS.md` 與本 Skill。
- 唯一可讀範圍：`coord/execution-v2` 的 canonical ExecutionRecords、DERIVED_CACHE_ONLY `ready-index`、`tools/execution_scheduler_view.py` 的純 read-only scheduler projection，以及解析 exact owning Issue / work branch / target branch / HEAD 所需的 GitHub metadata。若 current/ready 都為空，另允許用 `tools/scheduler_ready_ingress.py` 做**窄化 owner-authored marker discovery**：只掃 open Issue 的 number/state/author/body 第一個 machine marker `WHD_SCHEDULER_DISPATCH_REQUEST_V1` 與 `lane=ANY|A|B`；普通 open Issue、label、dependency-unblocked、PR 一律仍不是 authority。此 discovery 只為綁定 Preflight exact Issue，不授權 READY/ACQUIRE。
- 唯一目的：取得 trusted remote Phase6 Preflight 所需的 exact owning Issue + branch + HEAD，然後送出該 Issue 上的 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`。不得建立永久 bootstrap Issue；若 projection 確認沒有可執行工作，仍須完成本 invocation 的 project startup requirements後才能依正常 scheduler exit contract 判讀。
- `PRE_PREFLIGHT_MUTATION_FORBIDDEN`：Preflight GREEN 且全部 REQUIRED SKILLS / REQUIRED REFERENCES fresh-read 完成以前，禁止 canonical lane/runtime WAKE / HEARTBEAT / PROGRESS monitor write、claim、ACQUIRE、transaction request、Guard、repository mutation、QA、merge、closure、takeover、lease mutation、ExecutionRecord mutation或任何其他 execution side effect。**唯一觀測例外**是 host-layer fixed entrypoint file (`coord/monitor-v2:.dispatch/monitor/host/entrypoints/<a00|a20|a40|b15|b45>.json`) 的 WAKE/HEARTBEAT/EXIT，可在 project startup 前由 `tools/scheduler_entrypoint_observation.py` 以 `authority=NON_AUTHORITY` 寫入；它不得包含或授權 Issue ownership / ACQUIRE / mutation。除了 owner-authored trusted Phase6 Preflight request 本身，不得 dispatch 其他 workflow / mutation transport。
- bootstrap projection 只用來綁 Preflight identity；Preflight 完成後必須丟棄並 fresh-read `coord/execution-v2` / scheduler view，禁止把 bootstrap 時看到的 state 直接拿去 ACQUIRE 或 mutation。

startup declaration 只提供 provenance/intent，不取代 claim、Guard、Preflight、ExecutionRecord 或 transaction fencing；bootstrap read-only discovery 也不提供任何 mutation authority。缺任一步固定 `FAIL_CLOSED`。前一聊天、前一 runtime 或前一 scheduler wake 的宣告不得沿用。

<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->

本 Skill 是 WHD execution/control-plane 的唯一 CURRENT operational contract。其他 workflow Skills 只可做入口 bridge，不得建立第二套 ownership、resume、closure、scheduler 或 recovery state machine。

## Canonical authority

- code / PR / CI authority：GitHub repository。
- execution semantic state branch：`coord/execution-v2`。
- per-Issue state：`.dispatch/execution/issue-<N>.json`，schema=`WHD_EXECUTION_RECORD_V2`。
- record/store：`tools/execution_record.py` + `tools/execution_record_store.py`。
- action vocabulary：`tools/execution_action_contract.py`。
- merge precheck：`tools/flow_v2_merge_precheck.py`。
- atomic transition：`tools/control_transaction.py`。
- terminal transport：`tools/control_transaction_transport.py` + `tools/control_transaction_terminal_executor.py`。
- scheduler view：`tools/execution_scheduler_view.py`。
- invocation exit：`tools/execution_invocation_exit.py`。
- work-slot projection：`tools/execution_work_slot_view.py`。
- explicit READY ingress：`tools/execution_dispatch_ingress.py`。
- mutation policy：`tools/execution_authority_policy.py`。
- runtime observability (NON_AUTHORITY)：`coord/monitor-v2:.dispatch/monitor/runtime/*.json`。

### ISSUE_SYNC_ON_SPLIT_AND_DELIVERY_HARD_GATE_V1

Flow v2 對「拆工」與「delivery 完成」都要求 GitHub Issue durable synchronization：

1. **Split before READY**：新 child/follow-up 在 GitHub Issue create/reuse、parent/sub-issue/dependency 更新與 fresh readback 完成前，只是 transient draft；不得建立 `WHD_EXECUTION_RECORD_V2 READY`。Issue sync failure 固定 `ISSUE_SYNC_PENDING_CONTINUE_OTHER_EXECUTABLE_LEAF`。
2. **Delivery after merge**：`MERGE_READBACK_VERIFIED` + delivery receipt 後，必須同步 linked Issues 的 lane/generation/manifest/PR/merged SHA/test result 與 terminal/next_action/blocker，再 fresh-read為 `ISSUE_SYNC_READBACK_VERIFIED`。
3. terminal close authority 不變：只有 Flow v2 `FINALIZE` 可 close/readback Issue；`/推推` 只負責 delivery-side sync，不可另造 closure state machine。
4. `SPLIT_ISSUE_SYNC` / `POST_DELIVERY_ISSUE_SYNC` 是 narrow Issue-plane remote authority，不授權 repository content READ/FETCH/COMPARE/branch/commit/push/merge。

因此「本地已拆好但 GitHub 沒工單」不是 READY；「推推 merge 好但工單沒同步」也不是完整 durable cycle。

## WORKSPACE_EXECUTION_POLICY_V2 — SHARED UNPUSHED 0

互動式 / chat runtime 的 repository-content 工作面固定是 `/Google Drive/WHD` full repo root；正常施工**不建立 Git work branch**。

- docs authority=`.unpushed/docs/0`；body authority=`.unpushed/body/0`。
- worker candidate 可放 `.unpushed/{lane}/workers/<worker>/issue-<N>`；candidate 不是 authority。
- governance / Skill / AGENTS / process authority / governance tests → docs。產品 code/tests/UI/renderer/geometry/manufacturing → body。產品必要文件跟 body。
- later worker 若 path 已進 `0`，固定以 fresh latest `0` generation+hash 為 base。
- worker GREEN 後仍必須 fresh-read latest `0` 三方合併，並跑 post-merge tests；最新 `0` GREEN 才能 freeze。
- conflict 固定 `BLOCKED_USER_DECISION`；沒有使用者明確決策不能自動解。
- `source/manifests`、ZIP snapshot、`/work/active` 不再是 CURRENT repository-content authority。

### REMOTE_CONTENT_IMPLEMENTATION_HANDOFF_HARD_GATE_V2

scheduler / GITHUB_ONLY / REMOTE_ACTION 只擁有 control-plane 與 post-push integration。若 next action 會新增/修改/刪除 repository content，固定 handoff 到 canonical root shared-0 workflow；不得在 GitHub branch 直接 author/hotfix。

root/shared-0 完成 `ZERO_MANIFEST_FROZEN` 後，remote lane 才可進 delivery。GitHub Actions 只作 post-push verification；verification 發現內容錯誤時回 root/shared-0 修正。

### DELIVERY_PATH_RESERVATION_HARD_GATE_V1

Flow v2 `mutation_scope` / `RESERVE_PATHS` 保留，但**只在 selected lane 已 frozen GREEN、準備 `/推推 文檔|主體` 時作 delivery reservation**。它不再是 root/content write 前置 single-writer gate。

固定：

1. selected lane manifest frozen；
2. fresh-read target `main`；
3. 取得 delivery reservation，只綁本次 manifest exact paths；
4. `PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST`；
5. 才允許 `START_BRANCH / APPLY_COMMIT`；
6. reservation conflict 只阻擋 delivery，不得抹掉既有 shared-0 worker成果；
7. conflict 解除後 fresh target + revalidate manifest，再送 delivery。

`RESERVE_PATHS / RELEASE_PATHS` 是 delivery coordination，不算 engineering progress。

### INVOCATION_ADMISSION_SESSION_V2

Startup/root identity 與 Flow v2 lease 仍是 invocation/session-level gate；但 root content authoring 的 authority 是 shared-0 lineage，不是 mutation_scope。

- ACQUIRE/lease 可先存在，用於 owning Issue 與 liveness；不能因此禁止另一 worker以 latest `0` 為 base 做 candidate。
- delivery 前才要求 exact manifest reservation。
- `START_BRANCH / APPLY_COMMIT` 仍必須 fresh `mutation_writer_guard` + shared-0 freeze/unlock receipt。
- source/target/manifest 任一 identity drift，舊 delivery plan固定 `STALE_PLAN_MUST_DIE`。
- terminal tail沿用既有 Flow v2 merge/finalize規則。

### STALE_PLAN_MUST_DIE / ONE_ISSUE_ONE_MUTATION_WRITER

同一 Issue 的 stale execution path 不得「補完舊計畫」。每次 `START_BRANCH` / `APPLY_COMMIT` Git mutation 前必須 fresh-read canonical ExecutionRecord 與 live work/target refs，建立 `WHD_FLOW_V2_MUTATION_WRITER_GUARD_V1`，並把 guard 與 root-local-first receipt 一起交給 ingress。

硬規則：

1. guard 固定綁 `issue + generation + record_fingerprint + lease_token + invocation_identity + next_action + work_branch + work_head + target_head`。任一值改變，舊 plan **永久失效**；不得 retry 舊 semantic action。
2. `START_BRANCH/APPLY_COMMIT` ingress 必須再次 fresh-read ExecutionRecord；guard 與 current record 不完全相同即 `STALE_PLAN_MUST_DIE`。
3. ingress 必須 fresh-read live target ref；target 不等於 current `record.target_sha` 即拒絕。
4. ingress 必須 fresh-read live work ref；它必須等於本次 mutation 宣告的 exact post-head。若另一 writer 已先推進 branch，立即 `ONE_ISSUE_ONE_MUTATION_WRITER` conflict，不得繼續後續 QA/merge。
5. `ControlTransactionPlan` 額外綁 lease token 與 structured next_action；generation/fingerprint 相同之外，lease/next_action 也不得漂移。
6. unrelated Issue 造成 `coord/execution-v2` ref churn 只有在本 Issue fingerprint 完全沒變時才可內部重試；本 Issue 任一 identity 改變必須丟棄 plan 並從最新 `next_action` replan。
7. user-visible 執行不得把 guard 本身變成新工作步驟；它是每次 mutation 的 machine-internal precondition。

Machine owners：`tools/control_transaction.py` + `tools/control_transaction_request_ingress.py`。

### TERMINAL_QA_CONSUME_FAST_PATH_V1

已存在 GitHub Actions terminal run 且 trusted executor fresh-read 證明 `run_head_sha == current record.head_sha`、workflow path exact match、`status=completed`、`conclusion=success` 時，不再強迫原本 `START_QA → ACCEPT_QA` 的兩顆 durable transaction（中間另有 workflow round-trip）。

- canonical transaction=`CONSUME_QA`；record 當下仍必須是 structured `START_QA` continuation、沒有 `active_run`、live lease 屬於同一 invocation。
- trusted executor 自 GitHub API 讀 `run_id/head_sha/path/status/conclusion`；caller 不能自報 GREEN。
- 成功後單一 coord CAS 直接寫 `qa.last_accepted_run + accepted_head_sha`、清 `active_run` 並進入 supplied structured continuation（通常 `MERGE` 或下一個 implementation action）。
- run 尚未 terminal、head/workflow 不符、conclusion 非 success 一律 fail closed；需要真的啟動新 QA 時仍走既有 `START_QA → POLL_QA → ACCEPT_QA`。

這個 fast path 只消除「已經有 exact terminal GREEN 還要再綁一次再接受一次」的重複 round-trip，不降低 QA 證據要求。

### ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1

<!-- ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1 -->

同一 durable lane／work slot 一旦仍有 **non-DONE owning Issue**，不得因 stale reservation、recovery debt、舊 checkpoint 或 foreign control request 而切去另一張 Issue 做 mutation。canonical machine owner=`tools/execution_invocation_exit.py::assert_active_owning_issue_sticky(...)`，transaction enforcement=`tools/control_transaction_production_executor.py`，contract=`.agents/contracts/WHD_ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1.json`。

- foreign Issue 僅允許 `READ_ONLY_DISCOVERY / READ_ONLY_STATUS`；`ACQUIRE / RECONCILE / RELEASE_PATHS / HANDOFF / FINALIZE / takeover / repair` 等 control mutation 固定在 `prepare_transaction(...)` **之前** fail closed：`ACTIVE_OWNING_ISSUE_NO_PIVOT`。
- same-Issue continuation / recovery 保持合法；不同 `lane_id` 的獨立 writer 可正常平行，不得把本 gate 擴張成全 repo 單工。
- 若 current record 已進 terminal tail，既有 `TERMINAL_TAIL_OWNING_ISSUE_STICKINESS_HARD_GATE_V1` 是更強 specialization，仍回 `TERMINAL_TAIL_NO_PIVOT`。
- physical host boundary 不是 YIELD authority。fresh `next_action` 若仍是立即可執行 transaction（例如 `APPLY_COMMIT`），即使上一顆 substantive transaction 已 reconciled，也必須 `CONTINUE_EXECUTION`，**不得 YIELD**。只有真正 remote wait、durable blocker、explicit YIELD 或沒有可立即執行 continuation 時，才進既有 yield/exit 判定。
- `RESERVE_PATHS` 不得只更新 `mutation_scope` 後留下舊 continuation。effect **必須**攜帶 post-reservation structured `next_action`，machine owner=`tools/control_transaction.py::_execute_reserve_paths` 在同一 atomic transaction 寫入 scope + continuation；缺 `next_action` 固定 fail closed。若 reservation 完成後下一步是 `APPLY_COMMIT`，fresh record 必須直接呈現 `APPLY_COMMIT`，不得再靠額外 `RECONCILE` 補 continuation，也不得因此取得 YIELD 權限。

### TERMINAL_GREEN_DRAIN_HARD_GATE_V1

QA / CI GREEN 只是驗證 checkpoint，**不是 physical return authority，也不是 task terminal**。

1. exact-head terminal GREEN 一旦被 `ACCEPT_QA` 或 `CONSUME_QA` 接受，若 structured continuation 是 `MERGE`，該 record 立即進入 **no-yield terminal tail**。
2. no-yield terminal tail 固定涵蓋 `MERGE → FINALIZE → DONE`。`host_boundary`、進度回報、已完成 substantive transaction、PR 已 merged 都不得重新取得 YIELD 權限。
3. machine owner=`tools/execution_invocation_exit.py::terminal_tail_active / classify_invocation_exit`；命中時固定 `CONTINUE_TERMINAL_TAIL / may_return=false / requires_yield=false`。
4. `YIELD` trusted transaction 必須先通過 invocation-exit classifier；因此 GREEN→MERGE 或 MERGE→FINALIZE 中間的 YIELD request 必須 fail closed。
5. trusted MERGE executor 已負責把 `MERGE → FINALIZE` 在同一 workflow 內 drain；FINALIZE 必須 close Issue + fresh readback + RELEASE reservation/lease/owner 後才可成為 `DONE`。
6. 唯一可中斷 terminal tail 的是 fresh machine evidence 形成的 genuine blocker；不得把 host boundary、聊天回合結束、CI GREEN 或 PR merged 當 blocker。
7. `DONE` 是 execution terminal，不是 repository-content physical-cycle terminal。只要本票有 root workspace/diff，`FINALIZE → DONE` 後立刻交給 `assert_repository_content_cycle_complete`；`CONSUME_SOURCE_EXPORT → ARCHIVE_WORKSPACE_TO_DONE → DURABLE_CLEANUP_COMPLETE` 尚未完成時，不得對使用者宣稱整個施工 cycle 已完成。

<!-- TERMINAL_GREEN_DRAIN_HARD_GATE_V1 -->

### UNRELATED_COORD_CAS_RETRY_V1

共享 `coord/execution-v2` 被其他 Issue 推進時，不得把可證明無關的 CAS race 丟回 caller 人工重送。trusted executor 在 CAS 失敗後 fresh-read；只有 current Issue fingerprint 仍與本 transaction pre-state 完全一致時，才可在同一 workflow 內重建相同 semantic action。若 current Issue 已變則 fail closed。對 `RESERVE_PATHS` / atomic admission，任何 retry 都必須重新通過最新 cross-Issue path-conflict check。

### CHANGE_TEST_PROFILE_GATE_V1

任何 implementation / QA 在第一次實質程式 mutation 前，必須先以 `.agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json` + `tools/change_test_profile.py` 建立 machine-readable test profile。分類分成 **主要變更意圖**與 **domain overlay**：

- `BUGFIX`：reproducer RED → targeted regression → affected subsystem → integration。
- `FEATURE`：feature acceptance → unit/component → affected subsystem → integration。
- `UPDATE`：compatibility → migration/config → affected subsystem → integration。
- `REFACTOR`：behavioral equivalence → unit → integration。
- `GOVERNANCE`：contract → Control Plane Regression → Authority Consistency。
- `DOCS_METADATA`：schema/lint/link；只有 machine proof 為純 docs/metadata 時才可免重型 product full。
- UI domain 追加 `UI_CONTRACT_STATE / TK_XVFB / VISUAL_ACCEPTANCE`。
- Geometry/DXF/2D/3D/manufacturing domain 追加 `GEOMETRY_INVARIANTS / DXF_ACCEPTANCE / RENDERER_SYNC / SAVE_RELOAD`。

同一工單可同時是「BUGFIX + UI」或「FEATURE + GEOMETRY」；不得因單一 label 互斥而漏掉 domain 驗證。分類無法唯一判定時 fail closed，要求 explicit `change_type`，不得自行猜。

**final full gate：**
- product / behavior change → `PRODUCT_FULL_REGRESSION`；
- governance-only code/change → `GOVERNANCE_FULL_SUITE`（包含 Control Plane Regression、mirror gate 及該治理 owner 的完整 regression）；
- machine-proven docs/metadata-only → `NONE`。
- targeted / focused 測試不得取代 final full gate。任何要求 full gate 的工單，在 exact tested HEAD 沒有 final full GREEN 前，不得 `ACCEPT / CLOSE / FINALIZE`。

QA evidence 至少要保存 `change_type / domains / required_stages / full_gate_kind / exact head_sha`；若 changed files 擴張，必須重算 profile，新增 stage 視為尚未驗證。

`.dispatch/execution/ready-index.json` 固定 `authority=DERIVED_CACHE_ONLY`；它可重建，永遠不能授權 mutation 或 ownership。

## Main state machine

只有 `READY / ACTIVE / VERIFYING / INTEGRATING / BLOCKED / DONE`。Recovery 不是 phase；readback、poll、reconcile、generation fencing、retry 都由 structured action/fields 表達。

## Structured next_action

machine logic 只能讀 `next_action.kind + args`，不得解析 prose。主要 action：`ACQUIRE / RESERVE_PATHS / RELEASE_PATHS / START_BRANCH / APPLY_COMMIT / START_QA / POLL_QA / ACCEPT_QA / FAIL_QA / MERGE / SYNC_TARGET / HANDOFF / FINALIZE / YIELD / RECONCILE / BLOCK / WAIT_EXTERNAL`。

### MERGE_PRECHECK_AND_TARGET_SYNC_V1

Flow v2 的 `MERGE` 不是「accepted QA 後直接呼叫 GitHub merge API」。任何 external PR merge side effect 固定由 trusted `control_transaction_production_executor.py` 擁有，且在 side effect 前執行 live merge precheck。

MERGE precheck 必須 fresh-read並 exact 比對：

- current ExecutionRecord `head_sha / target_branch / target_sha`；
- PR number、open/merged state、PR head SHA、base branch、base SHA、mergeable；
- live target branch HEAD；
- target branch ruleset 的 required status checks，以及 current PR head 上對應 check conclusion。

固定結果：

- identity mismatch → fail closed，不得 merge。
- required checks 尚未 success → 保留 `MERGE`，只 poll/retry required checks；不得先撞 GitHub 405 再把 405 當流程判斷。
- live target 或 PR base 已前進 → **不得嘗試 stale MERGE**。該 `MERGE` transaction 必須原子轉為 `semantic_state=TARGET_DRIFT_REQUIRES_SYNC`，更新 fresh `target_sha`，並把 structured `next_action` 改成 `SYNC_TARGET`。
- exact identity + target current + required checks GREEN + mergeable=true → trusted executor 自己執行 PR merge，fresh-read target SHA 後才寫 `MERGE / RECONCILED`。

`SYNC_TARGET` 是正式 machine action，不是 recovery prose。固定走既有 scheduler-compatible `WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1` / `whd-control-transaction-v2-request.yml` trusted transport；chat/runtime 不得以 local git、Remote Desktop 或 connector `update_ref` 取代。trusted executor 使用 GitHub merge transport把 exact live target non-force merge 進 exact work branch：

- target/work ref 任一 SHA drift → CONFLICT，fresh-read重算；禁止 replay。
- merge conflict → fail closed，進 explicit repair；禁止 force push。
- sync 後 work HEAD 前進 → accepted QA 立即因 head mismatch失效，固定 `QA_INVALIDATED_BY_TARGET_SYNC → START_QA(exact new head) → POLL_QA → ACCEPT_QA → MERGE`。
- sync 判定 work branch 已包含 target、HEAD 不變 → 可只更新 target identity，回到 `MERGE`；既有 exact-head QA 可保留。
- `START_QA / POLL_QA / ACCEPT_QA` 必須把 post-sync PR identity與 revalidation workflow 以 structured args/effect 延續；不得靠聊天記憶找回 PR。

每次重新回到 `MERGE` 都必須再跑一次 live precheck，因 target 可在 QA 完成後再次前進。這個 gate 專門避免 #889 類「QA 已 GREEN，但 target 已 drift，最後到 GitHub merge 才報 required-check/merge error」事故。

## Atomic transaction

所有 mutation 綁定 issue + generation + canonical branch + expected record fingerprint + expected branch/head/target。結果只能是 `APPLIED / CONFLICT / FAILED`；不存在可跨 runtime 保存的中間授權 token。副作用後必須 fresh readback。

### CANONICAL_TRANSACTION_REQUEST_BUILDER_V1

所有 non-SEED Flow v2 push transaction request 必須由 `tools/control_transaction_request_builder.py` 建立 envelope；caller 不得手工拼接 `startup_evidence.declaration / execution_mode / work_root_gate`。builder 必須呼叫 canonical `tools/execution_entry_contract.py::build_startup_evidence`，並由 lane identity 唯一決定 `INTERACTIVE` 或 `SCHEDULER_LANE`。

若 push ingress 回 `CONFLICT` 且 `retryable=true`，固定執行 `FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION`：fresh-read `coord/execution-v2`、generation、lease、target/head，再用 builder 重建**同一 semantic action**。不得沿用 stale request payload，也不得因 coord/generation/live-lease race 重放外部副作用。startup evidence 驗證失敗不是 retryable conflict；先由 builder 重建 fresh evidence。

### MERGE_ANCHOR_DESCENDANT_FINALIZATION_V1

accepted merge SHA is an anchor，不是「target branch 永遠不可再前進」的 freeze point。ticket 已有 exact-head accepted QA 且 `closure.merged_sha` 已成立後，其他合法 ticket 可繼續推進同一 target branch；FINALIZE 不得因此強迫原 ticket 重跑 merge/QA/ancestry。

FINALIZE trusted executor 必須 fresh-read `record.target_branch`：
- current target == `closure.merged_sha`：直接使用 exact anchor readback。
- current target > anchor：只有在 machine proof 證明 `closure.merged_sha` 仍是 current target ancestor 時，才可把 `record.target_sha` 原子更新到 current target 並 FINALIZE。
- anchor 不是 current target ancestor、ref identity 不明、或 readback 無法證明：固定 fail closed；不得把 diverged history 當合法 target advance。

descendant proof 只能由 trusted `tools/control_transaction_production_executor.py` fresh-read GitHub ref/compare 後產生 `WHD_FLOW_V2_TARGET_ADVANCE_PROOF_V1`；caller-supplied prose/boolean 不構成 authority。

## Governance single authority

<!-- GOVERNANCE_SINGLE_AUTHORITY_V1 -->

Repository governance 的唯一 production authority 固定為 `cleanup/2d-3d-sync`。`main` 不再參與 governance mirror、paired PR、parity、second-parent ancestry reconciliation 或 terminal acceptance。

永久規則：
1. governance change 只需要 authoritative cleanup work branch → PR/QA → non-force integration；不得為了「同步 main」新增第二張治理 PR。
2. `docs/governance/governance_mirror_manifest.json`、`tools/governance_parity_gate.py` 與 ancestry reconciliation transport 已 retired；不得重建等價同步 state machine。
3. governance final gate 使用 `WHD Control Plane Regression` + authority/Registry/semantic-doc consistency；main/cleanup blob equality 或 ancestry 不再是 completion condition。
4. `main` 視為非治理 authority 的歷史/封存 branch；其內容差異不得阻塞 cleanup 的正常治理與產品交付。
5. GitHub ruleset 若仍保留 legacy check context `Governance Mirror Hard Gate`，該 workflow 只可作 **no-sync compatibility check**，不得讀取/比較/修改 main，也不得生成 mirror/ancestry candidate。


## Lease / YIELD

live lease 時其他 invocation 回 busy，不覆寫。`lease=null` 的 same-lane nonterminal record 必須先做 ACQUIRE；expired lease 只允許符合 owner/lane contract 的原子 reacquire。ACQUIRE 成功後同一 invocation 立即續原本 structured next_action，不得把『拿到 lease』當停止點。runtime 物理邊界但 task 未 terminal時用 YIELD 清 lease、保留 exact next_action。**trusted writer 必須先以 `tools/execution_invocation_exit.py::classify_invocation_exit(..., host_boundary=True)` 驗證 `requires_yield=true` 才能接受 YIELD；`ACQUIRE → 無 substantive action → YIELD` 必須 fail closed。** YIELD 不是 task complete；DONE 才是 terminal。

### STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1

「工單卡住且沒有人做」是合法 recovery condition；一旦 machine 證明成立，**任何合法 WHD executor**（互動工作槽、A/B scheduler 或其他具備 canonical transaction authority 的 executor）都可接手，不必等待原 owner 回來。但 takeover authority 必須由完整 issue-family fresh evidence 產生，不能只靠單一 stale signal。

固定判定順序：

1. fresh-read target Issue 的 canonical ExecutionRecord / lease / owner / slot / lane / `structured next_action` / QA state，以及 execution liveness evidence。target 已 `DONE`/terminal 不可 takeover。
2. 解析 canonical issue relationship，至少核對 target 的 parent、children，以及由 parent/child delegation 可到達的 delegated lineage；不得只讀 target 一張工單。
3. 對相關 lineage 每一個 nonterminal node 檢查 live lease、valid heartbeat、active trusted transaction、active remote QA 與 delegated state。任一 node 為 `ACTIVE_DELEGATED_WORK`，或可證明仍有 active writer，結果固定 `FAMILY_ACTIVE_WORK_NO_TAKEOVER`。
4. `STALE_RUNTIME_SUSPECTED`、單一 heartbeat expiry、舊 checkpoint、owner 沒有聊天回覆、host invocation 已 EXIT，都只能觸發調查，**不能單獨授權 takeover**。liveness=`UNKNOWN` 且仍有未過期 lease / active transaction evidence 時一律 fail closed。
5. 只有 target 仍 nonterminal/stuck，且 target + 相關 parent/child/delegated lineage 全部 fresh 證明沒有 active writer，才產生 `STUCK_UNOWNED_FAMILY_CONFIRMED`，並令 `takeover_eligibility=TAKEOVER_ELIGIBLE`。closed/DONE family node 不阻塞；expired/null lease 且沒有其他 active evidence 的 stale/unowned node也不阻塞。
6. `TAKEOVER_ELIGIBLE` 後，新的合法 executor 可透過 atomic `ACQUIRE/HANDOFF` 接手 target；不得因原 owner、原 handler、原 scheduler lane 不同而要求人工等待。HANDOFF 仍只改 owner/routing/lease，保留 target 的 `slot_id / branch / head_sha / structured next_action`；若 stale-writer 仍可能寫入，先套既有 generation fencing + salvage。
7. takeover mutation 前必須再 fresh-read target + family lineage 並以 CAS 驗證同一證據；若任何 writer 在 race 中恢復 ACTIVE，固定 `TAKEOVER_RACE_ACTIVE_WORK`，不得建立 duplicate writer。
8. takeover 成功後同一 invocation 立即 fresh-read並續跑 target 原 exact `next_action`；`ACQUIRE/HANDOFF` 本身不是 substantive progress，也不是停止點。

這個 gate 只解除「已證明 abandoned/stuck 的 ownership」；不削弱 `ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1`、terminal-tail focus lock、path conflict、QA、merge 或 closure gate。

<!-- STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1 -->

## Scheduler A/B

A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`，entrypoints=`00/20/40`。
B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`，entrypoints=`B15/B45`。

每次 wake：先用 `tools/scheduler_entrypoint_observation.py` 對 exact host entrypoint 寫 NON_AUTHORITY WAKE，再 fresh-read `coord/execution-v2` → same-lane nonterminal record優先 → 無 current record才讀 derived ready-index。若兩者都空，必須在 bootstrap read-only 範圍內檢查 `WHD_SCHEDULER_DISPATCH_REQUEST_V1` owner-authored explicit candidates；有 candidate 時 `execution_scheduler_view.py` 回 `INGRESS_REQUIRED`，Preflight 綁 exact candidate GREEN 後才由 `execution_dispatch_ingress.py` 建 READY，再 fresh-read並同 invocation ACQUIRE。只有 current/ready/explicit candidate 全空才是 NO_EXECUTABLE_WORK。active exact QA run只 poll；scheduler只走 GitHub/remote capability，不 fallback local。

### SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1

- `RESUME_CURRENT`：若 lease 缺失/expired，先 ACQUIRE；**ACQUIRE 成功只是續跑前置，不是本輪 progress，也不是停止點**。同一 invocation 必須立即 fresh-read，繼續執行 ACQUIRE 前保存的 exact `next_action`。
- `READY_CANDIDATES`：`execution_scheduler_view.py` 必須提供 deterministic `selected_issue`（fresh ready-index 中最小 Issue）；scheduler 必須對該 Issue 送 ACQUIRE。若 CAS/claim race 輸掉，fresh-read 後重新投影與選擇，不得以「有多張可選」停止。\n- `INGRESS_REQUIRED`：只可來自 `tools/scheduler_ready_ingress.py` 驗證通過的 repository-owner-authored `WHD_SCHEDULER_DISPATCH_REQUEST_V1` marker；依 issue number deterministic 選最小 eligible candidate。Preflight GREEN + required reads 完成後，建立 `execution_intent=SCHEDULER_LANE / authority_kind=USER_EXPLICIT` READY record；fresh-read ready-index 後立即走 ACQUIRE。`DISPATCH_READY` 本身不是 substantive progress/停止點。
- 本輪只有以下 evidence 可合法離開：`DONE`、`LANE_BUSY`、合法 `BLOCKED`、active remote QA wait，或本 invocation 已有至少一個 reconciled substantive transaction（`START_BRANCH/APPLY_COMMIT/START_QA/ACCEPT_QA/MERGE/HANDOFF/FINALIZE/RECONCILE/BLOCK`）後因 host boundary 執行 YIELD。
- **terminal-tail exception**：fresh record 若已接受 exact-head QA 且 `next_action.kind=MERGE`，或 `next_action.kind=FINALIZE`，substantive-transaction / host-boundary YIELD 權限立即失效；必須同 invocation drain `MERGE → FINALIZE → DONE`，只有 genuine machine blocker 可中斷。
- `WAKE`、讀取、文字回報、HEARTBEAT、單獨 ACQUIRE 都不是 substantive progress。
- scheduler 在任何正常 return 前必須等價執行 `classify_invocation_exit(..., host_boundary=True)`。若結果為 `SCHEDULER_EXECUTION_NO_PROGRESS`、`CONTINUE_EXECUTION` 或 `ACQUIRE_REQUIRED`，本輪**不得結束**；必須繼續 exact `next_action`。若 runtime 被外部強制切斷，視為 execution failure，不得宣稱 IDLE/DONE。

## Host scheduler lifecycle immutability

<!-- FLOW_V2_HOST_LIFECYCLE_IMMUTABILITY_V1 -->

Recurring scheduler entrypoints are persistent host infrastructure, not per-Issue execution state. Normal WHD execution MUST NOT call automation-management APIs and MUST NOT mutate scheduler host lifecycle; the only exception is the explicitly bounded `SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1` host-layer micro-bootstrap below. Invocation completion is only a cycle return; it never means the recurring task object is terminal. ExecutionRecord DONE, LANE_BUSY, BLOCKED, NO_EXECUTABLE_WORK, or any other per-cycle outcome must leave the recurring task object enabled and recurring. Outside the narrowly bounded host-recovery bootstrap, normal execution must leave the `recurring task object unchanged`.

### SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1

A/B 的 host recovery 是 **Flow v2 外層、NON_AUTHORITY、固定 allowlist 的 micro-bootstrap**，不是 execution phase。它由使用者明確啟用的五顆 recurring A/B host task 共同承擔，目的只是在第六顆 watchdog 無法存在時修復 host auto-pause；它不授權 repository execution。

固定 allowlist：
- A00=`6ab13f881c34819180cee63f5dd9446b`
- A20=`6ab4eaee5e008191a0e7e23303f64cea`
- A40=`6ab13fa557fc8191935c671214b865e2`
- B15=`6ab51d9226808191b9ae0c624e28c246`
- B45=`6ab51d9ec6708191a578d67065f8979b`

每個仍有機會啟動的 A/B host invocation，在進入 WHD project startup 前可執行這個窄 bootstrap：
1. 只讀上述五個 exact task 的 `is_enabled / title / schedule / timing_mode / last_run_time / updated_at`。
2. 若 allowlist 內任一 sibling 因 host auto-pause 成為 disabled，唯一允許的 mutation 是把該 exact task 設成 `is_enabled=true`。
3. **不得改 title / schedule / timing_mode / prompt**；不得 create/delete/complete/reschedule task；不得 disable任何 task。
4. 這個 host-layer repair **不授權 ACQUIRE、claim、lease、ExecutionRecord、transaction、Issue、PR、workflow 或 repository mutation**，也不得被當成 substantive progress。
5. host introspection/re-enable capability 缺失或 update 失敗時只記 `HOST_RECOVERY_DEGRADED`；不得因此阻止後續 canonical WHD startup/execution。
6. bootstrap 完成後仍必須從 `WORK_ROOT_BOOTSTRAP_HARD_GATE_V1` 第 0 步重新開始 project startup；host task state 不可代替 root/AI Library/declaration/Preflight evidence。
7. 不新增第六顆 ChatGPT watchdog；五顆 fixed entrypoint 本身就是 host recovery quorum。

每一輪 user-visible/task-level結果最後都只代表 physical cycle return。host surface 固定以 `CYCLE_END — KEEP_SCHEDULE_ENABLED` 表示 recurring object 必須保留；不得把 task-level DONE/BLOCKED/NO_EXECUTABLE_WORK 解讀成 automation terminal。

### HOST_LIFECYCLE_WATCHDOG_V1

Host lifecycle observation is NON_AUTHORITY and must remain separate from Flow v2 execution state.

- independent GitHub watchdog workflow: **RETIRED / ABSENT**；不得重新建立 `.github/workflows/whd-scheduler-host-watchdog.yml`。
- evaluator: `tools/scheduler_host_watchdog.py`（只由 scheduler invocation / explicit diagnostic 讀取，NON_AUTHORITY）
- optional evaluator output: `coord/monitor-v2:.dispatch/monitor/host/watchdog.json`
- optional ChatGPT host snapshot: `coord/monitor-v2:.dispatch/monitor/host/chatgpt-automations.json`
- exact entrypoint mirrors:
  - A00 → `.dispatch/monitor/host/entrypoints/a00.json`
  - A20 → `.dispatch/monitor/host/entrypoints/a20.json`
  - A40 → `.dispatch/monitor/host/entrypoints/a40.json`
  - B15 → `.dispatch/monitor/host/entrypoints/b15.json`
  - B45 → `.dispatch/monitor/host/entrypoints/b45.json`

Expected cadence is A=`:00/:20/:40`, B=`:15/:45`. After 120 seconds grace:
- expected occurrence without matching durable WAKE + fresh host snapshot enabled=true → `HOST_ENTRY_FAILURE`.
- expected occurrence without matching durable WAKE + fresh host snapshot enabled=false → `HOST_AUTO_PAUSE`.
- expected occurrence without matching durable WAKE and missing/stale host snapshot → `HOST_STATE_UNKNOWN`;不得猜成 auto-pause。
- matching WAKE but heartbeat expires before EXIT → `RUNTIME_LIVENESS_FAILURE`.

正常 Flow v2 runtime 對 host lifecycle 仍只有 read-only observability；唯一 mutation 例外只限上方 `SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1` 的 fixed allowlist disabled→`is_enabled=true`。完成 project startup 後，可 mirror `enabled / last_run_time` 到 NON_AUTHORITY host snapshot；不得以 snapshot 授權任何 execution mutation。

每個 scheduler runtime 都必須用 `tools/scheduler_entrypoint_observation.py` mirror 同一 invocation 的 `WAKE / HEARTBEAT / PROGRESS / EXIT` 到自己的 exact entrypoint file，保留 `invocation_identity / last_wake_at / last_heartbeat_at / heartbeat_expires_at / last_progress_at / exit_at / exit_state`。**host entrypoint WAKE 是 startup 前 fixed NON_AUTHORITY 例外**，因此即使後續 Preflight/startup fail closed，也不得讓 host occurrence 永久停在 SEED；正常 return（含 NO_EXECUTABLE_WORK / LANE_BUSY / startup blocker）前必須寫 EXIT。canonical lane runtime observation仍依 startup gate後才可寫。host snapshot、entrypoint mirror與watchdog result都不得授權 ACQUIRE、mutation、merge、closure、takeover 或 owner 變更。

## Work slot / handoff

固定 work-slot projection 為 `worker.slot.0/1/2/3`。slot 只是 routing/projection tag，沒有獨立 state database。HANDOFF 只能變更 owner/routing/lease，不得順手改 branch/head/slot/next_action。`worker.slot.N` identity 永遠固定；下面的自動遞增只決定新工作要綁哪個既有 fixed slot。

### DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1

- 互動式使用者明確要求執行新 ticket，且未指定任何 `/工作N` / slot 時，**預設就是 `/工作0` / `worker.slot.0`**；這個既有 default 不變，`tools/execution_dispatch_ingress.py` 的 default normalization 仍保留 `worker.slot.0`。
- 只有在**建立新 READY record 前**，fresh-read canonical ExecutionRecords 發現預設 slot0 已 BOUND 時，才呼叫 `tools/execution_work_slot_view.py::select_first_available_work_slot(...)` 做 overflow，依 `worker.slot.1 → 2 → 3` 找第一個 EMPTY；slot0 EMPTY 時仍使用原本預設 `worker.slot.0`。
- 新工作明確使用 `/工作0` 時同樣套用上述 overflow；這不是改變 default identity，而是「0 忙時才 +1」的 capacity routing。
- 0–3 全部 BOUND 時，結果固定為 fail closed / `NO_AVAILABLE_WORK_SLOT`；不得覆蓋現有 occupant、不得 takeover、不得建立 duplicate slot occupancy。 此句只約束「新 READY 工作的 capacity routing」；既有 Issue 若通過 `STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1`，可對該既有 record 執行 recovery takeover，兩者不得混用。
- 若 ticket 已有 nonterminal ExecutionRecord，必須 resume 其原 `slot_id`，不得重新跑自動遞增。
- 裸 `/工作0` query/status 仍只查 slot0；不因 slot0 BOUND 而跳去 slot1。
- `/工作1`、`/工作2`、`/工作3` 明確指定時保持原 fixed slot，不套用 auto-increment。
- `SCHEDULER_LANE`、chain successor、純 query/status 不得因本 gate 自動取得任何工作槽。
- selection 後若發生 stale read / CAS / transaction conflict，必須 fresh-read 後重新選槽，不得沿用舊 EMPTY 判斷。
- `/工作0` 是預設互動 routing 入口，不是新的 claim/lease/ExecutionRecord authority。

## Runtime observability

<!-- WHD_RUNTIME_OBSERVABILITY_V1 -->

聊天室輸出不是 liveness authority。每個 scheduler A/B 與 `/工作0/1/2/3` runtime 都必須把非權威 observation 投影到 `coord/monitor-v2:.dispatch/monitor/runtime/<source>.json`。

固定事件（語意不得合併）：
- `WAKE`：invocation 開始；runtime 成功進場並 fresh-read 本 Skill 後立即寫入。
- `HEARTBEAT`：invocation 仍存活；scheduler 沿用 `tools/scheduler_runtime_liveness.py`，interactive 工作槽沿用 #679 `tools/interactive_runtime_liveness.py` machine owner，Flow v2 只做 adapter/projection，不另造 heartbeat authority。
- `PROGRESS`：durable 工作有 substantive 進展；trusted Flow v2 transaction APPLIED 後必須自動投影。PROGRESS 可刷新 `last_heartbeat_at / heartbeat_expires_at`，但 event 仍必須是 PROGRESS。
- `EXIT`：invocation 結束；正常離開前更新；結果只使用 `IDLE_NO_WORK / LANE_BUSY / YIELDED / BLOCKED / DONE` 等可判讀狀態。

`last_progress_at`、host `last_run_time`、聊天室輸出都不是 liveness。heartbeat TTL 沿用既有 machine owner 的 maximum 300 秒。

Flow v2 adapter 固定為 `tools/flow_v2_runtime_observation.py`；它不是 authority，只把既有 scheduler/#679 liveness evidence 與 trusted transaction progress 投影到 `coord/monitor-v2`。

工作槽 observation 最低欄位：
`slot_id / issue / claim_worker / invocation_identity / conversation_identity / branch / head_sha / last_wake_at / last_heartbeat_at / heartbeat_expires_at / last_progress_at / exit_at / exit_state / liveness_state`。
`conversation_identity` host 無法提供時可用 machine-readable `UNAVAILABLE`，不得猜測。
`liveness_state` 只由 heartbeat/exit evidence 推導（`LIVE / EXPIRED / ENDED / UNKNOWN`），不得授權 execution/takeover。

Scheduler observation 亦必須保留 exact `invocation_identity`、branch/head、heartbeat timestamps 與 liveness_state。

監控 branch 僅供 observability：
- `coord/monitor-v2` 永遠不是 execution authority。
- monitor observation 不得授權 ACQUIRE、mutation、merge、closure 或 takeover。
- observation 與 `coord/execution-v2` 衝突時，以 ExecutionRecord 為準；monitor 只能標記 `OBSERVATION_DRIFT`。
- 缺少 EXIT 或長時間沒有 progress 可被 whd-monitor 判為 `STALE_RUNTIME_SUSPECTED`，但不能因此直接改 execution state。

## Generation fencing + salvage

偵測到可能仍存活的舊 writer時：bump generation、換 canonical branch、綁 exact base/head/fingerprint。舊 generation後續寫入=`ORPHAN_WRITE`，不可直接 merge/accept。舊成果仍可 freeze donor HEAD 後分類 `ADOPTABLE / PARTIAL / STALE_CONFLICT`；可用部分收編到 current generation，只重做不能證明相容的部分。

## Remote QA

### REMOTE_QA_NONBLOCKING_WAIT_HARD_GATE_V1

Remote QA 是外部等待，不得佔住同一 invocation 做 busy polling。對同一 `issue + run_id + head_sha`，**每個 invocation 的 active-status observation budget 固定為 1**：

1. fresh-read exact run/head 一次；若已 terminal，立刻走 `CONSUME_QA / ACCEPT_QA / FAIL_QA` 的既有 terminal 路徑。
2. 若第一次 observation 仍為 `queued / in_progress / pending / waiting / requested`，立即呼叫 `classify_invocation_exit(..., remote_qa_active_observation_count=1)`；其結果必須是 `YIELD_REQUIRED_REMOTE_WAIT`，接著 durable `YIELD`。
3. **同一 invocation 禁止第二次讀同一 active run 的 workflow/job/status**；machine budget owner=`tools/execution_invocation_exit.py::assert_remote_qa_active_observation_budget`。第二次 active observation 固定 `REMOTE_QA_POLL_BUDGET_EXHAUSTED`。
4. remote wait 不算 executable engineering progress，也不得阻止 scheduler/worker 在 durable YIELD 後處理另一個合法 executable leaf；原 QA 只在後續 wake/resume 再觀測。
5. progress/status 回報是 non-blocking checkpoint，不得用「再看一次 CI」延長本 invocation。

<!-- REMOTE_QA_NONBLOCKING_WAIT_HARD_GATE_V1 -->

### BLOCKED_LEAF_CONTINUATION_HARD_GATE_V1

任何單一 Issue/leaf 的 `BLOCKED / AUTHORITY_DENIED / MISSING_CAPABILITY / PLATFORM_FAILURE / external wait` 都只阻塞該 leaf，不得自動升格成整個 invocation/工作槽/排程 cycle 的停止權。

1. current leaf 若需要等待外部條件，先完成其 canonical durable checkpoint／`YIELD`；不得持有 live lease 一邊切去別張造成雙 writer。
2. durable `YIELD` 後必須 fresh-project 其他 candidate leaves。排除：terminal-tail、live foreign writer、`ACTIVE_DELEGATED_WORK`、same-path/reservation conflict、以及同樣缺少必要 authority/capability 的 leaf。
3. 只要至少一個 candidate 仍為合法 executable leaf，`tools/execution_invocation_exit.py::classify_invocation_exit(..., alternative_executable_leaf_count=N)` 固定回 `CONTINUE_OTHER_EXECUTABLE_LEAF`，`may_return=false`；不得因原 leaf 已 YIELD/BLOCKED 就退出。
4. `tools/execution_invocation_exit.py::assert_active_owning_issue_sticky` 對仍有 active writer 的 owning Issue 繼續 fail closed；但已 `lease=null + transaction=YIELD/RECONCILED` 的 nonterminal leaf 不再形成 foreign-issue pivot lock。terminal tail 永遠不適用此例外。
5. 只有所有合法替代路徑都以 fresh durable evidence 證明不可執行，且確實沒有其他 executable leaf，才可形成 `NO_EXECUTABLE_ALTERNATIVE` / 合法 physical return。progress/status query、單一 blocker、等待 push/CI/使用者明確 authority 都不是全域停止理由。
6. 這個 gate 不授權跳過 issue authority、path conflict、parent/child/delegated active-work gate 或 remote-connection gate；它只禁止「一個 leaf 卡住 = 整個 runtime 停止」的錯誤升格。

<!-- BLOCKED_LEAF_CONTINUATION_HARD_GATE_V1 -->

START_QA 綁 exact head；同 record/head只允許一個 active run。START_QA 可從 ACTIVE / VERIFYING / INTEGRATING 進入 VERIFYING：INTEGRATING 只用於「原 accepted head 後續因合法 APPLY_COMMIT / target reconciliation 前進而需要重新 exact-head QA」；不得把這條路徑當成跳過既有 acceptance。active只 POLL_QA；success→ACCEPT_QA；若來源是 integration revalidation，ACCEPT_QA 必須以 next_state=INTEGRATING 回到 merge gate，且 MERGE 仍強制 qa.accepted_head_sha == current head。terminal non-success→FAIL_QA。FAIL_QA 必須綁 exact run_id + run_head_sha，清除 active_run、保持 work_branch/head/target/owner/lane/slot 不變，回 ACTIVE/QA_FAILED_REPAIR，並寫入一個 executable repair next_action；不得把 failed QA 當 blocker 或 acceptance。

## Blocker

只有 `EXTERNAL_DEPENDENCY / MISSING_CAPABILITY / AUTHORITY_DENIED / PLATFORM_FAILURE` 可進 BLOCKED。一般 poll/readback/reconcile/retry不是 blocker。

## Finalization

### TERMINAL_TAIL_DRAIN_HARD_GATE_V1

當 current record 已有 live same-invocation lease 且 `next_action.kind=FINALIZE`，此狀態是 **terminal tail**，不是一般可延後工作。`tools/execution_invocation_exit.py::classify_invocation_exit(..., host_boundary=True)` 必須回 `CONTINUE_TERMINAL_TAIL`（`may_return=false / requires_yield=false`）。

硬規則：
- `MERGE` / `RECONCILE` / `ACQUIRE` 後只要 fresh record 的 exact next action 是 `FINALIZE`，同一 invocation 必須立即執行 FINALIZE；不得因「本輪已有 substantive progress」改走 YIELD。
- `YIELD_REQUIRED_HOST_BOUNDARY` 不得覆蓋 terminal tail。
- FINALIZE request 必須鎖 exact run 到 terminal，success 後 fresh-read record；只有 `DONE` 才可正常 return。
- genuine BLOCKED、active remote wait 或外部平台硬中斷仍依既有 fail-closed/recovery contract；聊天室 progress/status 不是停止理由。

### TERMINAL_TAIL_OWNING_ISSUE_STICKINESS_HARD_GATE_V1

Terminal tail 一旦成立，**current owning Issue 必須 focus-lock 到 terminal**；不得因 read-only discovery 看見別張 Issue 的 stale claim、expired lease、ACTIVE reservation、舊 blocker 或其他 coordination debt，就把本 invocation 切去修 foreign Issue。這條規則同樣適用於 current exact PR 已 required-CI GREEN + fresh mergeable/clean，而 ExecutionRecord 只差 current-Issue reconcile / MERGE / FINALIZE 的短暫落差。

固定規則：
1. foreign Issue 的 stale/nonterminal evidence只可標記 `UNRELATED_COORDINATION_DEBT_DEFERRED`、做 `READ_ONLY_DISCOVERY / READ_ONLY_STATUS` 或建立後續 handoff；**不得在 current Issue terminal 前執行 foreign `ACQUIRE / RESERVE_PATHS / RELEASE_PATHS / RECONCILE / HANDOFF / YIELD / BLOCK / START_BRANCH / APPLY_COMMIT / START_QA / ACCEPT_QA / CONSUME_QA / FAIL_QA / MERGE / SYNC_TARGET / FINALIZE`**。
2. `reservation_state=ACTIVE`、expired lease、缺 work branch、stale monitor 或其他 foreign inconsistency本身都不是 current terminal tail 的 interruption authority。只有 trusted current-Issue `MERGE / FINALIZE` 路徑本身回傳、且明確綁 current operation 的 genuine machine blocker，才可停止 current drain。
3. genuine foreign live writer 若真的讓 current trusted operation fail closed，current Issue保持 owning focus並記錄 blocker；不得自動 takeover / repair foreign Issue。foreign recovery 必須成為獨立 handoff / successor，在 current Issue terminal 或明確 YIELD/blocked handoff 之後處理。
4. user progress/status、額外 audit、順手治理 cleanup 都不得解除 focus lock。current exact next action可執行時，立即繼續 current Issue。
5. Machine helper=`tools/execution_invocation_exit.py::assert_terminal_tail_owning_issue_sticky(...)`；任何 orchestrator 在 terminal tail 期間準備對 foreign Issue 做 control mutation 前都必須先過此 guard。

這條 gate 的目的就是防止「current PR 已可收尾，卻被 unrelated stale reservation 拉去清舊工單」；coordination debt 可以存在，但不能插隊 terminal tail。

<!-- FLOW_V2_FINALIZE_ISSUE_CLOSE_HARD_GATE_V1 -->

FINALIZE 是 Issue closure 的唯一 terminal gate。trusted production executor 必須先 fresh-read current ExecutionRecord 並驗證 current HEAD 已有 accepted QA、MERGE 已有 fresh target readback，然後由 trusted FINALIZE path 自己 fresh-read GitHub Issue：

1. Issue 若仍 open，立即以 state=`closed`、state_reason=`completed` 關閉；不得把「PR 已 merge」當作 Issue 已 close。
2. close 後必須再次 fresh-read GitHub Issue；只有 `state=closed + state_reason=completed` 才能產生 closure evidence。
3. caller 傳入的 `issue_closed=true` 不具 authority，trusted writer 必須以 GitHub fresh readback 覆寫。caller 傳入的 `released_at` 同樣不具 authority；`released_at` 固定優先使用 fresh Issue `closed_at`，只有 GitHub 未提供 `closed_at` 時才可用 trusted writer current UTC time fallback；caller 不得因漏填 `released_at` 讓合法 FINALIZE 失敗。
4. close/readback 失敗、Issue 仍 open、state_reason 非 completed、QA/merge identity 不符時，FINALIZE 必須 fail closed；ExecutionRecord 保持 nonterminal，不得寫 DONE。
5. Issue 已 closed/completed 時仍必須 fresh-read確認，不得因為舊 comment、PR body 的 `Closes #N`、或 default/non-default branch 自動關單假設而跳過。
6. 只有 hard gate 成功後，才把 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。

因此「merge + acceptance 完成但 Issue 還開著」不是合法 terminal；同一 FINALIZE 必須把 Issue 收乾淨並 readback。

## Legacy compatibility

2026-09-28 前的舊 coordination、prewrite、separate finalization 與 turn-exit artifacts只作 audit/migration evidence。**例外：scheduler runtime liveness 與 #679 interactive runtime liveness 的既有 machine owners 仍為 CURRENT liveness capability，但只可經 Flow v2 observation adapter 投影為 NON_AUTHORITY observability，不得恢復成 execution authority。** 其他 legacy workflow 仍 fail-closed。

## Progress

進度/status是 non-blocking checkpoint。scheduler/長任務第一行固定：
`【處理者：<handler>｜owner=<record owner|NONE>｜工單：#<issue|NONE>】`
回報後只要 current invocation 還能合法施工，就立即繼續。

## Production transaction transport

<!-- FLOW_V2_PRODUCTION_TRANSACTION_V2 -->

Scheduler runtime 的 canonical mutation ingress 是 **push request**，不是 workflow_dispatch。

- A request branch: `coord/transaction-requests-a`
- B request branch: `coord/transaction-requests-b`
- interactive work-slot request branches:
  - `/工作0` → `coord/transaction-requests-work0`
  - `/工作1` → `coord/transaction-requests-work1`
  - `/工作2` → `coord/transaction-requests-work2`
  - `/工作3` → `coord/transaction-requests-work3`
- request branch/lane identity 是 hard gate：A/B branch 只接受各自 scheduler owner；work0~3 branch 只接受對應 `chatgpt.flowv2.workN`。禁止 scheduler 與 interactive runtime 共用 request branch，也禁止跨 lane 借道。
- request path: `.dispatch/transaction-request.json`
- trusted push workflow: `.github/workflows/whd-control-transaction-v2-request.yml`
- trusted writer: `tools/control_transaction_request_ingress.py` → `tools/control_transaction_production_executor.py`

建立／續送 control transaction 時固定遵守 **session-first**：
1. fresh-read `coord/execution-v2` exact HEAD、native record、generation 與 structured `next_action`；本 Issue identity 若已前進，舊 plan 立即 `STALE_PLAN_MUST_DIE`，不得補完舊 action。
2. 本 lane request branch 必須已有 `.dispatch/transaction-request.json` seed，所有 request 以 existing-file CAS 更新。
3. **只有新 invocation、沒有可重用 live lease、或 action 明確使 admission 失效時**才建立 fresh `startup_evidence`。同一 live `invocation_identity`、lease、root/source/target/scope 未變時，continuation transaction 必須用 `WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1 / LIVE_LEASE_CONTINUATION`；不得每顆 transaction 重做 5 分鐘 startup envelope。
4. request 永遠綁 `expected_coord_head + expected_generation + invocation_identity`；interactive `START_BRANCH/APPLY_COMMIT` 另綁 root-local-first receipt + `WHD_FLOW_V2_MUTATION_WRITER_GUARD_V1`。
5. 只接受 exact request commit 觸發的 exact push workflow run；terminal success 後 fresh-read record 驗 generation/post-state。
6. unrelated Issue 的 coord CAS churn 只有在本 Issue fingerprint 未變時可由 trusted executor內部 retry；本 Issue generation/fingerprint/lease/next_action/head/target 任一 drift 都必須丟棄舊 plan，從最新 `next_action` replan。

`coord/transaction-requests-a` / `coord/transaction-requests-b` / `coord/transaction-requests-work0~3` 的 seed 使用同一 request schema、`kind=SEED`、`issue=0`；trusted ingress 必須先驗 request branch 與 `lane_id` exact match，再回 `APPLIED / SEED_NOOP`，且不得讀寫 `coord/execution-v2`。seed 只負責確保後續 mutation 永遠走 existing-file CAS。\n\n`lease=null` 的 same-lane nonterminal record必須先送 ACQUIRE request（effect=`{}`），成功後同一 invocation 立即續原 structured next_action。

POLL_QA 是 observation。若 fresh-read 已存在 **exact-head + exact-workflow + completed/success** 的 terminal run，且 record 是 `START_QA` continuation、沒有 `active_run`，**優先送單顆 `CONSUME_QA`**，不得先做 `START_QA → ACCEPT_QA`。只有真的需要啟動新 run 時才走 `START_QA → POLL_QA → ACCEPT_QA`；terminal non-success 送 `FAIL_QA` 回 repair。PR merge 仍是 GitHub external side effect：merge前驗 exact PR identity，merge後 fresh-read target SHA，再送 MERGE request。FINALIZE由 trusted production writer自行 close/readback Issue，並由 fresh `closed_at` 產生 authoritative `released_at`；caller 的 FINALIZE effect 不得必填或授權 `released_at`。request workflow固定具有 `issues: write`。

手動 `whd-control-transaction-v2.yml` 只保留管理/診斷用途；scheduler不得依賴 connector 未提供的 workflow_dispatch。


### DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1
Repository-content implementation uses shared `.unpushed/{body|docs}/0`; no delivery branch or path reservation is allowed before post-merge-0 GREEN and freeze.

- 使用者詢問進度/狀態只算 non-blocking checkpoint，不得把 status/progress query 當停止理由。

- 若 runtime 無 canonical root content capability：`HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK`；禁止 GitHub-side content hotfix。

### Frozen root evidence current-fence rule
`generation` in the root test receipt is **freeze-time provenance** only. The current execution fence is `mutation_writer_guard`. A pure lease renewal / generation advance with unchanged source, lane manifest, paths, diff digest and test receipt must not invalidate frozen evidence and **不得要求重跑 root tests**.

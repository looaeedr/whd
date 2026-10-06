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


0. **WORK_ROOT_BOOTSTRAP_HARD_GATE_V2**：repository-content implementation 先解析該 executor 自己的 repo workspace，fresh 對齊 GitHub `cleanup/2d-3d-sync` production baseline；普通 startup 不要求 Drive mount/shared-0。scheduler/GitHub-only 仍依 trusted runtime contract 使用自己的 workspace/remote surface。
0.5. **WORKSPACE_ENTRY_HARD_GATE_V1**：CURRENT repository-content entry contract 固定 `route=WORKSPACE_DEFAULT`，並以 workspace-first：`WORKSPACE_SOURCE_CURRENT → WORKSPACE_MUTATIONS_COMPLETE → WORKSPACE_TESTS_GREEN → exact diff → delivery branch/PR/checks`。Drive/shared-zero 不得改變 route。Google Drive 已退出 repository-content execution routing；Drive 只允許保存資料、artifact、backup 與 production mirror。
0.5.1. **MERGE_CONFLICT_USER_DECISION_HARD_GATE_V1**：保留給歷史 shared-zero evidence 的解析；不參與 CURRENT repository-content routing。
1. **ChatGPT surface only**：若本 runtime 實際具有 AI Library connector，完成 `AI_LIBRARY_SEARCHED → RELEVANT_HISTORY_READ → LIVE_VS_HISTORY_RECONCILED`。Codex / CLI / headless / scheduler 沒有 AI Library surface 時固定 `NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE`，**不得因此 BLOCKED 或停止**；直接以 repo CURRENT authority + Phase6 required references 繼續。
2. 使用 canonical `tools/execution_entry_contract.py` 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`；每個 invocation 必須重新產生。interactive chat 必須 user-visible；Codex/CLI/headless 以 `WHD_EXECUTION_STARTUP_COMMUNICATION_V1` 留 `STDOUT / TASK_EVENT / LOG` machine-visible evidence。
3. fresh-read project `AGENTS.md` 與本 `flow-v2-execution` Skill，完成 surface-aware `SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1`。interactive chat 用 user-visible first line；Codex/CLI/headless 用 first machine-visible startup event。缺少 chat UI 本身不是 blocker。此時仍未取得 execution mutation authority。
4. recurring scheduler / `/排程A` / `/排程B` 若尚不知道 exact owning Issue，才可使用下面的 `SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1`；其他入口不得借此擴張 startup scope。
5. 對 exact owning Issue + branch + HEAD 執行 Phase6 Knowledge Preflight。interactive/chat 可用 owner-authored `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1` Issue comment transport；A/B scheduler **不得依賴 scheduler-side Issue comment mutation**，固定用 `.dispatch/preflight-request.json` existing-file CAS push 到 `coord/preflight-requests-a|b`，由 `.github/workflows/whd-phase6-preflight-push.yml` 執行同一 canonical remote runner並由 Actions 發 result comment。
6. fresh-read Preflight 回傳的全部 REQUIRED SKILLS / REQUIRED REFERENCES 並保留 evidence。
7. scheduler 若曾使用 bootstrap projection，必須丟棄該 projection 並再次 fresh-read canonical scheduler projection；只有到此時，才可進入 Flow v2 ExecutionRecord / transaction / lease / next_action 與正常 WAKE。


### CODEX_HEADLESS_EXECUTION_LIVENESS_V1

Codex / CLI / headless runtime 必須走同一 Flow v2 authority，但**不得把 chat-only capability 當硬 prerequisite**：

- `AI Library` 缺失 → `NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE`，不是 `PROJECT_STARTUP_HARD_GATE_FAILED`。
- startup declaration / Skill announcement → machine-visible evidence 即可；不得等待 chat UI。
- ordinary content root → executor-local workspace；Codex 常見 `/workspace/whd`，不得回退固定 Drive root。
- baseline `READ/FETCH/COMPARE/BRANCH_READ/REPO_METADATA_READ` 已由 workspace baseline policy 放行，不需第二份 remote authority。
- 使用者已明確授權 exact repository-content task 後，可 mint `WORKSPACE_DELIVERY` 供同 invocation + 同 task scope 的 tested delivery branch / push / PR / CI / merge/readback；**同 scope 不得在 push/PR 階段再次向使用者索取同一授權**。
- 真正 host credential/network failure 才屬 capability blocker；policy 不得把 AI Library、chat UI、Drive mount、重複確認偽裝成 capability blocker。

machine communication owner=`tools/execution_entry_contract.py::build_startup_communication_evidence`。


### OUTER_ACTION_MACHINE_GATE_V1 — control plane 必須退回 session internal


對 `INTERACTIVE` repository-content work，Flow v2 的 lease / reservation / CAS / session reuse / reconcile / Git-transport transaction / QA consume / finalize drain 都是 machine-internal plumbing。chat outer layer 不得把 `DISPATCH_READY / ACQUIRE / RESERVE_PATHS / RECONCILE / LEASE_RENEW / START_QA / ACCEPT_QA / FINALIZE` 等 transaction kind 當成本輪 primary task 或 user-visible next action。canonical content router=`tools/root_local_first_gate.py::select_repository_content_route`; shared-unpushed machine僅可解析歷史資料，不參與 CURRENT 路由； Flow v2 transaction guard仍由既有 execution owners負責；continuity 的 first-substantive-action 記錄也必須拒絕 background-only governance event。


外層普通 route只報 `FRESH_READ → WORKSPACE_MUTATE_TEST → EXACT_DIFF → DELIVERY_BRANCH_PR → POST_PUSH_CI → MERGE_FINALIZE`；不得追加已退役的 shared-zero 步驟。只有真 `PATH_CONFLICT / SAME_ISSUE_OTHER_WRITER / SUBSTANTIVE_TARGET_OVERLAP / MACHINE_FAIL_CLOSED / USER_INPUT_REQUIRED` 才以 `REPORT_BLOCKER` 浮到前台；普通 lease expiry、record stale、governance drift、test RED、status/progress query 一律記 evidence 後繼續目前 primary task。




### MISSING_EXECUTION_RECORD_POST_DELIVERY_RECOVERY_V1 — 已交付不得因缺 record 停住

若 fresh durable evidence 已證明 repository-content delivery PR **已 merged 到 `cleanup/2d-3d-sync`**，但 owning Issue 在 `coord/execution-v2` 沒有 native `ExecutionRecord`，這是 **recovery condition，不是施工 blocker，也不是重做 implementation 的理由**。

canonical recovery 只允許 trusted ingress `RECOVER_POST_DELIVERY`：

1. fresh-read exact PR，PR 必須 merged/closed，base 必須是 `cleanup/2d-3d-sync`，且 PR body 必須用 exact closing keyword（例如 `Closes #123`）綁定 owning Issue。
2. fresh-read PR head required checks；全部 required contexts 必須 GREEN。
3. fresh-read current production target；merged SHA 必須等於 current target 或仍是 current target ancestor。
4. Issue identity 必須 fresh-read 成功。
5. 只有上述 proof 都成立，trusted production executor 才可 create-only 建立 generation 1 的 `POST_DELIVERY_RECOVERY` record，直接進 `INTEGRATING / FINALIZE`。
6. recovery record **不得倒填** 過去不存在的 WAKE、lease、transaction、QA acceptance。唯一新 lease 是當前 recovery invocation；`qa.last_accepted_run` / `qa.accepted_head_sha` 必須維持空白，並以 `WHD_FLOW_V2_POST_DELIVERY_RECOVERY_PROOF_V1` 記錄 fresh merge/check/ancestry evidence。
7. 同一 trusted invocation 建立 recovery record 後必須立即 drain `FINALIZE → Issue close/readback → DONE/RELEASED`；不得把「record 已補好」或「準備 finalize」當停止點。
8. 若 same-Issue record 已在 recovery 前/途中出現，固定 fail-closed 回到 fresh canonical record；不得覆寫或建立第二筆 authority。
9. PR 未 merge、closing identity 不成立、required check 非 GREEN、merge anchor 不在 target ancestry、或 GitHub fresh readback 不完整，才是合法 fail-closed。

因此 `native ExecutionRecord missing for issue N` 在「已 merge delivery」情境下不得再直接成為終止訊息；必須先評估本 recovery route。

<!-- MISSING_EXECUTION_RECORD_POST_DELIVERY_RECOVERY_V1 -->


### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1


`READ_ONLY_BOOTSTRAP_ONLY` 是為解除「remote Preflight 需要 owning Issue，但 scheduler 必須先 discovery 才知道 owning Issue」循環依賴的窄例外；它不是 execution phase，也不是 authority。


- 前置條件固定為：work-root gate 已依 trusted scheduler/GitHub runtime contract 完成；AI Library 只在 runtime 實際具有 ChatGPT surface 時適用，否則記 `NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE`；fresh per-invocation startup declaration 已依 runtime surface 留 user-visible 或 machine-visible evidence；且已 fresh-read `AGENTS.md` 與本 Skill。
- 唯一可讀範圍：`coord/execution-v2` 的 canonical ExecutionRecords、DERIVED_CACHE_ONLY `ready-index`、`coord/monitor-v2:.dispatch/monitor/runtime/*.json` 的 NON_AUTHORITY latest-owner runtime observations、`tools/execution_scheduler_view.py` 的純 read-only scheduler projection，以及解析 exact owning Issue / work branch / target branch / HEAD 所需的 GitHub metadata。runtime observation 只能與 ExecutionRecord/lease/run/family evidence 合併做 takeover classification，不能單獨授權 mutation。若 current/ready 都為空，另允許用 `tools/scheduler_ready_ingress.py` 做**窄化 owner-authored marker discovery**：只掃 open Issue 的 number/state/author/body 第一個 machine marker `WHD_SCHEDULER_DISPATCH_REQUEST_V1`、`lane=ANY|A|B` 與可選 `completion=CONTROL_ONLY`；普通 open Issue、label、dependency-unblocked、PR 一律仍不是 authority。此 discovery 只為綁定 Preflight exact Issue，不授權 READY/ACQUIRE。
- 唯一目的：取得 trusted remote Phase6 Preflight 所需的 exact owning Issue + branch + HEAD，然後送出該 Issue 上的 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`。不得建立永久 bootstrap Issue；若 projection 確認沒有可執行工作，仍須完成本 invocation 的 project startup requirements後才能依正常 scheduler exit contract 判讀。
- `PRE_PREFLIGHT_MUTATION_FORBIDDEN`：Preflight GREEN 且全部 REQUIRED SKILLS / REQUIRED REFERENCES fresh-read 完成以前，禁止 canonical lane/runtime WAKE / HEARTBEAT / PROGRESS monitor write、claim、ACQUIRE、一般 transaction request、Guard、repository mutation、QA、merge、closure、takeover、lease mutation、ExecutionRecord mutation或任何其他 execution side effect。**唯一觀測例外**是 host-layer fixed entrypoint file (`coord/monitor-v2:.dispatch/monitor/host/entrypoints/<a00|a20|a40|b15|b45>.json`) 的 WAKE/HEARTBEAT/EXIT；另允許 Phase6 push request 本身，以及對既有 trusted GREEN receipt 的 read-only bot-comment readback/rebind admission。這兩者都不得自行授權 Issue ownership / ACQUIRE / mutation。
- bootstrap projection 只用來綁 Preflight identity；Preflight 完成後必須丟棄並 fresh-read `coord/execution-v2` / scheduler view，禁止把 bootstrap 時看到的 state 直接拿去 ACQUIRE 或 mutation。


startup declaration 只提供 provenance/intent，不取代 claim、Guard、Preflight、ExecutionRecord 或 transaction fencing；bootstrap read-only discovery 也不提供任何 mutation authority。缺任一步固定 `FAIL_CLOSED`。前一聊天、前一 runtime 或前一 scheduler wake 的宣告不得沿用。


<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->


本 Skill 是 WHD execution/control-plane 的唯一 CURRENT operational contract。其他 workflow Skills 只可做入口 bridge，不得建立第二套 ownership、resume、closure、scheduler 或 recovery state machine。


### REMOTE_AUTHORITY_NON_PROPAGATION_HARD_GATE_V1


Flow v2 的 execution/claim/lease/transaction authority **不等於 GitHub network authority**，也不得由 bridge 自動傳遞。任何 GitHub repo metadata、code search、contents、branch/commit、Issue/PR、Actions/workflow/run/artifact、GitHub API/Connector 或 network git (`fetch/pull/ls-remote/push`) 動作前，都必須先以 `tools/root_local_first_gate.py::assert_remote_connection_allowed(...)` 驗證 exact action 是否存在於 `WHD_REMOTE_CONNECTION_AUTHORITY_V1.allowed_actions`。


- interactive/default 對 production baseline 的 `READ/FETCH/COMPARE/BRANCH_READ/REPO_METADATA_READ` 可由 workspace-first gate直接允許；其他 GitHub/remote action沒有 explicit authority仍固定 `REMOTE_CONNECTION_DENIED`；
- `/推推 文檔|主體`：只授權 selected lane 的 frozen delivery/readback window；
- scheduler/GitHub-only：只在 user-authored entry contract 明確指定 GitHub-only 且 trusted runtime provenance 成立時，建立該 invocation scope 的 authority；
- `SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1`、Phase6 Preflight、Flow v2 bridge、工作槽/派工/closure、read-only/status/log query、GitHub tool/connector 可用，都不是 remote authority 來源。


因此下方任何 GitHub-backed bootstrap/discovery/control transaction 都必須先通過同一 remote gate；Flow v2 只消費既有 authority，不自行創造 authority。


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


## WORKSPACE_EXECUTION_POLICY_V3 — EXECUTOR LOCAL WORKSPACE FIRST


Repository-content routing 必須服從 `root-local-first` 的 CURRENT router；Flow v2 不得再另造 Drive-root-only content policy。


- 預設 route=`WORKSPACE_DEFAULT`：`cleanup/2d-3d-sync → executor-local repo workspace → edit/test → exact tested diff → delivery branch/PR/checks → cleanup/2d-3d-sync`。
- executor-local workspace 是 execution surface/cache，不是新的 canonical authority；共同 production baseline 是 fresh GitHub `cleanup/2d-3d-sync`。
- **Google Drive mount 不可見本身不是 blocker，也不得觸發 handoff。** ChatGPT / Codex / C2C / 其他 executor 都使用各自 runtime 可寫、可測的 repo workspace。
- `select_repository_content_route` 對 `shared_zero_drift_present=false|true` 都固定回 `WORKSPACE_DEFAULT`；舊 drift 只可記錄為 historical evidence。
- 舊 `.unpushed` lane、generation/freeze、shared-zero receipt 與 Drive readback 全部退出 CURRENT routing。
- Google Drive 只可作資料／mirror／backup；任何 Drive 可見性、不可見性或舊 pointer 都不得升格成 blocker 或 construction authority。
- `source/manifests`、ZIP snapshot、`/work/active` 與單一固定實體 workspace path 都不是 CURRENT repository-content authority。


### REMOTE_CONTENT_IMPLEMENTATION_ROUTING_HARD_GATE_V3


Repository-content 能否施工看 **executor repo workspace capability**，不是看 `/Google Drive/WHD` 是否掛載。


- `INTERACTIVE` / chat：只要 `WORKSPACE_ROOT_RESOLVED → WORKSPACE_GIT_IDENTITY_VERIFIED → PRODUCTION_BASELINE_CURRENT`，就必須在該 executor workspace 繼續 edit/test；不得因 Drive mount 不可見而 handoff。
- scheduler / `GITHUB_ONLY` / `REMOTE_ACTION` 仍是 control-plane / post-push 模式；execution mode 本身不授予 content authoring。遇 repository-content next action，固定 `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX`，由接手 runtime 再執行 CURRENT content router；handoff 原因是 execution-surface capability/authority，不是 Drive mount 缺失。
- 接手 content runtime 只看 executor-local repo workspace capability；沒有可寫、可測 workspace 才 `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX`。
- 任何 route 都禁止未測試的 GitHub-side content hotfix。Git write 只能承接已測 exact diff；GitHub Actions 只作 post-push verification，verification RED 必須回原 content route 修正/重測。


### DELIVERY_PATH_RESERVATION_HARD_GATE_V2


Flow v2 `mutation_scope` / `RESERVE_PATHS` 是 **delivery-only coordination**，不得回長成任何 route 的施工前置。


- `WORKSPACE_DEFAULT`：workspace tests GREEN + exact diff 後才可做 delivery reservation，然後開 tested delivery branch / PR/checks；不要求 shared-0 manifest、freeze 或 `/推推`。
- Drive/shared-zero 不再有 CURRENT delivery reservation route；歷史 lane evidence 只能作讀取/稽核資料。


歷史 lane evidence 不得啟動另一條 CURRENT delivery path。

`RESERVE_PATHS / RELEASE_PATHS` 是 delivery coordination，不算 engineering progress；WORKSPACE_DEFAULT 不得在 tests GREEN + exact diff 以前 reservation。


### INVOCATION_ADMISSION_SESSION_V3


Startup/workspace identity 與 Flow v2 lease 仍是 invocation/session-level gate；lease / mutation_scope 不得自行改寫 CURRENT `WORKSPACE_DEFAULT` content route。


- `WORKSPACE_DEFAULT` authoring surface 是 fresh-verified executor-local repo workspace；先 edit/test，再以 exact tested diff 開 delivery branch。
- ACQUIRE/lease 用於 owning Issue 與 liveness，不得把 repository-content work 改送 Drive/shared-zero。
- `START_BRANCH / APPLY_COMMIT`：CURRENT `WORKSPACE_DEFAULT` 必須已有 workspace tests GREEN + exact diff；沒有第二條 shared-zero authoring path。
- source/target/diff/manifest（若有）任一 identity drift，舊 delivery plan固定 `STALE_PLAN_MUST_DIE`。
- terminal tail沿用既有 Flow v2 QA/merge/finalize規則。


### SCHEDULER_CONTROL_ONLY_AUTO_FINALIZE_V1


對 owner-authored scheduler marker 明確帶 `completion=CONTROL_ONLY` 的工單，CURRENT Flow v2 必須把「不用改 repository content」寫成 durable machine continuation，而不是靠 scheduler prompt 猜下一步。


固定規則：


1. ingress 時 `source_branch == target_branch` 且 `source_sha == target_sha`；`work_branch` 直接等於 `source_branch`，不得建立 scheduler work branch。
2. READY record 的 `ACQUIRE.args.post_acquire` 必須綁定 `FINALIZE {completion_mode: CONTROL_ONLY}`；ACQUIRE caller 不得改寫成 `HANDOFF`、`START_BRANCH`、`RESERVE_PATHS` 或其他內容施工 continuation。
3. ACQUIRE 後只有在 `mutation_scope=None`、無 active run、無 accepted QA、無 merged anchor、`head_sha == source_sha` 且仍為 scheduler lane 時，CONTROL_ONLY FINALIZE 才合法。
4. trusted production executor 在 FINALIZE 前 fresh-read target HEAD；只有 fresh target readback + GitHub Issue close/readback 成功，才寫 `DONE / RELEASED`。CONTROL_ONLY 不偽造 QA、merge 或 content mutation evidence。
5. 任一 content identity 已改、reservation/run/QA/merge evidence 出現、unknown `completion`、或 caller 想覆寫 bound continuation，一律 fail-closed；普通施工工單固定走 CURRENT `WORKSPACE_DEFAULT` delivery → QA/merge/finalize；CONTROL_ONLY 不得改寫該 route。
6. 這條路徑的目的就是消除 #1080 類 `READY → ACQUIRE → HANDOFF/START_BRANCH` 漂移；control-only ticket 不得再回舊 handoff/branch 流程。


Machine owners：`tools/scheduler_ready_ingress.py`、`tools/execution_dispatch_ingress.py`、`tools/control_transaction.py`、`tools/control_transaction_production_executor.py`。


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
7. `DONE` 加上 trusted merge/Issue readback 就是 workspace terminal；`assert_repository_content_cycle_complete(record)` 驗同一 durable tuple。不得再要求 source export、workspace archive 或 shared-zero lane receipt。


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


### STALE_RELEASED_BRANCH_CLEANUP_TRANSPORT_V1


`RELEASE_PATHS` 對已 `reservation_state=RELEASED` 的 stale-reset residue，仍以「work branch 必須不存在」作為 READY reset 硬條件；不得放寬成 connector 無法刪 branch 就直接改 coord record。


canonical branch-delete side effect 固定由 `tools/control_transaction_production_executor.py` 的 trusted GitHub executor 擁有，透過既有 transaction request transport 執行，不新增旁路 state machine。caller 只能在 `RELEASE_PATHS` effect 明確帶 `delete_stale_work_branch=true`；其他 transaction kind 帶此欄位一律 fail closed。


trusted executor 在 DELETE 前必須 fresh 證明全部成立：
- exact record 的 mutation scope 已 `RELEASED`；
- lease 已 expired、`active_run=null`、無 accepted QA lock；
- work branch 不得等於 source/target、不得為 `main`、`cleanup/2d-3d-sync` 或任何 `coord/*` control branch；
- 沒有其他 non-DONE ExecutionRecord 引用同一 work branch；
- live work ref HEAD 必須 exact 等於 record `head_sha`，branch metadata 不得 drift，且 `protected=false`；
- fresh target HEAD 必須包含 work HEAD（work HEAD 是 current target ancestor），因此 stale branch 沒有 target 未包含的獨有 commit。


DELETE 後必須再次 GET exact ref，只有 404/ABSENT 才可產生 `work_branch_exists=false` 並繼續既有 stale `RELEASE_PATHS → READY` transition。若 ref 在進入 transaction 前已 absent，視為 idempotent cleanup；若 branch delete 已成功但 shared coord CAS 因 unrelated Issue 前進而競態，既有 `UNRELATED_COORD_CAS_RETRY_V1` 必須在同 workflow 內重建同一 post-record，不要求再刪一次。任何 head drift、divergence、protected/shared branch、readback 仍存在都 fail closed。


<!-- STALE_RELEASED_BRANCH_CLEANUP_TRANSPORT_V1 -->


### MERGE_ANCHOR_DESCENDANT_FINALIZATION_V1


accepted merge SHA is an anchor，不是「target branch 永遠不可再前進」的 freeze point。ticket 已有 exact-head accepted QA 且 `closure.merged_sha` 已成立後，其他合法 ticket 可繼續推進同一 target branch；FINALIZE 不得因此強迫原 ticket 重跑 merge/QA/ancestry。

**MERGE anchor identity 固定取 exact delivery PR 的 GitHub `merge_commit_sha`；fresh current target HEAD 只寫入 `record.target_sha`。** `ALREADY_MERGED` 也必須先驗 exact PR head/base identity，且當 current target 已超前 merge commit 時，用 trusted ancestry proof 證明 merge commit 仍是 target ancestor；不得把 current target HEAD 冒充 `closure.merged_sha`。若舊 machine 已寫錯 anchor，必須先走 trusted `RECONCILE` + `WHD_FLOW_V2_MERGE_ANCHOR_CORRECTION_PROOF_V1` 校正，再 FINALIZE；不得重跑 QA 或重做 delivery。


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


每次 wake：先用 `tools/scheduler_entrypoint_observation.py` 對 exact host entrypoint 寫 NON_AUTHORITY WAKE，再 fresh-read `coord/execution-v2` + latest owner runtime observations。decision priority 固定：same-lane nonterminal → `TAKEOVER_CANDIDATE` → READY → explicit ingress。`TAKEOVER_CANDIDATE` 只能由 `STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1` 完整證據產生；命中後先 HANDOFF 到本 lane、fresh-read、ACQUIRE，再同 invocation 續原 exact `next_action`。只有 current/takeover/ready/explicit candidate 全空才是 NO_EXECUTABLE_WORK。active exact QA run只 poll；scheduler只走 GitHub/remote capability，不 fallback local。


### SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1


- `RESUME_CURRENT`：若 lease 缺失/expired，先 ACQUIRE；**ACQUIRE 成功只是續跑前置，不是本輪 progress，也不是停止點**。同一 invocation 必須立即 fresh-read，繼續執行 ACQUIRE 前保存的 exact `next_action`。
- `TAKEOVER_CANDIDATE`：`execution_scheduler_view.py` 必須提供 deterministic `selected_issue / takeover_from_owner_id / takeover_reason`；scheduler 只可使用 `build_takeover_handoff_effect(...)` 產生 routing-only HANDOFF effect，HANDOFF 後 fresh-read、ACQUIRE，再立即續原 exact `next_action`。若 race 中 family 恢復 active writer，固定 `TAKEOVER_RACE_ACTIVE_WORK` 並 fresh-read重選。
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


### MERGED_DELIVERY_SIBLING_DRAIN_V1 — 同一 PR 的 closing siblings 不得留 OPEN 尾巴

當 FINALIZE 的 exact delivery PR body 同時包含多個 exact closing keyword（例如 `Closes #1197 / #1202 / #1203`），current Issue `DONE / RELEASED` **不是 invocation exit authority**，只要同一 PR 仍有 OPEN sibling 且該 sibling 沒有 native ExecutionRecord。

固定規則：
1. normal MERGE 與 `RECOVER_POST_DELIVERY` 都必須把 exact delivery `pr_number` 保留到 structured FINALIZE continuation。
2. trusted FINALIZE close/readback current Issue 後，必須 fresh-read exact merged PR，驗 base branch + `merge_commit_sha == closure.merged_sha`，再依 PR body closing order尋找下一張 OPEN sibling。
3. sibling 已有 native ExecutionRecord 時不得覆寫或建立第二套 authority；只有 **OPEN + missing record** 才可建立 chain `RECOVER_POST_DELIVERY`。
4. current DONE record 以 `chain.next_issue + chain.next_action=RECOVER_POST_DELIVERY` durable handoff；monitor 此時固定保持 `PROGRESS / LIVE`，不得先投影 `EXIT`。
5. 同一 trusted invocation 必須立即 create-only recovery sibling，沿既有 post-delivery recovery proof驗 merged PR / required checks / ancestry，然後 FINALIZE；若下一張仍有 sibling，遞迴 drain。
6. 只有 exact delivery PR 的全部 OPEN missing-record siblings 都已 terminal，最後一張 DONE 才可投影 `EXIT / ENDED`。
7. 不得因 sibling drain 重做 implementation / QA，也不得把普通 open Issue 擴張成 authority；scope 僅限 **同一 exact merged PR 的 closing-keyword siblings**。
8. fresh PR identity、merge anchor、required checks、Issue identity 或 ancestry 任何一項不能證明時固定 fail-closed；不得猜測 handoff。

Machine owner=`tools/control_transaction_production_executor.py`；durable handoff owner=`ExecutionRecord.chain`；missing-record sibling recovery沿用 `MISSING_EXECUTION_RECORD_POST_DELIVERY_RECOVERY_V1`。

<!-- MERGED_DELIVERY_SIBLING_DRAIN_V1 -->


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


## LEGACY_FLOW_HAS_NO_RUNTIME_COMPATIBILITY_RIGHT


**LEGACY_FLOW_HAS_NO_RUNTIME_COMPATIBILITY_RIGHT**：退休的 execution/control-plane 路徑沒有 production runtime 相容權。確認沒有 CURRENT inbound dependency 後，必須從 production tree 物理刪除；不得以 HISTORICAL、deprecated、fallback、compatibility alias、fenced procedure 或舊 executable-looking reference 的形式繼續保留。


**ONE_CANONICAL_EXECUTION_PATH**：同一 execution purpose 只能有一條 CURRENT machine path。合法的 MIRROR/entry Skill 只能薄路由到本 Flow v2，不能保有第二套 ownership、claim、checkpoint、Guard、resume、scheduler、remote-QA、turn-exit、finalization 或 closure state machine。


歷史證據只留在 Git history / closed Issues；production tree 不充當舊 execution procedure 的歷史博物館。若 CURRENT code/test/reference 仍依賴退休 artifact，先把 inbound dependency 遷移到 Flow v2 canonical owner，再刪除 retired artifact。CI/anti-regrowth tests 必須對已退休 path/symbol fail closed，禁止之後重新長回 production。


scheduler runtime liveness 與 #679 interactive runtime liveness 若仍是 CURRENT machine capability，只能作 Flow v2 NON_AUTHORITY observability adapter 的 implementation dependency；這不構成 legacy execution compatibility，也不得恢復成 execution authority。


## Progress


### RUNTIME_REPORT_IDENTITY_MACHINE_GATE_V1


進度/status是 non-blocking checkpoint。所有 interactive work-slot 與 scheduler 的 user-visible `PROGRESS / CHECKPOINT / terminal / EXIT` 第一行固定使用 **fresh current runtime identity**：
`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>｜slot=<worker.slot.N|NONE|UNBOUND>｜invocation_identity=<exact invocation_identity>】`


唯一 machine owner=`tools/runtime_report_identity.py`。caller 必須先用 `build_runtime_report_identity(...)` 驗證 `handler / owner / issue / slot / invocation_identity / runtime_kind`，再用 `format_runtime_report_prefix(...)` 產生第一行；不得手工拼接。`invocation_identity` 缺失、空白、`NONE / UNBOUND / UNAVAILABLE` 或 handler/runtime/slot identity 不一致都 fail closed。owner/issue/slot 取 fresh canonical ExecutionRecord/projection；invocation_identity 取 exact current runtime observation/startup provenance，禁止由聊天時間、entrypoint、task id 或上一輪 runtime 推測。


此 gate 只保證 user-visible provenance，不建立 execution authority。`tools/execution_invocation_exit.py` 在允許正常 turn exit 前必須驗 exact report identity 與 native ExecutionRecord exit state，因此「無身份退出」不是合法 terminal path。回報後只要 current invocation 還能合法施工，就立即繼續。


## Production transaction transport


<!-- FLOW_V2_PRODUCTION_TRANSACTION_V2 -->


Scheduler runtime 的 canonical mutation ingress 是 **push request**，不是 workflow_dispatch。

Phase6 Preflight 亦遵守同一能力模型：A/B scheduler 的 startup Preflight request 不走 Issue-comment mutation，固定使用 scheduler-owned push branches：
- A Preflight request branch: `coord/preflight-requests-a`
- B Preflight request branch: `coord/preflight-requests-b`
- request path: `.dispatch/preflight-request.json`
- request schema: `WHD_REMOTE_PHASE6_PREFLIGHT_PUSH_REQUEST_V1`
- trusted workflow: `.github/workflows/whd-phase6-preflight-push.yml`
- validator: `tools/phase6_preflight_push_request.py`
- canonical runner: `tools/phase6_remote_preflight.py`
- push branch/lane identity hard-bound；scheduler 只用 existing-file CAS 更新 request。Actions success 後由 trusted workflow 對 owning Issue 發 `WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1`，receipt 必須帶 `lane_id + invocation_identity + request_id + exact Issue/branch/HEAD`。若原 invocation 已結束，下一個**同 lane** invocation可只提交 `WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1(comment_id + request_id + branch + head_sha)`；trusted transaction ingress 必須自行 GitHub API 回讀 `github-actions[bot]` comment，驗證 receipt <= 40 分鐘且 identity 完全未漂移，才由 `tools/execution_entry_contract.py::rebind_scheduler_phase6_preflight_receipt` mint 當輪 exact-invocation `WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1`。caller-supplied raw receipt JSON 永遠不是 authority。若 receipt 已過期或 branch/HEAD 漂移，必須重新跑 Preflight；不得 fallback scheduler-side request comment。


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


### MISSING_EXECUTION_RECORD_READY_INGRESS_V1

對**尚未施工、尚未交付**且 native `ExecutionRecord` 不存在的 exact owning Issue，缺 record 本身不得成為永久 blocker。只有在本 invocation 已完成 startup + exact Phase6 Preflight，且有 typed explicit authority 時，才允許走 trusted `DISPATCH_READY` bootstrap：

1. request 固定走對應 lane 的 existing-file CAS push transport，`kind=DISPATCH_READY`、`expected_generation=1`，並綁 exact `expected_coord_head + invocation_identity`。
2. trusted ingress 必須以已驗證的 `startup_transition.branch + head_sha` 建立 `DispatchIngressRequest`；caller 不得自行提供另一組 source/target identity。
3. authority 僅接受 `execution_dispatch_ingress` 已允許的 typed authority（`USER_EXPLICIT / CHAIN_SUCCESSOR / WORK_SLOT_ASSIGNMENT`）；interactive slot 必須由 request branch/lane identity 推導，caller 不得跨 slot 偽造。
4. trusted production writer 只允許 **create-only**：same-Issue record 已存在即 fail-closed；成功時原子寫入 generation 1 `READY / UNCLAIMED / lease=null / next_action=ACQUIRE`，並同步重建 DERIVED_CACHE_ONLY ready-index。
5. 寫入後必須 fresh-read exact record 並驗 fingerprint；`DISPATCH_READY` 本身不得偷做 ACQUIRE、不得建立 lease、不得直接進 ACTIVE。
6. READY 建立成功後，同一 invocation 若仍可執行，立即 fresh-read 並走正常 `ACQUIRE`；不得把「READY 已建立」當成停止點。
7. 已 merge delivery 的 missing-record 情境仍只走 `RECOVER_POST_DELIVERY`，不得改走 `DISPATCH_READY` 倒填歷史。

Machine owner=`tools/control_transaction_request_ingress.py` → `tools/control_transaction_production_executor.py::dispatch_ready_missing_record`；planner owner=`tools/execution_dispatch_ingress.py`。

建立／續送 control transaction 時固定遵守 **session-first**：
1. fresh-read `coord/execution-v2` exact HEAD、native record、generation 與 structured `next_action`；本 Issue identity 若已前進，舊 plan 立即 `STALE_PLAN_MUST_DIE`，不得補完舊 action。
2. 本 lane request branch 必須已有 `.dispatch/transaction-request.json` seed，所有 request 以 existing-file CAS 更新。
3. **只有新 invocation、沒有可重用 live lease、或 action 明確使 admission 失效時**才建立 fresh `startup_evidence`。同一 live `invocation_identity`、lease、root/source/target/scope 未變時，continuation transaction 必須用 `WHD_INVOCATION_ADMISSION_SESSION_REUSE_V1 / LIVE_LEASE_CONTINUATION`；不得每顆 transaction 重做 5 分鐘 startup envelope。
4. request 永遠綁 `expected_coord_head + expected_generation + invocation_identity`；interactive `START_BRANCH/APPLY_COMMIT` 另綁 root-local-first receipt + `WHD_FLOW_V2_MUTATION_WRITER_GUARD_V1`。
5. 只接受 exact request commit 觸發的 exact push workflow run；terminal success 後 fresh-read record 驗 generation/post-state。
6. unrelated Issue 的 coord CAS churn 只有在本 Issue fingerprint 未變時可由 trusted executor內部 retry；本 Issue generation/fingerprint/lease/next_action/head/target 任一 drift 都必須丟棄舊 plan，從最新 `next_action` replan。


`coord/transaction-requests-a` / `coord/transaction-requests-b` / `coord/transaction-requests-work0~3` 的 seed 使用同一 request schema、`kind=SEED`、`issue=0`；trusted ingress 必須先驗 request branch 與 `lane_id` exact match，再回 `APPLIED / SEED_NOOP`，且不得讀寫 `coord/execution-v2`。seed 只負責確保後續 mutation 永遠走 existing-file CAS。\n\n`lease=null` 的 same-lane nonterminal record必須先送 ACQUIRE request（effect=`{}`），成功後同一 invocation 立即續原 structured next_action。


POLL_QA 是 observation。若 fresh-read 已存在 **exact-head + exact-workflow + completed/success** 的 terminal run，且 record 是 `START_QA` continuation、沒有 `active_run`，**優先送單顆 `CONSUME_QA`**，不得先做 `START_QA → ACCEPT_QA`。只有真的需要啟動新 run 時才走 `START_QA → POLL_QA → ACCEPT_QA`；terminal non-success 送 `FAIL_QA` 回 repair。PR merge 仍是 GitHub external side effect：merge前驗 exact PR identity，merge後 fresh-read target SHA，再送 MERGE request。FINALIZE由 trusted production writer自行 close/readback Issue，並由 fresh `closed_at` 產生 authoritative `released_at`；caller 的 FINALIZE effect 不得必填或授權 `released_at`。request workflow固定具有 `issues: write`。


`whd-control-transaction-v2.yml` direct workflow 已退休且不得存在；production mutation 只走 scheduler-compatible `whd-control-transaction-v2-request.yml` / request ingress trusted transport。scheduler不得依賴 connector 未提供的 workflow_dispatch。




### CONTENT_MUTATION_TEST_HARD_GATE_V2


- `WORKSPACE_DEFAULT`：repository-content 修改與 affected/profile tests 固定在 executor-local repo workspace 完成；tests GREEN + exact diff 後才可建立 tested delivery branch / PR。
- 使用者詢問進度/狀態只算 non-blocking checkpoint，不得把 status/progress query 當停止理由。
- runtime 看不到 `/Google Drive/WHD` **不得**形成 blocker；Drive 已退出 CURRENT施工路由。
- 有可寫、可測 executor repo workspace 就繼續 `WORKSPACE_DEFAULT`；真的沒有任何 repo workspace/edit/test capability 時，才 `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX`。


### Frozen root evidence current-fence rule
`generation` in the root test receipt is **freeze-time provenance** only. The current execution fence is `mutation_writer_guard`. A pure lease renewal / generation advance with unchanged source, lane manifest, paths, diff digest and test receipt must not invalidate frozen evidence and **不得要求重跑 root tests**.
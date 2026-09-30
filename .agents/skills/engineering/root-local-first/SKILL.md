---
name: root-local-first
description: WHD repository-content implementation 的入口硬閘門。任何執行來源只要要修改 repository 內容，都先在 canonical Google Drive root 完成 source-current 驗證、修改、測試與 diff freeze；只有 GIT_WRITE_UNLOCKED 後才把 exact tested diff 送進 Git/GitHub。
whd_doc_role: CURRENT
whd_contract: root-local-first-workflow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first

本 Skill 是 WHD **所有 repository-content implementation** 的入口 contract。它不取代 `WHD_WORK_ROOT_HARD_GATE_V1`、Phase6 Knowledge Preflight、`WHD_CHANGE_TEST_PROFILE_V1`、Flow v2 control-plane 或 release/final acceptance；它只決定「內容修改在哪裡先發生、何時才允許 Git write」。執行來源可以是 interactive、工作槽、scheduler 或 trusted remote runtime，但 execution mode **不能改變內容施工面**。

## 1. Scope

### 必須套用

- `INTERACTIVE` / chat / default development；
- `SCHEDULER_LANE` / `GITHUB_ONLY` / `REMOTE_ACTION` **只要下一步包含 repository-content implementation**；
- 使用者要求修改 production、tests、docs、workflow、Skill、AI Library、Registry、fixtures 或其他 repository content；
- bugfix / feature / update / refactor / governance / docs-metadata change，不因喚醒來源不同而例外。

### 不直接套用

只有**純 control-plane / post-push verification** 可以不進 root content workspace，例如：

- read-only discovery、WAKE / HEARTBEAT / ownership / lease / reservation coordination；
- trusted Phase6 Preflight；
- 已有 root-tested frozen diff 之後的 Git transport、PR/CI、remote QA、merge、finalization/readback；
- 不產生 repository-content diff 的 observation / reconciliation。

`SCHEDULER_LANE` / `GITHUB_ONLY` / `REMOTE_ACTION` 若發現下一個 executable action 需要新增、修改或刪除 repository content，固定先 `HANDOFF` 到 canonical root workspace implementation；在 root 完成 `ROOT_SOURCE_CURRENT → PATHS_RESERVED → ROOT_MUTATIONS_COMPLETE → ROOT_TEST_CLASSIFIED → ROOT_TESTS_GREEN → ROOT_DIFF_FROZEN → GIT_WRITE_UNLOCKED` 前，remote lane **不得在 GitHub branch 直接施工或熱修**。完成 root-tested handoff 後，remote lane 才可恢復 GitHub post-push verification / merge / finalization。

不得為了繞過本 gate 把一般 content work 假冒成 remote mode。**execution mode 字串本身不是例外證據**；它只決定 control-plane transport，不決定 repository-content implementation surface。

## 2. Canonical root

本 gate 在 `WHD_WORK_ROOT_HARD_GATE_V1` 之後執行。固定 canonical root：

`/Google Drive/WHD`

固定 interactive work prefix：

`/Google Drive/WHD/work/active`

Runtime materialization 可以存在，但只能當 execution machinery；必須保留 canonical-root identity、source SHA/tree 與 touched-path provenance。`/mnt/data`、host temp、GitHub checkout 都不能因此升格成 workspace authority。

## 3. 唯一順序

```text
ROOT_SOURCE_CURRENT
→ PATHS_RESERVED
→ ROOT_MUTATIONS_COMPLETE
→ ROOT_TEST_CLASSIFIED
→ ROOT_TESTS_GREEN
→ ROOT_DIFF_FROZEN
→ GIT_WRITE_UNLOCKED
```

### INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1

互動式 repository-content work 的外層 orchestration 固定走 **session fast path**。底層 lease / reservation / CAS retry / session reuse / QA consume / terminal finalize drain 仍是 machine hard gates，但**必須由同一 execution session 內部吸收，不得由聊天層逐顆手動編排、逐顆等待、逐顆回報**。

外層正常只允許看到：

`FRESH_READ → ROOT_MUTATE → TARGETED_TEST → EXACT_DIFF → POST_PUSH_CI → MERGE_FINALIZE`

明確禁止：

- live session 內重跑 admission；
- scope 未變卻重送 reservation；
- lease 尚未到期就人工 renew；
- 已有 exact-head terminal GREEN 且可 `CONSUME_QA` 時仍拆成 `START_QA → ACCEPT_QA`；
- 為了回報而另外建立 contract 未要求的 evidence artifact；
- 把 generation / lease / CAS / transaction kind 當成聊天層工作清單逐顆操作。

`TEST_RED` **不是離開 fast path 的理由**。interactive repository-content session 遇到 targeted / post-push QA RED 時，外層固定直接回到同一 canonical root workspace 的 `ROOT_MUTATE`（`RETURN_TO_ROOT_REPAIR_IN_SAME_SESSION`），修正後重新 targeted/full test、refreeze、repush。需要把 terminal failure 寫回 ExecutionRecord 時，`FAIL_QA` / failure consume 只能由同一 execution session 的 trusted machine path 內部吸收；聊天層不得因此逐顆送 `FAIL_QA / RECONCILE / START_QA / ACCEPT_QA / lease renew / reservation`。

只有下列條件才允許離開 fast path 升級 machine governance：

`PATH_CONFLICT / SAME_ISSUE_OTHER_WRITER / SUBSTANTIVE_TARGET_OVERLAP / MACHINE_FAIL_CLOSED / USER_INPUT_REQUIRED`

即使命中上述 escalation，`PER_TRANSACTION_MANUAL_ORCHESTRATION` 仍永久禁止；escalation 只改變 machine classifier / blocker 處理，不會把 generation / lease / CAS / transaction kind 重新暴露成聊天層工作清單。

任何升級前都先 fresh-read current Issue；若 generation / fingerprint / lease / next_action / work head / target head 已前進，舊 plan 依 `STALE_PLAN_MUST_DIE` 立即作廢，不准把舊流程補完。

使用者回報只報 phase outcome / 真 blocker；不得把 control-plane internals 當成主要進度。

### 3.1 ROOT_SOURCE_CURRENT

開始任何 root mutation 前：

1. fresh-read `/Google Drive/WHD/source/manifests/WHD Current Source Manifest`；
2. fresh-read authoritative target branch/head/tree；
3. manifest `source_sha/tree_sha` 與 live target exact match 時，可進 root mutation；
4. durable snapshot 若落後，只能當 bootstrap base；planned touched existing paths 必須逐一 fresh-compare exact target blob；
5. 新增 touched path 或依賴未被 current identity 證明時，先補 current materialization／comparison，否則 fail closed。

不得把 stale snapshot、聊天記憶、舊 branch 或「內容看起來差不多」當 `ROOT_SOURCE_CURRENT`。

### 3.2 PATHS_RESERVED

第一次 root content write 前，exact owning Issue 必須先取得 Flow v2 ACTIVE mutation scope。新 READY work 固定使用 atomic `ACQUIRE.effect.admission_reservation={target_branch,base_sha,write_paths,delete_paths}`，在同一 coord CAS 內取得 live lease + reservation；`RESERVE_PATHS` 只保留 compatibility 或既有 ACTIVE scope 的 monotonic 擴張。

硬規則：

- state owner 只有 ExecutionRecord；不得另建 lock database / lock file。
- 同一 `target_branch` 的 nonterminal ACTIVE reservation 以 exact repository path 做 `WRITE/WRITE`、`WRITE/DELETE`、`DELETE/WRITE` overlap check。
- 第一個 CAS 成功者取得 single-writer reservation；第二個固定 `PATH_RESERVATION_CONFLICT`，不得進 root mutation。
- 新 work 不得主動拆成 `ACQUIRE → RESERVE_PATHS` 兩次等待；scope 擴張才送 atomic `RESERVE_PATHS`，只允許 monotonic superset，不得偷偷縮 scope。
- handoff/takeover 只換 owner/lease；reservation 綁 Issue，不隨聊天/runtime 消失。
- reservation 只在 `FINALIZE` terminal 或 explicit atomic `RELEASE_PATHS` 後釋放。
- workspace 必須使用 `build_interactive_work_path(issue=<N>, source_sha=<base>)`，不同 Issue 不得共享同一 `/work/active` 實體工作目錄。
- 第一張 Issue 整合後，其他等待同 path 的 Issue 必須重新 `ROOT_SOURCE_CURRENT → RESERVE_PATHS → retest/refreeze`，不得沿用舊 base 的成果。

Static contract：`.agents/contracts/WHD_PATH_RESERVATION_V1.json`；Machine evaluator：`tools/execution_path_reservation.py`。

### 3.3 ROOT_MUTATIONS_COMPLETE

production / tests / docs / Skills / AI Library / Registry 等內容修改先在 canonical root workspace 完成。此階段 Git repository content plane 固定 read-only。

### 3.4 ROOT_TEST_CLASSIFIED

測試分類只有一個 owner：

- schema=`WHD_CHANGE_TEST_PROFILE_V1`
- machine owner=`tools/change_test_profile.py`

本 Skill 不建立第二套 BUGFIX/FEATURE/UPDATE/REFACTOR/GOVERNANCE/DOCS_METADATA parser。changed files 擴張時依 owner 規則重算 profile。

### 3.5 ROOT_TESTS_GREEN

在 root workspace 先完成 profile 要求的 RED/GREEN、targeted、affected subsystem、integration 與 final full gate。GitHub Actions / remote QA 是 **post-push verification**，不是第一個測試面。

### 3.5.1 TEST_EXECUTION_RECEIPT_HARD_GATE_V1

`ROOT_TESTS_GREEN` 不接受裸 `tests_green=true`。必須攜帶 machine-readable `WHD_TEST_EXECUTION_RECEIPT_V1`，至少 exact 綁定 `source_sha / issue / generation / exact_commands / manifest_digest`，且 status=`GREEN`。receipt 與本輪 source/reservation/test command 任一 identity 不一致即 fail closed。

### 3.6 ROOT_DIFF_FROZEN

root tests terminal GREEN 後 freeze：

- exact source SHA / tree SHA；
- touched paths；
- each final file SHA256；
- exact diff digest；
- test profile；
- test commands / terminal results；
- frozen timestamp / task identity。

freeze 後內容若再變，舊 freeze 失效；重測並產生新 freeze。

### 3.7 GIT_WRITE_UNLOCKED

只有前五步都成立才可解鎖 Git content write。

解鎖前 Git 只允許：

`READ / FETCH / COMPARE`

禁止：content write、commit、create/update ref、push、merge。

解鎖時先 fresh-read target。若 target base 或任何 touched target path drift：

`RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE`

不得把未重測的 stale root diff 直接套到 Git。

## 4. Git phase

`GIT_WRITE_UNLOCKED` 後：

1. 從 fresh authoritative target HEAD 建立新的 work branch；
2. fresh-read branch parent/base SHA；
3. 只允許 `EXACT_TESTED_DIFF_ONLY`；
4. Git phase 不得順手改內容、補小修、整理格式或另改 docs；任何差異回 root 修改 → 測試 → refreeze；
5. push 後跑 GitHub Actions / remote QA；
6. remote QA fail 時回 root 修正，不在 Git branch 上直接熱修；
7. interactive `START_BRANCH` / `APPLY_COMMIT` 進 Flow v2 mutation ingress 前，必須帶 `ROOT_LOCAL_FIRST_GIT_UNLOCK_RECEIPT_V1`；ingress 在讀 ExecutionRecord state **之前**先驗 receipt，缺失或不合法即 fail closed；
8. final integration 仍走 non-force PR/merge 與既有 acceptance/drift gate。

因此「Git phase 要用 work branch」仍是硬規則，但它位於 `GIT_WRITE_UNLOCKED` **之後**，不能再解讀成「root 開發前先建 branch」。

### CONNECTOR_MUTATION_REJECTION_CLASSIFICATION_V1

Git phase 的單次 connector/runtime mutation rejection **不得直接升級**為 permanent capability blocker。先分類為 `RETRYABLE_UNCLASSIFIED`，fresh-read authenticated permission、base/target existence、branch existence、matching ruleset/branch protection 與 exact connector action contract；new branch 使用 `create_branch(base_sha)`；只有**非 authoritative 的 dedicated work branch** 才可在 transport recovery 中使用 `update_ref(force=false)`。`cleanup/2d-3d-sync` / `main` 等 production target 的 ref advancement 一律交回 Flow v2 trusted `MERGE` / `SYNC_TARGET` transport，chat/runtime Connector `update_ref` 固定禁止。只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可標 permanent capability blocker。

## 5. Source manifest / snapshot durability

<!-- POST_INTEGRATION_DURABILITY_HARD_GATE_V1 -->

Flow v2 `DONE` 只代表 execution / merge / issue closure / reservation 已 terminal；**不代表 root-local durable cleanup 已完成**。accepted integration 後固定進入獨立 cleanup tail：

`FLOW_V2_DONE → EXPORT_RUN_GREEN → ARTIFACT_IDENTITY_BOUND → DRIVE_SNAPSHOT_WRITTEN → DRIVE_SNAPSHOT_READBACK_VERIFIED → MANIFEST_WRITEBACK_COMPLETE → WORKSPACE_ARCHIVE_ELIGIBLE → WORKSPACE_ARCHIVED → DURABLE_CLEANUP_COMPLETE`

唯一 machine owner 是 `tools/post_integration_durability.py`，static contract=`.agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json`。它不得改寫 ExecutionRecord、lease、mutation、merge 或 closure，只判斷 DONE 後 cleanup 下一步。

硬規則：

1. source export 必須 exact 綁 accepted/current cleanup `source_sha + tree_sha + GitHub run_id + artifact_id + artifact digest`；
2. workflow export manifest 必須自帶 `snapshot_name + snapshot_sha256 + artifact_name`；
3. snapshot 必須先寫入 `/Google Drive/WHD/source/snapshots`，再由 Drive readback 重新計算 SHA256；readback 不一致不得更新 manifest；
4. 只有 `WHD_SOURCE_SNAPSHOT_WRITEBACK_RECEIPT_V1.status=VERIFIED` 才可把 Current Source Manifest 寫成 `durable_snapshot_status=CURRENT_EXACT_HEAD` 與 `export_writeback_status=COMPLETE`；
5. stale snapshot 只能是 `STALE_BOOTSTRAP_BASE`，永遠不得冒充 current；
6. workspace 只有在 `state=DONE + lease=null + reservation=RELEASED + next_action=null + issue_closed=true` 才可由 `/work/active` 搬到 `/work/done`；
7. nonterminal/live work 永遠不可 auto-archive；
8. `DONE` 後若 export 還 pending，machine action 固定 `CONSUME_SOURCE_EXPORT`；export complete 但 workspace 還在 active，固定 `ARCHIVE_WORKSPACE_TO_DONE`；兩者都完成才是 `DURABLE_CLEANUP_COMPLETE`。
9. source-export transport 必須覆蓋 direct `push`、`pull_request closed + merged`，以及 trusted Flow v2 merge 不會自觸發後續 workflow 的情境。若 accepted merged SHA 尚無 exact export run，`CONSUME_SOURCE_EXPORT` 必須經既有 `.github/workflows/drive-source-snapshot-export.yml` 的 durable request transport：branch=`coord/source-export-requests`、path=`.dispatch/source-export-request.json`、schema=`WHD_SOURCE_EXPORT_REQUEST_V1`，request 明確綁 `source_branch=cleanup/2d-3d-sync + source_sha=<accepted merged SHA>`。workflow 必須證明 requested SHA reachable from current cleanup history，並以 requested SHA 而非 request-branch HEAD 產生 snapshot/artifact；不得新增第二顆 export workflow，也不得讓 `DONE` 因 transport event 缺口留下 orphan durability tail。

下一個 task 的 `ROOT_SOURCE_CURRENT` 必須能 machine 判斷 exact-current 或 scoped-current recovery；不得讓 manifest 長期留在舊 SHA 卻仍標 CURRENT，也不得讓 closed/DONE workspace 長期留在 `/work/active`。

## 6. Durable correction / anti-regrowth

以下 wording 在 CURRENT active governance 中視為 regression：

- 「第一個 repository write 前先建立 Git branch」作為 interactive content 開發起點；
- 「建立 branch 後才可開始 Skill/tests/docs/production 修改」；
- 用 GitHub checkout 取代 `/Google Drive/WHD` default root；
- focused/root test 尚未完成就先 push，再把 remote QA 當第一測試面。

歷史 incident 可保留舊 wording，但必須清楚標 `HISTORICAL / SUPERSEDED`，不得再作 CURRENT instruction。

## 7. Machine owners

- contract mirror: `.agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json`
- machine gate: `tools/root_local_first_gate.py`
- post-integration durability owner: `tools/post_integration_durability.py`；contract=`.agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json`
- path reservation contract: `.agents/contracts/WHD_PATH_RESERVATION_V1.json`；evaluator=`tools/execution_path_reservation.py`；state owner=`WHD_EXECUTION_RECORD_V2.mutation_scope`
- source/test profile owner: `tools/change_test_profile.py`
- startup owner: `AGENTS.md`
- execution/control-plane owner: `.agents/skills/engineering/flow-v2-execution/SKILL.md`
- authority map: `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`

完成狀態只能由 machine evidence + tested frozen diff 支撐；「我已經在 root 改過」或「branch 已存在」都不是完成證據。

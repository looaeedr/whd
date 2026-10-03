---
name: root-local-first
description: WHD repository-content implementation 的 CURRENT shared-unpushed 入口硬閘門。所有修改與測試先在 `/Google Drive/WHD` 完整 repo root 完成；不先開 Git branch。文檔/治理/Skill 與產品主體分成 docs/body 兩條共享 `0` lineage；只有 `/推推 文檔|主體` 在 lane GREEN 後建立 delivery branch。
whd_doc_role: CURRENT
whd_contract: root-shared-unpushed-v1
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first / shared-unpushed V1

## 0. ENTRY_ROUTER_FIRST_HARD_GATE_V1

任何 WHD repository-content 任務（新任務、續作、修補、測試、治理修改）進場時，**第一個路由不得先做一般 discovery**。每個 invocation 都必須 fresh 依序完成：

```text
READ .agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json
→ READ .agents/skills/engineering/root-local-first/SKILL.md
→ ENTRY_ROUTER_READY
```

`ENTRY_ROUTER_READY` 前只允許上述兩個 bootstrap read。以下動作全部 fail closed：

- generic Google Drive / file search；
- Remote Desktop / local-machine search；
- GitHub content discovery / branch create / mutation；
- claim / Flow v2 discovery；
- 任何用聊天記憶、舊摘要或上一 invocation evidence 代替 fresh entry read 的行為。

若操作員先走錯路，固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`：撤銷該段 discovery 作為 execution evidence，回到 `/Google Drive/WHD` canonical entry 從兩個 fresh read 重新開始；不得因已經查到資料就沿錯路續做。

machine owner=`tools/root_local_first_gate.py::build_entry_router_evidence / validate_entry_router_evidence / assert_entry_router_action_allowed`。

本 Skill 是 WHD CURRENT repository-content workflow。舊的 `/work/active` per-Issue workspace、root-write 前 single-writer reservation、`source/manifests`/ZIP snapshot current authority、branch-first 都已 superseded。

## 1. Canonical root hard gate

唯一預設 root：`/Google Drive/WHD`，Drive folder id=`1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN`。

開始任何內容工作前固定：

`WHD_ROOT_RESOLVED → ROOT_IDENTITY_VERIFIED → FULL_REPO_ROOT_VERIFIED → SHARED_UNPUSHED_LAYOUT_VERIFIED`

full repo root 至少必須存在 `.git/.agents/.github/AGENTS.md/tools/tests/ae_engine/gui_modules/.unpushed`。`source/state/work/artifacts` 不再是 CURRENT content-root 前置結構。

machine owner=`tools/work_root_gate.py`；contract=`.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json`。

### 1.1 ROOT_PATH_RESOLUTION_BEFORE_REMOTE_HARD_GATE_V1

repository-content 任務的第一個檔案定位動作必須從 `/Google Drive/WHD` root 開始，沿實際 parent-folder chain 解析到目標 path。

- 全域 Drive search、聊天記憶、GitHub code search、remote checkout、歷史 snapshot 只能提供候選，不得直接建立 baseline identity。
- 同名檔只有在 parent chain exact 等於 canonical repo path 時才可用；其他 `.scratch`、`.unpushed`、backup、mirror、歷史副本一律不是施工 baseline。
- 找檔、讀 baseline、判斷「目前版本」、建立 diff、修改與測試都必須先在 canonical root 完成。
- root path 無法解析時固定 `ROOT_PATH_UNRESOLVED_FAIL_CLOSED`；禁止為了找檔改連 GitHub 或遠端本機。

### 1.2 REMOTE_CONNECTION_DENY_BY_DEFAULT_HARD_GATE_V1

除非符合下列其中一項，interactive/default invocation 不得建立 GitHub 或遠端本機連線：

1. 使用者明確要求「開工單」：只授權 issue create/readback 所需 GitHub 連線；
2. 使用者明確要求 GitHub/遠端操作；
3. 使用者下達 `/推推 文檔` 或 `/推推 主體`：只授權 selected lane delivery window；
4. recurring/scheduler invocation 的 user-authored entry contract 明確指定 GitHub-only execution，且僅限該 invocation scope。

「想確認最新」、「找不到檔」、「Preflight 需要」、「工具剛好可用」都不是 remote authority。Remote Desktop/遠端本機尤其不得被當成 root lookup fallback。

### 1.3 ISSUE_SYNC_ON_SPLIT_AND_DELIVERY_HARD_GATE_V1

使用者已把「拆工同步工單、推推完成後再同步工單」定為 WHD durable workflow rule。這只開放 **GitHub Issue plane**，不開放 repository-content plane：

- **拆工同步**：一個工作被拆成 child/follow-up 時，child 可以先存在 transient local draft，但在 GitHub Issue create/reuse + parent/child/dependency sync + fresh readback 完成前，禁止標成 READY、禁止排程/派工、禁止建立 Flow v2 READY record。同步失敗固定 `ISSUE_SYNC_PENDING_CONTINUE_OTHER_EXECUTABLE_LEAF`，不得把 local-only child 當 executable work。
- **推推後同步**：selected lane `MERGE_READBACK_VERIFIED` + delivery receipt 後，必須把 lane/generation/manifest/PR/merged SHA/test result 與 terminal state 或 exact next_action/blocker 同步到 linked GitHub Issue，再 fresh-read 成 `ISSUE_SYNC_READBACK_VERIFIED`，之後才可視為完整 delivery cycle。
- terminal Issue 的 close authority 仍只有 Flow v2 `FINALIZE`；`/推推` 不另造 closure state machine。非 terminal Issue 必須保持 open 並同步 exact next action/blocker。
- 這兩個例外對應 `SPLIT_ISSUE_SYNC` / `POST_DELIVERY_ISSUE_SYNC` remote authority，只允許 Issue create/update/relation/comment/readback；**不得**藉此 READ/FETCH/COMPARE repository content、建 branch、commit、push、merge。

machine owner=`tools/root_local_first_gate.py::build_remote_connection_authority/validate_remote_connection_authority`；contract=`issue_sync_hard_gate`。

## 2. 兩條未推送 lineage

固定：

- 文檔 lane：`.unpushed/docs/0`
- 主體 lane：`.unpushed/body/0`

分類看**歸屬**而不是副檔名：

- 治理、Skill、`AGENTS.md`、流程 authority、Registry、SOP、治理 contract、治理 tests、純說明文件 → docs。
- 產品程式、產品 tests、UI、renderer、geometry、manufacturing → body。
- **主體必要的文件屬於 body**：若不同步交付會讓產品不完整、不可驗收或契約不一致，就不能丟到 docs。

machine owner=`tools/shared_unpushed_integration.py::classify_lane`。

## 3. 每一步硬閘門

唯一順序：

```text
ROOT_IDENTITY_CURRENT
→ LANE_CLASSIFIED
→ ZERO_INITIALIZED_OR_FRESH_READ
→ WORKER_BASE_LATEST_ZERO
→ WORKER_MUTATION_COMPLETE
→ WORKER_TESTS_GREEN
→ MERGE_TO_FRESH_LATEST_ZERO
→ CONFLICT_GATE_OR_MERGED
→ POST_MERGE_ZERO_TESTS_GREEN
→ ZERO_MANIFEST_FROZEN
→ DELIVERY_RESERVATION
→ GIT_WRITE_UNLOCKED
```

任一步沒有 machine evidence，下一步 fail closed。

### 3.1 ROOT_IDENTITY_CURRENT

在未進入明確 remote-authorized delivery 前，只以 canonical root 的實際 repo tree、`.git` 本地 identity 與 exact parent-chain path 驗證 root identity；**不得為了做這一步先連 GitHub fresh-read `main`**。root tracked content 不能以舊 ZIP、聊天記憶、全域搜尋同名檔或 remote mirror 冒充 current。

真正的 live target HEAD fresh-read 只在 `/推推` 已取得使用者遠端授權後執行。

### 3.2 LANE_CLASSIFIED

planned paths 全部先分類到 docs/body。未分類 path fail closed；同一 path 不得同時存在兩 lane manifest。

### 3.3 ZERO_INITIALIZED_OR_FRESH_READ

第一次有人要改某 path：從 CURRENT root copy 該 path 進對應 lane `0`，記錄 hash/generation/issue/worker，建立 lineage lock。若 `0` 已有該 path，不得再從 root 舊版本當 base。

### 3.4 WORKER_BASE_LATEST_ZERO

後來者固定讀最新 `0` 的 generation+hash 作 base。base generation 落後時先 rebase/merge 到 latest `0`，禁止直接施工後覆寫。

worker candidate 可以存在 `.unpushed/{lane}/workers/<worker>/issue-<N>`；它只是 candidate，不是 authority，也不是 Git branch。

### 3.5 WORKER_MUTATION_COMPLETE / WORKER_TESTS_GREEN

修改與測試都發生在 canonical root namespace，不建立 Git work branch。測試 profile 由 `tools/change_test_profile.py` 決定。TEST_RED 留在 root 修正並重測；禁止 GitHub-side hotfix。

### 3.6 MERGE_TO_FRESH_LATEST_ZERO

worker 完成後必須重新 fresh-read latest `0`，以「worker 起始 base + worker delta + fresh latest 0」做三方合併。merge 成功才可 generation+1。

## 4. MERGE_CONFLICT_USER_DECISION_HARD_GATE_V1

任何 conflict 都固定：

`CONFLICT → WRITE WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1 → BLOCKED_USER_DECISION → NOTIFY USER`

checkpoint 必須記錄 lane/path/base_generation/latest_generation/base_hash/latest_hash/worker_hash/conflict hunks/worker/issue。

取得 `EXPLICIT_USER_CONFLICT_DECISION` 前，禁止：

- auto resolve / ours / theirs / AI 自行選邊；
- 改寫 conflict hunk；
- generation+1；
- merge 回 0；
- 建 delivery branch；
- `/推推`；
- push / PR。

## 5. POST_MERGE_ZERO_TESTS_GREEN

worker 自己 GREEN 不代表 `0` GREEN。合併進最新 `0` 後必須再跑 affected/profile tests。只有最新 `0` 的 post-merge evidence GREEN 才能 freeze。

## 6. ZERO_MANIFEST_FROZEN

freeze 必須 exact 綁 lane、generation、source SHA、target branch、write/delete paths、每檔 hash、manifest digest、test commands/results。`0` 任何內容再變，舊 freeze 立即失效。

## 7. Git delivery 只由 /推推 開啟

正常施工階段 **GitHub network content plane 完全關閉**；本地 `.git` 只可作 root identity/diff 的 offline 輔助，不得 FETCH/PULL/remote compare，也不得先建 branch。

只有使用者下達 `/推推 文檔` 或 `/推推 主體`，且 selected lane frozen GREEN 後，才開啟本次 GitHub delivery window，取得 delivery reservation、fresh-read live target，並固定：

`DELIVERY_FILESET_LOCKED → PUSH_SCOPE_MUST_EQUAL_LOCK → FRESH_TARGET_HEAD → DELIVERY_RESERVATION → CREATE_DELIVERY_BRANCH → EXACT_LOCKED_FILESET_APPLY → POST_PUSH_CI → PRE_MERGE_LATEST_FILE_RECHECK → MERGE_READBACK_VERIFIED → FINALIZE_DELIVERED_PATHS`

fileset lock 必須 exact 綁 path + hash/delete marker；merge 前再次驗 target/head/changed filenames/locked blob hashes。任何 drift 都回 canonical root/shared-0 reconcile + retest + refreeze，不得 Git-side hotfix。

Flow v2 path reservation 保留在這個 delivery phase，**不再作為 root 施工前置 single-writer gate**。

## 8. Anti-regrowth

CURRENT 文件/Skill/contract 不得再宣告：

- `/work/active` 是 repository-content authority；
- `source/manifests` 或 ZIP snapshot 是 current root authority；
- root write 前必須 single-writer `PATHS_RESERVED`；
- 建 branch 後才開始修改/測試；
- pre-delivery 可以先連 GitHub READ/FETCH/COMPARE；
- 可以用 GitHub/Remote Desktop/全域同名搜尋取代 canonical root parent-chain lookup；
- conflict 可自動 ours/theirs。

舊文字如需保留，只能明確標 `HISTORICAL/SUPERSEDED`，不得參與 routing。


## Machine owners

- test profile: `WHD_CHANGE_TEST_PROFILE_V1` / `tools/change_test_profile.py`

- `INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1`: outer layer reports phase outcomes; low-level control transactions 不得由聊天層逐顆手動編排。

- `DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1`: root-capable execution must mutate/test shared-0 in the same invocation until GREEN or a real blocker.

- delivery Git write mode 固定 `EXACT_TESTED_DIFF_ONLY`；任何 delivery branch 上新增內容變更都必須退回 shared-0 重測。
- delivery 成功後只清除 readback 已證明交付的 locked paths；其他未推送/後續變更保留。之後同檔再改必須重新登記為新的 shared-0 未推送修改。


## 9. POST_INTEGRATION_DURABILITY_HARD_GATE_V2

Flow v2 `DONE` 之後，repository-content physical cycle 還必須完成：

`MERGE_READBACK_VERIFIED → SYNC_CANONICAL_ROOT_TO_ACCEPTED_HEAD → LANE_DELIVERY_RECEIPT_BOUND → FINALIZE_DELIVERED_LANE_ZERO → DURABLE_CLEANUP_COMPLETE`

硬規則：

- canonical `/Google Drive/WHD` 的 `.git` HEAD/tree 必須 exact 等於 accepted merged commit/tree；
- selected `.unpushed/{body|docs}/0` 的已交付 generation 必須變成 `EMPTY` 或 `ROLLED_FORWARD`，並留下 `WHD_UNPUSHED_LANE_DELIVERY_RECEIPT_V1`；
- `source/snapshots`、`Current Source Manifest`、`/work/active` archive 全部是 SUPERSEDED，不得再作完成 authority；
- machine owner=`tools/post_integration_durability.py`；contract=`.agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json`。

- production target 的 ref advancement 一律交回 Flow v2 trusted `MERGE` / `SYNC_TARGET`；chat/runtime connector `update_ref` 不得直接推進 main/production target。


### TEST_RECEIPT_AND_CONNECTOR_REJECTION_HARD_GATE_V2

`POST_MERGE_0_TESTS_GREEN` 不接受裸 `tests_green=true`；必須攜帶 `WHD_TEST_EXECUTION_RECEIPT_V1`，並 exact 綁定 manifest digest 與 exact commands。

單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接宣告 permanent blocker。fresh-read authenticated permission、target/base existence、branch protection/ruleset 與 connector action contract 後再分類。delivery branch 只使用 `create_branch(base_sha)`；`update_ref` 只允許 non-authoritative delivery/recovery branch 且 `force=false`，不得直接前推 main/production target。只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可標 permanent capability blocker。

Pre-write reservation 已退役；root shared-0 authoring 不取得 path reservation。只有 `LANE_MANIFEST_FROZEN` 後的 delivery phase 才允許 reservation。

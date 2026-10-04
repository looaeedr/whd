---
name: root-local-first
description: WHD repository-content implementation 的 CURRENT workspace-first 入口。每個 executor 使用自己的 repo workspace，以 `cleanup/2d-3d-sync` 作共同 production baseline；修改/測試在該 workspace 完成後走 delivery branch + PR/checks。Google Drive shared-0 只在 fresh unpushed drift 存在時作 fallback/reconcile。
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

本 Skill 是 WHD CURRENT repository-content workflow。預設路徑是 executor-local workspace-first；`cleanup/2d-3d-sync` 是共同 production baseline。舊的 `/work/active`、固定 Google Drive-first、每次 shared-0 generation/freeze、以及任何單一實體 workspace 路徑都不是普通工作前置。

## 1. EXECUTOR_LOCAL_WORKSPACE_FIRST_V1

普通 repository-content 任務固定：

`cleanup/2d-3d-sync → executor-local repo workspace → edit/test → tested delivery branch → PR/checks → cleanup/2d-3d-sync`

每個 executor 使用自己的 workspace；**不得硬編單一全域路徑**：
- Codex 可是 `/workspace/whd`；
- ChatGPT 使用自己的 runtime workspace；
- 其他 executor 使用各自 runtime repo workspace。

共同 identity 是 production branch `cleanup/2d-3d-sync` 與 fresh HEAD，不是某個實體資料夾。

開工前只需：
`WORKSPACE_ROOT_RESOLVED → WORKSPACE_GIT_IDENTITY_VERIFIED → PRODUCTION_BASELINE_CURRENT`

普通 workspace startup **不要求** Google Drive generation/manifest、shared-0、`workspace_canonical_sync.py` 或 `CANONICAL_SHARED_0_UPDATED`。

### 1.1 Workspace baseline / GitHub read policy

為了把 executor workspace 對齊 production baseline，普通 content work 可直接做窄化 GitHub baseline：
`READ / FETCH / COMPARE / BRANCH_READ / REPO_METADATA_READ`。

這些 read-only baseline actions 不需要額外 `/推推` authority。Git write 仍受限：
- 禁止 direct push `cleanup/2d-3d-sync`；
- 修改與測試先在 executor workspace；
- 測試 GREEN + exact diff 後，只能建立 delivery branch、push、PR、跑 required checks；
- target drift 時 refresh workspace baseline、retest，再 delivery。

### 1.2 Conditional Drive/shared-0 fallback

`/Google Drive/WHD/.unpushed/{docs|body}/0` 保留，但只在 **fresh evidence 證明 touched paths 存在 GitHub/workspace 沒有的 unpushed overlay/drift** 時啟動。

route machine owner=`tools/root_local_first_gate.py::select_repository_content_route`：

- `shared_zero_drift_present=false → WORKSPACE_DEFAULT`
- `shared_zero_drift_present=true → SHARED_ZERO_FALLBACK`

只有 `SHARED_ZERO_FALLBACK` 才啟動既有 `tools/workspace_canonical_sync.py`、generation/hash、三方合併、conflict checkpoint、manifest freeze、`CANONICAL_SHARED_0_UPDATED` 與 `/推推 文檔|主體`。

workspace dirty work 不得被 fallback sync silent overwrite；同 path drift 固定 `WORKSPACE_CANONICAL_RECONCILE_REQUIRED`。

### 1.3 Authority boundary

executor-local workspace 是 execution surface/cache，不是新的 canonical content authority。普通共同 baseline authority 是 GitHub `cleanup/2d-3d-sync`；Drive shared-0 在 fallback active 時只對該未推送 lineage 擁有較新 overlay authority。

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

窄化 recovery 例外：durable delivery/readback evidence 已明確證明 canonical root 落後 accepted production lineage 時，有 root-capable runtime 才可選擇執行 `python tools/work_root_gate.py recover-current-production`。machine owner=`tools/work_root_gate.py::recover_canonical_root_to_current_production`；它只允許 tracked-clean、同一 production branch、local HEAD 為 fresh remote HEAD ancestor 的 fast-forward catch-up，保留 untracked `.unpushed`，不建立/修改 ExecutionRecord、不關 Issue、不簽 closure authority。**此 recovery 是 optional maintenance，不是 terminal/startup closure hard gate；沒有 root-capable surface 時不得因此要求額外權限或阻塞已完成 Issue。**

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

正常施工階段允許為 production baseline 做 `READ / FETCH / COMPARE / BRANCH_READ / REPO_METADATA_READ`；內容修改與測試仍在 executor-local workspace。Git write 只在 exact tested diff 準備完成後進 delivery branch，production target 禁止直推。

普通 WORKSPACE_DEFAULT 不需要 `/推推`；tests GREEN + exact diff 後即可開 tested delivery branch / PR window。只有 SHARED_ZERO_FALLBACK 才要求使用者下達 `/推推 文檔` 或 `/推推 主體` 並走 selected lane frozen delivery：

`DELIVERY_FILESET_LOCKED → PUSH_SCOPE_MUST_EQUAL_LOCK → FRESH_TARGET_HEAD → DELIVERY_RESERVATION → CREATE_DELIVERY_BRANCH → EXACT_LOCKED_FILESET_APPLY → POST_PUSH_CI → PRE_MERGE_LATEST_FILE_RECHECK → MERGE_READBACK_VERIFIED → FINALIZE_DELIVERED_PATHS`

fileset lock 必須 exact 綁 path + hash/delete marker；merge 前再次驗 target/head/changed filenames/locked blob hashes。任何 drift 都回 canonical root/shared-0 reconcile + retest + refreeze，不得 Git-side hotfix。

Flow v2 path reservation 保留在這個 delivery phase，**不再作為 root 施工前置 single-writer gate**。

## 8. Anti-regrowth

CURRENT 文件/Skill/contract 不得再宣告：

- `/work/active` 是 repository-content authority；
- `source/manifests` 或 ZIP snapshot 是 current root authority；
- root write 前必須 single-writer `PATHS_RESERVED`；
- 建 branch 後才開始修改/測試；
- 把 GitHub `cleanup/2d-3d-sync` 當普通 workspace production baseline；
- 可以用 GitHub/Remote Desktop/全域同名搜尋取代 canonical root parent-chain lookup；
- conflict 可自動 ours/theirs。

舊文字如需保留，只能明確標 `HISTORICAL/SUPERSEDED`，不得參與 routing。


## Machine owners

- test profile: `WHD_CHANGE_TEST_PROFILE_V1` / `tools/change_test_profile.py`

- `INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1`: outer layer reports phase outcomes; low-level control transactions 不得由聊天層逐顆手動編排。

- `DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1`: 只在 `SHARED_ZERO_FALLBACK_ACTIVE` 生效；普通 WORKSPACE_DEFAULT 不進 shared-0。

- delivery Git write mode 固定 `EXACT_TESTED_DIFF_ONLY`；任何 delivery branch 上新增內容變更都必須退回 shared-0 重測。
- delivery 成功後只清除 readback 已證明交付的 locked paths；其他未推送/後續變更保留。之後同檔再改必須重新登記為新的 shared-0 未推送修改。


## 9. POST_INTEGRATION_DURABILITY_V2

Flow v2 `FINALIZE → DONE` 加上 trusted GitHub merge/Issue readback就是 terminal authority；**不得再以 canonical Drive root sync/recovery receipt 阻塞已完成 Issue closure**。

repository-content cleanup 固定：

`MERGE_READBACK_VERIFIED → LANE_DELIVERY_RECEIPT_BOUND → FINALIZE_DELIVERED_LANE_ZERO → DURABLE_CLEANUP_COMPLETE`

### ROOT_SYNC_MAINTENANCE_NON_BLOCKING_V1

- canonical `/Google Drive/WHD` root sync/recovery 保留為 maintenance / next-start catch-up，不是 terminal gate、不是 closure authority。
- 有 root-capable runtime 時，可執行 `tools/post_integration_durability.py::sync_canonical_root_to_accepted_head` 或 `tools/work_root_gate.py::recover_canonical_root_to_current_production` 並留下 VERIFIED receipt。
- execution surface 無法存取 `/Google Drive/WHD/.git` 時，固定記錄 maintenance drift；**不得要求額外「root-capable 權限」、不得保持 Issue OPEN、不得撤銷既有 DONE/FINALIZE**。
- 缺少 `WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1` / `WHD_WORK_ROOT_RECOVERY_RECEIPT_V1` 不得成為 `FINALIZE`、Issue close、scheduler cycle return 的 blocker。
- 若有人提供 root receipt，machine 仍驗 exact accepted head/tree；receipt 無效只代表 maintenance drift，不得重新打開 terminal Issue。
- selected `.unpushed/{body|docs}/0` 的已交付 generation 仍必須變成 `EMPTY` 或 `ROLLED_FORWARD`，並留下 `WHD_UNPUSHED_LANE_DELIVERY_RECEIPT_V1`。
- `source/snapshots`、`Current Source Manifest`、`/work/active` archive 全部是 SUPERSEDED，不得再作完成 authority。
- machine owner=`tools/post_integration_durability.py`；contract=`.agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json`。
- production target 的 ref advancement 一律交回 Flow v2 trusted `MERGE` / `SYNC_TARGET`；chat/runtime connector `update_ref` 不得直接推進 main/production target。


### TEST_RECEIPT_AND_CONNECTOR_REJECTION_HARD_GATE_V2

`POST_MERGE_0_TESTS_GREEN` 不接受裸 `tests_green=true`；必須攜帶 `WHD_TEST_EXECUTION_RECEIPT_V1`，並 exact 綁定 manifest digest 與 exact commands。

單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接宣告 permanent blocker。fresh-read authenticated permission、target/base existence、branch protection/ruleset 與 connector action contract 後再分類。delivery branch 只使用 `create_branch(base_sha)`；`update_ref` 只允許 non-authoritative delivery/recovery branch 且 `force=false`，不得直接前推 main/production target。只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可標 permanent capability blocker。

Pre-write reservation 已退役；root shared-0 authoring 不取得 path reservation。只有 `LANE_MANIFEST_FROZEN` 後的 delivery phase 才允許 reservation。

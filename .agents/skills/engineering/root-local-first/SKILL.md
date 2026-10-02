---
name: root-local-first
description: WHD repository-content implementation 的 CURRENT shared-unpushed 入口硬閘門。所有修改與測試先在 `/Google Drive/WHD` 完整 repo root 完成；不先開 Git branch。文檔/治理/Skill 與產品主體分成 docs/body 兩條共享 `0` lineage；只有 `/推推 文檔|主體` 在 lane GREEN 後建立 delivery branch。
whd_doc_role: CURRENT
whd_contract: root-shared-unpushed-v1
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first / shared-unpushed V1

本 Skill 是 WHD CURRENT repository-content workflow。舊的 `/work/active` per-Issue workspace、root-write 前 single-writer reservation、`source/manifests`/ZIP snapshot current authority、branch-first 都已 superseded。

## 1. Canonical root hard gate

唯一預設 root：`/Google Drive/WHD`，Drive folder id=`1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN`。

開始任何內容工作前固定：

`WHD_ROOT_RESOLVED → ROOT_IDENTITY_VERIFIED → FULL_REPO_ROOT_VERIFIED → SHARED_UNPUSHED_LAYOUT_VERIFIED`

full repo root 至少必須存在 `.git/.agents/.github/AGENTS.md/tools/tests/ae_engine/gui_modules/.unpushed`。`source/state/work/artifacts` 不再是 CURRENT content-root 前置結構。

machine owner=`tools/work_root_gate.py`；contract=`.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json`。

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

fresh-read live `main` HEAD/tree，並驗證 canonical root 是完整 repo root。root tracked content 不能以舊 ZIP snapshot 或聊天記憶冒充 current。

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

正常施工階段 Git content plane 只允許 READ/FETCH/COMPARE。**不得先建 branch。**

只有 selected lane frozen GREEN 後才取得 delivery reservation，fresh-read `main`，然後執行 `/推推 文檔` 或 `/推推 主體`：

`DELIVERY_RESERVATION → PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST → CREATE_DELIVERY_BRANCH → EXACT_MANIFEST_APPLY → POST_PUSH_CI → MERGE_READBACK`

Flow v2 path reservation 保留在這個 delivery phase，**不再作為 root 施工前置 single-writer gate**。

## 8. Anti-regrowth

CURRENT 文件/Skill/contract 不得再宣告：

- `/work/active` 是 repository-content authority；
- `source/manifests` 或 ZIP snapshot 是 current root authority；
- root write 前必須 single-writer `PATHS_RESERVED`；
- 建 branch 後才開始修改/測試；
- conflict 可自動 ours/theirs。

舊文字如需保留，只能明確標 `HISTORICAL/SUPERSEDED`，不得參與 routing。


## Machine owners

- test profile: `WHD_CHANGE_TEST_PROFILE_V1` / `tools/change_test_profile.py`

- `INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1`: outer layer reports phase outcomes; low-level control transactions 不得由聊天層逐顆手動編排。

- `DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1`: root-capable execution must mutate/test shared-0 in the same invocation until GREEN or a real blocker.

- delivery Git write mode 固定 `EXACT_TESTED_DIFF_ONLY`；任何 delivery branch 上新增內容變更都必須退回 shared-0 重測。


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

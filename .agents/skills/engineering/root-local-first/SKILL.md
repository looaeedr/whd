---
name: root-local-first
description: WHD repository-content implementation 的 CURRENT workspace-first 入口。Git production X 是唯一流程 authority；每個 executor 在自己的 repo workspace 修改/測試後走 delivery branch + PR/checks。Google Drive 僅為資料／mirror／backup，永不參與 startup、routing 或施工 authority。
whd_doc_role: CURRENT
whd_contract: root-shared-unpushed-v1
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first / workspace-first V2

## 0. ENTRY_ROUTER_FIRST_HARD_GATE_V1

任何 WHD repository-content 任務（新任務、續作、修補、測試、治理修改）進場時，**第一個路由不得先做一般 discovery**。每個 invocation 都必須 fresh 依序完成：

```text
READ .agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json
→ READ .agents/skills/engineering/root-local-first/SKILL.md
→ ENTRY_ROUTER_READY
```

`ENTRY_ROUTER_READY` 前只允許上述兩個 bootstrap read。**兩個 bootstrap path 都只從已解析的 executor-local repo workspace 讀取。Google Drive mirror、舊 Drive Skill、`.unpushed`、shared-zero 或任何 Drive 可見性都不得參與 startup routing。Drive mount 不可見永遠不是 repository-content blocker。**

以下動作全部 fail closed：

- generic Google Drive / file search；
- Remote Desktop / local-machine search；
- GitHub content discovery / branch create / mutation；
- claim / Flow v2 discovery；
- 任何用聊天記憶、舊摘要或上一 invocation evidence 代替 fresh entry read 的行為。

若操作員先走錯路，固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY`：撤銷該段 discovery 作為 execution evidence，回到**本 executor 的 repo workspace canonical entry** 從兩個 fresh read 重新開始；Codex 通常是 `/workspace/whd`，不得因這個 recovery 去尋找或等待 `/Google Drive/WHD`。

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

這些 read-only baseline actions 不需要額外 `/推推` authority，也不得因缺少 chat/AI Library/Drive capability回 `REMOTE_CONNECTION_DENIED`。

對 Codex / executor-local workspace，若使用者已明確要求本次 exact repository-content task，該 user authorization 可在 tested exact diff 準備完成時 mint 一次 `WHD_REMOTE_CONNECTION_AUTHORITY_V1(kind=WORKSPACE_DELIVERY)`，供**同 invocation + 同 repository + 同 task scope** 的 delivery branch / push / PR / CI / merge / readback 使用；不得到 push/PR 階段再要求使用者重複同一授權。scope 擴張、換 repository 或要求額外 remote action 才需新 authorization。

Git write 仍受限：
- 禁止 direct push `cleanup/2d-3d-sync`；
- 修改與測試先在 executor workspace；
- 測試 GREEN + exact diff 後，只能建立 delivery branch、push、PR、跑 required checks；
- target drift 時**先做 GREEN reuse revalidation，不得直接重跑測試**；只有 candidate/head、test profile/contract、exact test commands、touched path 或 dependency impact 任一改變，才 refresh workspace baseline + retest。

### 1.1.1 GREEN_REUSE_FAST_PATH_V1

已有 GREEN 的 candidate 遇到 production target drift 時，固定先做 cheap revalidation：

`FRESH_TARGET_COMPARE → CANDIDATE_IDENTITY_CHECK → IMPACT_CHECK → REUSE_GREEN | RETEST_REQUIRED`

`REUSE_GREEN` 必須同時成立：
- candidate diff digest 與 candidate head 未變；
- prior result 確實為 GREEN；
- exact test commands、test profile、test contract 未變；
- fresh target changed paths 與 candidate touched paths 不重疊；
- fresh impact analysis 證明沒有 dependency impact。

符合時直接沿用舊 GREEN，**禁止為了 refresh timestamp / target SHA 再跑一次測試或 CI**。若 branch protection 要求新 SHA 上同名 required context，必須由 lightweight reuse classifier 產生 `GREEN_REUSED_NO_RETEST` 並讓同名 required check 成功；不得用重跑 full regression 來刷新 status。缺 evidence 時先補 compare/identity/impact revalidation；只有 revalidation 證明有影響或 identity 改變才進 `RETEST_REQUIRED`。

machine owner=`tools/root_local_first_gate.py::classify_target_drift_action`；schema=`WHD_GREEN_REUSE_REVALIDATION_V1`。

### 1.2 Drive mirror/data boundary

Google Drive 已退出 repository-content execution routing。Drive 只允許保存資料、artifact、backup 與 production mirror；不得作為 CURRENT Skill/contract、施工 root、workspace、shared-zero fallback 或 blocker authority。

固定 machine rule：

- `shared_zero_drift_present=false → WORKSPACE_DEFAULT`
- `shared_zero_drift_present=true → WORKSPACE_DEFAULT`（舊 shared-zero evidence 只可記錄為 retired/historical drift，不得改變 route）
- Drive mount / mirror / pointer 不可見 → `CONTINUE_WORKSPACE_DEFAULT`
- executor-local repo workspace 不存在或不可執行測試 → `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME`

### 1.3 Authority boundary

executor-local workspace 是 execution surface；共同 CURRENT process/content baseline authority 是 GitHub `cleanup/2d-3d-sync`。Drive mirror 永遠沒有 routing、startup、workspace 或 overlay authority。Skill 自動觸發只會選 workspace route，不會授權非-baseline GitHub/remote action；未授權動作仍 `REMOTE_CONNECTION_DENIED`。

## 2. Retired shared-zero history

舊 `.unpushed/docs/0`、`.unpushed/body/0`、shared-zero generation/freeze、Drive canonical root、`/推推` 專屬 shared-zero delivery 與 `DIRECT_ROOT_MUTATION_TEST_HARD_GATE_V1` 全部屬 **HISTORICAL / SUPERSEDED**。它們可存在於 Git 歷史或備份資料，但不得被 CURRENT router、Skill、contract、scheduler、工作槽或 executor 啟動。

CURRENT 唯一路徑：

`production X → executor-local workspace → edit/test → exact tested delivery branch → PR/checks → production X`

## 8. Anti-regrowth

CURRENT 文件/Skill/contract 不得再宣告：

- `/work/active` 是 repository-content authority；
- `source/manifests` 或 ZIP snapshot 是 current root authority；
- root write 前必須 single-writer `PATHS_RESERVED`；
- 建 branch 後才開始修改/測試；
- 把 Drive mirror、Drive Skill、`.unpushed` 或 shared-zero 當 production baseline / CURRENT authority；
- 要求先解析 `/Google Drive/WHD` parent-chain 才能開始施工；
- conflict 可自動 ours/theirs。
- 讓任何 Drive mirror/pointer 自稱 `whd_doc_role: CURRENT`；
- 因 Drive mount、Drive mirror、`.unpushed` 或 shared-zero 不可見而回 blocker、要求重新指定施工 root。

舊文字如需保留，只能明確標 `HISTORICAL/SUPERSEDED`，不得參與 routing。


## Compatibility / delivery invariants

- Git write mode remains `EXACT_TESTED_DIFF_ONLY`.
- `INTERACTIVE_ORCHESTRATION_FAST_PATH_HARD_GATE_V1` remains CURRENT; control-plane internals **不得由聊天層逐顆手動編排**.
- Repository-content fixes must never be a GitHub-side hotfix; mutate/test in the executor-local workspace first.
- Delivery still requires `DELIVERY_RESERVATION` after the exact tested diff is frozen.
- production target 的 ref advancement 一律交回 Flow v2 trusted `MERGE` / `SYNC_TARGET`；chat/runtime connector 不得直接前推 production target。
- `ROOT_SYNC_MAINTENANCE_NON_BLOCKING_V1` is retained as a compatibility label only: Drive/root sync is non-blocking maintenance and no longer nominates Drive as a construction root.

## Machine owners

- entry/router + workspace delivery gate: `tools/root_local_first_gate.py`
- test profile: `WHD_CHANGE_TEST_PROFILE_V1` / `tools/change_test_profile.py`
- legacy shared-zero helpers may remain only for historical data/recovery parsing and MUST NOT participate in CURRENT routing.

## 9. POST_INTEGRATION_DURABILITY_V2

Flow v2 `FINALIZE → DONE` 加上 trusted GitHub merge/Issue readback就是 terminal authority；**不得再以 canonical Drive root sync/recovery receipt 阻塞已完成 Issue closure**。

repository-content cleanup 固定：

`MERGE_READBACK_VERIFIED → LANE_DELIVERY_RECEIPT_BOUND → FINALIZE_DELIVERED_LANE_ZERO → DURABLE_CLEANUP_COMPLETE`

### DRIVE_MIRROR_NON_AUTHORITY_V1

- `/Google Drive/WHD/WHD_MIRROR/CURRENT` 是 backup/mirror storage，不是 repo workspace、CURRENT Skill source 或 closure authority。
- mirror 缺失、延遲、損壞或 mount 不可見，不得阻塞 workspace execution、FINALIZE、Issue close、scheduler return 或 #1279 類產品施工。
- GitHub 暫時不可用時可用 mirror 作 recovery material，但不得把 Drive 自動升格成 production authority；恢復後必須 reconcile 到 production X。

### TEST_RECEIPT_AND_CONNECTOR_REJECTION_HARD_GATE_V2

`POST_MERGE_0_TESTS_GREEN` 不接受裸 `tests_green=true`；必須攜帶 `WHD_TEST_EXECUTION_RECEIPT_V1`，並 exact 綁定 manifest digest 與 exact commands。

單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接宣告 permanent blocker。fresh-read authenticated permission、target/base existence、branch protection/ruleset 與 connector action contract 後再分類。delivery branch 只使用 `create_branch(base_sha)`；`update_ref` 只允許 non-authoritative delivery/recovery branch 且 `force=false`，不得直接前推 main/production target。只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可標 permanent capability blocker。

Pre-write reservation 已退役；workspace authoring 不取得 path reservation。只有 exact tested diff 的 delivery phase 才允許 reservation。

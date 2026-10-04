---
name: 推推
description: WHD shared-0 fallback 的 interactive Git delivery 出口。普通 executor-local workspace flow 直接走 tested delivery branch + PR/checks，不需要 `/推推`；只有 fresh Drive/shared-0 drift 啟動 fallback 時才使用 `/推推 文檔|主體`。
whd_doc_role: CURRENT
whd_contract: shared-unpushed-integration
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推

`/推推` 只負責 **shared-0 fallback lane** 的 Git delivery。普通 workspace-first 施工不經 `/推推`。

## 0. WORKSPACE_DEFAULT_AND_SHARED_ZERO_FALLBACK_V1

普通 repository-content 預設路徑：

`cleanup/2d-3d-sync → executor-local repo workspace → edit/test → tested delivery branch → PR/checks → cleanup/2d-3d-sync`

每個 executor 使用自己的 workspace。GitHub `cleanup/2d-3d-sync` 是共同 production baseline；普通 startup 可直接做 `READ / FETCH / COMPARE / BRANCH_READ / REPO_METADATA_READ`，不需要 `/推推`、Drive generation、shared-0 manifest 或 `workspace_canonical_sync.py`。

只有 fresh evidence 證明 touched paths 存在 GitHub/workspace 沒有的 `/Google Drive/WHD/.unpushed/{docs|body}/0` drift，才切入 `SHARED_ZERO_FALLBACK`。這時才使用本 Skill、selected lane freeze、fileset lock、Drive readback 與 `CANONICAL_SHARED_0_UPDATED`。

普通 WORKSPACE_DEFAULT 的 Git write 仍禁止 direct push production target；只能把 exact tested diff 推到 delivery branch，跑 required checks，再 merge。
## 1. 指令

只接受：

- `/推推 文檔`
- `/推推 主體`

`文檔` 對應 `.unpushed/docs/0`；`主體` 對應 `.unpushed/body/0`。

`/推推` 本身就是本次 GitHub delivery 的明確使用者授權；authority 僅限 selected lane、frozen manifest 與這一輪 delivery/readback，完成或失敗退出後立即失效。

## 2. 分類原則

分類看歸屬，不看副檔名：

- 治理、Skill、`AGENTS.md`、流程 authority、Registry、SOP、治理 contract、治理 tests → `文檔`。
- 產品程式、產品 tests、UI、renderer、geometry、manufacturing → `主體`。
- **主體必要的文件屬於主體**：若文件不跟產品改動一起交付會造成產品不完整、不可驗收、契約不一致，該文件進 `主體`。

machine owner：`tools/shared_unpushed_integration.py::classify_lane`。

## 3. 0 是唯一未推送 authority

同一 lane 只允許一份 authoritative `0`：

```text
.unpushed/docs/0
.unpushed/body/0
```

worker 可以有自己的暫存修改，但 authority 永遠是最新 `0`。**`0` 允許作為修改基準**；後來者要修改已存在於 `0` 的 path，必須以最新 `0` 的 `generation + hash` 為 base，不得回 root 舊版本、GitHub mirror 或遠端副本施工。

worker 完成後固定做三方合併：

```text
worker 起始 base
+ worker delta
+ fresh latest 0
→ merge candidate
```

merge 前必須逐 path fresh-read latest `0` 的 generation/hash；只要任一 path 自 worker base 後已變更，就重新 merge/reconcile，不得拿舊 candidate 直接覆蓋。merge 成功後才允許 generation + 1。

## 4. MERGE_CONFLICT_USER_DECISION_HARD_GATE_V1

只要 worker → 最新 0 發生任何 merge conflict：

1. **禁止自動 resolve**；
2. **禁止自行選 ours / theirs**；
3. **禁止自行推論使用者要哪一邊**；
4. 立即寫入 `WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1`；
5. checkpoint 必須記錄 lane、path、base/latest generation、base/latest/worker hash、每個 conflict point、worker/issue；
6. state 固定：`BLOCKED_USER_DECISION`；
7. 明確通知使用者衝突位置與兩邊差異；
8. 在取得 `EXPLICIT_USER_CONFLICT_DECISION` 前，禁止 merge 回 0、advance generation、改寫 conflict、create delivery branch、`/推推`、任何 Git push/PR。

machine owner：`tools/shared_unpushed_integration.py::build_conflict_checkpoint` 與 `assert_conflict_checkpoint_blocks_action`。

## 5. DELIVERY_FILESET_LOCK_HARD_GATE_V1

selected lane 通過 post-merge tests 後，先 freeze manifest，再建立不可變的 delivery fileset lock：

- exact lane + generation；
- exact write/delete path set；
- 每一 path 的 exact content hash / delete marker；
- manifest digest；
- source `0` identity；
- 本次 delivery invocation identity。

從 `DELIVERY_FILESET_LOCKED` 起到 `MERGE_READBACK_VERIFIED` 前，stage/commit/push/PR changed filenames **必須 exact 等於 lock**。新增、遺漏、hash 漂移、跨 lane 夾帶都 fail closed，回 root/shared-0 重做，不得在 delivery branch 補修。

## 6. /推推 文檔 hard gates

固定順序：

```text
DOCS_0_EXISTS
→ DOCS_0_NO_UNRESOLVED_WORKER
→ DOCS_0_NO_CONFLICT_CHECKPOINT
→ DOCS_0_POST_MERGE_TEST_GREEN
→ DOCS_0_MANIFEST_FROZEN
→ DELIVERY_FILESET_LOCKED
→ PUSH_SCOPE_MUST_EQUAL_LOCK
→ FRESH_TARGET_HEAD
→ DELIVERY_RESERVATION
→ GIT_WRITE_UNLOCKED
→ CREATE_DELIVERY_BRANCH
→ EXACT_LOCKED_FILESET_APPLY
→ POST_PUSH_CI
→ PRE_MERGE_LATEST_FILE_RECHECK
→ MERGE
→ MERGE_READBACK_VERIFIED
→ FINALIZE_DELIVERED_PATHS
```

任一步不成立，不得進下一步。

## 7. /推推 主體 hard gates

固定順序：

```text
BODY_0_EXISTS
→ BODY_0_NO_UNRESOLVED_WORKER
→ BODY_0_NO_CONFLICT_CHECKPOINT
→ BODY_0_POST_MERGE_TEST_GREEN
→ BODY_0_MANIFEST_FROZEN
→ DELIVERY_FILESET_LOCKED
→ PUSH_SCOPE_MUST_EQUAL_LOCK
→ FRESH_TARGET_HEAD
→ DELIVERY_RESERVATION
→ GIT_WRITE_UNLOCKED
→ CREATE_DELIVERY_BRANCH
→ EXACT_LOCKED_FILESET_APPLY
→ POST_PUSH_CI
→ PRE_MERGE_LATEST_FILE_RECHECK
→ MERGE
→ MERGE_READBACK_VERIFIED
→ FINALIZE_DELIVERED_PATHS
```

主體 lane 的測試 profile 必須由 `tools/change_test_profile.py` 決定；GitHub Actions 只做 post-push verification，不是第一測試面。

## 8. PRE_MERGE_LATEST_FILE_RECHECK_HARD_GATE_V1

真正 merge 前必須再次確認「要合併的就是目前最新檔」：

1. fresh-read live target HEAD；
2. fresh-read PR/delivery head；
3. 驗 changed filenames exact 等於 fileset lock；
4. 對每個 locked path 驗 delivery blob/hash 仍等於 frozen manifest；
5. 驗 target 自 `FRESH_TARGET_HEAD` 後是否改到任一 locked path。

若 target 只前進但未碰 locked paths，可依 CURRENT target-sync/rebase 規則重建 candidate 後重新驗；若碰到 locked path，必須回 root/shared-0 以 fresh latest 做 reconcile/test/freeze，禁止直接 merge stale file。

## 9. Scope isolation

`/推推 文檔` 只能 stage / commit / push docs lane lock 裡的 paths；`/推推 主體` 只能處理 body lane lock。

任何額外 path 都必須 fail closed：`PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_LOCK`。

## 9.4 CONDITIONAL_SHARED_ZERO_RECONCILE_V1

`tools/workspace_canonical_sync.py` 保留為 CURRENT fallback/reconcile machine，**不是普通 startup hard path**。

只有 route machine fresh 判定：`FRESH_SHARED_ZERO_DRIFT_ON_TOUCHED_PATHS=true` 才啟動：

`Drive/shared-0 → executor workspace reconcile → edit/test → outbound relay → Drive readback → CANONICAL_SHARED_0_UPDATED → /推推`

普通 WORKSPACE_DEFAULT：
- 不要求 Drive mount；
- 不要求 `sync-in/status/prepare-outbound/verify-outbound`；
- 不要求 canonical generation/manifest；
- 不要求 `CANONICAL_SHARED_0_UPDATED`；
- 直接使用各 executor 自己的 repo workspace + fresh `cleanup/2d-3d-sync` baseline。

Codex 的 `/workspace/whd` 只是 Codex 自己的 workspace 實例；ChatGPT 與其他 executor 使用各自 runtime workspace，不得硬編單一共享實體目錄。

shared-0 fallback active 時，workspace dirty paths 不得被 sync silent overwrite；同 path drift 固定 `WORKSPACE_CANONICAL_RECONCILE_REQUIRED`。

machine invariant：`WORKSPACE_CANONICAL_SYNC_IS_CONDITIONAL_FALLBACK_NOT_DEFAULT_STARTUP`。
## 9.5 WORKSPACE_STAGED_GIT_DELIVERY_FALLBACK_V1

當 selected lane 已 `FROZEN`、fileset lock 已建立，而且來源 connector 不能直接作為 Git content-write 輸入時，允許使用 **workspace-staged relay** 作為同一 delivery window 內的相容 transport。這不是新的 authority，也不能改變 lock。

固定規則：

1. 只把 frozen manifest 的 exact write paths materialize 到本 invocation 的工作區；workspace 只是 staging surface，不是 canonical authority。
2. materialize 後逐檔重新計算 hash，必須 exact 等於 frozen manifest；任一不符立即 fail closed。
3. 建立一個 deterministic frozen bundle（建議 `tar.xz`），至少包含 payload + manifest；bundle 只作 transport capsule / audit evidence，**不得把 bundle 檔本身提交進 repository 取代 locked paths**。
4. Git object 建立只能使用已通過 hash readback 的 workspace bytes；若 connector 需要文字 relay，可由同一 workspace 產生 temporary encoded relay，再建立 exact Git blobs。relay 不得改內容、不得新增 path、不得跨 lane。
5. Git tree 必須展開成原本 fileset lock 的 exact write/delete paths；changed filenames 仍必須 exact 等於 lock。
6. bundle / temporary relay 都不是 repository content；delivery terminal 後應移出 active scope或清除。
7. 若 direct transport 恢復，兩條 transport 的產物仍必須由同一 frozen manifest/hash 驗證；不得因 transport 差異跳過 CI、pre-merge recheck、Issue sync、Flow v2 DONE 或 lane cleanup。

machine invariant：`WORKSPACE_STAGED_RELAY_DOES_NOT_CHANGE_DELIVERY_AUTHORITY_OR_FILESET`。

## 10. ISSUE_SYNC_ON_SPLIT_AND_DELIVERY_HARD_GATE_V1 — 推推後半邊

`/推推 文檔|主體` 在 `MERGE_READBACK_VERIFIED` 後還不能直接宣告整個 delivery cycle 完成。必須先把交付結果同步回本次 manifest/Flow v2 關聯的 GitHub Issue，再由 Flow v2 自己 drain terminal tail：

`MERGE_READBACK_VERIFIED → DELIVERY_RECEIPT_BOUND → SYNC_LINKED_GITHUB_ISSUES → ISSUE_SYNC_READBACK_VERIFIED → FLOW_V2_FINALIZE → FLOW_V2_DONE`

同步至少包含：lane、generation、manifest digest、PR、accepted/merged SHA、post-push test/CI 結果，以及 **terminal state 或 exact remaining next_action/blocker**。

- merge/readback 或 Issue sync **都不等於 Flow v2 terminal**。若工單已符合 terminal acceptance，close 只由 canonical `FINALIZE` 執行並 fresh readback成 `state=DONE`；`/推推` 不自行創造第二套 closure authority。
- 若尚未 terminal，Issue 必須保持 open，並把 exact next action/blocker 同步回去；不能因 push/merge 成功就假裝工單完成，也不能提前清 selected shared-0。
- carried-forward Issues 也必須 reconcile GitHub open/closed 狀態與 lane provenance，禁止只留 stale `carried_forward_issues` 數字。
- remote authority 固定 `POST_DELIVERY_ISSUE_SYNC`，只允許 Issue update/comment/relation/readback；不能用它擴張 repository-content scope。
- Issue sync/readback 失敗時，delivery content merge 可保留 VERIFIED，但 physical cycle 狀態固定 `ISSUE_SYNC_PENDING`，不得把整輪視為 durable cleanup complete。

## 11. POST_INTEGRATION_DURABILITY_V2 — DONE 後才清 selected lane

`MERGE_READBACK_VERIFIED` 只證明 Git delivery 成功；selected `0` 的 durable cleanup 還必須服從 CURRENT `WHD_POST_INTEGRATION_DURABILITY_V2`。

固定順序：

`FLOW_V2_DONE → MERGE_READBACK_VERIFIED → LANE_DELIVERY_RECEIPT_BOUND → FINALIZE_DELIVERED_LANE_ZERO → DURABLE_CLEANUP_COMPLETE`

固定規則：

- **Flow v2 尚未 DONE 時不得把 selected lane 視為 cleanup complete**；先續 exact `next_action` 到 canonical FINALIZE/DONE。
- DONE 後，對本次 delivered generation 綁定 `WHD_UNPUSHED_LANE_DELIVERY_RECEIPT_V1`；receipt 必須 exact 綁 issue、lane、generation、manifest digest、merged SHA、delivered paths 與 cleanup 後 lane state。
- 只清除本次 lock 中且 readback 已證明交付成功的 paths；未推送、後來新增、hash 已不同、其他 worker 正在修改的 paths 必須保留並形成 `ROLLED_FORWARD`，否則 lane state 為 `EMPTY`。
- `FINALIZE_DELIVERED_LANE_ZERO` 成功後才能宣告 `DURABLE_CLEANUP_COMPLETE`。
- 若同一檔之後要再修改，必須重新從當下 canonical root/latest `0` 登記成新的未推送修改；舊 receipt 只作歷史證據，不得讓舊內容自動再推。

這裡的「清除」是清掉已交付的未推送修改狀態，不是刪除 repository 實體檔案。

### 11.1 ROOT_SYNC_MAINTENANCE_NON_BLOCKING_V1

canonical root sync / recovery **不是** `/推推` terminal gate，也不是 Issue closure authority。

- 缺少 `WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1` 或 `WHD_WORK_ROOT_RECOVERY_RECEIPT_V1`，不得阻擋 Flow v2 `FINALIZE → DONE`、Issue close/readback、scheduler cycle return，亦不得阻擋 `FINALIZE_DELIVERED_LANE_ZERO → DURABLE_CLEANUP_COMPLETE`。
- 有 root-capable runtime 時可依 CURRENT transport 做 optional maintenance；成功 receipt 只證明 root catch-up。
- 沒有 root-capable runtime、receipt 缺失或 receipt invalid 時，只記 `ROOT_SYNC_MAINTENANCE_DRIFT` / non-blocking maintenance evidence；**不得因此保持 Issue OPEN、撤銷 DONE、或重開已完成 delivery**。

## 12. Branch timing

正常施工階段不開 Git branch，也不連 GitHub/遠端本機做 repository-content discovery。

只有 selected lane 已 GREEN、manifest frozen、fileset locked，且使用者已下 `/推推 文檔|主體`，才可開啟本次 GitHub delivery window。delivery 完成/失敗退出後 remote authority 立即關閉。

Flow v2 path reservation 在此只屬 delivery phase；root/shared-0 施工階段禁止用 reservation 當 pre-write gate。Git branch 是 delivery transport，不是工作區 authority。

---
name: 推推
description: WHD shared-unpushed integration 的唯一 interactive Git delivery 出口。只允許 `/推推 文檔` 或 `/推推 主體`；delivery 前鎖定 exact 檔案集合與 hash，merge 前重新驗最新檔；merge 後先同步 Issue/Flow v2，只有 Flow v2 DONE 才進 selected lane durable cleanup。root sync/recovery 只屬 optional maintenance，不得阻塞 terminal closure。
whd_doc_role: CURRENT
whd_contract: shared-unpushed-integration
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推

`/推推` 是 WHD 新流程中唯一允許把 canonical root 內「未推送整合 0」送進 Git/GitHub 的 delivery Skill。

## 0. ROOT_FIRST_AND_REMOTE_DENY_DEFAULT_HARD_GATE_V1

任何 repository-content 的找檔、baseline、比對、修改、測試與 shared-0 合併，**一律先從 canonical root `/Google Drive/WHD` 開始**。

本節 remote-deny 只約束 **interactive/default repository-content discovery / authoring / delivery**；不得拿本節去撤銷 Flow v2、scheduler、trusted Preflight、Issue create/readback、post-delivery Issue sync 等 control-plane 自己已由 CURRENT contract 授權的遠端能力。反過來，這些 control-plane authority 也不得被拿來取代 canonical root 施工面。

對 interactive/default repository-content 而言，未取得下列任一明確 authority 前，禁止把 GitHub checkout/mirror、Remote Desktop、遠端本機或其他遠端內容來源升格為 repository-content baseline / authoring surface：

1. 使用者明確要求「開工單」：只授權 issue create/readback 所需 GitHub 連線，不授權 repository-content 讀寫；
2. 使用者明確下達遠端 repository-content 操作指示；
3. 使用者下達 `/推推 文檔` 或 `/推推 主體`：只授權本次 selected lane 的 Git delivery window。

一般 interactive 任務、Skill 自動觸發、想確認「GitHub 是否更新」、或 root 找不到檔案，**都不是 repository-content remote authority**。不得先從 GitHub 找同名檔再回 root，也不得用 remote copy 取代 root baseline。trusted Preflight / scheduler bootstrap / Flow v2 control-plane 是否可讀 GitHub，完全依各自 CURRENT contract 判定，不由本節額外阻擋或放寬。

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

## 4.5 SHARED_ZERO_FREEZE_REQUIRES_WORKER_CENSUS_HARD_GATE_V1

任何 docs/body lane 要進入 `FROZEN` 前，必須 fresh census 該 lane 的全部 worker candidates；freeze 是**所有目前合法可合併工作已收斂後的批次邊界**，不是先凍結一部分、再把其他 GREEN candidate 留到下一輪。

固定規則：

1. fresh-list `.unpushed/{lane}/workers/**`，逐一分類為 `MERGED_TO_0 | HISTORICAL_SUPERSEDED | CONFLICT_BLOCKED | NOT_GREEN | ACTIVE_DELEGATED | MERGEABLE_GREEN`；
2. 任一 `MERGEABLE_GREEN` 存在時，禁止 `LANE_MANIFEST_FROZEN`、禁止建立 delivery lock、禁止 `/推推`；必須先以 fresh latest `0` 做 reconcile/merge；
3. 多個互不衝突且已 GREEN 的 candidates 必須合併進**同一個下一代 0**，再對 union fileset 跑 post-merge tests；
4. 只有 census 證明 `MERGEABLE_GREEN=0` 且最新 `0` post-merge GREEN，才允許一次 freeze 完整 manifest；
5. 若 post-push CI 發現需要 repository-content 修改，該 frozen generation 視為 delivery attempt failed：回 canonical root/shared-0 修完整、重新 census/merge/test/refreeze；**禁止在 delivery branch 做 incremental remote repair**；
6. `FROZEN` 後新出現的合法 candidate 不得偷塞進既有 lock；若使用者要求「一起推」，必須回 shared-0 生成新的完整 generation，再以新 lock 整批 delivery。

這個 gate 的目的就是保證：**先全部併 → 全部測 → freeze 一次 → 推一次**。

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
→ DELIVERY_RECEIPT_BOUND
→ SYNC_LINKED_GITHUB_ISSUES
→ ISSUE_SYNC_READBACK_VERIFIED
→ FLOW_V2_DONE
→ LANE_DELIVERY_RECEIPT_BOUND
→ FINALIZE_DELIVERED_LANE_ZERO
→ DURABLE_CLEANUP_COMPLETE
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
→ DELIVERY_RECEIPT_BOUND
→ SYNC_LINKED_GITHUB_ISSUES
→ ISSUE_SYNC_READBACK_VERIFIED
→ FLOW_V2_DONE
→ LANE_DELIVERY_RECEIPT_BOUND
→ FINALIZE_DELIVERED_LANE_ZERO
→ DURABLE_CLEANUP_COMPLETE
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

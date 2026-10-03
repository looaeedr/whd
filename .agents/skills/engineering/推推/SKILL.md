---
name: 推推
description: WHD shared-unpushed integration 的唯一 Git delivery 出口。只允許 `/推推 文檔` 或 `/推推 主體`；delivery 前鎖定 exact 檔案集合與 hash，merge 前重新驗最新檔，完成 readback 後只清除已交付 paths；未收到 `/推推` 或其他使用者明確遠端指示時禁止連 GitHub/遠端本機。
whd_doc_role: CURRENT
whd_contract: shared-unpushed-integration
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推

`/推推` 是 WHD 新流程中唯一允許把 canonical root 內「未推送整合 0」送進 Git/GitHub 的 delivery Skill。

## 0. ROOT_FIRST_AND_REMOTE_DENY_DEFAULT_HARD_GATE_V1

任何 repository-content 的找檔、baseline、比對、修改、測試與 shared-0 合併，**一律先從 canonical root `/Google Drive/WHD` 開始**。

未取得下列任一明確 authority 前，禁止連線 GitHub、Remote Desktop、遠端本機、GitHub checkout/mirror 或其他遠端內容來源：

1. 使用者明確要求「開工單」：只授權 issue create/readback 所需 GitHub 連線，不授權 repository-content 讀寫；
2. 使用者明確下達遠端操作指示；
3. 使用者下達 `/推推 文檔` 或 `/推推 主體`：只授權本次 selected lane 的 Git delivery window。

一般任務、Skill 自動觸發、Preflight、想確認「GitHub 是否更新」、或找不到檔案，**都不是遠端連線 authority**。不得先從 GitHub 找同名檔再回 root，也不得用 remote copy 取代 root baseline。

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

## 10. Push 完成後只清已交付 paths

只有 `MERGE_READBACK_VERIFIED` 證明 production/accepted target 已含 exact locked file hashes 後，才允許 finalize selected `0`。

固定規則：

- 只清除本次 lock 中且 readback 已證明交付成功的 paths；
- 未推送、後來新增、hash 已不同、其他 worker 正在修改的 paths 必須保留；
- 清除後留下 delivery receipt，記錄 delivered generation、manifest digest、path/hash、accepted commit、cleared_at；
- 若同一檔之後要再修改，必須重新從當下 canonical root/latest `0` 登記成新的未推送修改；舊 receipt 只作歷史證據，不得讓舊內容自動再推。

這裡的「清除」是清掉已交付的未推送修改狀態，不是刪除 repository 實體檔案。

## 11. Branch timing

正常施工階段不開 Git branch，也不連 GitHub/遠端本機做 repository-content discovery。

只有 selected lane 已 GREEN、manifest frozen、fileset locked，且使用者已下 `/推推 文檔|主體`，才可開啟本次 GitHub delivery window。delivery 完成/失敗退出後 remote authority 立即關閉。

Flow v2 path reservation 在此只屬 delivery phase；root/shared-0 施工階段禁止用 reservation 當 pre-write gate。Git branch 是 delivery transport，不是工作區 authority。

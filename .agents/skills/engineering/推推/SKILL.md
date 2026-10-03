---
name: 推推
description: WHD shared-unpushed integration 的唯一 Git delivery 出口。只允許 `/推推 文檔` 或 `/推推 主體`，從對應 `.unpushed/{docs|body}/0` manifest 建立 delivery branch；merge conflict 必須 checkpoint 並等待使用者決策，禁止自動選邊。
whd_doc_role: CURRENT
whd_contract: shared-unpushed-integration
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# /推推

`/推推` 是 WHD 新流程中唯一允許把 root 內「未推送整合 0」送進 Git/GitHub 的 delivery Skill。

## 1. 指令

只接受：

- `/推推 文檔`
- `/推推 主體`

`文檔` 對應 `.unpushed/docs/0`；`主體` 對應 `.unpushed/body/0`。

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

worker 可以有自己的暫存修改，但 authority 永遠是最新 `0`。後來者要修改已存在於 `0` 的 path，必須以最新 `0` 的 `generation + hash` 為 base，不得回 root 舊版本施工。

worker 完成後固定做三方合併：

```text
worker 起始 base
+ worker delta
+ fresh latest 0
→ merge candidate
```

merge 成功後才允許 generation + 1。

## 4. MERGE_CONFLICT_USER_DECISION_HARD_GATE_V1

只要 worker → 最新 0 發生任何 merge conflict：

1. **禁止自動 resolve**；
2. **禁止自行選 ours / theirs**；
3. **禁止自行推論使用者要哪一邊**；
4. 立即寫入 `WHD_UNPUSHED_CONFLICT_CHECKPOINT_V1`；
5. checkpoint 必須記錄：
   - lane；
   - path；
   - base_generation / latest_generation；
   - base_hash / latest_hash / worker_hash；
   - 每一個 conflict hunk / semantic conflict point；
   - worker / owning issue；
6. state 固定：`BLOCKED_USER_DECISION`；
7. 明確通知使用者衝突位置與兩邊差異，要求使用者決定；
8. 在取得 **EXPLICIT_USER_CONFLICT_DECISION** 前，禁止：
   - merge 回 0；
   - advance generation；
   - 改寫 conflict hunk；
   - create delivery branch；
   - `/推推`；
   - 任何 Git push / PR。

machine owner：`tools/shared_unpushed_integration.py::build_conflict_checkpoint` 與 `assert_conflict_checkpoint_blocks_action`。

## 5. /推推 文檔 hard gates

固定順序：

```text
DOCS_0_EXISTS
→ DOCS_0_NO_UNRESOLVED_WORKER
→ DOCS_0_NO_CONFLICT_CHECKPOINT
→ DOCS_0_POST_MERGE_TEST_GREEN
→ DOCS_0_MANIFEST_FROZEN
→ PUSH_SCOPE_MUST_EQUAL_MANIFEST
→ FRESH_TARGET_HEAD
→ DELIVERY_RESERVATION
→ GIT_WRITE_UNLOCKED
→ CREATE_DELIVERY_BRANCH
→ EXACT_MANIFEST_APPLY
→ POST_PUSH_CI
→ MERGE_READBACK
```

任一步不成立，不得進下一步。

## 6. /推推 主體 hard gates

固定順序：

```text
BODY_0_EXISTS
→ BODY_0_NO_UNRESOLVED_WORKER
→ BODY_0_NO_CONFLICT_CHECKPOINT
→ BODY_0_POST_MERGE_TEST_GREEN
→ BODY_0_MANIFEST_FROZEN
→ PUSH_SCOPE_MUST_EQUAL_MANIFEST
→ FRESH_TARGET_HEAD
→ DELIVERY_RESERVATION
→ GIT_WRITE_UNLOCKED
→ CREATE_DELIVERY_BRANCH
→ EXACT_MANIFEST_APPLY
→ POST_PUSH_CI
→ MERGE_READBACK
```

主體 lane 的測試 profile 必須由 `tools/change_test_profile.py` 決定；GitHub Actions 仍只是 post-push verification，不是第一測試面。

## 7. Scope isolation

`/推推 文檔` 只能 stage / commit / push docs lane manifest 裡的 paths。

`/推推 主體` 只能 stage / commit / push body lane manifest 裡的 paths。

任何額外 path 都必須 fail closed：

`PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST`

禁止順手夾帶另一 lane 的修改。

## 8. Branch timing

正常施工階段不開 Git branch。

只有 selected lane 已 GREEN、manifest frozen、scope exact match、target fresh-read，且 `DELIVERY_RESERVATION` + `GIT_WRITE_UNLOCKED` 都有 fresh machine evidence 後，`/推推` 才允許建立 delivery branch。

Flow v2 path reservation 在此只屬 delivery phase；root/shared-0 施工階段禁止用 reservation 當 pre-write gate。

Git branch 是 delivery transport，不是工作區 authority。

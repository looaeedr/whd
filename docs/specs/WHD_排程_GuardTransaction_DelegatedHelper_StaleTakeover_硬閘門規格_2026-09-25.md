# WHD 排程 Guard Transaction 與 Delegated/Helper Stale-Takeover 硬閘門規格
日期：2026-09-25  
狀態：Draft for implementation  
Revision: v1.2 — Completion Gate SSOT dedupe + explicit cross-reference  
適用倉庫：`looaeedr/whd`

<!-- ISSUE646_ACCEPTED_IMPLEMENTATION_OVERLAY_2026_09_25 -->
> **Accepted implementation overlay — 2026-09-25**
>
> 本檔保留原始 v1.2 規格正文。以下 overlay 反映 v1.2 發布後已接受的治理修補，若與正文衝突，**只在明列項目上由本 overlay 優先**；其餘 v1.2 規則不變。
>
> 1. **Equivalent duplicate GREEN deterministic dedupe（#651 / PR #652）**：若多張 GREEN 的 mutation-relevant identity（issue / worker / executor / action / branch / base / head / claim blob / guard authority / tested target / changed files）全部 exact-equivalent，視為同一 transaction group，不因張數 >1 自動進 `AMBIGUOUS`。canonical representative = 最早 `issued_at`；同時則最小 `run_id`。shadow receipt 不得獨立 consume/replay。任何 mutation-relevant mismatch 仍 `AMBIGUOUS → FAIL_CLOSED`。此條 narrow-supersede 原文 Section 3.6、Section 7、P-R10 與 Part F 第 6 項中「任何第二張 GREEN 一律失敗」的絕對化敘述。
> 2. **Expired recovery**：`EXPIRED_UNCONSUMED` 舊 receipt 永久不可 consume；fresh-reconcile exact issue/claim/blob/branch/HEAD 且證明 mutation 未發生後，才可 mint 一顆 fresh recovery Guard。若已發生 mutation，必須轉 `MUTATION_DONE_RECONCILE_ONLY`。
> 3. **Interactive runtime liveness（required follow-up）**：`chatgpt_interactive` active owner 必須補與 scheduler 對稱的 machine-readable heartbeat/liveness；heartbeat 只證 runtime liveness，不取代 claim/checkpoint/Guard ownership authority。
> 4. **Exact executor provenance（required follow-up）**：durable evidence 必須能指出 exact source，而不是只寫 generic executor type。interactive 必須保存 **specific conversation/chat identity + invocation identity**；scheduler 必須保存 **scheduler_lane + invocation_identity**。在 machine owner完成前，此條是 required implementation gate，不得假稱 generic `chatgpt_interactive` / `scheduler` 已滿足 provenance。
> 5. **#641 checkpoint fingerprint normalization**：禁止 raw JSON SHA256；只使用 `load_checkpoint(path) → checkpoint_fingerprint(checkpoint)` 或 `authorize-finalization`。事故證據：run `36051135751` FAIL → run `36051265277` GREEN。
>
> Overlay authority evidence：#651 closed/completed、PR #652 merged/accepted；#646 governance writeback commit `d11180dbec0ffa4e1c47c2c57cfb7a9a5a162517`；本 canonical spec publication 由 #646 Guard run `36111311539` 授權。

---


## 1. 目的

本規格同時解決兩類已反覆出現的治理缺口：

1. **Remote Guard 已 GREEN，但 executor 未立即 consume / mutation / readback**
   - 造成數分鐘空窗。
   - 期間可能重複申請 Guard、切換其他工單、只留下 heartbeat，甚至 runtime 結束。
   - 典型案例：#638 implementation Guard GREEN 後，實際 commit 約 8 分鐘後才落盤。

2. **parent 看似 stale，但實際工作正在 helper / proof / delegated child 上進行**
   - 若 stale evaluator 只看 parent durable progress，就可能誤判 parent `EXECUTOR_STUCK`。
   - 之後又建立新的 helper。
   - 下一輪再次只看 parent，造成 helper 重複建立與 takeover loop。
   - 典型鏈：parent #631 → helper/proof #636。

本規格的核心原則：

> **先處理已授權但未完成的 Guard transaction；再沿 structured delegated/helper dependency 找真正 executable leaf；最後才允許 stale/takeover 判定。**

prompt 只負責要求執行順序。  
**stale/takeover 的最終 machine classification 必須仍由 canonical evaluator 決定，不得在 prompt 中另造第二套 stale 演算法。**

---

# Part A — Pending Guard Transaction Hard Gate

## 2. 問題定義

現有 Remote Guard 已有：

- exact issue / worker / executor_source
- branch / base SHA / head SHA
- claim blob SHA
- guard authority SHA
- tested target SHA
- changed-file scope
- `issued_at`
- `expires_at`
- single-use receipt 語意
- post-commit claim reconciliation

但仍缺少一個 machine rule：

> **GREEN receipt 存在且仍有效、且授權 mutation 尚未 durable 完成時，executor 不得做任何其他控制型動作。**

目前這一點主要靠 prompt 約束，因此仍可能發生 executor 拿到 GREEN 後停住。

---

## 3. Canonical Transaction Classification

新增 machine-level classification：

### 3.1 `NONE`

沒有 exact-valid pending GREEN transaction。

允許正常 discovery / dispatch / stale evaluation。

### 3.2 `PENDING`

同時成立：

- `WHD_REMOTE_GUARD_RESULT_V1`
- `result=GREEN`
- receipt identity 與 current owning state exact match
- `current UTC < expires_at`
- 尚無 exact durable mutation readback

此時：

> **唯一合法下一步 = single-use consume → exact mutation → fresh readback**

禁止任何其他 repository-side substantive action。

### 3.3 `MUTATION_DONE_RECONCILE_ONLY`

durable evidence 已證明授權 mutation 已經發生，但 claim/checkpoint metadata 尚未追上。

例如：

- Guard 綁 H0
- commit 已把 live branch 推進 H1
- shared claim 還停在 H0

此時：

- 禁止 replay mutation
- 唯一合法下一步是 canonical reconciliation
- reconciliation 必須使用 fresh exact Guard /既有 narrow recovery contract

### 3.4 `EXPIRED_UNCONSUMED`

- receipt 曾 GREEN
- `now >= expires_at`
- durable readback 無法證明授權 mutation已發生

此時：

- 舊 GREEN 永久不可 consume
- 不得拿舊 receipt 授權 mutation
- fresh-reconcile identity 後才能重新申請 fresh Guard

### 3.5 `CONSUMED`

action-specific durable readback 已證明授權 mutation完成。

receipt 永遠不得再次使用。

### 3.6 `AMBIGUOUS`

例如：

- 同一 owning transaction 出現多張 valid unconsumed GREEN
- branch / claim / receipt identity 無法唯一配對
- changed-file scope 不吻合
- parent/head/blob 無法證明 exact mutation

一律 fail closed。

---

## 4. Transaction Identity

transaction identity 至少包含：

- issue
- worker
- executor_source
- action
- branch
- base_sha
- head_sha
- claim_blob_sha
- guard_authority_sha
- tested_target_sha
- request_comment_id
- guard_run_id
- changed_files
- issued_at
- expires_at

不得僅以 run ID 或 issue number 判定同一 transaction。

---

## 5. Pending Transaction Absolute Hard Gate

新增 canonical machine assertion：

`assert_pending_guard_transaction_clear(...)`

若 classification=`PENDING`，以下全部禁止：

- 新 Guard request
- heartbeat
- scheduler END
- 切換其他 Issue
- stale/takeover evaluation
- helper creation
- dispatch / claim another leaf
- QA dispatch
- workflow dispatch
- PR write
- finalization
- assistant turn exit

固定 machine error：

`PENDING_GUARD_TRANSACTION_NOT_CONSUMED`

錯誤 evidence 必須包含：

- issue
- worker
- guard run ID
- action
- branch/head
- changed files
- issued_at
- expires_at
- required_next_action

---

## 6. Consume Definition

不能只靠 claim metadata 寫：

`"consumed": true`

判定 consumed 必須依 action-specific durable evidence。

### 6.1 commit

要求：

- live branch HEAD 已前進
- new commit parent exact 等於 receipt H0
- commit timestamp 在 receipt validity window
- changed-file set 與 receipt exact match
- 若屬 merge/reconciliation 特例，必須走既有 canonical contract

### 6.2 write

要求：

- exact target durable blob/content 已變更
- mutation scope 與 receipt exact match
- pre/post identity 可追溯

### 6.3 branch-create

要求：

- exact branch 已存在
- initial branch HEAD 與授權 identity 一致

### 6.4 claim-takeover

要求：

- shared claim CAS 已從 previous owner 轉成 exact requesting owner
- takeover evidence exact match receipt

### 6.5 qa-dispatch / workflow-dispatch

要求：

- request 後產生 exact-bound run
- run identity 與 receipt 綁定

### 6.6 pr-write

要求 exact PR durable readback。

---

## 7. Remote Guard 自身必須拒絕第二張 GREEN

trusted Remote Guard workflow 在處理新 request 前，必須先檢查 owning Issue 是否已有 valid pending transaction。

若存在：

`REMOTE_GUARD_REJECTED: PENDING_GUARD_TRANSACTION`

禁止在同一 pending transaction 尚未完成時再 mint 第二張 GREEN。

---

## 8. Turn Exit Gate 整合

`tools/continuity_controller.py::assert_turn_exitable`

必須增加 pending transaction gate。

以下任一狀態都禁止正常 turn exit：

- `PENDING`
- `MUTATION_DONE_RECONCILE_ONLY`
- `EXPIRED_UNCONSUMED`
- `AMBIGUOUS`

其中 `EXPIRED_UNCONSUMED` 必須明確視為未完成 transaction，而不是「receipt 已失效所以可以離場」：

- 舊 GREEN 永久不可 consume；
- 但原本授權的 mutation/next_action 仍未完成；
- machine 必須回 `TURN_EXIT_BLOCKED: EXPIRED_UNCONSUMED_GUARD`；
- exact recovery 固定為：

```text
fresh-reconcile issue / claim / branch / checkpoint identity
→ 確認 durable mutation 尚未發生
→ mint fresh exact Guard
→ consume → mutation → readback
```

若 fresh-read 反而證明 mutation 已經發生，分類必須轉成 `MUTATION_DONE_RECONCILE_ONLY`，禁止 replay。

平台 hard-cut 不得偽造 END。

下一個 invocation 必須 fresh-read durable evidence，繼續 exact pending/recovery transaction。

---

## 9. Stall Warning

可以增加 read-only watchdog evidence：

`WHD_PENDING_GUARD_STALL_V1`

例如 GREEN 後 90 秒仍為 `PENDING` 時記錄：

- issue
- worker
- action
- guard run
- pending_seconds
- expires_at

注意：

- warning 不能讓 receipt 自動失效
- warning 不能 takeover
- warning 不能 mint 新 Guard
- `expires_at` 仍是唯一 expiry authority

---

# Part B — Helper / Delegated Work Must Precede Stale/Takeover

## 10. 問題定義

錯誤循環：

```text
parent 看起來沒動
→ parent 被判 stale
→ takeover
→ 開 helper/proof child
→ helper 正在合法工作
→ 下一輪又只看 parent
→ parent 再次被判 stale
→ 再開一張 helper
→ 重複
```

這種行為錯在：

> stale evaluator 沒有先沿 durable delegated/helper dependency 追到真正 executable leaf。

---

## 11. Absolute Evaluation Order

所有 scheduler / interactive takeover flow，固定順序：

```text
1. Skill / authority fresh-read
2. pending Guard transaction recovery
3. live drift reconciliation
4. structured helper / proof / delegated / blocker traversal
5. exact child/helper live-state readback
6. canonical stale evaluator
7. only then claim-takeover / helper-create
```

任何第 4～5 步尚未完成時：

> **禁止直接對 parent 做 stale / takeover classification。**

---

## 12. Structured Delegated Evidence

parent owning durable state 可透過 canonical structured field 指向：

- helper
- proof issue
- delegated child
- blocker repair
- governance helper
- finalization helper

至少必須能 machine-read：

- parent_issue
- child_issue
- relationship
- helper_key / blocker_key
- child claim path/blob
- child work branch
- child current phase
- child next_action
- optional exact run identity

禁止只靠自由文字 comment 猜 dependency。

---

## 13. Fresh Traverse Rules

在 parent stale classification 前，對所有 exact parent-bound delegated work：

fresh-read：

- child Issue state
- child claim + blob
- child work branch live HEAD
- child claim phase
- child `last_update`
- child `next_action`
- child exact remote run（若存在）
- child checkpoint / closure state（若存在）

---

## 14. `ACTIVE_DELEGATED_WORK`

若 exact parent-bound child/helper 滿足任何有效 active 條件：

- child Issue open
- child claim 為 active phase
- child durable progress fresh
- exact run queued / in_progress / waiting / pending / requested
- child 有尚未完成且合法的 `next_action`
- child checkpoint 尚未 terminal + released

則 canonical evaluator 應回：

`ACTIVE_DELEGATED_WORK`

並：

- `actionable=false`
- 禁止 takeover parent
- 禁止再開同功能 helper
- scheduler 應 resume / observe / continue真正 child leaf

---

## 15. Helper Dedupe — Atomic Reservation / CAS

canonical dedupe key：

`parent_issue + helper_key`

或對 blocker repair：

`parent_issue + blocker_key`

**禁止使用 check-then-create。**

原因：`00/20/40` 與 `B15/B45` 分屬不同 durable lane owner，可能真正並發；若兩條 lane 同時 fresh-read 到「沒有 active helper」，再各自 create helper，仍會產生 duplicate-helper race。

### 15.1 Canonical atomic owner

helper dedupe reservation 必須落在 **parent owning claim** 的 durable structured state 中，沿用既有 `coord/dispatch-claims` authority，不新增第二套 helper registry。

建議 parent claim structured field：

```json
{
  "delegated_work": [
    {
      "relationship": "helper",
      "helper_key": "<canonical-key>",
      "state": "RESERVING|ACTIVE|TERMINAL",
      "reserved_by": "<worker-or-scheduler-lane>",
      "reservation_token": "<exact unique token>",
      "reserved_at": "<UTC>",
      "child_issue": null,
      "child_claim_blob_sha": null
    }
  ]
}
```

欄位名稱可依現有 schema 調整，但 machine invariant 不得改。

### 15.2 Atomic reservation

helper-create 前固定順序：

```text
fresh-read parent claim + blob
→ canonical evaluator 確認沒有既有 ACTIVE/RESERVING same-key helper
→ CAS parent claim：寫入 same-key RESERVING reservation
→ fresh readback reservation exact match
→ only then create helper Issue / claim / branch
→ CAS parent claim：RESERVING → ACTIVE，綁 child_issue / child claim identity
→ fresh readback
```

CAS 必須使用 fresh parent claim blob SHA。

只有成功取得 `RESERVING` 的 executor 才有 helper-create authority。

### 15.3 CAS conflict

若 CAS 失敗：

- 必須 fresh-read parent claim；
- 若 same key 已出現 `RESERVING` 或 `ACTIVE`：
  - 不得 retry create；
  - 必須分類 `ACTIVE_HELPER_ALREADY_RESERVED` 或 `ACTIVE_HELPER_DUPLICATE`;
  - resume / reuse 該 reservation/helper。
- 若是其他無關 drift，依 canonical claim reconciliation 重算。

不得用「CAS 失敗後再查一次沒有 child Issue」作為重新 create 的理由。

### 15.4 Reservation crash recovery

若 owner 在 `RESERVING` 後、helper Issue 建立前死亡：

- reservation 本身仍是 durable authority；
- 其他 lane 不得建立第二個 same-key helper；
- 必須先 resume/recover 該 reservation；
- 只有 canonical recovery 能：
  - 完成原 helper creation，或
  - 在證明沒有 child/helper durable mutation 後，Guard + CAS 清除/重置 reservation。

`RESERVING` 不得僅因時間經過自動視為不存在。

### 15.5 ACTIVE / TERMINAL

若已存在相同 canonical key 的 `ACTIVE` helper：

> **必須 resume / reuse；禁止建立第二張 helper。**

machine failure：

`ACTIVE_HELPER_DUPLICATE`

只有 child 已符合 Section 16 的完整 terminal 定義，parent reservation 才可 CAS 成 `TERMINAL`。

### 15.6 Cross-lane invariant

不同 scheduler lane identity **不是**繞過 dedupe reservation 的許可。

`00/20/40` lane 與 `B15/B45` lane 即使同時執行，也只能有一個 executor成功取得 exact `parent + helper_key` reservation。

helper-create 前仍必須跑 canonical evaluator/helper creation guard；該 guard 必須驗證 reservation ownership/token，而不是只驗「目前沒看到 helper Issue」。

---

## 16. Child Terminal Definition

只有以下全部成立，child 才可視為真正 terminal：

- Issue 已 closed/completed
- claim phase 已 RELEASED / terminal canonical phase
- `next_action=null`
- exact run 無 active state
- checkpoint closure 若適用已完成

若：

- Issue closed 但 claim active
- claim terminal 但 Issue open
- branch/checkpoint/claim drift

都不是「忽略 child 回 parent stale」。

應先做 reconciliation。

---

## 17. Returning to Parent Stale Evaluation

只有當 parent-bound child/helper 已：

`terminal + closed/released`

才回到 parent stale evaluator。

之後 stale 判定仍使用：

`tools/stale_claim_takeover.py`

prompt 不自行算：

- stale seconds
- RUN_LIVE
- EXECUTOR_STUCK
- ORPHANED_SCHEDULER_OWNER
- ACTIVE_DELEGATED_WORK
- helper dedupe

prompt 只規定：

> **先收集 fresh evidence，然後把判定交給 canonical machine evaluator。**

---

# Part C — 00 / 20 / 40 / B15 / B45 Automation Prompt Requirements

## 18. Scope

適用 currently enabled：

- 00
- 20
- 40
- B15
- B45

本規格只修改 prompt 行為。

禁止修改：

- cadence
- schedule minute
- automation ID
- lane owner
- lane identity
- recurring enabled policy

---

## 19. Required Prompt Block

五條 automation prompt 都必須加入下列語意，位置：

> **SKILL FIRST HARD GATE 之後，任何 stale / takeover / helper-create 判定之前。**

建議 canonical prompt block：

```text
【HELPER / DELEGATED BEFORE STALE — ABSOLUTE HARD GATE】

任何 stale / takeover / helper-create 判定之前，必須先 fresh-traverse owning Issue / claim / checkpoint 中 structured helper / proof / delegated / blocker dependency evidence，沿 exact parent binding 找到真正 executable leaf。

對每個 exact parent-bound child/helper，fresh-read：
- Issue state
- exact claim + blob
- work branch live HEAD
- claim phase / last_update / next_action
- checkpoint/closure state（若存在）
- exact remote run state（若存在）

只要 child/helper 仍 active，且 durable progress fresh、exact run active，或仍有合法未完成 next_action，必須以 canonical machine evaluator 判定為 `ACTIVE_DELEGATED_WORK` / non-actionable parent；禁止 takeover parent。

已存在相同 canonical `parent_issue + helper_key` 或 `parent_issue + blocker_key` 的 active helper 時，必須 resume/reuse；禁止建立 duplicate helper。

只有 child/helper 已 terminal 且 Issue closed/completed、claim released/terminal、next_action=null，必要 reconciliation 已完成後，才可回到 parent stale evaluation。

最終 stale/takeover/helper-create 判定一律交給 live canonical `tools/stale_claim_takeover.py`（或 live authority 指定的 successor）。prompt 不自行發明第二套 stale 演算法。

若 live evaluator 尚不能取得或驗證必要 delegated/helper evidence，fail closed：禁止 takeover、禁止 helper-create。
```

---

## 20. 00 / 20 / 40 Specific Rule

00 / 20 / 40 共用 durable lane：

`scheduler.6ab13fa557fc8191935c671214b865e2`

新 hard gate 不改 same-lane mutex。

same-lane flow：

```text
same-lane mutex
→ pending Guard transaction
→ live drift reconciliation
→ delegated/helper traversal
→ stale evaluator
→ takeover if and only if machine actionable
```

禁止因 same-lane entrypoint 不同而略過 helper traversal。

---

## 21. B15 / B45 Specific Rule

B lane owner：

`scheduler.e58ea936e7d0b12bd0d475314709d6f1`

B lane 原有 parallel-claim rule 保留。

額外要求：

- 在評估可安全平行的新 leaf 前，也要先解析 candidate 的 structured delegated/helper chain。
- parent 有 active helper 時，不得因 parent 本身安靜而把它視為「另一張可平行接手的 leaf」。
- duplicate helper 不算平行工作。
- exclusive integration/finalization ownership規則不變。

---

# Part D — Machine Authority

## 22. Canonical Owners

建議 authority ownership：

### stale / delegated helper classification

`tools/stale_claim_takeover.py`

負責：

- ACTIVE_DELEGATED_WORK
- helper dedupe
- parent/child binding validation
- fail-closed delegated evidence parsing
- existing stale classification

### Guard transaction identity / prewrite

`tools/execution_claim_guard.py`

負責：

- pending Guard transaction validation
- second Guard rejection
- post-mutation reconciliation binding
- single-use transaction enforcement

### turn exit / closure

`tools/continuity_controller.py`

負責：

- pending transaction turn-exit blocking
- existing continuity state
- finalization / closure state machine

不得在 automation prompt、Skill 與 workflow 中複製三套不同判斷器。

---

# Part E — RED / GREEN Acceptance

## 23. Delegated/Helper RED Tests

### D-R1
parent stale + active exact-bound helper → `ACTIVE_DELEGATED_WORK`, actionable=false。

### D-R2
parent declared helper 但 fresh child evidence missing → fail closed。

### D-R3
child terminal + closed/released → 不再 block parent stale evaluator。

### D-R4
delegated evidence parent binding mismatch → fail closed。

### D-R5
同 `parent + helper_key` active helper → helper-create rejected `ACTIVE_HELPER_DUPLICATE`。

### D-R6
parent quiet、child exact run active → parent takeover forbidden。

### D-R7
Issue closed 但 child claim active → reconciliation required，不得當 terminal。

### D-R8
active helper stale → evaluator 對 child leaf 判定；不得 takeover parent 另開 helper。

### D-R9
00/20/40 lane 與 B15/B45 lane 同時對同一 `parent + helper_key` 嘗試 create：只有一個 parent-claim CAS reservation 可成功。

### D-R10
losing lane CAS conflict 後 fresh-read 發現 same-key `RESERVING|ACTIVE` → 必須 resume/reuse，禁止 create 第二 helper。

### D-R11
winner 在 `RESERVING` 後死亡、child 尚未建立 → reservation 仍阻止其他 lane duplicate create；必須走 reservation recovery。

### D-R12
只有證明 reservation 無任何 child/helper durable mutation後，才可 Guard + CAS 清除/重置 reservation。

### D-R13
same-key reservation 已 ACTIVE，helper-create guard 未攜 exact reservation token/ownership → machine RED。

---

## 24. Pending Guard RED Tests

### P-R1
valid unconsumed GREEN + new Guard request → RED。

### P-R2
valid unconsumed GREEN + turn exit → RED。

### P-R3
valid unconsumed GREEN + heartbeat → RED。

### P-R4
valid unconsumed GREEN + other Issue discovery/claim → RED。

### P-R5
mutation 已發生、claim 尚未 reconcile → `MUTATION_DONE_RECONCILE_ONLY`。

### P-R6
expired unconsumed GREEN → 舊 receipt 不得 consume。

### P-R7
changed-file mismatch → fail closed。

### P-R8
claim blob / worker / branch / head drift → fail closed。

### P-R9
same receipt replay → RED。

### P-R10
兩張 valid pending GREEN → `AMBIGUOUS` fail closed。

### P-R11
new scheduler invocation 遇到 pending transaction → 必須先 resume transaction。

### P-R12
mutation + readback + reconciliation完成 → `CONSUMED`。

### P-R13
`EXPIRED_UNCONSUMED` + mutation未發生 → `TURN_EXIT_BLOCKED: EXPIRED_UNCONSUMED_GUARD`，只能 fresh-reconcile → fresh Guard recovery。

### P-R14
`EXPIRED_UNCONSUMED` 但 fresh-read 證明 mutation已發生 → 必須轉 `MUTATION_DONE_RECONCILE_ONLY`，禁止 replay。

---

# Part F — Completion Gate

本治理修補只有在以下全部成立才可關單：

1. 00 / 20 / 40 / B15 / B45 prompt 都具有 delegated/helper-before-stale hard gate。
2. cadence / lane / automation identity 完全未變。
3. parent active helper 不再被 stale evaluator直接 takeover。
4. duplicate helper 可被 machine 阻止。
5. parent-bound child evidence缺失時 fail closed。
6. pending GREEN 存在時不能 mint 第二張 Guard。
7. pending GREEN 存在時不能正常 turn exit。
8. mutation 已完成但 metadata drift 時只能 reconcile，不得 replay。
9. expired GREEN 永遠不得 consume。
10. scheduler 下一 wake 能恢復 pending transaction。
11. existing exact-run lock / finalization / same-lane mutex / parallel-claim rules不退化。
12. focused process tests全 GREEN。
13. integration / protected governance tests全 GREEN。
14. clean-up 後 temporary proof workflow 若屬 one-shot 必須移除；permanent governance workflow 不得誤刪。
15. `EXPIRED_UNCONSUMED` 必須明確阻擋 turn exit；不得只靠 generic `next_action != null` 間接推論。
16. helper-create dedupe 必須以 parent claim fresh blob CAS 做 atomic reservation；不得使用 check-then-create。
17. 00/20/40 與 B15/B45 跨 lane 競爭同一 `parent + helper_key` 時，只允許一個 reservation winner。
18. `RESERVING` crash recovery 必須可 resume/recover，且不得因 owner/runtime 消失就自動允許 duplicate helper。

> **SSOT note:** 本 Part F 第 15–18 項是上述四條治理驗收規則的唯一正文 authority。Section 37 只能引用，不得逐字複製；任何後續修改只改本處。

---

# Part G — Implementation Order

建議順序：

1. 完成 #638 現有 helper-aware stale evaluator repair。
2. merge / acceptance / close / release #638。
3. 開新的 governance repair Issue。
4. RED：pending Guard transaction + scheduler prompt contract tests。
5. Implement transaction classifier / guard gate。
6. 接到 turn-exit machine gate。
7. 補 trusted Remote Guard second-request rejection。
8. 更新 00 / 20 / 40 / B15 / B45 prompt。
9. 更新派工 / Remote Guard Skill 與 scheduler usage doc。
10. remote QA。
11. cleanup / drift proof。
12. finalization / close / release。

---

## 25. Non-Goals

本規格 V1 不做：

- 不改排程 cadence。
- 不改 lane identity。
- 不自動 takeover active helper。
- 不以 prompt 取代 `tools/stale_claim_takeover.py`。
- 不讓 stall warning 自動使 Guard 過期。
- 不在 Guard GREEN 後自動執行任意 application code mutation。
- 不新增第二套 durable transaction authority 檔案。

---

## 26. Future V2

若 V1 穩定後仍要徹底消除「GREEN 後 executor 停住」窗口，再另做：

`TRUSTED_REMOTE_MUTATION_EXECUTOR_V1`

只允許 fully deterministic、Guard 前已完整綁定 payload/tree/content 的 mutation，由 trusted workflow 在 GREEN 後直接執行。

V2 不應與本次 helper-aware stale evaluator repair 混在同一張工單。

---

# Part H — Closure / Turn-Exit Machine Hardening

## 27. 根因確認

要避免 WHD 工單反覆死在收尾，不能只靠 scheduler prompt。

目前已知的結構性缺口是：

> `tools/continuity_controller.py::assert_turn_exitable()` 主要依賴 continuity checkpoint 判定是否可離場；若 active claim 已存在但 checkpoint 尚未建立，或 Remote Guard 已 GREEN 但未 consume，turn-exit gate 缺少足夠 durable state 可以阻擋 executor 正常離場。

尤其在 implementation / cleanup / closing 階段，若：

- claim 已 active
- `next_action` 仍不為 null
- Remote Guard 已 GREEN
- branch / PR / production 已有 durable mutation
- checkpoint 尚未建立或尚未更新

只檢查 checkpoint 的 turn-exit gate 會留下 blind spot。

因此本規格新增下列四個 machine-level hard fix。

---

## 28. ACTIVE_CLAIM_REQUIRES_CHECKPOINT

### 28.1 規則

任何 active execution claim 一旦建立，就必須存在 exact-bound continuity checkpoint。

checkpoint 不得等到：

- terminal
- QA 完成
- closing
- finalization

才建立。

claim create / claim takeover / claim resume 成功後，必須在同一 durable transition 中建立或確認 checkpoint。

### 28.2 Identity Binding

checkpoint 至少必須 exact 綁定：

- issue
- worker / owning execution identity
- work branch
- head_sha
- continuity state
- next_action
- master/child linkage（若適用）
- closure_state（若適用）

### 28.3 Hard Failure

若 fresh-read 發現：

```text
claim = active
checkpoint = missing
```

固定 machine failure：

`ACTIVE_CLAIM_REQUIRES_CHECKPOINT`

並禁止：

- normal turn exit
- scheduler END
- stale takeover
- helper-create
- finalization
- claim release

exact recovery：

```text
reconstruct checkpoint from fresh durable authority
→ Guard
→ checkpoint write/readback
→ resume exact next_action
```

不得以「checkpoint 尚未建立」作為正常狀態。

### 28.4 Required Phases

至少以下 active claim phases 都必須有 checkpoint：

- CLAIMED
- RED
- IMPLEMENTING
- GREEN
- REMOTE_QA
- RECOVERING
- CLEANUP
- DRIFT_AUDIT
- CLOSING

若 live authority 增加新的 active phase，必須同步進 machine allowlist。

---

## 29. UNCONSUMED_GREEN_MACHINE_GATE

### 29.1 目的

將原本 prompt-level：

```text
有 valid GREEN 就不得停
```

升格為 canonical machine assertion。

### 29.2 Fresh Evidence

turn-exit 判定前必須 fresh-read owning Issue 上：

- latest relevant `WHD_REMOTE_GUARD_REQUEST_V1`
- matching `WHD_REMOTE_GUARD_RESULT_V1`
- exact request_comment_id
- guard run identity
- current UTC
- current claim/blob
- live branch HEAD
- action-specific durable mutation evidence

### 29.3 Block Condition

若 receipt 同時滿足：

- exact issue match
- exact worker match
- exact executor_source match
- exact branch/base/head match
- exact claim_blob match
- exact guard authority match
- exact tested target match
- `result=GREEN`
- `now < expires_at`
- durable evidence 尚不能證明 consume 完成

則固定：

`TURN_EXIT_BLOCKED: UNCONSUMED_GREEN`

### 29.4 Required Next Action

machine 回傳的唯一 next_action：

```text
consume exact GREEN
→ perform exact authorized mutation
→ fresh readback
→ classify transaction again
```

禁止：

- heartbeat-only
- new Guard
- switch Issue
- stale classification
- helper-create
- scheduler END
- normal return

---

## 30. DURABLE_MUTATION_RECONCILIATION_GATE

### 30.1 問題

有些情況 Guard GREEN 後，mutation 其實已完成，例如：

- branch HEAD 已前進
- PR 已 merge
- production target 已前進
- workflow 已刪除
- Issue 已 close
- claim ownership 已 CAS

但 claim / checkpoint 還停在舊 state。

此時不能：

- replay mutation
- 把舊 GREEN 再 consume 一次
- 正常 return
- 直接 finalization

### 30.2 Classification

固定 machine classification：

`DURABLE_MUTATION_ALREADY_HAPPENED`

turn-exit 固定拒絕：

`TURN_EXIT_BLOCKED: DURABLE_MUTATION_ALREADY_HAPPENED`

### 30.3 Forced Next Action

exact next_action：

```text
reconcile claim
→ reconcile checkpoint
→ fresh readback
→ continue current closure state machine
```

如果 current durable state 已進 closing，則：

```text
reconcile
→ establish/update terminal checkpoint
→ ISSUE_CLOSE_PENDING
→ finalization proof
→ Issue close/readback
→ RELEASE_HANDOFF_PENDING
→ atomic CLOSED + RELEASED
```

### 30.4 Replay Protection

若 durable mutation evidence 已成立：

- old commit Guard 永久不得 replay
- old merge Guard 永久不得 replay
- old issue-close action 永久不得 replay

machine 必須辨識：

`mutation already happened; metadata is stale`

而不是：

`mutation still pending`

---

## 31. TRUSTED_REMOTE_TURN_EXIT_EXECUTOR_V1

### 31.1 目的

scheduler / automation runtime 若沒有 shell 或不能直接執行 canonical Python gate，不得再自行文字判斷：

> 「我認為現在可以結束」

建立 trusted workflow：

`.github/workflows/whd-turn-exit-gate.yml`

作為 Remote Turn-Exit Executor。

### 31.2 Inputs / Fresh Reads

trusted workflow 必須 fresh-read：

- owning Issue state
- claim + exact blob SHA
- continuity checkpoint + exact blob/fingerprint
- work branch live HEAD
- production target live HEAD（若 closure/integration relevant）
- relevant PR state / merge SHA
- latest relevant Guard request/receipt
- exact remote QA run（若 claim 綁定）
- delegated/helper state（若存在）
- closure state
- current UTC

### 31.3 Canonical Execution

workflow 必須真正執行 canonical machine logic，例如：

- `tools/continuity_controller.py`
- pending Guard transaction classifier
- active-claim/checkpoint invariant
- durable mutation reconciliation classifier

不得只用 shell `if` 重寫一套簡化判斷。

### 31.4 Receipt

machine-readable receipt：

`WHD_REMOTE_TURN_EXIT_RESULT_V1`

至少包含：

- issue
- worker / scheduler lane
- invocation_identity
- claim_blob_sha
- checkpoint_blob/fingerprint
- branch
- head_sha
- closure_state
- pending_guard_state
- durable_mutation_state
- delegated_work_state
- result
- reason
- issued_at
- run_id

只有：

`result=TURN_EXIT_PERMITTED`

才准 scheduler 寫：

`WHD_SCHEDULER_RUNTIME_END_V1`

### 31.5 Fail Closed

以下任一情況：

- active claim 無 checkpoint
- valid unconsumed GREEN
- durable mutation 已發生但尚未 reconcile
- active exact run
- executable next_action
- active delegated/helper work
- closure_state != CLOSED（terminal closure flow）
- claim != RELEASED（terminal closure flow）
- identity drift
- receipt ambiguity

都必須：

`TURN_EXIT_DENIED`

不得寫 scheduler END。

---

## 32. Scheduler END Ordering

新的 canonical ordering：

```text
fresh Skill / authority
→ recover pending Guard transaction
→ reconcile live durable mutation drift
→ ensure active claim has checkpoint
→ traverse helper/delegated work
→ execute exact next_action
→ complete closure if terminal
→ claim RELEASED + checkpoint CLOSED
→ trusted Remote Turn-Exit Executor
→ TURN_EXIT_PERMITTED
→ WHD_SCHEDULER_RUNTIME_END_V1
```

`WHD_SCHEDULER_RUNTIME_END_V1` 必須是最後一步，不得早於 machine permission。

---

# Part I — #638 / PR #639 Regression Fixture

## 33. Mandatory Regression Scenario

必須建立與 #638 收尾事故同型的 regression fixture。

fixture 至少包含：

- Issue #638 ownership model
- PR #639 已 merged
- production target 已前進
- closure / merge-related Guard 已 GREEN
- claim 仍寫舊 state，例如：
  - `merged=false`
  - old head / old phase
  - next_action 尚未完成
- continuity checkpoint missing
- Issue 仍未完成 canonical close/release

此 fixture 模擬：

> durable mutation 已經做到約 95%，但 metadata / closure state 尚未追上，而 executor 有機會直接結束。

---

## 34. Expected Old Behavior

測試應明確重現舊版缺口：

```text
PR merged
+ production advanced
+ Guard GREEN
+ stale claim
+ checkpoint missing
→ old checkpoint-only turn-exit path lacks sufficient machine state to block reliably
```

此段是 regression reproduction，不代表接受舊行為。

---

## 35. Expected New Behavior

新版必須：

### Step 1

偵測 active claim + checkpoint missing：

`ACTIVE_CLAIM_REQUIRES_CHECKPOINT`

或在 durable merge 已先被辨識時：

`TURN_EXIT_BLOCKED: DURABLE_MUTATION_ALREADY_HAPPENED`

### Step 2

禁止 replay merge。

### Step 3

強制：

```text
reconcile claim
→ create/reconcile checkpoint
→ fresh readback
```

### Step 4

建立 terminal checkpoint，進入 canonical closure：

```text
FINALIZATION_PENDING
→ ISSUE_CLOSE_PENDING
```

### Step 5

執行 exact finalization proof。

### Step 6

close owning Issue，fresh-read：

```text
closed/completed
```

### Step 7

進：

`RELEASE_HANDOFF_PENDING`

### Step 8

atomic durable closure：

```text
checkpoint = CLOSED
claim = RELEASED
next_action = null
```

### Step 9

執行 trusted Remote Turn-Exit Executor。

只有最後得到：

`TURN_EXIT_PERMITTED`

才可寫 scheduler END。

---

## 36. Regression Assertions

至少新增：

### C-R1
active claim + checkpoint missing → machine FAIL。

### C-R2
active claim phase=CLOSING + checkpoint missing → machine FAIL。

### C-R3
valid GREEN unconsumed → `TURN_EXIT_BLOCKED: UNCONSUMED_GREEN`。

### C-R4
PR merged + production advanced + stale claim → `DURABLE_MUTATION_ALREADY_HAPPENED`。

### C-R5
上述狀態禁止 replay PR merge / production mutation。

### C-R6
reconcile claim 後 checkpoint仍 missing → turn exit仍 denied。

### C-R7
terminal checkpoint建立但 Issue未 close → turn exit denied。

### C-R8
Issue closed但 claim未 RELEASED → turn exit denied。

### C-R9
checkpoint CLOSED但 claim active → turn exit denied。

### C-R10
claim RELEASED但 checkpoint closure != CLOSED → turn exit denied。

### C-R11
CLOSED + RELEASED + no pending Guard + no active run + no delegated work → trusted gate `TURN_EXIT_PERMITTED`。

### C-R12
只有在 C-R11 成立後才能寫 `WHD_SCHEDULER_RUNTIME_END_V1`。

---

# Part J — Revised Completion Gate

## 37. Final Completion Gate

原 Completion Gate 全部保留，並新增以下必要條件：

15. active claim 自 claim-create / takeover 起即具有 exact continuity checkpoint。
16. active claim + missing checkpoint 必須 machine FAIL。
17. valid unconsumed GREEN 必須由 machine turn-exit gate 阻擋，不只靠 prompt。
18. durable mutation 已發生但 claim/checkpoint stale 時，machine 必須強制 reconciliation 並禁止 replay。
19. scheduler 無本機 shell 時必須可透過 trusted Remote Turn-Exit Executor 執行 canonical turn-exit gate。
20. `WHD_SCHEDULER_RUNTIME_END_V1` 只能在 machine receipt=`TURN_EXIT_PERMITTED` 後產生。
21. #638 / PR #639 regression fixture 必須完整跑過：
    - merged/production advanced
    - claim stale
    - checkpoint missing
    - machine block
    - reconcile
    - terminal checkpoint
    - finalization
    - Issue close
    - CLOSED + RELEASED
    - TURN_EXIT_PERMITTED
22. 任何 95% 完成但仍有 closing work 的 state 都不得合法 turn exit。
23. focused process tests、trusted workflow tests、existing closure/finalization regressions全部 GREEN。
24. 00 / 20 / 40 / B15 / B45 的 cadence、lane owner、automation identity 不因本修補改變。
25. 本節不重複定義 Part F 的 governance-specific completion rules；**Part F Completion Gate 第 15–18 項為唯一正文 authority**，Section 37 僅引用其成立結果。
26. 在進入本 Final/Revised Completion Gate 前，必須 fresh-verify Part F 第 15–18 項全部成立；若 Part F 日後修改該組規則，本節自動引用最新版，不得在此另抄一份 divergent copy。

---

## 38. Revised Implementation Order

建議新的完整順序：

1. 完成並關閉 #638 helper-aware stale evaluator repair。
2. 建 governance repair Issue。
3. RED：`ACTIVE_CLAIM_REQUIRES_CHECKPOINT`。
4. RED：`UNCONSUMED_GREEN_MACHINE_GATE` + `EXPIRED_UNCONSUMED` turn-exit block。
5. RED：`DURABLE_MUTATION_RECONCILIATION_GATE`。
6. RED：cross-lane helper reservation race（00/20/40 vs B15/B45）。
7. RED：`RESERVING` owner crash recovery。
8. RED：#638 / PR #639 full closing regression fixture。
9. 實作 parent-claim helper atomic reservation / CAS。
10. 實作 active-claim checkpoint invariant。
11. 實作 pending Guard machine transaction classification。
12. 整合 `assert_turn_exitable()`。
13. 建 `.github/workflows/whd-turn-exit-gate.yml`。
14. 實作 `WHD_REMOTE_TURN_EXIT_RESULT_V1`。
15. 更新 Remote Guard / 派工 / continuity Skills。
16. 更新 00 / 20 / 40 / B15 / B45 prompt 的 delegated/helper-before-stale + machine turn-exit rule。
17. focused RED→GREEN。
18. protected governance regression。
19. remote QA。
20. cleanup / drift audit。
21. finalization / close / release。
22. 最後由 trusted Remote Turn-Exit gate 證明 `TURN_EXIT_PERMITTED`。

---

## 39. Final Invariant

完成後，WHD scheduler 必須滿足：

```text
只要 owning work 還有任何 machine-visible 未完成狀態，
scheduler 就沒有合法 END 路徑。
```

machine-visible 未完成狀態包括但不限於：

- active claim without checkpoint
- valid unconsumed GREEN
- durable mutation pending reconciliation
- active exact remote run
- active helper/delegated work
- executable next_action
- closure_state != CLOSED
- claim != RELEASED
- Issue 未 closed/completed

目標不是再提醒 AI：

> 「不要停。」

而是讓 machine state 直接證明：

> **「你現在根本沒有權限停。」**

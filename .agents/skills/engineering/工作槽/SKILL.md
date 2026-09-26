---
name: 工作槽
description: 當使用者明確輸入 /工作1、/工作2、/工作3 或 /工作槽 時使用；管理 WHD 三個固定 durable work slots 的查詢、指派、續跑、接手、執行位置與 planned handoff routing。裸工作指令只查狀態，不得自動取得 execution authority。
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: work-slot-routing
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 工作槽

本 Skill 只管理「哪一個固定工作槽承載哪一個已授權工作」的 routing / occupancy / provenance。
它不是 Issue 系統、不是 claim owner、不是 checkpoint engine、不是 Scheduler lane，也不建立第二套 takeover / continuity state machine。

## 0. Authority

執行本 Skill 前，依命令類型 fresh-read 既有 canonical authority：

- execution intent / ticket execution：`.agents/skills/engineering/執行開發任務/SKILL.md`。
- ownership / claim / branch / Guard / checkpoint：`.agents/skills/engineering/派工/SKILL.md`。
- stale / takeover：`tools/stale_claim_takeover.py` + live 派工/Guard contract。
- continuity / finalization：`.agents/skills/engineering/executable-continuity-controller/SKILL.md` 與 `issue-closure-gate`。
- `/排程A` / `/排程B` lane：`.agents/skills/engineering/排程模擬/SKILL.md`。
- planned handoff：使用目前 canonical handoff implementation / owning Issue；工作槽本身不冒充 handoff transaction owner。

若本 Skill 與上述 CURRENT authority 衝突，以上述 CURRENT authority 為準。本 Skill 只做 routing bridge。

## 1. WORK_SLOT_FIXED_IDENTITY_V1

固定且唯一的使用者入口：

```text
/工作1 = worker.slot.1
/工作2 = worker.slot.2
/工作3 = worker.slot.3
```

- 三個 `slot_id` 是 durable routing identity，不隨聊天室、runtime、Issue 或 Scheduler invocation 改名。
- 不得動態把 /工作1 重新編號成其他 slot。
- `/工作槽` 是三槽 aggregate/status/admin surface，不是第四個槽。
- slot identity 可長期存在；slot 內承載的 Issue/runtime/location 可以依合法 routing 改變。

## 2. WORK_SLOT_IDENTITY_MODEL_V1

固定 identity invariant：

`slot != issue != claim owner != runtime != execution location`

- `Issue = 工作本體`：要完成的 ticket / requirement。
- `claim = durable ownership`：目前誰合法擁有該 Issue 的施工權。
- `checkpoint = progress / next_action`：目前做到哪、下一個 canonical action 是什麼。
- `work slot = execution capacity / occupancy / routing identity`：固定 `worker.slot.1/2/3`。
- `runtime = 本輪 physical invocation`：實際這一輪 ChatGPT / Scheduler invocation。
- `execution location = LOCAL / SCHEDULER / REMOTE_ACTION`：工作目前依賴哪種 execution surface。

`claim exists != runtime is live`。判斷 runtime 是否仍活著，必須讀 exact liveness / heartbeat / recent substantive durable mutation；不能看到 claim 就宣稱「正在跑」。

`排程 A/B lane != work slot`。工作槽可以被 routed 到 Scheduler A/B，但 lane owner 與 slot_id 永遠是不同 identity。

### 2.1 Durable slot binding

不得新增 `.dispatch/work-slots/**` 或其他第二套 ownership database。

當已授權 execution 真正把 Issue 綁進某槽時，`slot_id` 應作為 provenance 寫入既有 owning claim/checkpoint（依 live schema/Guard 所允許欄位）；slot 查詢從 canonical claim/checkpoint + liveness + location evidence投影。

- legacy claim/checkpoint 沒有 `slot_id` → 顯示 `UNBOUND`，不得猜它屬於工作1/2/3。
- runtime 重開不代表 slot ownership 消失；重新 fresh-read durable claim/checkpoint。
- slot binding 不能取代 claim owner；真正 ownership 仍由派工 claim authority 決定。

## 3. WORK_SLOT_QUERY_ONLY_V1

### 3.1 裸指令預設只查

裸 `/工作1` / `/工作2` / `/工作3` 預設等同 `狀態`。

以下全部是 query-only：

- `/工作1`、`/工作1 狀態`（工作2/3 同義）。
- `/工作槽` / `/工作槽 狀態`：列三槽總覽。
- `/工作槽 空槽`：只列目前沒有 durable binding 的槽。
- `/工作槽 #<issue>`：找該 Issue 是否有 explicit `slot_id` binding，沒有就回 `UNBOUND`。

`query-only 不取得 execution authority`。

query-only 固定禁止：

- 不得建立 execution claim。
- 不得建立 implementation branch。
- 不得 takeover。
- 不得啟動 successor。
- 不得因空槽自動找工單。
- 不得因 open/unblocked Issue 自動塞入工作槽。
- 不得修改 Scheduler enabled/cadence/prompt。

## 4. Execution authority verbs

只有下列明確 execution verb 才能從 query surface 進 execution routing。

以下以工作1表示；工作2/3完全同義。

### 4.1 `/工作1 指派 #<issue>`

- intent = `EXECUTE_TICKET`。
- 只授權指定 Issue + 指定 slot；不允許 discovery unrelated Issue。
- fresh-read slot occupancy、Issue state、active claim、checkpoint、branch、liveness。
- slot 已有非 terminal binding → fail closed，先回目前 occupancy；不得隱式釋放。
- Issue 已有 foreign live owner → 不得搶 claim。
- 合法後交給 `派工` 建立/恢復 canonical claim；`slot_id=worker.slot.1` 只作 provenance。
- 之後沿 normal path `claim → branch → RED → implementation → GREEN → PR/QA → merge → close/release`。

### 4.2 `/工作1 繼續`

- intent = `EXECUTE_TICKET`。
- 必須先找到 `worker.slot.1` 的 explicit durable binding；沒有 binding → fail closed，不自動挑票。
- fresh-read owning claim/checkpoint/branch/liveness，直接 resume exact `next_action`。
- 不因本票 terminal 就自動接 successor；跨 ticket continuation 仍需 `EXECUTE_CHAIN` / `SCHEDULER_LANE` authority。

### 4.3 `/工作1 接手`

- 只對該槽目前 explicit bound Issue 生效。
- 先用 `stale_claim_takeover.py` / canonical liveness 判斷原 owner 是否可接管。
- 原 owner live → fail closed；不得只因使用者輸入「接手」就覆寫 owner。
- evaluator 允許後依 live Guard 走 canonical `claim-takeover`。

### 4.4 `/工作1 強制接手`

- 這個 exact command 構成 user-directed takeover request，但仍不能直接覆寫 claim。
- 必須驗 `WHD_USER_DIRECTED_TAKEOVER_V1` + canonical stale/eligibility checks + Guard。
- Guard GREEN 後才 CAS 改 shared claim owner並從原 checkpoint / next_action 繼續。

本 Skill 不得建立第二套 claim/checkpoint/takeover state machine。

## 5. Location / planned handoff routing

工作槽可表達 execution routing intent，但不能假裝 handoff 已完成。

以下以工作1表示；工作2/3同義：

- `/工作1 本機`：要求目前 bound work 使用 `LOCAL` execution location；真正 ownership/receiver transition依 canonical handoff/claim authority。
- `/工作1 交給排程A`：planned handoff target = Scheduler A exact lane。
- `/工作1 交給排程B`：planned handoff target = Scheduler B exact lane。
- `/工作1 收回本機`：planned reverse handoff target = `LOCAL`。
- `/工作1 準備關機`：只對此 slot執行 local drain / durability / handoff readiness；它不等於 Windows shutdown command。

planned handoff 不得退化成 stale takeover；交接必須 fresh-read exact claim/checkpoint/branch/HEAD/Guard/readiness。

工作槽本身不冒充 handoff transaction owner。

空槽收到 location/handoff 命令時，只回 `EMPTY/UNBOUND`；不得為了滿足 location request 自動挑一張 Issue。

## 6. WORK_SLOT_RELEASE_GATE_V1

`/工作1 釋放`（工作2/3同義）只允許：

1. slot 本來就是 `EMPTY/UNBOUND`，屬 safe empty-slot transition；或
2. bound Issue 已 fresh-read `closed/released`，checkpoint 已 canonical terminal/closed，claim 已 RELEASED；或
3. live authority 明確定義另一個可證明安全的 release transaction。

固定禁止：

- 不得刪除、覆寫或假裝釋放 active claim。
- 不得把 runtime 不活躍等同 Issue 已 terminal。
- 不得用 slot release 取代 Issue closure/finalization。
- release 後不得因空槽自動找下一張票。

## 7. Execution-intent boundary

本 Skill 繼承：

- `UPDATE_DOES_NOT_IMPLY_EXECUTION`。
- `ISSUE_EXISTENCE_IS_NOT_EXECUTION_AUTHORITY`。
- `NORMAL_PATH_FIRST`。
- `RECOVERY_IS_EXCEPTION_NOT_PHASE`。

具體到工作槽：

- `empty slot != execution authority`。
- `open / unblocked Issue != execution authority`。
- `UPDATE_ONLY 不得自動佔用空槽`。
- `EXECUTE_TICKET` 只處理明確指定 slot/Issue。
- `EXECUTE_CHAIN` / `SCHEDULER_LANE` 只有在既有 chain/lane authority 已成立時才可把 terminal slot rotation 到 canonical successor。

## 8. Status projection

`/工作1 狀態` 至少回讀：

```text
slot_id=worker.slot.1
issue=<N|NONE|UNBOUND>
claim_owner=<exact|NONE>
claim_phase=<exact|NONE>
checkpoint_state=<exact|NONE>
runtime_status=LIVE|ENDED|STALE|UNVERIFIED|NONE
runtime_identity=<exact|UNAVAILABLE>
execution_location=LOCAL|SCHEDULER|REMOTE_ACTION|UNVERIFIED|NONE
scheduler_lane=<exact|NONE>
branch=<exact|NONE>
head_sha=<exact|NONE>
next_action=<exact|NONE>
execution_authority=QUERY_ONLY|EXECUTE_TICKET|EXECUTE_CHAIN|SCHEDULER_LANE
```

`/工作槽 狀態` 對工作1/2/3各輸出同一 projection，不新增第四套聚合 state machine。

## 9. Stop / liveness semantics

- slot 有 claim 但沒有 fresh liveness，只能回「有 ownership，runtime 未證明 live」。
- 「進度？」、「怎麼了？」、「為什麼停？」是 observation request，不改 execution state。
- 如果本輪本來就是 execution mode，狀態回報後仍依原 normal path繼續；query-only 則 readback 後完成，不會自動升級施工。

## 10. Forbidden shortcuts

- 不從聊天室標題推導 slot ownership。
- 不從 Issue number 推導 slot number。
- 不從 Scheduler lane 推導 slot number。
- 不把 claim owner 名稱當 slot_id。
- 不把空槽當 worker queue consumer。
- 不用 `/工作槽 空槽` 觸發 discovery/claim。
- 不因某 ticket dependency 解鎖就自動佔用工作1/2/3。
- 不建立第二套 slot claim/checkpoint/takeover/continuity資料庫。

## 11. Examples

```text
/工作1
→ 只查 worker.slot.1 狀態

/工作1 指派 #680
→ 明確 EXECUTE_TICKET；只有 #680 可被綁入 worker.slot.1

/工作2 繼續
→ 只 resume worker.slot.2 已 durable binding 的 exact Issue

/工作3 強制接手
→ 對工作3目前 bound Issue走 WHD_USER_DIRECTED_TAKEOVER_V1 + Guard

/工作槽 空槽
→ 只列空槽，不找票、不 claim
```

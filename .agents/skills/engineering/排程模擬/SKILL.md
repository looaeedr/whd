---
name: 排程模擬
description: 當使用者在 WHD 聊天室輸入 /排程A 或 /排程B 時使用；以對應 durable scheduler lane 的 logical owner 與現行排程行為做互動式 same-lane resume，避免另建第二個 logical owner，並在合法接手後執行 NEW排程A/B 聊天室標題與釘選交接。不得用來偽造平台 scheduled trigger。
whd_doc_role: CURRENT
whd_contract: scheduler-interactive-lane-resume
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 排程模擬

## EXECUTION_MODE_GATE_BRIDGE_V1

`/排程A`、`/排程B` 是明確 execution command，進入對應 `SCHEDULER_LANE` mode；普通文字提到排程、修改排程設定、補 prompt、改名稱或改 cadence，仍屬 `UPDATE_ONLY`，不得因此取得 lane execution authority。

Canonical machine bridge：`tools/execution_scope_gate.py`。

- `SCHEDULER_LANE` 可在 claim/dependency/Guard 合法時做 `DYNAMIC_DISCOVERY / START_SUCCESSOR`。
- `UPDATE_ONLY` 只做指定 scheduler/automation update + validation + readback；不得 claim successor、不得啟動工單施工。
- stale/takeover/reconcile 只有 fresh machine evidence 存在時才進 `RECOVERY / TAKEOVER`；不得把 recovery 當 activation 固定步驟。

這個 Skill 只處理 WHD A/B recurring lane 的**互動式接手與續跑**。它不是第三條 scheduler lane，也不是新的派工 authority。

## 0. Trigger

只在使用者明確輸入下列命令時啟用：

- `/排程A`
- `/排程B`

普通文字提到「排程 A/B」不自動取得 lane ownership。

固定 lane mapping：

```text
/排程A
lane_owner=scheduler.6ab13fa557fc8191935c671214b865e2
behavior_profile=A
live_prompt_source=00

/排程B
lane_owner=scheduler.e58ea936e7d0b12bd0d475314709d6f1
behavior_profile=B
live_prompt_source=B15+B45
```

A 的 `:00 / :20 / :40` 是同一 durable lane；entrypoint 不是 owner。
B15 / B45 是同一 durable B lane；entrypoint 不是 owner。

## 1. First hard gate

任何 Guard、claim、branch、write、commit、PR、workflow、Issue mutation、takeover、reconciliation 前：

1. fresh-read owning branch `.agents/skills/engineering/派工/SKILL.md`，驗證 `name: 派工`、`whd_contract: dispatching-workflow`。
2. fresh-read `.agents/skills/engineering/remote-execution-guard/SKILL.md`。
3. 需要 remote QA / wait / recovery / finalization 時，fresh-read `monitoring-remote-qa` 與 `executable-continuity-controller`。
4. 若 runtime 能讀 automation live state：
   - A fresh-read live `00` prompt；`20/40` 只用於確認同 lane，不能建立新 owner。
   - B fresh-read live B15 與 B45 prompt；兩者除 entrypoint/cadence 外若出現語意衝突，回 `SCHEDULER_PROFILE_DRIFT` 並 fail closed。
5. prompt / 本 Skill 與 live canonical Skill 或 executable authority 衝突時，以 live authority 為準。

不得因本 Skill 已記 lane id 就跳過 fresh read。

## 1.1 Exit-time recurring automation enable

<!-- EXIT_TIME_SCHEDULER_ENABLE_GATE -->

`/排程A` 或 `/排程B` 被使用者明確啟動時，先確認所選 durable lane 的 live automation identity/profile，但**不得在 command activation 階段 enable**。互動式 ownership/resume/施工期間不因命令啟動而改變 recurring enable state；本 gate 的目的，是避免同一 lane 的 scheduled trigger 與本輪 interactive runtime 在施工中重疊，同時確保本輪結束後 recurring lane 重新可喚醒。

1. command start fresh-read/list live automations；不得只靠 title 猜 identity。
2. 依 exact `lane_owner` + entrypoint profile 找 matching set：A = `00 / 20 / 40`；B = `B15 / B45`。
3. matching set 缺少、重複、lane owner 漂移或 prompt profile 不一致 → `SCHEDULER_PROFILE_DRIFT`，fail closed；不得以猜測 title/entrypoint 補洞。
4. command start 只記錄 matching set 的目前 `is_enabled` 狀態：已 enabled 不自動 disable，已 disabled 也不因 activation 自動 enable。
5. 先完成本輪所有 GitHub durable work、Guard consume/readback、claim/checkpoint reconciliation、必要 QA/finalization、以及可執行的 Chat UI handoff；canonical turn-exit gate 未允許結束時，不得提前進入 enable step。
6. 當 canonical authority 已允許本 invocation return / handoff，才執行 **允許的 turn exit 前最後一個 host-side automation control step**：只把所選 lane matching set 中仍為 `is_enabled=false` 的 entrypoint 更新成 `is_enabled=true`；已 enabled 則 no-op。
7. **不得修改 cadence、timing_mode、prompt、title、entrypoint id、lane owner**；不得 enable、disable 或改寫另一 lane。
8. update 後立即 fresh-read matching set；全部 `is_enabled=true` 才成立 `SCHEDULER_ENABLE_ESTABLISHED`。此 readback 是 exit gate 的一部分，不得只相信 update API 回傳。
9. `SCHEDULER_ENABLE_ESTABLISHED` 後不得再做 repository/claim/checkpoint/Issue/PR/workflow/Chat UI mutation；只允許輸出最終狀態並 return。若在 return 前又發現新的 substantive next_action，回到施工流程，待下一次真正允許 exit 時重新執行本 gate。
10. automation control capability 不可用時回 `SCHEDULER_ENABLE_UNAVAILABLE`，不得假稱已開啟；matching set identity 不成立時回 `SCHEDULER_PROFILE_DRIFT`。

## 2. Identity contract

### 2.1 Logical owner 與 physical invocation 分離

`lane_owner` 是 durable ownership identity；互動聊天室只是本輪 physical invocation。

```text
logical_owner = scheduler.<lane-id>
entrypoint = interactive:/排程A | interactive:/排程B
invocation_identity = exact current chat/conversation identity if exposed,
                      otherwise a fresh stable-per-invocation chat.<token>
actual_invocation_source = chatgpt_interactive
```

**不得把「logical owner 相同」解讀成「本輪真的由平台 scheduler 觸發」。**

如果 host 不暴露 conversation id：
- 不得杜撰 conversation id；
- 使用合法 `chat.<token>` 作本輪唯一 invocation identity；
- durable provenance 明記 `conversation_identity=UNAVAILABLE`。

### 2.2 Same-lane resume

當 active claim 的 exact `worker == lane_owner`：

- 視為同一 logical owner；
- **SAME_LANE_RESUME_NO_RECLAIM**：不得另建 parallel claim，不得把 worker 改成 `chatgpt.*`，也不得送 self takeover；
- 保留 claim 既有 `executor_source`，不得只因本輪來自聊天室就做 cosmetic owner/source rewrite；
- fresh-read claim/checkpoint/branch HEAD/Guard transaction/liveness 後，直接沿 exact next_action 續跑。

這是「直接接手」的主要路徑。

### 2.3 New claim

沒有 active owner、且 canonical 派工判定該 leaf 可認領時，`/排程A` 或 `/排程B` 可用對應 `lane_owner` 建立新 claim。

因實際 invocation 是聊天室：
- claim provenance 必須另外保存 `actual_invocation_source=chatgpt_interactive` 與本輪 `invocation_identity`；
- 不得聲稱本輪有 platform scheduled invocation；
- claim / Guard 所需 legacy routing 欄位依 live 派工與 Guard schema 寫入，不自行發明格式。

### 2.4 Foreign owner

若 active claim 的 worker 不是本 lane：

- 禁止把 worker 直接覆寫成 A/B；
- 禁止因使用者輸入 `/排程A` 或 `/排程B` 就跳過 stale / active-run / delegated-work / Guard 判定；
- 必須走 live `派工` + `stale_claim_takeover.py` + local/Remote Guard 的 canonical takeover；
- Guard / evaluator 不允許時，fail closed。

命令選擇的是**目標 lane**，不是繞過 ownership 的萬用鑰匙。

## 3. Exact invocation provenance + liveness

持有 lane active claim 時，本輪必須有唯一 `invocation_identity`。

若 live authority 要求 `WHD_SCHEDULER_RUNTIME_LIVENESS_V1`：
- `scheduler_lane` 固定等於 A/B `lane_owner`；
- `invocation_identity` 必須能區分聊天室 invocation；
- legacy V1 的 `executor_source=scheduler` 只代表 scheduler-lane liveness schema/routing，不是「平台真的以排程觸發」的證據；
- 同一個 durable observation 必須另外保留 `actual_invocation_source=chatgpt_interactive` / interactive entrypoint provenance；
- 不得只留下 generic `scheduler` 而丟失本輪 invocation identity。

same-lane latest heartbeat 無 matching END 且仍在 live window 時，新的 A/B invocation 只讀退讓；逾 live window才可依 live authority做 same-lane resume，仍不是 self-takeover。

canonical same-lane liveness window = **300 秒**；matching END 可立即結束 exact invocation 活性。

## 4. A profile — /排程A

A 模擬目前 `00` 的施工語意，且與 `20/40` 共用同一 lane owner。

固定保留：

1. **DYNAMIC DISCOVERY**：不得硬編 issue/master/child/branch/SHA/run_id/next issue；每輪從 live GitHub durable claim/checkpoint/Issue/dependency/branch/Actions 重建 executable leaf。
2. **EXACT PROVENANCE + LIVENESS**：lane owner 固定 A，invocation identity 每輪唯一。
3. **GUARD TRANSACTION FIRST**：fresh classify `PENDING / MUTATION_DONE_RECONCILE_ONLY / EXPIRED_UNCONSUMED / AMBIGUOUS`；PENDING 只能 consume canonical live receipt；AMBIGUOUS fail closed。
4. **LIVE DRIFT RECONCILIATION**：branch 已前進但 metadata 落後時先 reconcile，禁止 replay mutation。
5. **DELEGATED-BEFORE-STALE**：先沿 delegated child 到真正 executable leaf；child stale 才接 child，不 takeover parent。
6. **STALE / TAKEOVER**：只使用 canonical machine evaluator，不用聊天時間感猜 stale。
7. **GREEN SINGLE-USE**：fresh exact GREEN → consume → 唯一 mutation → fresh readback；過期 GREEN 永不 consume。
8. **SUBSTANTIVE CONTINUITY**：heartbeat/CHECKPOINT/Guard/QA PASS 都不是 substantive completion；exact next_action 可做就繼續。
9. **TURN EXIT / FINALIZATION**：canonical turn-exit gate 未放行不得正常 return；terminal child 仍需 closure/release/successor handoff。

`/排程A` 只有在本輪 canonical gate 已允許結束時，才於 exit-time final step 把 exact A lane 的 00/20/40 設為 `is_enabled=true`；command activation 不 enable；不得修改 cadence、timing_mode、prompt、automation id 或 lane owner。

## 5. B profile — /排程B

B 保留 A 的全部核心 gate，另外必須保留 B lane 的平行施工限制：

- B 是獨立 durable lane：`scheduler.e58ea936e7d0b12bd0d475314709d6f1`。
- 不得修改、停用、重排 A 的 00/20/40。
- **PARALLEL CLAIM RULE**：B 只能 claim 與其他 active owner 安全平行的不同 executable leaf。
- claim 前 fresh-read 全部 active claims、dependency graph、branch/mutation scope、integration/finalization ownership。
- 已有 active owner、dependency blocked、共享不可平行 scope、exclusive integration/finalization gate 的候選一律跳過。
- 不同 lane identity 絕不是搶同一 scope 的許可。

`/排程B` 只有在本輪 canonical gate 已允許結束時，才於 exit-time final step 把 exact B lane 的 B15/B45 設為 `is_enabled=true`；command activation 不 enable；不得修改 cadence、timing_mode、prompt、automation id 或 lane owner。

## 6. Chat UI handoff

只有 durable ownership/resume readback 已成立後才做 UI handoff。

成功 gate：

```text
LANE_RESUME_ESTABLISHED =
  selected_lane exact
  AND claim/readback authority exact
  AND no forbidden foreign active runtime
  AND current invocation is allowed to continue
```

未達此 gate：
- 不改目前聊天室標題；
- 不改 pin；
- 不清舊聊天室的 `NEW`。

### 6.1 /排程A

依使用者指定順序：

1. 目前聊天室標題 → `NEW排程A`。
2. 目前聊天室 → 釘選。
3. 找到其他舊的 exact `NEW排程A` 聊天室。
4. 舊聊天室 → 取消釘選。
5. 舊聊天室標題移除前綴 `NEW` → `排程A`。

完成後 invariant：
- 最多一個 `NEW排程A`；
- 最多一個 A control chat 被釘選；
- `NEW排程A` 指向本輪最新成功接手的互動聊天室。

### 6.2 /排程B

同樣順序：

1. 目前聊天室標題 → `NEW排程B`。
2. 目前聊天室 → 釘選。
3. 找到其他舊的 exact `NEW排程B` 聊天室。
4. 舊聊天室 → 取消釘選。
5. 舊聊天室標題 → `排程B`。

完成後 invariant 同 B lane。

### 6.3 UI capability hard gate

在做 UI handoff 前，必須確認 runtime 真正具備：
- current chat rename；
- chat discovery / exact old-chat selection；
- pin；
- unpin。

能力缺任一項：
- 不得聲稱已改名或已釘選；
- durable lane resume 可以繼續；
- user-visible 回報固定含 `CHAT_UI_HANDOFF_UNAVAILABLE` 與缺少的 capability。

部分 UI mutation 後失敗：
- 回 `CHAT_UI_HANDOFF_PARTIAL`；
- 列出已完成與未完成步驟；
- 下一次同 lane invocation 先 reconcile UI invariant，再做新的 handoff；
- 禁止假報完整成功。

## 7. Guard transaction / duplicate GREEN

本 Skill 不建立自己的 Guard state machine。

每次 mutation 前一律沿 live `派工` + `遠端執行守門`：

- exact active claim；
- exact branch/base/head/blob；
- exact changed-file scope；
- fresh unexpired receipt；
- receipt single-use；
- mutation 後 fresh readback；
- post-commit claim HEAD reconciliation。

Equivalent duplicate GREEN 的 canonical/shadow 規則完全服從 live authority；不得因「我是同一 A/B lane」重播 shadow receipt。

## 8. Turn output

每次 `/排程A` / `/排程B` 至少可反讀：

```text
lane=A|B
lane_owner=scheduler....
entrypoint=interactive:/排程A|/排程B
invocation_identity=<exact or generated>
conversation_identity=<exact|UNAVAILABLE>
claim_issue=<N|NONE>
claim_worker=<exact>
claim_phase=<exact>
branch=<exact>
head_sha=<exact>
guard_transaction=<exact classification>
resume_mode=SAME_LANE_RESUME|NEW_CLAIM|GUARDED_TAKEOVER|BLOCKED
chat_ui_handoff=COMPLETE|UNAVAILABLE|PARTIAL|NOT_STARTED
scheduler_enable=UNCHANGED_DURING_RUN|SCHEDULER_ENABLE_ESTABLISHED|SCHEDULER_ENABLE_UNAVAILABLE|SCHEDULER_PROFILE_DRIFT
next_action=<exact>
```

不得只回「已接手」。只要 canonical next_action 可自主執行，就繼續到合法 turn-exit gate。

## 9. Forbidden shortcuts

- 不把互動 runtime 假稱為平台 scheduled invocation。
- 不用 `chatgpt.*` 另開第二個 claim 來「模擬」同一 A/B 工作。
- 不因 A/B logical owner 一樣就忽略仍活著的 same-lane invocation。
- 不用聊天室 title/pin 當 claim authority。
- 不用 `NEW排程A/B` 判斷 GitHub owner。
- 不因 UI handoff 做不到就回滾已合法建立的 durable lane resume。
- 不因 UI handoff 成功就宣稱 GitHub takeover 成功。
- 禁止在 command activation 階段把所選 lane 從 disabled 改成 enabled；activation 只 fresh-read/verify identity/profile。
- 除 exit-time final gate 將所選 lane matching recurring entrypoints 設為 `is_enabled=true` 外，不自動 enable、disable、reschedule 或改寫任何 automation；另一 lane 絕不碰。

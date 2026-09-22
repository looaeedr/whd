---
name: 遠端執行守門
description: WHD 排程／automation 已取得 shared execution claim，但目前 runtime 沒有 repository command execution、shell 或無法本機執行 tools/execution_claim_guard.py 時使用；透過 trusted default-branch GitHub Actions Remote Guard 取得 canonical prewrite guard receipt，驗證後才允許單次 repository mutation。若本機 guard 可執行，優先使用本機 guard。
whd_doc_role: CURRENT
whd_contract: remote-execution-guard
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 遠端執行守門

本 Skill 把「scheduler 沒有 shell，因此不能跑 canonical execution claim guard」從永久 blocker 變成可驗證的遠端 guard 路徑。它不放寬 `派工` 的 claim/prewrite hard gate；它要求 GitHub Actions 在 exact identity 上真正執行同一支 `tools/execution_claim_guard.py`，再回傳 machine-readable receipt。

## 1. Responsibility boundary

本 Skill只擁有 scheduler/runtime command-execution capability fallback。

它不擁有：
- execution claim 的取得／轉移／釋放：由 `派工` + shared `coord/dispatch-claims` authority 擁有；
- generic remote QA polling：由 `monitoring-remote-qa` 擁有；
- continuity/checkpoint/finalization：由 `executable-continuity-controller` 擁有；
- long-log 讀取：由 `long-log-context-safe-execution` 擁有；
- Issue closure：由 owning closure gate 擁有。

Remote Guard 不是第二套 ownership authority。它只能驗證已存在、仍 active 的 shared claim。

## 2. Trigger gate

依序判定：
1. runtime 能直接執行 canonical `tools/execution_claim_guard.py` → 使用 local executable guard。
2. shared claim 有效，但 runtime 沒有 repository command execution / shell / Python execution primitive，且 trusted Remote Guard 可用 → **必須優先走 Remote Guard**。
3. local guard 與 Remote Guard 都不可用 → 才 durable handoff interactive。

固定路由：

`LOCAL_GUARD_AVAILABLE → local guard`

`LOCAL_GUARD_UNAVAILABLE + REMOTE_GUARD_AVAILABLE → Remote Guard`

`LOCAL_GUARD_UNAVAILABLE + REMOTE_GUARD_UNAVAILABLE → durable interactive handoff`

因此 `no repository command execution` 不再自動等同永久 `GUARD_EXECUTION_CAPABILITY_BLOCKER`。

## 3. Trusted workflow authority

Current trusted entrypoint：

`.github/workflows/whd-remote-execution-guard.yml`

Trigger：

`issue_comment: created`

Current V1 workflow 只接受 repository owner 發出的固定 schema request。禁止 comment payload 帶 arbitrary shell。

workflow 必須：
- 位於 GitHub default branch；
- checkout trusted workflow repository；
- fresh verify exact `guard_authority_sha`；
- fresh fetch `coord/dispatch-claims`；
- verify exact claim blob；
- verify branch existence/current branch SHA；
- run canonical Phase6 Preflight；
- run canonical `tools/execution_claim_guard.py`；
- publish bounded log + machine-readable receipt + artifact；
- guard 非 GREEN 時整顆 job terminal failure。

Actions job success 不能單獨當 guard authority；receipt 也必須 GREEN。

## 4. Request contract — WHD_REMOTE_GUARD_REQUEST_V1

Issue comment 第一行固定：

`WHD_REMOTE_GUARD_REQUEST_V1`

必要欄位：
- `issue=<positive issue number>`
- `worker=<claim owner identity>`
- `action=<branch-create|write|commit|qa-dispatch|workflow-dispatch|pr-write>`
- `branch=<exact claimed/delegated branch>`
- `base_sha=<40-char claim base SHA>`
- `head_sha=<40-char current claimed HEAD>`
- `claim_blob_sha=<exact blob SHA of .dispatch/claims/issue-N.json>`
- `guard_authority_sha=<exact SHA containing canonical guard/preflight authority>`
- `tested_target_sha=<exact target/head being guarded>`

`write` / `commit` 必須至少一個：
`changed_file=<repo-relative path>`

多檔案一行一個 `changed_file`；receipt 的 changed-file scope 必須與實際 mutation 完全一致。

Current V1 要求：
`tested_target_sha == head_sha`

## 5. Action-specific rules

### branch-create
Request 前：
- shared claim active；
- `work_branch` 已在 claim 宣告；
- remote branch 尚不存在；
- pre-branch state 可為 `base_sha == head_sha`。

GREEN receipt 只授權建立該 exact branch 一次。

### write / commit
Request 前：
- branch 必須存在；
- remote branch HEAD exact 等於 `head_sha`；
- `changed_file` 列完整 mutation scope；
- Skill target 必須讓 canonical Preflight evidence 包含 `寫技能` + required Skills/references。

若 GitHub primitive 支援 atomic multi-file commit，優先用一張 `commit` receipt 綁完整 changed-file set，做單一 tree/commit/ref transition；不要把一張 receipt 拆成多次獨立 write。

### qa-dispatch / workflow-dispatch / pr-write
同樣要求 fresh claim/blob/branch/head identity。receipt 只授權 request 中那一種 action。

## 6. Remote identity — three layers

每次 Remote Guard 分開記：
- `run_id`
- `orchestrator_head_sha`
- `tested_target_sha`

workflow `head_sha` 是 orchestrator identity，不等於 tested target。

禁止：
- 用 orchestrator SHA 取代 tested target；
- 用 `head_sha == tested_target_sha` 搜不到 run 就宣告 RUN_NOT_CREATED；
- 跳過 locked run 改看別顆 run。

## 7. Monitoring

送出 request comment 後：
1. 記 `request_comment_id`；
2. 找 request 後新產生的 `WHD Remote Execution Guard` issue_comment run；
3. 鎖 exact `run_id + orchestrator_head_sha`；
4. 依 `monitoring-remote-qa` poll 到 terminal；
5. 找 `WHD_REMOTE_GUARD_RESULT_V1`，要求 receipt 的 `request_comment_id` exact match；
6. artifact / bounded log 是 evidence，不取代 receipt identity。

run terminal failure → 先分類 exact failure，不得 mutation。

## 8. Receipt contract — WHD_REMOTE_GUARD_RECEIPT_V1

只有全部成立才可執行緊接的單次 mutation：
- `schema == WHD_REMOTE_GUARD_RECEIPT_V1`
- `result == GREEN`
- `reason == EXECUTION_CLAIM_GUARD_GREEN`
- exact run `completed/success`
- exact `request_comment_id`
- exact issue / worker / action / branch
- exact base_sha / head_sha
- exact claim_blob_sha
- exact guard_authority_sha
- exact tested_target_sha
- exact changed_files
- exact run_id
- exact orchestrator_head_sha
- current time < `expires_at`

mutation **立即前**再 fresh-read：
- claim blob 仍等於 receipt；
- claim owner/phase 仍允許 action；
- branch/head existence condition 仍一致；
- movable guard authority（若契約要求 current）仍未漂移。

任何一項變動 → receipt stale，重新申請。

## 9. Single-action / single-use rule

Remote Guard GREEN 不是 session token。
- receipt 只授權 request 中一個 action；
- action 完成後立即更新 claim/head/progress；
- claim blob 或 branch HEAD 變化後舊 receipt 自動 stale；
- 不得同 receipt 做第二次 branch/write/commit/PR/dispatch；
- 不得跨 issue/branch/HEAD/changed-file scope 重用。

Atomic multi-file commit 可以把完整 changed-file set 視為一個 `commit` action，但只能產生一個 exact commit/ref transition。

## 10. Race / stale identity handling

Remote Guard 是 optimistic concurrency gate。以下 fail-closed 是預期安全行為：
- request 後另一 executor 更新 claim → claim blob 改變；
- branch HEAD 移動；
- guard authority 漂移；
- action/changed-files scope 擴大；
- ownership/takeover 改變。

處理：
1. 不 mutation；
2. fresh-read claim / branch / authority；
3. ownership 仍合法且只是 durable evidence 更新 → 用新 blob/head 重送；
4. ownership 已轉移 → 停止施工，服從 foreign-runtime lease。

#496 首次 Skill 實戰已證明 stale claim blob request 會被 Remote Guard FAIL 擋下；fresh blob 重送才可 GREEN。

## 11. Failure classification

至少使用：
- `REMOTE_GUARD_REQUEST_INVALID`
- `REMOTE_GUARD_STALE_IDENTITY`
- `REMOTE_GUARD_PREFLIGHT_FAILED`
- `REMOTE_GUARD_EXECUTION_CLAIM_FAILED`
- `REMOTE_GUARD_RUN_FAILED`
- `REMOTE_GUARD_RECEIPT_MISMATCH`
- `REMOTE_GUARD_RECEIPT_EXPIRED`
- `REMOTE_GUARD_UNAVAILABLE`

只有 `REMOTE_GUARD_UNAVAILABLE` 且 local executable guard 也不可用，才 durable interactive handoff。

## 12. Scheduler integration

```text
fresh claim / dependency / ownership
→ action_mode == EXECUTE_NOW
→ local guard available?
   → yes: local canonical guard
   → no: Remote Guard available?
        → post fixed request
        → lock exact run
        → poll terminal
        → validate exact GREEN receipt
        → fresh pre-mutation identities
        → execute one mutation
        → update durable claim/head
        → continue
        → unavailable: durable interactive handoff
```

## 13. Liveness bridge

Remote Guard request 已產生 active exact run：
- 合法 WAITING_REMOTE / REMOTE_QA_ACTIVE；
- exact run 是 real progress producer；
- watchdog 只 monitor，不得 duplicate request。

沒有 run：
- 不得假 WAITING_REMOTE；
- 回到 trigger/prerequisite，建立真正 progress producer。

terminal 後立即 reconcile；receipt FAIL/identity mismatch 不能當 GREEN。

## 14. Security / fail-closed invariants

禁止：
- arbitrary shell comment；
- 不驗 trusted requester；
- 不驗 claim blob；
- 不驗 branch SHA；
- receipt FAIL 仍 mutation；
- job success 但 receipt 缺失仍 mutation；
- receipt GREEN 但 run failure 仍 mutation；
- 過期 receipt；
- 舊 receipt 覆蓋新 claim/head；
- 只靠 Issue comment 宣稱 guard 已執行。

workflow shell 必須真正 fail-fast；不可依賴在條件語境中被抑制的 `set -e`。

artifact 不應放在 upload-artifact 預設忽略的 hidden directory。artifact failure 會讓整顆 run 非 success；即使內層 guard log GREEN，也不能把該 run 當 accepted terminal success。

## 15. Durable evidence

successful action 至少保存：
- request/result comment IDs
- run_id
- orchestrator_head_sha
- tested_target_sha
- claim_blob_sha
- action
- branch/base/head
- changed_files
- receipt result/reason
- artifact ID（若有）
- mutation commit/ref/run/PR identity
- consumed/next-action state

## 16. Historical provenance

Remote Guard bootstrap：
- #493
- PR #494
- recovery PR #495
- accepted smoke run `35719871936`
- receipt schema `WHD_REMOTE_GUARD_RECEIPT_V1`

這些只證明 workflow 已建立；未來每次 mutation 仍要 fresh receipt。

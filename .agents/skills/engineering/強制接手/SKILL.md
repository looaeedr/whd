---
name: 強制接手
description: 當使用者明確要求「強制接手／接手卡住的 WHD 工單」時使用；以 canonical stale evaluator、使用者授權、Remote/local Guard 與 single-use CAS 安全轉移 shared execution claim，禁止直接覆寫 foreign owner。
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: user-directed-force-takeover
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 強制接手

本 Skill 是使用者明確要求接管既有 foreign execution claim 時的操作入口；它不創造新的 ownership 規則，也不允許跳過既有 hard gate。

## 0. Canonical chain

固定順序，不能換序：

```text
派工
→ tools/stale_claim_takeover.py
→ 判定原 owner 是否可接管
→ 使用者指定強制接手時驗 WHD_USER_DIRECTED_TAKEOVER_V1
→ 遠端執行守門
→ execution_claim_guard.py action=claim-takeover
→ GREEN
→ CAS 改 shared claim owner
→ 繼續原 checkpoint / next_action
```

任何一步缺 evidence 都 fail closed。

## 1. First hard gate

1. fresh-read owning branch `.agents/skills/engineering/派工/SKILL.md`，驗 `name: 派工` 與 `whd_contract: dispatching-workflow`。
2. fresh-read `.agents/skills/engineering/remote-execution-guard/SKILL.md`。
3. fresh-read exact owning Issue、shared claim blob、checkpoint、work branch HEAD、active remote run、delegated child/helper 與 scheduler runtime liveness。
4. 不得用聊天記憶、Issue title、聊天室 title、排程 title 或「很久沒動」代替 machine evidence。

## 2. User-directed authority

互動聊天室要求強制接手時，新 requesting worker 必須是 exact `chatgpt.<instance-token>`，且 owning Issue 上存在 repository owner authored：

```text
WHD_USER_DIRECTED_TAKEOVER_V1
issue=<N>
requesting_worker=<exact chatgpt.*>
previous_worker=<exact current claim.worker>
executor_source=chat
```

authority comment 必須 fresh、identity exact；由 `tools/stale_claim_takeover.py` 驗證。缺失、過期、previous/requesting worker 不符、self-takeover 一律拒絕。

## 3. Liveness before takeover

先看 active exact run，再看 delegated work，再看 exact runtime liveness。

- active exact run = absolute lock，不得 takeover。
- active delegated child/helper = 接 child leaf，不搶 parent。
- foreign scheduler heartbeat 使用 owner-authored `WHD_SCHEDULER_RUNTIME_LIVENESS_V1`。
- matching `WHD_SCHEDULER_RUNTIME_END_V1` 代表該 exact invocation 已正常結束；不得再把舊 heartbeat 當活著。
- canonical runtime lease maximum = 300 秒；不得另造 420 秒 same-lane 規則。
- missing / expired / ended liveness 只解除 invocation 活性；仍需 evaluator actionable + Guard。

## 4. Guard + single-use CAS

只有 `tools/stale_claim_takeover.py --require-actionable` 回 actionable，才可進 Guard。

- local guard 可用：跑 canonical `tools/execution_claim_guard.py ... --action claim-takeover`。
- local 不可用但 trusted transport 可用：走「遠端執行守門」。
- interactive transport 傳 exact `takeover_worker`、`requesting-executor-source=chat` 與 owner-authored user authority JSON。
- receipt 必須 exact GREEN、未過期、single-use。
- mutation 前 fresh-read claim blob / branch HEAD；任一 drift → receipt stale。
- 真正 owner 轉移只能是一個 compare-and-swap（CAS）shared coordination mutation。

CAS 成功後 fresh-read證明 owner/blob/head/branch exact，並保存 previous owner、machine classification、authority comment、Guard run/receipt；不得建立第二個 parallel claim。

## 5. Resume is mandatory

owner CAS readback 成功後，必須立即沿原本 canonical `checkpoint / next_action` 續工並完成 same-invocation first substantive action。只改 owner 就停、另開 branch 重做、清空 checkpoint、把 takeover receipt 當 session token全部禁止。

## 6. Output

至少回顯 issue、previous_worker、takeover_worker、machine_classification、user_authority_comment_id、guard_run_id、guard_receipt、claim_cas、claim_blob_after、checkpoint 與 next_action。任一 hard gate 失敗不得宣稱「已強制接手」。

---
whd_doc_role: REFERENCE
whd_contract: scheduler-prompt-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Scheduler Prompt Authoring / 排程「有醒但沒施工」踩坑

## SCHEDULER_PROMPT_AUTHORING_PITFALL_V1

### 事故

2026-09-24 的 WHD recurring lanes 出現一組可重複事故：

1. scheduler invocation 確實被喚醒，也留下 heartbeat，但沒有接著完成可執行 next_action，形成 **heartbeat-only**。
2. runtime 拿到 Remote Guard GREEN 後，在真正 consume / mutation / readback 前就結束 invocation，留下 **unconsumed GREEN**。
3. scheduler 把「自己其實能做的 run discovery / poll / readback」寫成 `BLOCKED`，再利用 BLOCKED 可結束 turn 的語意提前退出。
4. 為了縮短／重寫 automation prompt，authoring 過程曾把「fresh-read《遠端執行守門》」顯式 hard gate 刪掉，只剩《派工》，造成 transport / consume authority 依賴隱含記憶。
5. update API 回 SUCCESS 後若沒有 **post-update readback**，無法立即發現 schedule、lane identity、enabled 或 hard-gate marker 被誤改。
6. 前一輪 Guard GREEN 已經超過 `expires_at`，後一輪仍把它當作可 consume 的 authorization，形成 **expired GREEN / STALE_GUARD_RECEIPT** 漏洞。
7. branch / canonical checkpoint 已經有新的 durable mutation，但 `claim.head_sha` 與 next_action 還停在舊狀態；後一輪若只信 claim，可能重播已完成 mutation，而不是先對齊 **live branch HEAD**。

### 根因

- 把「prompt 有一句不能停」誤當成 machine enforcement。
- 把 heartbeat / Guard receipt / QA PASS 誤當 substantive progress。
- 把 `BLOCKED` 當成 turn-exit escape hatch，而不是 genuine external wait。
- 修改 prompt 使用 replacement semantics，卻沒有 baseline + invariant diff；刪一段文字就可能刪掉整個 Skill authority。
- 沒有把 schedule、durable lane owner、entrypoint identity 分開管理。
- 把 GREEN 誤當跨 invocation session token，沒有在 consume 當下驗 `now < expires_at`。
- 把 claim snapshot 誤當最高 runtime truth，沒有先比較 branch/checkpoint live durable evidence。

### 永久規則

1. 建立／修改 WHD scheduler prompt 必須使用 `.agents/skills/engineering/寫排程/SKILL.md`。
2. authoring 前先 baseline-read automation 的 id/title/schedule/timing_mode/enabled/full prompt/updated_at/last_run_time。
3. 施工型 scheduler prompt 必須顯式保留 **派工 + 遠端執行守門**；不可把後者假設成前者的隱含內容。
4. 每次 wake 先比對 `claim.head_sha` / claim.next_action 與 **live branch HEAD** / canonical checkpoint；branch/checkpoint 已前進時先 reconcile，禁止重播已完成 mutation。
5. 任何 GREEN consume 前都必須 fresh 驗 receipt identity + `current UTC < expires_at`；expired GREEN 固定分類 `STALE_GUARD_RECEIPT`，永久禁止 consume。若 mutation 未發生就重申 fresh Guard；若已發生則只做 durable drift reconciliation。
6. 有 exact-valid、**未過期**的 unconsumed GREEN 時，下一 wake first recovery = validate → consume → exact mutation → readback；heartbeat 不得搶在前面成為假終點。
7. heartbeat / progress / CHECKPOINT / Guard GREEN / QA PASS 都不是 substantive completion。
8. `BLOCKED` 只給真正 runtime 無法自行排除的 external authority/capability/dependency blocker。Discovery、poll、read、Guard、mutation、readback、reconcile 都不是 blocker。
9. exact remote run 存在時鎖 `run_id + head_sha` 到 terminal，不 duplicate dispatch。
10. 正常 return 前要實際經過 **machine turn-exit** authority；文字說「可以結束」沒有證明力。
11. 沒有 matching `WHD_SCHEDULER_RUNTIME_END_V1` 的 invocation 不得視為正常完成。
12. automation update 後必須做 post-update readback；驗 title/schedule/timing_mode/enabled/lane owner/entrypoint 與 required hard gates。
13. 同一 logical lane 的多 entrypoint 共用 owner是 mutex；不同 owner才可能真平行，但仍受 shared claim / dependency / integration scope 約束。
14. 修改一個 prompt 發現 reusable authoring defect 時，要搜尋 sibling / parallel lanes 是否有同型缺口，不能只補眼前入口。

### Documentation != enforcement

`寫排程` Skill 能避免 authoring 時刪錯 contract，但不能保證平台 runtime 永遠不會 hard-cut，也不能取代 executable continuity controller。

真正判斷必須區分：

- prompt contract：下一個 runtime 應該怎麼做；
- Remote Guard：這次 mutation 是否獲授權；
- continuity controller：目前 workflow state 是否允許 turn exit / finalization；
- durable GitHub evidence：上一輪實際做到哪裡。

因此禁止說：「prompt 補好了，所以排程不會再停。」

正確說法只能是：prompt authoring contract 已補；是否持續施工要看下一輪的 durable mutation、exact run、turn-exit proof 與 END readback。

<!-- ISSUE646_PROMPT_AUTHORING_V1 -->
## #646 prompt authoring hard order

Scheduler prompt 固定：Guard recovery → drift reconciliation → delegated/proof/helper traversal → helper dedupe → stale evaluator → guarded mutation → readback → turn-exit。不得把『10分鐘沒更新』放在第一判斷。

必須明寫 active delegated child = parent liveness、same helper key reuse、equivalent duplicate GREEN dedupe、expired unconsumed GREEN不可 replay、cadence/IDs/lane owner/recurring enabled policy不得因 writeback改動。

Prompt/status provenance 要顯示 exact scheduler lane + invocation identity；interactive counterpart後續必須保存 conversation/chat identity + invocation identity並補 heartbeat。


<!-- ISSUE667_END_LIVENESS_V1 -->
## #667 Scheduler END / unified liveness / interactive takeover

- heartbeat 與 invocation 終態使用 `WHD_SCHEDULER_RUNTIME_LIVENESS_V1` + exact matching `WHD_SCHEDULER_RUNTIME_END_V1`。
- selector 綁 exact `issue + scheduler_lane + invocation_identity + claim_blob_sha + branch + head_sha`；identity drift fail closed。
- matching END 後 machine status 是 `ENDED`；active exact remote run 仍是 absolute lock。
- runtime heartbeat maximum TTL 與 same-lane mutex 統一為 **<=300 秒**；不得另造 420 秒 prompt-only 判斷。
- user-directed interactive takeover 的 trusted Remote Guard 必須 fresh-read owner-authored `WHD_USER_DIRECTED_TAKEOVER_V1` 並傳給 canonical stale evaluator。
- `/排程A` / `/排程B` activation 只 enable exact selected lane matching recurring entrypoints；post-update fresh readback，不改 cadence/prompt/title/owner，不碰另一 lane。

## EXECUTION_INTENT_ROUTING_PITFALL_V1

### 事故

2026-09-26 重新檢查 WHD scheduler / Skill 更新流程時，發現「更新控制面」與「執行工單」容易被同一套 continuity/dispatch wording 混在一起：

- 使用者只是要求修改排程 prompt、Skill、Issue body 或治理規則；
- runtime 卻因看到 open/unblocked Issue、空工作槽、next_action 或可用 Guard，順手取得 claim、建立 implementation branch，甚至自動接 successor；
- scheduler prompt 又把 drift/reconciliation/takeover capability 寫得像每輪固定前置 phase，造成正常工單也繞進 recovery。

### 永久規則

1. Scheduler authoring / automation update 預設是 `UPDATE_ONLY`；完成條件是 requested update + minimum validation/readback。
2. `UPDATE_ONLY` 不授權 implementation claim、implementation branch、successor chain 或 scheduler lane execution。
3. `/排程A` / `/排程B` 與真正 scheduled invocation 才是 `SCHEDULER_LANE` execution entrypoint。
4. `open / unblocked Issue`、空 work slot、Guard 可用、next_action 存在都不是 execution authority。
5. `NORMAL_PATH_FIRST`：正常 implementation 只走 `claim → branch → RED → implementation → GREEN → PR/QA → merge → close/release`。
6. `RECOVERY_IS_EXCEPTION_NOT_PHASE`：takeover / reactivate / reconciliation / legacy repair 僅由 fresh machine evidence 觸發；condition 修復後立即回 normal path。
7. 修改 live recurring automation prompt 時只改本次 scope；cadence、enabled、lane owner 若未被使用者點名就保持原值，並 post-update fresh readback。

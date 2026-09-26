---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Execution Claim Pre-Write Hard Gate Pitfall

## 問題

只有成功建立 **atomic claim** 還不等於形成真正的施工硬鎖。若後續 branch-create、repository write、commit 或 QA dispatch 沒有再次驗證 shared claim，另一個 worker 仍可能從 stale context 直接建立平行 branch 並施工。

## 永久規則

每一個受 execution claim 管制的 GitHub 工單，在下列動作前都必須執行 **pre-write owner check**：

- `branch-create`
- production / test / Skill / AI Library `write`
- `commit`
- `qa-dispatch` / `workflow-dispatch`
- PR write

可執行 guard：

`tools/execution_claim_guard.py`

Guard 必須 fail closed 驗證：owning Issue、Issue URL、worker identity、claimed work branch、base/head SHA、claim phase，以及 explicit delegated QA branch（若有）。

## 禁止的錯誤做法

- 看到 Issue comment 說「已 claim」就當 owner。
- 只在 claim acquisition 時驗一次，後續 write 不再驗。
- 非 owner 因為「只是補測試 / 只開 QA branch」就進場。
- branch 名稱含同一 Issue number 就當成授權。
- shared claim 缺失、malformed、branch mismatch 時繼續施工。

**非 owner / non-owner 必須直接 FAIL，不能另開平行實作來繞過 claim。**

## 邊界

此 guard 不負責建立、接管或釋放 claim；它只消費既有 shared coordination authority 並決定目前 action 是否允許。stale takeover 仍必須走既有 compare-and-swap recovery 規則。

GitHub 平台本身若沒有 repository ruleset / server-side hook，任意外部 API 仍可能繞過 repo 內工具；因此 WHD 的派工流程必須把此 executable pre-write guard 視為 branch/write/QA action 的強制前置條件，而不是建議。


## Skill write preflight identity（2026-09-22）

execution claim 只證明「誰可以寫」，不能證明「寫 Skill 的資格已完成」。過去曾出現 owner/branch/head 全部合法，但 Agent 直接修改 `.agents/skills/**/SKILL.md`，漏掉 `寫技能` Preflight 的流程洞。

固定防錯：
- file mutation 的 execution guard 必須知道實際 `changed-file`；`write/commit` 缺 changed-file identity 直接拒絕。
- Skill write target 命中 `.agents/skills/**/SKILL.md` 時，guard 必須驗 `preflight evidence`，至少證明 canonical registry 要求的 `寫技能`、其他 required Skills 與 required references 都完成。
- 只在聊天中說「有讀寫技能」、只留 Issue comment、或只持有 atomic claim 都不是 Skill authoring authority。
- scope 新增 Skill/AI Library/測試檔時，先重跑 changed-file Preflight，再進下一次 write。


## POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1（2026-09-23）

### 問題
prewrite guard 的 `write/commit` 必然綁 mutation 前的 claim/work HEAD H0。合法 commit 完成後 branch 變 H1，但 shared claim 還是 H0；若下一張普通 `write` guard 同時要求 live branch==request HEAD 與 claim HEAD==request HEAD，就會形成「合法 commit 成功後反而永遠無法更新 claim HEAD」的 bootstrap deadlock。

### 永久規則
- **不得放寬一般 stale-head write。** ordinary write/commit 仍要求 claim HEAD exact 等於 guarded live HEAD。
- 唯一例外是 exact shared claim path 的 post-commit reconciliation write。
- reconcile 前必須反查 prior repository-owner request + github-actions bot GREEN receipt，並綁 current claim blob、owner、branch、base、H0。
- live H1 必須是 H0 的單一直接子 commit；H1 changed-file set 必須與 prior GREEN receipt 完全一致；commit timestamp 必須位於 prior receipt issued/expires window。
- reconcile receipt 只授權一次 optimistic CAS 把 shared claim head H0→H1；不得拿 prior commit receipt做第二次 mutation。
- parent/file/blob/request/receipt/time 任一 drift 一律 fail closed，不得為了「只是更新進度」直接改 coordination claim。

### 2026-09-23 live RED
#533 在合法 commit Guard RUN `35873300186` GREEN 後，work branch `09e19c06… → fb544321…`，shared claim 仍記舊 HEAD；後續普通 claim-progress write Guard RUN `35873592503` 因 stale identity FAIL。此案例是本規則的 canonical regression。


## MERGE_SYNC_WORK_DELTA_VS_PRODUCTION_PARENT_V1（2026-09-24）

### 問題
evidence-bound merge-sync 的 post-commit claim HEAD reconciliation 不能直接把 GitHub merge commit 的 generic `files` 清單當成 Worker mutation delta。當 H1 以 claim H0 與 production X 為兩個 parents 時，generic commit file evidence 可能包含「由 production parent 帶進來」的治理／流程檔；這些檔案不是 owning Issue 的 mutation，因此本來就不會出現在 prior GREEN receipt。

### 永久規則
- merge-sync 仍先證明 exactly one parent == claim H0，另一 parent 是合法 production parent。
- authorized work delta 必須以 **production parent → H1** 的 compare file set 為準，而不是 H1 相對另一 parent 的 generic commit `files`。
- production-parent-only files 不要求出現在 owning Issue prior mutation receipt。
- production parent → H1 的 work delta 必須全部受 prior exact GREEN `write|commit` receipt 授權；任何額外 work-delta file 仍 fail closed。
- issue/worker/source/branch/base/current claim blob/request/receipt/guard authority/receipt window 等既有 identity checks 不得放寬。
- ordinary single-parent post-commit reconciliation 維持原本 direct-child commit-file evidence。
- canonical regression：`tests/process/test_issue570_merge_head_claim_reconciliation.py`；governance repair owner：#603。


## LEGACY_ACTIVE_CLAIM_CHECKPOINT_REPAIR_V1（2026-09-26）

### 事故
#617 的 scheduler claim 建於 checkpoint invariant 上線前；claim 歷史存在、checkpoint 歷史為 0。#642/#649 上線後，Remote Guard/Turn Exit/Finalization 都正確 fail closed，但 Claim Activation 只有「兩者都不存在」或「兩者都存在」兩種入口，形成 migration catch-22。

### 永久規則
- 不放寬 `ACTIVE_CLAIM_REQUIRES_CHECKPOINT`。
- trusted Claim Activation 提供窄 transition `legacy-checkpoint-repair`。
- prior claim 必須存在、prior checkpoint 必須 missing。
- candidate claim blob 必須與 prior blob byte-for-byte 相同；repair 只能 bootstrap checkpoint，不能偷帶 owner/branch/base/head/phase/next_action 變更。
- candidate checkpoint 必須 canonical non-terminal 並 exact 綁 unchanged claim issue/branch/head。
- coordination parent + prior claim blob 共同作 CAS identity；任何 drift fail closed。
- repair 後的 branch HEAD drift仍走 `POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1`，不得把 legacy repair 升格成 stale-head bypass。

## LEGACY_EXPIRED_POSTCOMMIT_RECONCILE_RECOVERY_V1（2026-09-26）

### 事故
#617 的歷史 mutation 已有 exact GREEN Guard request/receipt，H1 也是 claim H0 的直接子 commit且 changed files 完全吻合；但 commit timestamp 落在舊 receipt 的有效窗之外，因此 ordinary post-commit reconciliation 正確 RED。若直接放寬 receipt window，等於讓所有過期 GREEN 重新取得 mutation authority，會破壞 single-use / expiry contract。

### 永久規則
- ordinary `POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1` 完全不改；沒有 recovery authority 時，過期 receipt 照舊 RED。
- 唯一 migration 入口是 repository owner 在 owning Issue 留下 fixed-schema `WHD_LEGACY_POSTCOMMIT_RECONCILE_V1`。
- recovery 必須 exact 綁 issue/worker/source/branch、claim H0、live H1、historical guard run id、request comment id、changed-file set。
- canonical guard 必須先通過既有 current claim blob、direct-child H0→H1、historical request+GREEN receipt、base/head/tested-target/files identity；只有最後的 receipt-time-window check 可由 exact recovery authority取代。
- wrong live head、wrong run/request、foreign owner/source、wrong files、non-direct child、malformed/foreign comment 一律 fail closed。
- trusted Remote Guard 僅在 `action=write` 接受 `legacy_reconcile_recovery_comment_id`，fresh fetch exact comment 後驗 owner + issue + marker，再傳 `--legacy-reconcile-recovery`；禁止 arbitrary payload/shell。
- recovery 只授權 coordination reconciliation，不重播原 implementation，也不把舊 GREEN receipt 升格為可重用 mutation token。
- trusted workflow 必須先部署到 default branch `main` 並 readback，之後才能用於 #617/#671 的 live repair。

Primary regression：`tests/process/test_issue675_legacy_expired_postcommit_recovery.py`。Governance owner：#675。

## BRANCH_CREATE_EXACT_READBACK_AUTO_CONSUME_V1（2026-09-26）

### 事故
#689、#691 都出現同一類停滯：`branch-create` Guard 已 GREEN，branch 也實際建立且 HEAD 正確，但 caller 沒把 action-specific durable readback交回 transaction classifier，就直接送下一顆 commit/write Guard。安全 gate 會正確回 `PENDING_GUARD_TRANSACTION / CONSUME_GUARD_TRANSACTION`，但流程因此卡死；#689 曾用 reactivate/換 claim blob 才繞開，這不應成為常態 recovery。

### 永久規則
- `branch-create` 的 mutation postcondition就是「remote branch 存在於 exact guarded HEAD」，因此 trusted Remote Guard 可直接 fresh-read GitHub branch 作 durable readback。
- 只有 prior exact GREEN receipt 的 issue/worker/source/branch/base/claim blob/head/tested-target 全部仍匹配，且 live branch HEAD exact 等於 receipt head 時，才投影 `mutation_applied=true / reconciled=true / branch_exists=true / branch_head_sha=<exact>`。
- canonical classifier 收到這份 readback後，transaction 直接進 `CONSUMED`；後續 Guard 可正常前進，不要求 caller 另寫 consume marker。
- branch missing、wrong HEAD、identity drift 一律不建立 readback，維持 fail closed。
- 這個 auto-consume **只適用 branch-create**。commit/write/pr-write/qa-dispatch/workflow-dispatch/claim-takeover 仍要原本的 action-specific mutation proof與 coordination reconciliation，不能拿本規則擴張成 generic auto-consume。
- 禁止用 claim reactivate、換 claim blob、重送 Guard 來當 branch-create 的一般恢復流程；那只是 #731 修補前的 bootstrap workaround。

Regression：`tests/process/test_issue731_branch_create_auto_consume.py`。
Focused RED：run `36250856862`。
Focused GREEN：run `36251018227`。



## MAIN_TO_X_BATCH_FIRST_PARITY_V1 — per-fix helper fragmentation

### 事故
#731 修補已進 main 後，第一次處理 main→`cleanup/2d-3d-sync` parity 時，執行者看到兩分支 diverged，立即把問題縮成「只搬 #731」，並另開 per-fix parity helper。這雖然比 blind full-main merge 安全，但漏了更高一層的問題：**沒有先 census 同批 accepted governance changes，也沒有先判斷 bounded batch 是否能一次 non-force 整合**。結果會造成 per-fix helper fragmentation、重複 claim/Guard/QA，以及 main/X governance history 長期碎片化。

### 永久規則
- main→X parity 一律 **batch-first**。
- diverged 只代表要做 BATCH_FEASIBILITY_AUDIT，不代表直接 cherry-pick。
- 先 census eligible accepted governance set，再做 merge-base/overlap/conflict/protected/active-chain audit。
- 安全時一次 bounded non-force batch integration。
- selective compatible-equivalent 是 **fallback only**；必須 durable 記錄 excluded commits/files 與原因。
- 同一 batch 能共用 owner 時，不得預設 one-fix-one-helper。
- blind full-main merge 仍禁止；batch 必須受授權 scope 約束。
- X 更新後不得倒灌 active frozen chains；`FROZEN_X_BASE_SHA` 不變。

Governance owner：#736。Parent parity rule：#692。
## PR_WRITE_EXACT_EVENT_AUTO_CONSUME_V1（2026-09-26）

### 事故
#733 的 PR #734 已 durable 建立／後續已 durable merge，但 `pr-write` GREEN 沒有 action-specific readback，因此下一顆 Guard 被 `PENDING_GUARD_TRANSACTION` 擋住，只能靠 reactivate workaround。

### 永久規則
- **PR existence alone 不足以 consume**，因為 PR 可能在 Guard 前就存在。
- 只接受 exact branch/head/base，且 create/merge/close timestamp 落在 exact GREEN receipt window 的 durable event。
- 多個 exact candidate 固定 ambiguous/fail closed。
- 不使用 `updated_at` 證明 metadata mutation，避免 CI/check/comment 等非目標更新誤消耗 authority。
- metadata-only PR write 在沒有更窄 postcondition 前維持 explicit reconciliation。
- 這條規則只補 `pr-write` durable readback，不放寬 commit/write/dispatch/takeover。

Regression：`tests/process/test_issue739_pr_write_auto_consume.py`。Owner：#739。


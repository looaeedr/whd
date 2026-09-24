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

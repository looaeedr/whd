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

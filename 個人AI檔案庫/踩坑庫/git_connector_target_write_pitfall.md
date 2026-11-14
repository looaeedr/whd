---
whd_doc_role: REFERENCE
whd_contract: git-connector-target-write-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# GitHub Connector 誤寫 production target 踩坑

## 事故模式

在原本意圖只是「建立 branch」或「把已驗證 candidate fast-forward 回 production」時，若誤呼叫 Contents API 的 `create_file` / `update_file` 並把 `branch` 指向 `cleanup/2d-3d-sync` 或 `main`，GitHub 會直接在 production target 建立新 commit。這不是 branch 建立，也不是 integration；即使內容看起來接近預期，仍已違反 root-local-first / exact-tested-diff transport。

## 現行 GitHub 寫入安全邊界／歷史執行路由區分

> **REFERENCE／歷史事故說明**：本檔不擁有 repository 施工、DC、`localX` 或正式 X 發布權限。舊 `WORKSPACE_DEFAULT`、shared-zero、root-local-first 泛用啟動程序是事故背景；**現在先讀 GitHub `ref=localX` exact HEAD 的 `AGENTS.md`、CURRENT Skill 與現行受信任 gate**，不能依 X 的舊 `AGENTS.md` 重新決定工作路線。

1. **現行工作入口以 GitHub `localX` 為準**：純治理／Skill／文件從 `localX` 開工作分支、跑適用治理 CI、PR 合回 `localX`；產品 `/派工` 於 GitHub／雲端執行並經必要產品回歸整合 `localX`。只有當次明確 `/接手` 才可在 RC 授權範圍施工；**治理及產品正式 X 都需使用者當次 `/推推`（即發布驗收決定）、exact SHA 與受信任 gate**，不以 Windows UAT 當額外發布前置，也不授予 DC。
2. **舊路由只作歷史證據**：外部儲存/shared-zero 與 `WORKSPACE_DEFAULT` 曾用來區分舊施工基準；今日不得把它們當作入口、施工或交付前置，也不得藉歷史流程改變 `/推推` 或 localX 邊界。
3. **Contents API 永遠不得直接寫 authoritative production target。** 此處包括 GitHub `localX` 與正式 X 等權威分支： `create_file` / `update_file` / `delete_file` 的 `branch` 只可為本次已授權的 dedicated work branch；禁止指定 `localX`、`cleanup/2d-3d-sync`、`main` 或其他受保護目標。`localX` 一律走已驗證同範圍工作 PR／必要 CI／GitHub 非強制 merge；X 一律依當次 `/推推` 與受信任發布 gate。
4. **寫入前做 target-name denylist + exact-tested-diff check。** target branch、changed-file set、tested HEAD、expected parent/ancestry 任一項不符即 fail closed；不得以「內容看起來一樣」取代 durable identity。
5. **事故後禁止 force rollback。** 先停止 production 寫入；從當前 production HEAD 開 fresh repair branch，恢復已驗證 tree，重新驗證後只用合法 non-force integration 往前修復。
6. **事故必須保留可追溯證據。** 記錄誤寫 commit、repair commit、驗證 RUN、production readback 與 branch cleanup；不可用改史把事故隱藏掉。

## 寫入前檢查表

- 我現在要做的是「內容修改」還是「branch/ref 操作」？
- 是否已讀最新 GitHub `ref=localX` exact HEAD 的 `AGENTS.md`、CURRENT Skill，確認同 Issue 範圍、產品／治理分類、工作分支、必要 CI 與目標 `localX`？禁止用歷史 X／`WORKSPACE_DEFAULT` 決定今天的權限。
- exact tested diff 是否已完成？changed-file set、tested HEAD、fresh target readback 是否一致？
- tool recipient / action 名稱是否與意圖一致？建立 branch 必須是 `create_branch`；移動 non-authoritative branch 才可 `update_ref`；檔案修改才是 `create_file` / `update_file` / `delete_file`。
- production HEAD 是否在寫入前最後一次重新讀取並鎖定？

## 事故復原模板


這條規則的目的不是讓事故看起來沒發生，而是確保事故之後仍保持 non-force、可追溯、可驗證，並阻止同類工具選擇錯誤再次直接落到 production。

## 單次 mutation rejection 的分類規則

- 單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接寫成 permanent `CAPABILITY_BLOCKED`。
- 升級 blocker 前必須 fresh-read：authenticated repo permission、base/target existence、branch existence、matching ruleset/branch protection、exact connector action contract。
- 建新 branch 用 `create_branch(base_sha)`；`update_ref(force=false)` 只移動既有 branch。
- 只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可宣告 permanent capability blocker。
- recovery 不得把一次被拒的 mutation 當停止點；必須 fresh retry 或切換另一條仍合法的 executable leaf。


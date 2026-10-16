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

> **REFERENCE／歷史事故說明**：本檔不擁有 repository 施工位置、DC、localX 或正式 X 發布權限。舊 `WORKSPACE_DEFAULT`、shared-zero、root-local-first 泛用啟動程序只是當時的事故背景；一律以正式 X 的 `AGENTS.md`、對應 CURRENT Skill 與 `tools/change_lane_gate.py` 判定實際路線。

1. **現行執行路線先看正式 X**：純治理白名單在 GitHub／雲端獨立工作分支 PR 直送 X；產品 `/派工` 於 GitHub／雲端施工、測試並交付 `localX`，使用者當次明確 `/接手` 才可於 RC 施工。正式 X 的產品發布仍需當次 `/推推`；本文件不得自行授予任何本機或 DC 權限。
2. **舊路由只作歷史證據**：外部儲存/shared-zero 與 `WORKSPACE_DEFAULT` 曾用來區分舊施工基準；今日不得把它們當作入口、施工或交付前置，也不得藉歷史流程改變 `/推推` 或 localX 邊界。
3. **Contents API 永遠不得直接寫 authoritative production target。** `create_file` / `update_file` / `delete_file` 的 `branch` 只能是 dedicated non-authoritative work/delivery branch，不得是 `cleanup/2d-3d-sync`、`main` 或其他 authoritative target。
4. **寫入前做 target-name denylist + exact-tested-diff check。** target branch、changed-file set、tested HEAD、expected parent/ancestry 任一項不符即 fail closed；不得以「內容看起來一樣」取代 durable identity。
5. **事故後禁止 force rollback。** 先停止 production 寫入；從當前 production HEAD 開 fresh repair branch，恢復已驗證 tree，重新驗證後只用合法 non-force integration 往前修復。
6. **事故必須保留可追溯證據。** 記錄誤寫 commit、repair commit、驗證 RUN、production readback 與 branch cleanup；不可用改史把事故隱藏掉。

## 寫入前檢查表

- 我現在要做的是「內容修改」還是「branch/ref 操作」？
- 是否已依正式 X 的 `AGENTS.md` 確定產品／治理分類、實際施工權限與交付目標？不要從歷史 外部儲存/shared-zero／`WORKSPACE_DEFAULT` 流程推導今日權限。
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


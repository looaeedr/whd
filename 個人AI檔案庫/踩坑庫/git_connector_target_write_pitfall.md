---
whd_doc_role: REFERENCE
whd_contract: git-connector-target-write-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# GitHub Connector 誤寫 production target 踩坑

## 事故模式

在原本意圖只是「建立 branch」或「把已驗證 candidate fast-forward 回 production」時，若誤呼叫 Contents API 的 `create_file` / `update_file` 並把 `branch` 指向 `cleanup/2d-3d-sync` 或 `main`，GitHub 會直接在 production target 建立新 commit。這不是 branch 建立，也不是 integration；即使內容看起來接近預期，仍已違反 Branch-First。

## 硬規則

1. **所有內容修改先建 fresh work branch。** Contents API 的 `branch` 參數只能是本輪 work/QA/docs branch，不得是 production target。
2. **production integration 禁用 Contents API。** 已驗證 candidate 要進 `cleanup/2d-3d-sync` 時，只能先雙重鎖定 target HEAD / candidate ancestry，再用 `update_ref(force=false)` 或等價 non-force integration。
3. **寫入前做 target-name denylist。** 若 action 是 `create_file` / `update_file` / `delete_file`，且 branch 是 `cleanup/2d-3d-sync`、`main` 或其他 authoritative target，必須 fail closed。
4. **不要把『內容相同』當成歷史正確。** integration 前後都要讀回 commit SHA、parent/ancestry 與 tree SHA；若 candidate tree 已驗證，repair tree 應以相同 tree SHA 作為強證據。
5. **事故後禁止 force rollback。** 先停止 production 寫入；從當前 production HEAD 開 fresh repair branch，移除誤加內容、恢復已驗證 tree，重新驗證後只用 non-force fast-forward 往前修復。
6. **事故必須保留可追溯證據。** 記錄誤寫 commit、repair commit、驗證 RUN、production readback 與 branch cleanup；不可用改史把事故隱藏掉。

## 寫入前檢查表

- 我現在要做的是「內容修改」還是「branch/ref 操作」？
- 若是內容修改：fresh branch 是否已存在且已反讀 HEAD？
- 若是 integration：是否明確使用 `update_ref(force=false)`，而不是 Contents API？
- tool recipient / action 名稱是否與意圖一致？建立 branch 必須是 `create_branch`；移動 branch 必須是 `update_ref`；檔案修改才是 `create_file` / `update_file` / `delete_file`。
- production HEAD 是否在寫入前最後一次重新讀取並鎖定？

## 事故復原模板

`STOP_PRODUCTION_WRITES → READ_CURRENT_TARGET → FRESH_REPAIR_BRANCH → RESTORE_VERIFIED_TREE → VERIFY_TREE_SHA → RUN_ACCEPTANCE → UPDATE_REF(force=false) → POST_MERGE_READBACK → CLEAN_TEMP_REFS`

這條規則的目的不是讓事故看起來沒發生，而是確保事故之後仍保持 non-force、可追溯、可驗證，並阻止同類工具選擇錯誤再次直接落到 production。

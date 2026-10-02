---
whd_doc_role: REFERENCE
whd_contract: git-connector-target-write-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# GitHub Connector 誤寫 production target 踩坑

## 事故模式

在原本意圖只是「建立 branch」或「把已驗證 candidate fast-forward 回 production」時，若誤呼叫 Contents API 的 `create_file` / `update_file` 並把 `branch` 指向 `cleanup/2d-3d-sync` 或 `main`，GitHub 會直接在 production target 建立新 commit。這不是 branch 建立，也不是 integration；即使內容看起來接近預期，仍已違反 root-local-first / exact-tested-diff transport。

## 硬規則

1. **所有 repository-content 修改先走 canonical root-local-first。** 在 `/Google Drive/WHD/work/active/...` 完成 mutation、tests、diff freeze；只有 `GIT_WRITE_UNLOCKED` 後才從 fresh target 建 dedicated work branch。Contents API 的 `branch` 參數只能是該 work branch，不得是 production target。
2. **production integration 禁用 chat/runtime Contents API 與 `update_ref`。** 已驗證 candidate 要進 `cleanup/2d-3d-sync` 時，必須回到 Flow v2 trusted `MERGE / SYNC_TARGET` transport；`update_ref(force=false)` 只可用於 non-authoritative dedicated work branch，不能前推 production target。
3. **寫入前做 target-name denylist。** 若 action 是 `create_file` / `update_file` / `delete_file`，且 branch 是 `cleanup/2d-3d-sync`、`main` 或其他 authoritative target，必須 fail closed。
4. **不要把『內容相同』當成歷史正確。** integration 前後都要讀回 commit SHA、parent/ancestry 與 tree SHA；若 candidate tree 已驗證，repair tree 應以相同 tree SHA 作為強證據。
5. **事故後禁止 force rollback。** 先停止 production 寫入；從當前 production HEAD 開 fresh repair branch，移除誤加內容、恢復已驗證 tree，重新驗證後只用 non-force fast-forward 往前修復。
6. **事故必須保留可追溯證據。** 記錄誤寫 commit、repair commit、驗證 RUN、production readback 與 branch cleanup；不可用改史把事故隱藏掉。

## 寫入前檢查表

- 我現在要做的是「內容修改」還是「branch/ref 操作」？
- 若是內容修改：canonical root mutation/tests/freeze 是否完成，且 `GIT_WRITE_UNLOCKED` receipt 是否已成立？
- 若是 integration：是否已回到 Flow v2 trusted `MERGE / SYNC_TARGET`，而不是 chat/runtime Contents API / `update_ref`？
- tool recipient / action 名稱是否與意圖一致？建立 branch 必須是 `create_branch`；移動 branch 必須是 `update_ref`；檔案修改才是 `create_file` / `update_file` / `delete_file`。
- production HEAD 是否在寫入前最後一次重新讀取並鎖定？

## 事故復原模板

`STOP_PRODUCTION_WRITES → READ_CURRENT_TARGET → RETURN_TO_ROOT_WORKSPACE → RESTORE_VERIFIED_TREE → RUN_ACCEPTANCE → ROOT_DIFF_FROZEN → GIT_WRITE_UNLOCKED → DEDICATED_REPAIR_BRANCH → FLOW_V2_MERGE_OR_SYNC_TARGET → POST_MERGE_READBACK → CLEAN_TEMP_REFS`

這條規則的目的不是讓事故看起來沒發生，而是確保事故之後仍保持 non-force、可追溯、可驗證，並阻止同類工具選擇錯誤再次直接落到 production。

## 單次 mutation rejection 的分類規則

- 單次 connector/runtime mutation rejection 先標 `RETRYABLE_UNCLASSIFIED`，不得直接寫成 permanent `CAPABILITY_BLOCKED`。
- 升級 blocker 前必須 fresh-read：authenticated repo permission、base/target existence、branch existence、matching ruleset/branch protection、exact connector action contract。
- 建新 branch 用 `create_branch(base_sha)`；`update_ref(force=false)` 只移動既有 branch。
- 只有所有合法 transport 都有 fresh durable evidence 證明 unavailable/forbidden，才可宣告 permanent capability blocker。
- recovery 不得把一次被拒的 mutation 當停止點；必須 fresh retry 或切換另一條仍合法的 executable leaf。


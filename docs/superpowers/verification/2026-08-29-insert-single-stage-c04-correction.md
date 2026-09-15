# 2026-08-29 INSERT 單級拓撲 / linked-FW C04 修正驗證

## 問題

使用者指出 `16×23` 不可能是正確第一級截角，並進一步指出純「嵌入 INSERT」不應存在二級截角。

## 根因

1. `CornerTypeSelection(INSERT)` 可殘留 `secondary_retain_t` / `secondary_depth_t`，資料模型允許非法「單級語意 + 二級參數」狀態。
2. `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1` 曾錯把 3D 候選 band 升格為公式：`primary_u=side+0.5T`、`secondary_u=side-0.5T`。
3. 2026-08-21 已認證 C04 契約早已明定：第一級 X=`side_fold+FW`；第二級 CUTTING=`side_fold+0.5T`；深度=`2T`。後來的 3D 候選不得覆寫此已知公式。

## 修正

- INSERT / OVERLAY / CROSS 一律清除 secondary 參數；只有 INSERT_OVERLAY 可保存二級參數。
- Registry lookup 強制驗證 `topology_levels` 與 evaluator 實際輸出的 stage count；INSERT/OVERLAY 必須 1 級、INSERT_OVERLAY 必須 2 級。
- linked-FW INSERT_OVERLAY 改回既有 C04 公式：
  - `primary_u = side_fold + FW`
  - `primary_v = FW - 1T`（無獨立 ytop1）
  - `secondary_u = side_fold + 0.5T`
  - `secondary_depth = 2T`
- `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1` 改為 `CERTIFIED`，證據來源為既有 C04 製造契約，不再是錯誤 3D 候選。

## 實檔結果

`自訂(10).p6fold`, T=2, side_fold=15, FW=25：

- 原 INSERT_OVERLAY：Head/Tail = `40×23 + 16×4`，rule=`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`，trust=`CERTIFIED`，shadow residual pair count=0。
- 同檔切換純 INSERT：Head/Tail = `38×27`，`secondary_u=None`、`secondary_depth=None`。
- INSERT 存檔 raw top corner 不含 `secondary_retain_t` / `secondary_depth_t`；Reload 後仍為單級。
- INSERT_OVERLAY Save/Reload 後 rule/revision/trust 與 canonical material 一致；main 2D vs assembly symmetric difference area=0。

## 防退化

新增測試：
- `test_insert_canonicalization_strips_illegal_secondary_parameters`
- `test_insert_raw_state_cannot_preserve_secondary_parameters`
- `test_registry_rejects_insert_result_that_invents_second_stage`
- `test_user10_insert_overlay_without_ytop_fold_treats_cut_boundary_skin_crossings_as_contact` 更新正確 C04 fixture。

# Phase6 FinalScene View 驗證報告

## 範圍

本輪把 `fold_designer_bridge.py` 中 FinalScene 3D 顯示實作收斂到 `phase6_final_scene_view.py`。Bridge 保留 manufacturing query、active draft profile adapter 與 operator 數值解析；View 只消費已解析 `PartRenderData`。

## Ownership 驗證

- `phase6_final_scene_view.py` 不含：
  - `build_part_render_data(`
  - `material_polygon_from_final_scene(`
  - `fold_guides_from_final_scene(`
  - `CornerTypeId`
  - `SettingsService`
  - `ProjectSession`
- `fold_designer_bridge.py` 不再實作：
  - profile geometry / fold map
  - triangulation
  - mesh boundary
  - BEND / MARKING projection
  - Matplotlib 3D axis fit / viewport / zoom
- `Bridge` 只建立 `FinalSceneViewRequest`，`Phase6FinalSceneView.render()` 直接使用 `request.render_data.material / scene / fold_guides`。
- 實際 designer 的 `_phase6_zoom_scale / _phase6_last_cutting_mesh / _phase6_last_cutting_material / _phase6_cutting_mesh_error` 為 compatibility property，backing state 只存在 `final_scene_view`。

Ownership 專屬測試：`5 passed`。

## 功能回歸

### 聚焦 3D

`87 passed`。

涵蓋：

- Final material hole → 3D mesh hole 不回填。
- finite BEND fold guide。
- retained corner fold ownership。
- BEND / MARKING / BLIND_HOLE 投影。
- operator finished dimensions。
- rectangular 3D viewport。
- scroll zoom。
- legacy renderer 不執行。
- editor Fold Profile 直接送 View，不從 BEND linework 重建 profile。

### 原始完整 suite

`303 passed, 2 skipped, 4 failed`

4 個 failure 全部是既有環境缺件 `/mnt/data/自訂.p6fold`：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

### 明確排除上述 4 個外部 fixture

`304 passed, 2 skipped, 4 deselected, 0 failure`

## 程式結構結果

- 修改前 `fold_designer_bridge.py`：4685 行。
- 修改後：4118 行。
- 減少：567 行。
- 新增 `phase6_final_scene_view.py`：FinalScene View 深模組。

重點不是行數，而是 Bridge 已不需要知道 Matplotlib mesh / triangulation / axis / zoom implementation。

## config.ini

未修改。

SHA256：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`

# 2026-08-23 EndCap 最終幾何唯一所有權驗證

## 驗證範圍

本文件驗證 `docs/superpowers/specs/2026-08-23-resolved-part-geometry-ownership-design.md` 的第一階段 EndCap 收斂：CornerType → Fold Profile → AE resolver → structural → Final Scene → PartRenderData → 2D/3D/DXF。

## 已驗證不變量

1. Head/Tail 上方 CornerType 由 `EndCapAssemblySemantics` 唯一解析裝配機械語意。
2. `endcap_outer_thickness_factor()` 共用同一 resolver，不再維護第二套判斷。
3. Fold Profile → effective scalar fold 只在 `resolve_endcap_request()` 解析。
4. 有 CornerType policy 時，profile 不得改變 CornerType 固有 X topology；雙向 stale profile 都會被 AE resolver 丟棄。
5. unknown／baseline stretched structural builder 都接收 resolved `x_topology`，不自行判斷 OVERLAY。
6. `OVERLAY W=400` 的 Head/Tail material 與 DXF CUTTING X span 均為 400，無左右 X BEND。
7. `generate_part()` EndCap 共用 `build_part_render_data()` Final Scene，不走 legacy exporter bypass。
8. 單軸 Fold Profile 只覆寫同軸 BEND。
9. 基準檔 CornerType topology 改變時，不再用 polygon vertex index 強配；synthetic baseline OVERLAY 測試可完成且 effective X folds = 0/0。
10. `fold_designer_bridge.py` 未取得 Final Scene／PartRenderData ownership。

## 測試證據

- `tests/test_endcap_resolved_geometry_ownership.py`：`20 passed`。
- 聚焦回歸（排除四個外部缺件 fixture）：`161 passed, 2 skipped, 4 deselected`。
- 全套原始回歸：`259 passed, 2 skipped, 4 failed`。四個 failure 都是 `FileNotFoundError: /mnt/data/自訂.p6fold`，與修改前基線相同。
- 全套排除上述四項：`259 passed, 2 skipped, 4 deselected`，0 failure。
- `py_compile`：通過。
- Bridge ownership guard：`OK`。
- `config.ini` SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，與修改前一致。

## 已知環境限制

交付容器沒有 `/mnt/data/自訂.p6fold`，因此四個硬編碼該外部檔案的歷史 regression 無法執行。未用自造資料假裝取代該真檔 fixture；其餘可執行測試全部為 0 failure。

## Git 狀態

此 FULL 副本沒有 `.git` metadata，因此本輪無 commit、branch merge 或 PR；交付證據以差異、測試與 ZIP 完整性驗證為準。

# Box Body Assembly BEND Solid-Line Verification

## 問題
組合體中的封頭／封尾已有 physical-sheet crease 實線，但箱身只有 mesh 外框，authoritative BEND 沒有顯示。

## 根因
`phase6_final_scene_view.py` 的 assembly path 對 `box_body` 未呼叫任何 scene BEND overlay。若直接以 BEND 線自己的 bounds 呼叫 assembly placement，又會因 centering reference 不同而錯位。

## 修正
- `ae_engine/assembly_geometry.place_assembly_points(points, reference_triangles, ...)`：任意 local 3D points 使用完整 reference folded mesh 的 bbox/placement。
- `place_assembly_triangles()` 改委派同一 point transform。
- `Phase6FinalSceneView._draw_assembly_box_body_bends()`：從 Box Body `PartRenderData.scene` 取 BEND，依 Fold Profile 映到 local 3D，再共用 assembly point transform，固定 `linestyle='-'`。

## TDD 證據
新增 `test_assembly_box_body_draws_authoritative_bend_guides_as_solid_lines`。
- 修正前：FAIL，`assembly Box Body must render its authoritative BEND guide`。
- 修正後：PASS。

## Fresh regression
`xvfb-run -a pytest -q tests/test_phase6_final_scene_view_ownership.py tests/test_phase6_assembly_3d_view.py tests/test_assembly_collision_integration.py tests/test_phase6_3d_single_source_renderer.py tests/test_phase6_3d_view_regressions.py`

結果：`59 passed`。

## 真 GUI 自檢
從 201653 FULL 工作副本啟動正式 `gui.py -> open_original_fold_designer()`：
- `part_var = 組合體`
- `_phase6_3d_display_mode = assembly`
- `renderer.ax3d.lines = 8`
- 8 條皆 `color=#2563eb`、`linestyle=-`、`linewidth=1.35`
- 實際輸出圖 `/mnt/data/boxbody_bend_actual.png` 可看到箱身左右與上下折彎實線。

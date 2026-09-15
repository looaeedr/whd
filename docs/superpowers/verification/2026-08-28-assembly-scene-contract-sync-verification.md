# Assembly Scene Contract Sync Verification

## 問題
使用者實機畫面：`AssemblySceneRenderData.__init__() got an unexpected keyword argument 'show_interference'`。

## 根因重現
- Base: `PHASE6_ENDCAP_HOLE_RIM_SOLID_BEND_FULL_20260828_065113.zip`
- Overlay: `PHASE6_3D_BACKPROJECTED_RELIEF_UPDATE_20260828_130705.zip`
- 結果：`test_bridge_assembly_display_request_queries_only_boxbody_head_tail` 失敗，錯誤與實機完全相同。
- 主 GUI `gui.BoxCalculatorGUI -> open_original_fold_designer()`：`designer.final_scene_view.cutting_mesh_error` 同樣為 unexpected keyword。

## 修正
- `fold_designer_bridge._phase6_make_assembly_scene_render_data()` 對 live constructor signature 過濾 optional kwargs。
- 新 UPDATE 強制同步 `phase6_final_scene_view.py`。
- 新增 legacy constructor regression。

## 修後證據
- 同一個 065113+130705 混版副本覆蓋修正後：
  - exact regression + backward compatibility: `2 passed`
  - assembly/final-scene/layout focused suite: `31 passed`
  - 主 GUI：`cutting_mesh_error=None`
  - 初始 `part_var=組合體`
  - `_phase6_3d_display_mode=assembly`
  - `last_cutting_mesh=1438 triangles`

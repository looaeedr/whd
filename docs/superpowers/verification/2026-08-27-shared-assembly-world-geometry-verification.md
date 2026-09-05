# Shared Assembly World Geometry Verification

## 目的

把原先只存在於 `phase6_final_scene_view.py` 的折彎 mesh 與組合 placement，收斂成 AE/manufacturing 可共同使用的純幾何 Source of Truth，讓 Box Body 與 EndCap/Tail 可以先被折起並放進同一套世界座標；本階段不宣稱已完成真正 3D collision → 2D relief 反投影。

## 實作範圍

- 新增 `ae_engine/assembly_geometry.py`
  - `folded_mesh_from_polygon()`：由 authoritative 2D material + Fold Profile + final BEND guides 建立 local folded mesh。
  - `place_assembly_triangles()`：將 local folded mesh 放入共用 cabinet world coordinates。
  - `folded_world_mesh_from_render_data()`：直接由 `PartRenderData` 建立 world mesh。
- `phase6_final_scene_view.py`
  - `_phase6_folded_mesh_from_polygon()` 改為 compatibility wrapper，委派共享 folding。
  - `_phase6_place_assembly_triangles()` 改為 compatibility wrapper，委派共享 placement。
- `ae_engine/assembly_collision.py`
  - 新增 `BoxBodyEndCapWorldMeshes`。
  - 新增 `assemble_boxbody_endcap_world_meshes()`。
  - 新增 `assemble_boxbody_endcap_render_meshes()`，可直接將 Box Body / EndCap authoritative render data 與 Fold Profile 組成同一世界座標 mesh。

## TDD 證據

新增測試先確認 RED：

- `test_boxbody_endcap_world_meshes_share_one_assembly_coordinate_system`
  - 初始失敗：`assemble_boxbody_endcap_world_meshes` 不存在。
- `test_phase6_assembly_placement_delegates_to_shared_engine`
  - 初始失敗：`ae_engine.assembly_geometry` 不存在。
- `test_boxbody_endcap_render_data_can_be_folded_into_same_world_assembly`
  - 初始失敗：`assemble_boxbody_endcap_render_meshes` 不存在。

完成最小實作後上述測試轉為 PASS。

## Fresh Verification

### 聚焦 collision + 3D regression

```text
xvfb-run -a python -m pytest -q \
  tests/test_assembly_collision.py \
  tests/test_assembly_collision_integration.py \
  tests/test_phase6_assembly_3d_view.py \
  tests/test_phase6_final_scene_view_ownership.py \
  tests/test_phase6_3d_cutting_mesh.py \
  tests/test_phase6_3d_operator_view.py \
  tests/test_phase6_3d_retain_and_baseline.py \
  tests/test_phase6_3d_single_source_renderer.py \
  tests/test_phase6_3d_view_regressions.py \
  tests/test_phase6_shared_assembly_and_dimensions.py
```

結果：`98 passed`。

### Folding 等價驗證

以修改前備份 `BACKUP/20260827-212514-phase6_final_scene_view.py` 與新共享 folding，對同一組 90 度 X/Y Fold Profile 和同一 material 比較：

```text
old_triangles 18
new_triangles 18
identical True
```

### Compile

```text
python -m py_compile ae_engine/assembly_geometry.py ae_engine/assembly_collision.py phase6_final_scene_view.py tests/test_assembly_collision.py tests/test_phase6_assembly_3d_view.py
```

結果：exit code 0。

## 已知既有失敗

擴大到 `tests/test_phase6_box_body_structure.py` 時有 4 個 GUI 測試失敗，內容是目前 UI 已沒有測試期待的 `箱身結構` / `🔓 解鎖結構` 控件。將 `phase6_final_scene_view.py` 暫時還原成修改前備份後，完全相同的 4 個測試仍失敗，因此判定為本次 shared assembly geometry 之前就存在的測試/介面落差，不由本次修改處理。

## 邊界

目前完成的是：

```text
PartRenderData + Fold Profile
        ↓
shared folded mesh
        ↓
shared assembly world coordinates
        ↓
Box Body + EndCap/Tail 真正處於同一空間座標
```

尚未完成：

```text
world mesh / simplified solid collision
        ↓
collision region
        ↓
EndCap local/unfolded inverse projection
        ↓
2D CUTTING relief
```


## 組合體 UI 可見性修正

原先 assembly mode 雖已存在，但入口仍是 Menubutton，不能把「底層 mode 存在」當成使用者已看得到。2026-08-27 後改為 3D 置頂列固定顯示兩顆按鈕：

```text
3D顯示： [單件] [組合體]
```

TDD 新增 `test_3d_control_bar_exposes_single_and_assembly_as_separate_buttons`，先確認舊版 RED，再改為直接可見按鈕。

真 Tk 驗證：

```text
single_text= 單件
assembly_text= 組合體
single_manager= pack
assembly_manager= pack
single_viewable= 1
assembly_viewable= 1
mode_after_invoke= assembly
assembly_state_after= disabled
```

第一階段 assembly render query 僅抓 `box_body / head / tail`，不混入 door / base plate。


### Regression RED/Green

新增真 Tk 測試 `test_real_tk_3d_display_buttons_are_visible_and_switch_to_assembly` 後，將 `fold_designer_bridge.py` 暫時切回使用者原始 ZIP 版本：

```text
AttributeError: Phase6FoldDesignerApp has no attribute display_single_button
Did you mean: display_3d_choice_button?
```

確認測試能抓到舊版「組合體藏在 Menubutton」問題；恢復修正版後同一測試 PASS。

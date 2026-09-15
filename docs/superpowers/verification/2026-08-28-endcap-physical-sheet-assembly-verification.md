# 2026-08-28 EndCap 組合體實體板成型驗證

## 問題
標準金庫型 Head/Tail Fold Profile 與 BEND 數量完整，但組合體只渲染零厚度 mid-surface，且直接以 `z=0` 中心面作 mating datum，造成外側成型面視覺上消失、折邊像由箱內往外穿。

## Source of Truth
- `phase6_fold_profiles.py`：折法 / BEND topology；標準未修改金庫型不得因本修正增刪折段。
- `ae_engine/assembly_geometry.py::folded_mesh_from_polygon()`：折後 mid-surface。
- `ae_engine/assembly_geometry.py::thicken_triangle_surface()`：由 mid-surface + T 產生 physical sheet 內外 skin、外周側壁與 fold-edge bridge。
- `ae_engine/assembly_geometry.py::place_endcap_against_box_body()`：Head/Tail mating center-plane offset；內側 skin 接觸箱身。
- `phase6_final_scene_view.py` 與 `ae_engine/assembly_collision.py`：共同消費上述 physical sheet geometry。

## 已鎖定語意
- local `z=0` = 板厚中心面，不是實體接觸面。
- local `+z` = EndCap 折邊朝箱內方向。
- Head：中心面位於箱身上緣外側 `T/2`；內側 skin 貼上緣，外側 skin 位於箱外。
- Tail：保持 native X/Y orientation；中心面位於箱身下緣外側 `T/2`；內側 skin 貼下緣，外側 skin 位於箱外。
- 標準金庫型 Head/Tail 仍為 X 2 折 + Y 3 折，共 5 BEND；本修正不改 2D / DXF / Fold Profile。

## TDD
- RED：`thicken_triangle_surface` 不存在；physical mating API 不接受 `sheet_thickness`；assembly viewer 未傳 T、未實體化。
- GREEN：新增 sharp-bend physical sheet solid 與 T/2 mating offset；viewer/collision 共用。

## 相關測試
- `tests/test_assembly_collision.py`
  - physical sheet 兩面 + 外周側壁。
  - Head/Tail inner skin 貼箱身、outer skin 在箱外。
  - shared collision world mesh 可要求 physical EndCap sheet。
- `tests/test_phase6_assembly_3d_view.py`
  - assembly viewer 將 request.thickness 傳入 mating 並實際 thicken Head/Tail。

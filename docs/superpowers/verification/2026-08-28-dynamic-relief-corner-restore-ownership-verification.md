# Dynamic Relief Corner Restore Ownership Verification

## 問題
`200245 FULL` 的 world-backprojected relief solver 使用完整 rectangular restored blank 作最終材料，造成沒有參與本輪求解的兩個 legacy corners 也被補回，組合體看起來多出兩片角料。

## 根因證據
標準 W400/H600/D250/T2/FW25：
- Head solved-original = 527.9999999 mm²
- Tail solved-original = 528.0 mm²
- 每片包含兩個錯誤 `16×16 = 256 mm²` 角片 + 兩個正確 `2×4 = 8 mm²` 留肉。

## 修正
`solve_world_backprojected_endcap_relief()` 最終 material 從 authoritative original material 起算，只 union 回 `raw_cuts` 實際求解角所屬的 restored delta component，再扣除 verified cut。完整 restored blank 只留作 3D probe/reference。

## TDD
新增 `test_world_backprojected_relief_restores_only_the_two_solved_mating_corners`：
- 修正前 FAIL：added area = 528 mm²。
- 修正後 PASS：added area = 16 mm²。
- Head 新增材料只在下方 mating corner band；Tail 只在上方 mating corner band。

## 回歸
Assembly/collision focused tests 新增測試通過。廣泛 Manufacturing suite 仍有 6 個既有 fixture/policy failures；在未修改 `200245 FULL` 跑同一批亦為相同 6 個 failure，非本輪造成。

## Fresh focused verification
`pytest -q tests/test_assembly_collision.py tests/test_assembly_collision_integration.py tests/test_phase6_assembly_3d_view.py tests/test_phase6_final_scene_view_ownership.py tests/test_phase6_shared_assembly_and_dimensions.py`

結果：`98 passed / 0 failed`。

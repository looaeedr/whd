# Phase6 參數解鎖右側面板可見性驗證

## 問題

`參數鎖定` 按鈕在組合體模式可切換 state，但右側「組合體診斷」肉眼無法看到。舊測試只驗 `winfo_manager()==pack`，因此未捕捉實際 1×1 geometry。

## 根因

Matplotlib canvas 先以 `pack(fill=BOTH, expand=True)` 佔滿右側；diagnostics/settings 後 pack 時沒有保證位於 canvas 前方。Tk manager 顯示 `pack` 不代表 widget 實際可見。

## 修正

- 新增 `_phase6_pack_right_panel_above_canvas(self, widget)`。
- diagnostics/settings 顯示統一使用 `pack(before=canvas_widget, side=TOP, fill=X, ...)`。
- assembly -> single part 切換亦走同一 helper。
- 真操作測試使用 `parameter_lock_button.invoke()`，驗 `winfo_viewable()` 與實際高度。

## Fresh verification

```text
pytest:
  test_parameter_lock_button_invoke_makes_assembly_panel_actually_visible
  test_parameter_unlock_then_select_box_body_shows_real_part_settings
=> 2 passed

focused 3D/layout suite:
  test_phase6_latest_layout_contract.py
  test_phase6_assembly_3d_view.py
  test_phase6_final_scene_view_ownership.py
  test_phase6_shared_assembly_and_dimensions.py
  test_phase6_3d_single_source_renderer.py
=> 87 passed / 0 failure
```

驗證不依賴 screenshot/mainloop；使用 Xvfb + Tk `invoke/update/geometry introspection`。

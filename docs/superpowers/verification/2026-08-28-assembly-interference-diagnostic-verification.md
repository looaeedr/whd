# 2026-08-28 組合體干涉診斷驗證

## 範圍
- 修正第一次進組合體後「參數解鎖」無可見反應。
- 組合體診斷可忽略固定 exterior corner relief，但不修改生產 CUTTING / DXF。
- 顯示固定截角 **relief delta** 與 BoxBody physical sheet 的局部非共面穿越區。

## RED
- 組合體解鎖時不存在 `assembly_diagnostics_frame`。
- 無 `restore_unrelieved_endcap_material()`。
- 無 `detect_world_mesh_surface_interference()`。

## GREEN
- 真 Tk：組合體解鎖後 diagnosis frame 顯示、一般 settings center 維持隱藏；切到箱身後 diagnosis frame 隱藏且板件 settings 顯示。
- 未退讓 material：exterior notch 被補回，hole interior 保留。
- world mesh：非共面 crossing 產生 intersection segment；disjoint / coplanar mating contact 不產生。
- ownership：`phase6_final_scene_view.py` 不直接 import `assembly_collision`。
- 早期整片 EndCap probe 的 947 段結果已判定不合格：包含正常 mating seam 假紅。
- 修正後固定截角 probe = `restored - production`；標準金庫型真 GUI 為 **454 段局部交線（Head 227 + Tail 227）**、166 個命中 delta triangles，本測試環境單次重算約 0.9 s。
- AI 已自行檢查 Head / Tail 兩個視角：紅色半透明區與紅色實線只集中固定截角角落，未沿正常長接縫擴散。
- 關閉 `診斷時忽略固定截角` 後 detector 不執行，畫面無紅區，狀態提示先啟用該診斷。

## 回歸
```text
185 passed（assembly / collision / 3D / UI ownership fresh regression）
```

另以未修改 071002 FULL 對照確認 `test_phase6_settings_panel_ownership.py` 仍有 2 個既有舊測試失敗（advanced 預設狀態、已移除 draw_stock），本輪未新增。
相關測試：layout / assembly 3D / assembly collision / collision integration / shared assembly dimensions / FinalSceneView ownership / EndCap resolved ownership / corner semantics。

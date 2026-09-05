# 2026-08-29 EndCap 單級 INSERT 38×27 / 2D-3D-Assembly 同步驗證

## 範圍
- 修正 EndCap/Tail 單級 `INSERT` 將 physical skin contact 誤算為 penetration 的問題。
- 保持單級 topology，不允許迭代 union 長出第二級階梯。
- 確保主 2D、單板 3D、組合圖與尺寸標註共用 canonical Manufacturing geometry。
- 保留上一輪 UI：組合圖板件顯示勾選、組合左側全部截角尺寸、各板件 2D/3D 截角尺寸、「回2D截角」。

## 使用者實檔證據
Fixture：`/mnt/data/自訂(9).p6fold`。

Fresh runtime 結果：
- `errors = {}`。
- Head `verified=True`：bottom_left = `38×27`、bottom_right = `38×27`，無 secondary stage。
- Tail `verified=True`：top_left = `38×27`、top_right = `38×27`，無 secondary stage。
- GUI 組合診斷字串：`實際截角尺寸：封頭：38×27；封尾：38×27`。
- 主 2D authoritative Head material vs assembly Head material：`symmetric_difference.area = 0.0`。
- 主 2D authoritative Tail material vs assembly Tail material：`symmetric_difference.area = 0.0`。

## 根因證據
同一單級 INSERT mating corner 的 ±T/2 physical skins 回投影可落在真實 mating boundary 兩側，實檔約為 `37.02` 與 `38.98`。舊求解若取外側 extrema，會產生約 `38.98×27`，顯示成 `39×27`；若單板 3D relief state 回退 legacy fixed geometry，則曾顯示 `40×27`。

真正製造邊界必須由折後 mating geometry 回投影，本案為 `38.00×27.00`。禁止以 UI rounding 或固定 `-0.5T` 補償假裝修正。

## Fresh focused regression
執行：
```text
xvfb-run -a python -m pytest -q \
  tests/test_assembly_collision_integration.py \
  tests/test_phase6_assembly_3d_view.py \
  tests/test_phase6_corner_dimension_controls.py \
  tests/test_phase6_latest_layout_contract.py \
  tests/test_phase6_return_2d_corner.py
```
結果：`46 passed / 0 failed`（僅 headless font glyph warnings）。

核心 38 regression：`tests/test_assembly_collision_integration.py::test_deleted_fold_insert_relief_keeps_single_stage_topology_across_iterations`，要求 Head/Tail 左右角 `primary_u=38`、`primary_v=27`、secondary 為 None，且 solution verified。

## 資料契約
1. contact ≠ penetration；normal skin contact 不得產生 relief。
2. 單級 INSERT solver 只改尺寸，不改 topology。
3. verified relief 先 commit canonical state，再由 Manufacturing API 重建 2D/3D/DXF。
4. 尺寸文字量 canonical final material，不讀 legacy fixed relief。
5. 組合圖 visibility checkbox 僅控制 renderer，不改 production geometry。
6. `38×27` 只作本實檔 regression evidence，不得硬編碼。

## 文件同步 Gate
本輪同步更新：
- `AI_HANDOFF.md`
- `CONTEXT.md`
- `DELIVERY_README.md`
- `目前主要任務.md`
- `截角類型.md`
- `修改日誌/20260829.md`
- `個人AI檔案庫/README.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `docs/superpowers/specs/2026-08-28-assembly-relief-backprojection-design.md`
- `docs/superpowers/specs/2026-08-28-live-canonical-2d-3d-sync-design.md`
- 本文件。

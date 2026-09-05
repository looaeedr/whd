# Assembly Relief Backprojection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 將 Box Body ↔ EndCap/Tail 的真實 3D 干涉精確反投影為可量測、可套用且可回折驗證的 2D 截角尺寸。

**Architecture:** `assembly_geometry.py` 提供保留 flat UV 的折彎三角形與 shared world transform；`assembly_collision.py` 擁有 3D→2D backprojection、corner cut polygon、尺寸解析、A clearance 與回折驗證；GUI 只顯示 solver 結果。Viewer 不擁有製造公式。

**Tech Stack:** Python, Shapely, NumPy, Tkinter, Matplotlib, pytest

**Spec:** `docs/superpowers/specs/2026-08-28-assembly-relief-backprojection-design.md`

## Global Constraints

- Box Body=RETAIN；EndCap/Tail=CUT。
- Fold Profile / BEND / holes / CornerType 仍以 Manufacturing API 為 Source of Truth。
- 不修改 `config.ini`。
- 所有文字 UTF-8；交付 ZIP 不得出現 `#Uxxxx`。
- TDD：production code 前先看見新測試正確失敗。

---

### Task 1: UV-aware folded geometry

**Files:**
- Modify: `ae_engine/assembly_geometry.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Produces: `FoldedTriangleMap(flat, local)`、`MappedSkinTriangle(flat, world)`、`folded_mesh_with_flat_uv_from_polygon(...)`、`endcap_world_skin_with_flat_uv(...)`。

- [x] 寫失敗測試：90° fold 後 triangle 的 flat UV 不變，world skin 仍能對回原 2D 座標。
- [x] 執行該測試確認 RED。
- [x] 抽出與 `folded_mesh_from_polygon` 共用的 triangulation/fold mapping，回傳 UV-aware triangles。
- [x] 產生 ±T/2 skin triangles 並保留 flat UV。
- [x] 執行測試確認 GREEN。

### Task 2: 3D intersection backprojection

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Produces: `FlatInterferenceProjection(segments_2d, points_2d, pair_count)`、`backproject_world_interference_to_endcap_flat(...)`。

- [x] 寫失敗測試：已知 target triangle 上的 world 交線，barycentric backprojection 必須得到手算 2D 線段。
- [x] 執行確認 RED。
- [x] 實作 triangle pair crossing + barycentric world→flat 映射。
- [x] 去重並輸出 2D segments。
- [x] 執行確認 GREEN。

### Task 3: Corner cut polygon and dimensions

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`

**Interfaces:**
- Produces: `CornerReliefMeasurement`、`AssemblyBackprojectedReliefSolution`、`derive_corner_relief_from_flat_interference(...)`。

- [x] 寫失敗測試：矩形 corner component 被一條干涉線切開後，選到連接 blank corner 的一側。
- [x] 寫失敗測試：A=2 時 primary U/V 尺寸各依幾何正確增加。
- [x] 執行確認 RED。
- [x] 使用 Shapely split/polygonize 建立 cut polygon，按四角 canonical 座標解析 primary/secondary 尺寸。
- [x] 執行確認 GREEN。

### Task 4: End-to-end verified solver

**Files:**
- Modify: `ae_engine/assembly_collision.py`
- Test: `tests/test_assembly_collision.py`
- Test: `tests/test_assembly_collision_integration.py`

**Interfaces:**
- Produces: `solve_world_backprojected_endcap_relief(...)`，回傳 cut polygon、尺寸、solved render data、verified。

- [x] 寫失敗整合測試：restore fixed relief → 3D collision → 2D cut → rebuild CUTTING → refold → corner zone collision=0。
- [x] 執行確認 RED。
- [x] 實作 solver，僅 verified candidate 可標成功。
- [x] 執行 focused regression 確認 GREEN。

### Task 5: Assembly diagnostic UI

**Files:**
- Modify: `phase6_final_scene_view.py`
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_assembly_3d_view.py`
- Test: `tests/test_phase6_latest_layout_contract.py`

**Interfaces:**
- Consumes: `solve_world_backprojected_endcap_relief(...)` 的量測結果。

- [x] 寫失敗 UI contract：解鎖組合體需有 `淨空 A` 與 `實際截角尺寸`。
- [x] 執行確認 RED。
- [x] 接診斷計算結果與狀態文字；A 改變即重算。
- [x] 3D 顯示 solver 前/後干涉狀態，不直接在 renderer 製造 CUTTING。
- [x] 執行真 Tk + geometry regression。

### Task 6: AI library, verification, delivery

**Files:**
- Modify: `個人AI檔案庫/README.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- Modify: `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- Create: `docs/superpowers/verification/2026-08-28-assembly-relief-backprojection-verification.md`
- Modify: `修改日誌/20260828.md`

- [x] 記錄 3D→2D backprojection Source of Truth 與禁止 UI/renderer 自造截角公式。
- [x] 跑 fresh focused regression、py_compile、UTF-8 strict、`config.ini` SHA。
- [x] 以最新 FULL 為基準打 FULL + UPDATE 同 Asia/Taipei 時間戳。
- [x] 將 UPDATE 實際套到基準副本後重跑同一組測試並做逐檔 SHA256。

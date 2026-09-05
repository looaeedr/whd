# CornerType / 未知類型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase6 `ae_engine/` clean-break 架構內加入有限 CornerType 與 unknown-only 手動選角，且 Vault 輸出零退化。

**Architecture:** `sheetmetal_geometry` 擁有 CornerType 殘差與 fold-base 組合；Part Adapter 固定 Vault mapping 或接受 unknown policy；GUI 只建立 policy，製造輸出仍經 PartSpec → `manufacturing_api.generate_part()`。所有核心檔維持 `ae_engine/` package-relative imports。

**Tech Stack:** Python 3、Tkinter、Shapely、ezdxf、pytest。

## Global Constraints

- 金庫型現有 CUTTING/BEND 與 stretched baseline 結果不可變。
- 只有「未知類型」可手選 C01～C04。
- C02 旋轉表達 X/Y 留肉，不新增另一種類型。
- 不得恢復任何根目錄 AE compatibility shim。
- GUI 不得直接擁有製造公式或繞過 headless API。

---

### Task 1: CornerType 純幾何

**Files:**
- Modify: `ae_engine/sheetmetal_geometry.py`
- Test: `tests/test_corner_types.py`

- [x] 先建立 C01～C04 residual 與 C02 rotation 的 failing tests。
- [x] 實作 `CornerTypeId`、`CornerTypeSelection`、`corner_type_residual()`、`resolve_corner_relief()`。
- [x] 讓 FourSideFlange 接受 `FourCornerTypePolicy`。
- [x] 將 EndCap relief 改為 fold base + residual 組合。
- [x] 驗證 Vault geometry snapshot 不變。

### Task 2: Adapter 與 Vault 固定映射

**Files:**
- Modify: `ae_engine/sheetmetal_part_adapters.py`
- Test: `tests/test_corner_types.py`
- Test: `tests/test_corner_type_phase6_integration.py`

- [x] Door/Indicator Box 固定 C02、Base Plate 固定 C01。
- [x] EndCap/Tail 固定 Bottom C03、Top C04。
- [x] 新增 unknown Door/Base/Indicator/EndCap builders。
- [x] Unknown Door 保留 Phase6 `DoorFrameEdges` 多門語意。

### Task 3: Headless API 與 contract

**Files:**
- Modify: `ae_engine/contracts.py`
- Modify: `ae_engine/manufacturing_api.py`
- Modify: `ae_engine/ae.py`

- [x] 可需要 CornerType 的 PartSpec 增加 optional `corner_policy`。
- [x] `corner_policy is None` 完全走原 Vault/baseline 路徑。
- [x] `corner_policy != None` 才走 unknown exporter。
- [x] Door final X mirror、Head final Y mirror 保持 Phase6 規則。
- [x] Unknown 不套 Vault-only fixed EndCap features。

### Task 4: Unknown-only GUI

**Files:**
- Create: `ae_engine/corner_type_ui.py`
- Modify: `gui.py`
- Test: `tests/test_corner_type_ui.py`
- Test: `tests/test_corner_type_phase6_integration.py`

- [x] baseline 下拉加入 `未知類型`。
- [x] Vault/既有 baseline 隱藏 CornerType 面板。
- [x] Unknown 顯示四角、C01～C04 小圖、放大預覽。
- [x] C02 支援 0° / 90°。
- [x] Unknown 不被送入 baseline loader。
- [x] export PartSpec 攜帶 `corner_policy` 並仍透過 `manufacturing_api.generate_part()`。

### Task 5: Clean-Break Recovery 與完整驗證

**Files:**
- Create: `apply_corner_type_phase6_fix2.py`
- Create: `APPLY_CORNER_TYPE_PHASE6_FIX2.bat`
- Restore: `tests/conftest.py` (Phase6 version)

- [x] 增加 root-shim regression test。
- [x] 用 Xvfb 跑完整 suite。
- [x] `py_compile` 全通過。
- [x] Unknown headless DXF readback。
- [x] Phase6 母版與修改版 Vault direct/stretched DXF 逐 entity 比對。
- [x] 模擬「先套錯誤 FIX1，再套 FIX2 + cleanup」並再次跑完整驗證。

### Task 6: FIX3 — authoritative CornerType preview

**Files:**
- Modify: `ae_engine/corner_type_ui.py`
- Modify: `gui.py`
- Test: `tests/test_corner_type_ui.py`

- [x] 先建立 failing tests，要求 C01/C02/C03/C04 preview material corner 包含正式 geometry 的關鍵座標。
- [x] 建立 `build_corner_type_preview_geometry()`，內部呼叫 `build_four_side_outline()` 取得真正 material polygon，再裁切單角。
- [x] `_draw_corner_type_icon()` 移除自行拼 relief boundary 的做法，只 render preview material polygon 與 bend references。
- [x] C02 0° / 90° 分別驗證 X 留肉 / Y 留肉。

### Task 7: FIX3 — multi-door W/H hard guard

**Files:**
- Modify: `gui.py`
- Test: `tests/test_multi_door_gui.py`

- [x] 為每個欄寬/層高保存最後 committed 合法值。
- [x] 欄寬 commit 前計算 `W - 其他固定欄總和`，超過即拒絕並 rollback。
- [x] 層高 commit 前計算 `H - 同欄其他固定層總和`，超過即拒絕並 rollback。
- [x] 非數字、0、負數輸入同樣拒絕並 rollback。
- [x] 自動 remainder 被合法手改時仍 promotion 成 fixed，並重新補剩餘尺寸。
- [x] Xvfb 完整 suite 驗證：158/158 PASS。

### Task 8: FIX4 — top/bottom pair editing defaults

**Files:**
- Modify: `ae_engine/corner_type_ui.py`
- Modify: `gui.py`
- Test: `tests/test_corner_type_ui.py`
- Test: `tests/test_corner_type_phase6_integration.py`

- [x] 先建立 failing tests：每個 part 預設 `top=True`、`bottom=True`。
- [x] grouped target `top` 一次同步 `top_left/top_right`；`bottom` 同理。
- [x] 取消「左右相同」後只改指定 physical corner。
- [x] 重新勾回時以左側 selection 同步右側。
- [x] GUI 移除固定四角按鈕流程，改成上/下兩列；split 時才顯示左右按鈕。

### Task 9: FIX4 — canonical cut-profile thumbnails

**Files:**
- Modify: `ae_engine/corner_type_ui.py`
- Modify: `gui.py`
- Test: `tests/test_corner_type_ui.py`

- [x] 先建立 failing tests，要求 preview 暴露 `cut_outline` 而非 material L crop。
- [x] Preview 由 `resolve_corner_relief()` 的 Primary/Secondary cut union 產生 canonical removed-material polygon。
- [x] C01/C02/C03/C04 關鍵 cut profile 座標全部鎖定。
- [x] C02 90° 驗證 U/V cut profile 軸交換。
- [x] catalog 小圖固定 canonical 方向；physical corner placement 不改圖示。
- [x] GUI large preview 才反映 C02 X/Y 留肉方向。

### Task 10: FIX4 verification

- [x] `xvfb-run -a pytest -q`：162/162 PASS。
- [x] `py_compile` production files。
- [x] 實際啟動 Unknown Door GUI 並截取 CornerType panel，人工確認 C01/C02/C03/C04 顯示為 square/narrow/larger/step cut profile，而非四張 L 形材料圖。
- [x] 驗證 manufacturing core (`sheetmetal_geometry/part_adapters/ae/manufacturing_api/contracts/features/drawing`) 與 FIX3 byte-identical。


## FIX5 — CornerType 預覽共用尺度

- C01～C04 縮圖禁止各自依自身 bbox 自動 fit；否則 C01/C02/C03 都會被放大成同樣的矩形。
- 所有類型必須使用同一組示意參數與同一 viewport scale。
- GUI 示意參數固定為 `fold_u=fold_v=12`、`T=4`、`FW=8`（僅供圖示辨識，不參與製造幾何）。
- 藍色虛線固定代表相同折彎基準；紅色 CUT profile 相對基準顯示：C02 少切 1T、C01 標準、C03 多切 0.5T、C04 雙段。
- 實際 DXF / Factory Policy / 金庫型公式不得讀取上述示意參數。

### Task 11: FIX6 — extract thumbnails from existing verified part geometry

**Files:**
- Modify: `ae_engine/corner_type_ui.py`
- Modify: `gui.py`
- Test: `tests/test_corner_type_ui.py`

- [x] RED：要求 preview 暴露 `source_part/source_corner`，且 module 不得含 `resolve_corner_relief`。
- [x] C01 從現有 Base Plate 左下角擷取。
- [x] C02 從現有 Door 左下角擷取。
- [x] C03/C04 分別從現有 EndCap 左下/左上角擷取。
- [x] C02 90° 只旋轉擷取結果。
- [x] 四種 preview 共用同一 crop span。
- [x] GUI 移除 FIX5 illustrative fold/T/FW 常數。
- [x] 完整 Phase6 Xvfb regression：164/164 PASS。


### Task 9: FIX7 — crop literal production linework

- [x] RED：要求 preview 暴露 `cut_paths` / `bend_paths`，並禁止 GUI `create_polygon` 畫 removed-area。
- [x] 直接以現有 `StructuralGeometryResult.outline` 建立 CUTTING LineString，裁指定物理角。
- [x] 直接裁同一 result 的 `bends`；不建立 preview-only bend reference。
- [x] Top-left source 只做 local orientation normalize；C02 90° 只交換已裁 linework 的 local axes。
- [x] Tk Canvas CUTTING 使用綠線、BEND 使用藍色虛線。
- [x] 用真正 Tk Canvas PostScript 渲染 C01~C04 人工檢視。
- [x] Phase6 回歸拆組驗證：119 + 24 + 24 = 167 tests PASS。

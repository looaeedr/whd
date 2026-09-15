# Phase6 FinalScene View 實作計畫

> **給代理執行者：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans`，依任務逐項實作；使用核取方塊（`- [x]`）追蹤完成狀態。

**目標：** 將 Phase6 FinalScene 的 3D 顯示實作從 `fold_designer_bridge.py` 收斂到深模組 `phase6_final_scene_view.py`，維持 `PartRenderData` 為唯一製造幾何來源。

**架構：** Bridge 仍擁有 manufacturing query 與 operator value adapter；新的 View module 擁有 profile folding、mesh、operation linework、尺寸繪圖與 viewport/zoom。Bridge 只建立 `FinalSceneViewRequest` 並安裝／呼叫 View。

**技術：** Python、Tkinter、Matplotlib 3D、Shapely、pytest。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-final-scene-view-design.md`

## 全域限制

- 不更動 CornerType／EndCap／Fold Profile 機械公式。
- View 不得建立或重新解析 CUTTING material。
- View 不得呼叫 manufacturing build API。
- scene query 保留在 Bridge。
- `config.ini` 不得修改。
- FULL／UPDATE 共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳。

---

### 任務 1： 建立 FinalScene View 純幾何 seam

**檔案：**
- 新增： `phase6_final_scene_view.py`
- 新增： `tests/test_phase6_final_scene_view_ownership.py`
- 修改： `fold_designer_bridge.py`

**介面：**
- 產出： `FinalSceneViewRequest`, `Phase6FinalSceneView`, profile/mesh helper direct re-exports.

- [x] **步驟 1：** 新增 RED 測試，要求 View module 存在、含洞 `material` mesh 不填洞，且 source 不含 `build_part_render_data`／`material_polygon_from_final_scene`／`fold_guides_from_final_scene`。
- [x] **步驟 2：** 執行 ownership 測試，確認因 module/interface 尚不存在而 RED。
- [x] **步驟 3：** 搬移 profile mapping、mesh folding、limits、operation projection helpers 到新 module；Bridge 改 direct re-export。
- [x] **步驟 4：** 執行 ownership 與既有 `test_phase6_core_fold_ownership.py`、`test_phase6_3d_cutting_mesh.py`，確認 GREEN。

### 任務 2： 建立 `Phase6FinalSceneView.render()`

**檔案：**
- 修改： `phase6_final_scene_view.py`
- 修改： `fold_designer_bridge.py`
- 測試： `tests/test_phase6_final_scene_view_ownership.py`
- 測試： `tests/test_phase6_3d_single_source_renderer.py`

**介面：**
- 使用： `FinalSceneViewRequest(render_data, profiles, part_key, alpha_bend, finished_dimensions, thickness)`.
- 產出： authoritative folded triangles and View diagnostics.

- [x] **步驟 1：** 新增 RED 測試：`render()` 必須直接使用 request 的 `render_data.material` 與 `render_data.fold_guides`，不得查詢 manufacturing。
- [x] **步驟 2：** 搬移 mesh collection、BEND/MARKING、operator dimension drawing、axis fit 到 View。
- [x] **步驟 3：** Bridge 新增 request adapter，operator finished dimensions 的數值解析仍留在 Bridge。
- [x] **步驟 4：** 跑 single-source renderer／operator view／baseline alignment regressions。

### 任務 3： View install、zoom 與 compatibility state

**檔案：**
- 修改： `phase6_final_scene_view.py`
- 修改： `fold_designer_bridge.py`
- 測試： `tests/test_phase6_final_scene_view_ownership.py`
- 測試： `tests/test_phase6_3d_view_regressions.py`
- 測試： `tests/test_phase6_3d_operator_view.py`

**介面：**
- 產出： `install(request_provider, after_render=...)`, `on_scroll(event)` and read-only View diagnostics.

- [x] **步驟 1：** 新增 RED 測試，要求 zoom state／last mesh backing state 屬於 View，不屬於 app `__dict__`。
- [x] **步驟 2：** 搬移 rectangular viewport、zoom limits、scroll 與 renderer override 到 View。
- [x] **步驟 3：** `Phase6FoldDesignerApp` 保留 compatibility properties／event adapter，不保留第二份 backing state。
- [x] **步驟 4：** 跑 3D view/operator/Tk regressions（Xvfb）。

### 任務 4： Ownership guard、文件、完整回歸與封包

**檔案：**
- 修改： `使用說明書.md`
- 修改： `DELIVERY_README.md`
- 修改： `修改日誌/20260823.md`
- 修改： `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- 新增： `docs/superpowers/verification/2026-08-23-phase6-final-scene-view-verification.md`

- [x] **步驟 1：** 靜態 guard：Bridge 不再實作 profile mesh／Matplotlib FinalScene View helpers；View 不含 manufacturing build/material reconstruction。
- [x] **步驟 2：** `py_compile` 與聚焦 3D 回歸。
- [x] **步驟 3：** 跑原始完整 suite；另外明確排除既知 `/mnt/data/自訂.p6fold` 4 項後要求 0 failure。
- [x] **步驟 4：** 驗證 `config.ini` SHA256 未改。
- [x] **步驟 5：** 同步繁中規格／使用說明／踩坑／修改日誌，建立同 timestamp FULL／UPDATE，UPDATE 排除 `config.ini`，兩包做 CRC。

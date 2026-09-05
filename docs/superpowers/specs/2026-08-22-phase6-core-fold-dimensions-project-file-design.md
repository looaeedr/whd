# Phase6 Core Fold / Dimensions / Project File Design

## Goal
Fix Phase6 3D so each part folds around its semantic core, retained material follows authoritative BEND coverage, operator dimensions replace coordinate axes, startup does less redundant work, and the whole fold workspace can be saved/loaded as a `.p6fold` project file.

## Architecture
1. The semantic base segment is selected from profile segments carrying `core`; when multiple core segments exist, the middle core segment wins. Fallback remains the geometric middle segment.
2. Manufacturing `PartRenderData` exposes normalized BEND guides derived from the final scene. Each guide records fold axis, fold coordinate and the orthogonal span where that fold physically exists.
3. 3D folding applies each profile fold only where its matching manufacturing BEND guide covers the orthogonal coordinate. Mesh tessellation is split at BEND span endpoints so one triangle never crosses a fold-ownership discontinuity.
4. Phase6 3D hides X/Y/Z axes and draws operator-facing finished dimensions and fold-size annotations. Initial camera orientation keeps W predominantly horizontal and H predominantly vertical.
5. Opening the workspace must not re-run the root TextScaleController tree scan. Automatic initial/configure redraws are coalesced so first visible model render is not repeated unnecessarily.
6. `.p6fold` is UTF-8 JSON with schema `phase6-fold-project-v1`. One file stores all part profiles/features/corner state/global settings/active part and per-part final-geometry diagnostics. Main GUI can load the file, restore the full fold workspace and open Phase6 on the saved active part.
7. On Windows the app registers `.p6fold` under HKCU so a double click invokes the current executable (or the Python script when not frozen) with the project path as argv[1].

## Invariants
- `fold_designer_original.py` remains byte-identical.
- Final material still comes from `manufacturing_api.build_part_render_data`; 3D never rebuilds holes/corners.
- Head/tail remain native orientation; tail is not mirrored.
- Project final-geometry blobs are diagnostic evidence, not an editable source of manufacturing truth.

## 2026-08-23 補充：全域專案讀寫入口（取代舊 3D Footer 專案按鈕）

### 使用流程
```text
主視窗左上角
├─ 開啟專案
├─ 儲存專案
└─ 另存新檔
      ↓
    *.p6fold
      ↓
phase6_project_file 驗證 / 寫入
      ↓
BoxCalculatorGUI authoritative project state
├─ 全域尺寸／settings
├─ CornerType／assembly mirror
├─ Fold profiles
├─ holes/features
├─ existing_parts
├─ 2D tabs／左側結果／輸出列
└─ active_part
```

### 交易邊界
- `.p6fold` 是全專案檔，不屬於任一板件頁，因此 3D Footer 不提供專案 `讀檔 / 存檔`。
- 主視窗左上角提供全域 `開啟專案 / 儲存專案 / 另存新檔`；因 3D 是 modal，3D 視窗左上角也必須提供同一組全域入口，避免進 3D 後全域功能不可達。
- 板件頁／3D Footer 仍只做 `套用 / 確定 / 取消`；全專案按鈕與板件 transaction 在視覺與語意上分區。
- `開啟專案` 與 Windows 雙擊 `.p6fold` 必須共用 `load_phase6_project()`；無效檔案驗證失敗時不得破壞目前專案。
- GUI 內開啟專案不強迫啟動 3D；argv／雙擊啟動可維持既有 active-part 開啟流程。
- 任何讀檔都必須一起恢復 physical presence、輸出資格、2D/3D、Corner/Fold/features；不得只讀 JSON 而漏 UI/製造鏈刷新。

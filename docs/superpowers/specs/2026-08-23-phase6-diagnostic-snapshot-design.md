# Phase6 診斷快照深模組設計

## 目標

把 `fold_designer_bridge.py` 內的診斷資料序列化與 Final Geometry 聚合收斂到 `phase6_diagnostics.py`。Bridge 只負責把目前 Fold Designer draft 狀態轉成明確診斷輸入、提供 manufacturing render callback，以及處理 Tk 檔案對話框；Diagnostics module 擁有診斷 schema、JSON-safe 轉換、Scene／Material／FoldGuide 序列化、錯誤隔離與 all-part final geometry 聚合。

## 現況摩擦

目前 Bridge 同時知道：

- dataclass／Enum／Mapping 如何轉成 JSON-safe 值。
- `DrawingScene` primitive 如何序列化。
- Shapely material 的 bounds／area／interior／GeoJSON 如何產生。
- `PartRenderData.fold_guides` 如何序列化。
- active-part diagnostic JSON schema 與 render error 欄位。
- `.p6fold` 內 all-part `final_geometry` 診斷如何逐板件聚合。
- 診斷 JSON UTF-8 寫檔。

這些規則沒有 Tk 或 Fold Designer 專屬性，卻和 UI／交易 adapter 混在同一 module，造成 locality 不足，也讓 Project Snapshot 與 standalone Diagnostic Snapshot 重複知道同一組序列化規則。

## Seam 與所有權

### `phase6_diagnostics.py` 擁有

- `DIAGNOSTIC_SCHEMA = "phase6-fold-diagnostic-v1"`。
- `DiagnosticSnapshotContext`：active diagnostic 所需的已組合資料。
- JSON-safe 值轉換。
- Scene primitive 序列化。
- Material diagnostics：geometry type、bounds、area、interior count、GeoJSON。
- FoldGuide 序列化。
- `PartRenderData` diagnostic 序列化。
- active-part diagnostic snapshot schema/timestamp/render error 隔離。
- all-part final geometry diagnostic 聚合；一個 render provider 失敗只記錄該 part 的 `error`。
- UTF-8 JSON 寫檔。

### `fold_designer_bridge.py` 保留

- `_phase6_collect_workspace_state()`：Designer workspace → plain mapping adapter。
- `_phase6_scene_query_payload()`／`_phase6_scene_query_payload_for_part()`：draft → manufacturing query adapter。
- `_phase6_query_final_render_data()`：active manufacturing callback 驗證。
- active diagnostic context 的組裝。
- `.p6fold` 的 reloadable `snapshot` 組裝與 `PROJECT_SCHEMA`。
- Tk `filedialog`／`messagebox`、預設檔名與 status text。
- standalone project save/load transaction。

### 不得移入 Diagnostics

- `ProjectSession`／`Phase6ProjectController` ownership。
- `SettingsService`／Factory Defaults。
- CornerType、EndCap、Fold Profile 機械公式。
- manufacturing query payload 的推導。
- `PartRenderData` 的建立或 CUTTING material 重建。
- Tk widget 或 renderer view state。

## Interface

```python
@dataclass(frozen=True)
class DiagnosticSnapshotContext:
    model: str
    active_part: str | None
    settings: Mapping[str, object]
    corner_state: Mapping[str, object]
    corner_pair_same: Mapping[str, object]
    workspace: Mapping[str, object]
    active_part_payload: Mapping[str, object]


def build_active_diagnostic_snapshot(
    context: DiagnosticSnapshotContext,
    render_provider: Callable[[], object] | None,
) -> dict: ...


def collect_final_geometry_diagnostics(
    part_keys: Sequence[str],
    payload_provider: Callable[[str], Mapping[str, object]],
    render_provider: Callable[[str, Mapping[str, object]], object] | None,
) -> dict[str, dict]: ...


def write_diagnostic_json(path, payload) -> Path: ...
```

序列化 helper 保留 module-level function 供 diagnostics 自身測試與 Bridge compatibility direct re-export 使用，但新的 production caller 應優先使用三個深 interface。

## 錯誤模型

- active part 存在但 render provider 缺失／失敗：`final_geometry=None`，`render_error="<Type>: <message>"`。
- all-part render provider 缺失：每個 row 的 `error="3D final-scene provider is not connected"`。
- all-part 某一板件 render 失敗：只有該 row 記錄 error；其他板件仍完整輸出。
- payload provider 失敗屬 adapter／project snapshot 建構錯誤，維持 fail-fast，不在 diagnostics 假造 payload。
- JSON 寫檔 I/O error 原樣丟給 Bridge，由既有 messagebox 顯示。

## 相容策略

既有 caller／測試若使用 `_phase6_json_safe`、`_phase6_serialize_scene`、`_phase6_material_diagnostic`、`_phase6_serialize_fold_guides`、`_phase6_write_diagnostic_json`，Bridge 改成 direct alias/re-export 新 module 的同一函式物件，不保留第二套 wrapper 實作。

`_phase6_build_diagnostic_snapshot(self)` 與 `_phase6_build_project_snapshot(self)` 保留 Bridge adapter 名稱，因為它們仍需要讀 Fold Designer state；其內部聚合規則改委派 Diagnostics。

## 不做

- 不改 `phase6-fold-diagnostic-v1` schema。
- 不改 `PROJECT_SCHEMA` 或 `.p6fold` schema。
- 不改 project save/load transaction。
- 不改 FinalScene View、AE、CornerType、Fold Profile。
- 不把 `_phase6_collect_workspace_state()` 搬進 diagnostics。
- 不新增第二份 committed/draft/settings state。

## 回歸契約

1. 既有 diagnostic JSON 欄位與 UTF-8 round-trip 不變。
2. active diagnostic 仍保存 exact FinalScene material，含洞 material 的 `interior_count` 與 GeoJSON 不變。
3. `.p6fold.final_geometry` 仍包含所有 existing parts 的 payload、scene、material、fold_guides、error。
4. 單一 part render error 不得阻止其他 part diagnostics。
5. Diagnostics module 不 import Tk、`fold_designer_bridge`、ProjectSession、SettingsService，也不得呼叫 manufacturing build/material reconstruction。
6. Bridge 不再實作 Scene／Material／FoldGuide diagnostic serialization。
7. `config.ini` 不修改；FULL／UPDATE 共用 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳，UPDATE 不含 `config.ini`。

# Phase6 Settings 單一 Runtime 狀態來源設計規格

## 目標

把 Phase6 的「已確認 runtime 設定」收斂到 `phase6_settings_center.py` 內單一深模組 `SettingsService`，讓主 GUI、AE runtime mirror、`config.ini` 持久化與 3D transaction draft 各自有明確所有權。

本次不改 `SETTING_SPECS` 的製造參數定義、不改 `.p6fold` schema、不改 CornerType / Fold Profile 幾何、不拆 `gui.py`、不讓 Fold Designer 直接持有 main runtime service。

## 核心領域語意

### Factory Defaults

程式不可變的「還原初始值」來源，來自 `ae_engine.ae.default_config`；不受 `config.ini`、main runtime 或 3D draft 修改。

### Persisted Defaults

`config.ini` 中供**下次啟動**使用的預設值。它是 persistence，不是目前 runtime Source of Truth。明確按「儲存預設值」可以改它，但不代表要提交目前 3D transaction。

### Committed Runtime Settings

目前主 GUI 已確認、AE 應同步使用的設定。唯一所有者是 `SettingsService`。

### 3D Settings Draft

Fold Designer transaction 內的 `_settings_values`。它是隔離中的 editor draft，不是第二份 committed runtime state；取消可直接丟棄，確定後由 main GUI 經 `SettingsService.update(...)` 提交。

`ui_text_size` 保留既有產品語意：它是應用程式 UI 偏好，可在 3D 中立即更新並持久化；其餘製造設定遵守 transaction 隔離。

## Deep Module 與 Seam

外部 seam 位於 `SettingsService`：

```python
service = SettingsService(ae)
service.snapshot()              # immutable Phase6Settings
service.factory_snapshot()      # immutable factory defaults
service.update({"w": 450})     # 提交 runtime，並同步 AE mirror
service.persist_defaults(...)   # 只寫 config.ini，不提交 runtime
```

caller 不再需要知道：

- `SettingSpec` 的 coercion 細節；
- AE module scalar / `RELIEF_CONFIG` / fixed-hole policy 如何同步；
- `config.ini` 寫入與 parser refresh；
- factory default 與 persisted default 的差異。

`SettingsService` 必須保持 UI-agnostic，不 import Tk、`gui.py`、Fold Designer 或 renderer。

## `Phase6Settings` snapshot

新增 immutable Mapping 型 snapshot：

```python
class Phase6Settings(Mapping[str, object]):
    def as_dict(self) -> dict[str, object]: ...
```

要求：

- 建立時複製輸入；
- `as_dict()` 每次回 defensive copy；
- caller 無法透過 snapshot 反向修改 service current/factory state；
- key/value 必須經現有 `SettingSpec` coercion。

## `SettingsService` interface

```python
class SettingsService:
    def __init__(self, ae_module): ...
    def snapshot(self) -> Phase6Settings: ...
    def factory_snapshot(self) -> Phase6Settings: ...
    def update(self, values: Mapping[str, object]) -> Phase6Settings: ...
    def persist_defaults(
        self,
        *,
        context: str = GLOBAL_CONTEXT,
        values: Mapping[str, object] | None = None,
        keys: Iterable[str] | None = None,
    ) -> None: ...
```

### 啟動

1. `SettingsService(ae)` 讀 `config.ini` 取得 persisted defaults。
2. 建立 current committed runtime snapshot。
3. 把 current 套到 AE runtime mirror，確保 AE 與 service 一致。
4. 另從 `ae.default_config` 建立 immutable factory snapshot。

### `update()`

- 只接受 `SETTING_SPECS` 已知 key；未知 key 忽略。
- 依 `SettingSpec.kind` coercion。
- 只把**實際有變更**的 key 套到 AE，避免每次 snapshot/collect 都重建 policy。
- 更新後回新的 immutable snapshot。
- 不寫 `config.ini`。

### `persist_defaults()`

- `values is None`：持久化 current runtime snapshot。
- 有 explicit `values`：以 current 為 base，套入合法 explicit values 後寫入。
- **永遠不改 current runtime，也不套入 AE runtime mirror。**
- `context` / `keys` 延續既有 `save_defaults_to_ini` 選擇規則。
- 寫完仍更新 `ae.config` parser，讓 persistence view 與磁碟一致。

這條規則是本次關鍵：3D draft 可以被「儲存為下次預設」但不能因此偷渡成目前 committed runtime。

## Main GUI 整合

`BoxCalculatorGUI` 建立：

```python
self.settings_service = SettingsService(ae)
```

移除 `_settings_state` 作為第二份 mutable runtime owner。Tk variables 保留為 UI cache / input adapter。

### Main Tk 變數變更

```text
Tk var
  ↓
_on_main_setting_var_changed
  ↓
SettingsService.update
  ↓
AE runtime mirror
```

### 收集主畫面 snapshot

`_collect_main_setting_values()` 從 service snapshot 起始，再讀 Tk vars，最後經 `SettingsService.update()` 正規化/提交；不得直接 mutating dict。

### 3D 確定

沿用 ProjectSession transaction：Fold Designer payload 套回 main GUI 時，`_apply_fold_designer_live_settings()` 呼叫 `SettingsService.update(...)`，此時才成為 committed runtime。

### 3D 取消

不呼叫 `SettingsService.update(...)`，所以 committed runtime 與 AE mirror 保持 3D 開啟前狀態。

### 3D「儲存為預設值」

`_save_fold_designer_defaults()`：

1. current service snapshot 作 base；
2. merge Fold Designer explicit draft values；
3. `SettingsService.persist_defaults(values=draft, context=...)`；
4. Corner defaults 仍走既有 `save_corner_defaults_to_ini(...)`；
5. 不更新 service current，不套入 AE runtime。

## AE seam

`apply_settings_to_ae()` 保留為 `SettingsService` 的 implementation helper / legacy compatibility function。Main GUI 不再直接呼叫它。

`save_defaults_to_ini()` 保留 legacy compatibility，但新增 `apply_runtime` 控制；`SettingsService.persist_defaults()` 固定以 `apply_runtime=False` 使用。新 production call site 不直接用它。

AE module globals（例如 `W`, `FW`, `RELIEF_CONFIG`）是 compatibility mirror，不是 Source of Truth。它們只由 `SettingsService.update()` 對 main runtime 進行同步。

## 不建立的第二套狀態

- 不把 `SettingsService` 放進 Fold Designer；3D `_settings_values` 是 transaction-local draft。
- 不把 `config.ini` parser 當 current runtime。
- 不新增另一份 `settings` dict 到 `ProjectSession`；ProjectSession snapshot 只序列化 service 提供的 current values。
- 不把 Tk StringVar / BooleanVar 當 runtime source。

## 強制驗證情境

1. service startup 從 INI 讀 W=400 → `snapshot()["w"] == 400` 且 `AE.W == 400`。
2. `service.update({"w": 450})` → service W=450、AE.W=450、INI 仍是 400。
3. `service.persist_defaults(values={"w": 500})` → INI=500，但 service/AE 仍 450。
4. 重新建立新的 service → 新 service/AE 從 INI 取得 500。
5. factory snapshot 始終來自 `default_config`，即使 INI/runtime 已變更也不變。
6. snapshot / `as_dict()` 外部修改不能污染 service。
7. main GUI Tk W 改值 → service 與 AE 同步。
8. 3D draft W=500 未按確定 → main service/AE 保持 committed W=400。
9. 3D draft W=500 按「儲存為預設值」→ INI=500，但 main service/AE 仍 400。
10. 3D draft W=500 按「確定」→ main service/AE 成為 500。
11. 既有 ProjectSession save/load、CornerType、EndCap resolved geometry 回歸保持綠燈。

## 不在本次範圍

- 不移除 Fold Designer `_settings_values`；它是合法 transaction draft。
- 不重構 Corner defaults 成另一個 service。
- 不改 CornerType / EndCap / PartRenderData。
- 不拆 `gui.py` / `fold_designer_bridge.py`。
- 不升級 `.p6fold` schema。
- 不新增 UI 控制項。

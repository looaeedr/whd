# FIX13 Baseline Resolver：禁止硬寫路徑與共用型號

日期：2026-08-20

## 本輪問題

最新 FIX13 中仍存在兩類 baseline ownership 錯誤：

1. `gui.py` 直接用 `os.path.dirname(ae.__file__) / 基準檔 / <model>` 組實體路徑，繞過既有 resource-root / PyInstaller resolver。
2. 指示燈盒與小門雖然是全域共用件，卻以固定字串 `"指示燈"` 當 shared baseline model/fallback。這等於把實體資料夾名稱寫死。

使用者要求：不要再逐點人工修漏，必須建立永久 TEST 檔把規則鎖住。

## 正確 ownership

- GUI：只知道「目前要門、盒子、小門、開孔 catalog」，不得組 baseline filesystem path，也不得知道共用資料夾名稱。
- `manufacturing_api.py`：只表達 PartSpec / resource_root / part role；不得知道 `基準檔` 目錄名稱與 shared folder 名稱。
- `ae.py`：唯一擁有 baseline resource resolver。

## 單一 baseline resolver

`ae.py` 新增／統一：

- `baseline_root_path()`：唯一允許呼叫 `get_resource_path("基準檔")` 的位置。
- `baseline_expected_path(model, filename)`：組 expected path，不要求檔案存在。
- `baseline_part_path(model, filename)`：只回傳存在的 baseline part。
- `baseline_hole_catalog_root_path()`：GUI 的開孔 catalog 也從同一 baseline root 取得。

舊的箱身、封頭尾、門 baseline loader 直接組路徑的位置一併改走上述 resolver。

## 全域盒子／小門 shared resolver

不再存在：

```python
INDICATOR_SHARED_BASELINE_MODEL = "指示燈"
```

新的 `indicator_shared_baseline_model_name()` 規則：

1. 若使用者在 `config.ini` 明確設定：

```ini
[INDICATOR_BOX]
shared_baseline_model = 任意資料夾名稱
```

則使用該名稱。

2. 若未設定，掃描目前 resource root 下的 baseline model folders；只有「同時包含 `盒子.dxf` 與 `小門.dxf`」的資料夾才是候選。
3. 候選剛好 1 個：自動使用。
4. 候選 0 個：明確報錯，不 fallback。
5. 候選超過 1 個：明確報 ambiguous，要求設定 `shared_baseline_model`，不猜。

因此現有專案如果只有 `基準檔/指示燈/盒子.dxf + 小門.dxf`，不需要修改 config，仍會自動解析到該資料夾；名稱本身已不是 production contract。

## 小門角色判斷

小門不能再靠：

```text
model_name == shared_model
```

判斷。

現在以既有 PartSpec 語意：

```text
indicator_window_groups is not None
```

判斷這是一片 indicator small door。因此小門視窗與 baseline loading 不依賴 shared folder 名稱。

## GUI 修正

- `on_baseline_changed()` 不再自行組 `ae.__file__/基準檔/...`；改問 `ae.has_baseline_part(model, "門.dxf")`。
- 盒子 preview/editor 呼叫 AE 時不傳 shared model，僅傳 part role / layer groups。
- 小門 preview/editor 呼叫 AE 時 `model_name=None`，由 `indicator_window_groups` 表示小門角色。
- hole catalog 改用 `ae.baseline_hole_catalog_root_path()`。

## Manufacturing API 修正

- 移除 `_indicator_shared_model_name()`。
- 移除 API 對 `"基準檔"` 的實體 path 拼接。
- `expected_baseline_path_for()` 在 `ManufacturingContext.resource_root` scope 內呼叫 AE resolver。
- `indicator_small_door_spec()` 的 `model_name=None`；不再塞 shared folder 名稱。
- indicator box / small door export 都用 AE shared resolver 取得實際 baseline。

## 永久回歸 TEST

新增：

```text
tests/test_baseline_resource_resolution.py
```

目前鎖 11 類檢查：

1. GUI 不得使用 `os.path.dirname(ae.__file__)` 組 baseline。
2. GUI 不得直接 `join(...基準檔...)` 或 `ae.get_resource_path("基準檔...")`。
3. GUI 不得讀 shared model name。
4. Manufacturing API 不得包含 baseline directory ownership / fixed shared fallback。
5. AE 只能有一個 `get_resource_path("基準檔")` 入口。
6. AE 不得存在固定 `INDICATOR_SHARED_BASELINE_MODEL`。
7. 小門角色不得以 shared model name 比對。
8. 任意 shared folder name 可自動解析。
9. config 明確指定 shared folder 可覆蓋 auto-discovery。
10. 0 個 / 多個候選必須 fail，不准 fallback。
11. 切換 `ManufacturingContext.resource_root` 與實際 box/small-door DXF export 必須跟 resolver 走。

實際 export test 會建立一個名為「完全任意名稱」的 shared folder，產生有效 `盒子.dxf + 小門.dxf`，再由 manufacturing API 真正輸出盒子與小門 DXF；baseline path 必須指向該任意 folder。

## 驗證

- 新 resolver TEST：11 passed。
- Door / indicator window / dynamic gap / startup / baseline UI 相關組合：29 passed。
- 全 GUI suite 以 `--maxfail=7` 檢查時，在 69 passed 後遇到 7 個既有 Fold Designer 舊失敗；同 7 支已在修正前 DYNAMIC_GAP 版本逐支重跑，結果同樣 7/7 fail，因此不是本輪 resolver 修改造成。

## 本輪未改

- 盒子尺寸公式。
- 盒子淨開口 → 主門開孔 → 小門尺寸鏈。
- 3.5 gap policy / dynamic gap 顯示。
- 一組／多組指示燈排列公式。
- 小門視窗由實際 lamp pattern center 推導的規則。
- 2/3/2 多門與 Door transaction 行為。

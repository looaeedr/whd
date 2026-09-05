# FIX13 指示燈盒／主門開孔／小門單一尺寸鏈

日期：2026-08-20

## 使用者確認規則

指示燈盒與指示燈小門皆為全域共用件，不依 PW / PSR / RF / 未知類型分類。

尺寸 ownership 必須只有一條：

```text
指示燈層數／每層組數
        ↓
盒子展開尺寸
        ↓
盒子成品外尺寸
        ↓ 扣左右/上下各一個板厚 T
盒子內部淨開口
        ├──→ 主門上的盒子安裝開孔
        └──→ 四邊門縫各 3.5 mm
                     ↓
                小門成品尺寸
                     ↓
                小門自己的折邊
                     ↓
                小門展開尺寸
```

禁止小門再維護獨立的 `254 / 144 / 374` 尺寸公式；未來盒子尺寸規則變更時，主門開孔與小門必須同步跟著變。

## 正式公式

### 盒子

盒子展開仍由既有指示燈排列規則產生。

```text
box_unfolded_w/h = get_indicator_box_data(layer_groups, T)
box_finished_w = box_unfolded_w - 2*box_fold + T
box_finished_h = box_unfolded_h - 2*box_fold + T
```

### 盒子內部淨開口／主門開孔

```text
opening_w = box_finished_w - 2*T
opening_h = box_finished_h - 2*T
```

主門上的指示燈盒開孔尺寸直接等於 `opening_w × opening_h`。

### 小門

四邊門縫由 `ManufacturingPolicy.indicator_small_door_gap` 控制；目前預設值為 3.5 mm：

```text
small_door_finished_w = opening_w - 2*small_door_gap
small_door_finished_h = opening_h - 2*small_door_gap
```

再由小門自己的折邊規則計算展開：

```text
small_door_unfolded_w = small_door_finished_w - 2*T + fold_left + fold_right
small_door_unfolded_h = small_door_finished_h - 2*T + fold_top + fold_bottom
```

## 1 層 2 組，T=2 mm 驗證基準

既有盒折 `49 mm`、小門折邊 `19 mm`：

| 項目 | W | H |
|---|---:|---:|
| 盒子展開 | 396 | 445 |
| 盒子成品外尺寸 | 300 | 349 |
| 盒子內部淨開口 | 296 | 345 |
| 主門盒子開孔 | 296 | 345 |
| 小門成品 | 289 | 338 |
| 小門展開 | 323 | 372 |

這組數字是本次回歸測試的固定基準。

## 程式修改

### `ae_engine/contracts.py`

`ManufacturingPolicy` 增加：

```text
indicator_small_door_gap = 3.5
```

放在 dataclass 最後以維持既有 positional 相容性。

### `ae_engine/ae.py`

增加工廠預設：

```text
indicator_small_door_gap_def
```

來源為 `[INDICATOR_BOX] small_door_gap`，設定不存在時 fallback `3.5`。

### `ae_engine/manufacturing_api.py`

新增單一尺寸鏈 API：

- `indicator_box_unfolded_size()`
- `indicator_box_finished_face_size()`
- `indicator_box_opening_size()`
- `indicator_small_door_finished_size()`
- `indicator_small_door_unfolded_size()`

`indicator_box_opening_feature()` 改為只讀 `indicator_box_opening_size()`。

`indicator_small_door_spec()` 移除獨立 `254 / 144 / 374` 公式，改由 `indicator_small_door_finished_size()` 取得成品尺寸。

### `gui.py`

- 移除 GUI 對 `sheetmetal_features.indicator_box_opening_size` 的直接 import。
- 單門與多門主門盒子開孔全部改讀 `manufacturing_api.indicator_box_opening_size()`。
- 小門預覽、開孔編輯器、結果列、Fold Designer snapshot 全部改讀 manufacturing API 的 linked size chain。
- 小門頁面說明文字由目前 policy 動態顯示，例如預設值時為「盒子內部淨開口 → 四邊各留 3.5 mm → 小門成品 → 小門展開」；不得在 GUI 寫死 3.5。

## 不變更事項

- 盒子與小門仍是全域共用基準件。
- 盒子基準：共用 `指示燈/盒子.dxf` 資源角色。
- 小門基準：共用 `指示燈/小門.dxf` 資源角色。
- 門板本身仍依目前盤體基準型號。
- 2/3/2 多門 layout ownership 不變。
- 指示燈盒/直接指示燈 fit guard 不變。
- 使用者自訂開孔 ownership 不變。

## 驗證

TDD 新測試覆蓋：

- 1層2組固定尺寸鏈 `396×445 → 296×345 → 289×338 → 323×372`。
- 1/2/3 組與多層變化，主門開孔及小門同步。
- 改盒折值時，小門透過盒子 opening 同步改變。
- GUI 不再 import 第二套 `indicator_box_opening_size`。
- 單門 GUI 結果列顯示 linked blank size。
- 多門 cell 的 `indicator_hole` 讀同一 manufacturing API。
- 實際小門 DXF CUTTING bbox 為 `323×372`。

開發回歸：29 passed（尺寸鏈、單/多門 GUI、fit guard、Door tab、2/3/2 contract）。

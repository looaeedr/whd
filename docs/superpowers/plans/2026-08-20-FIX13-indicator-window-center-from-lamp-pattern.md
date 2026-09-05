# FIX13 指示燈小門視窗中心改由實際燈孔排列推導

日期：2026-08-20

## 使用者確認規則

原始 `指示燈/盒子.dxf`、`指示燈/小門.dxf` 與早期程式中的 `191 / 155 / 105~205 / 135+90*i` 等座標，來源是實際樣本量測後寫入；樣本只能當參考，不能假設它本身已精確置中。

正式規則改為：

```text
layer_groups
    ↓
盒子實際生成的指示燈孔
    ↓
取得整組指示燈排列 bbox 中心
    ↓
計算「燈孔排列中心 - 盒子中心」offset
    ↓
小門放在盒子淨開口中心（四邊門縫各 3.5）
    ↓
小門視窗中心 = 小門成品中心 + 同一個 offset
```

因此：

- 一組與多組都不再固定使用樣本的絕對視窗中心。
- 不要求樣本中的 `191`、`155` 數字本身相等。
- 真正要求的是組裝後，小門視窗中心跟著目前實際生成的整組指示燈排列中心。
- 如果未來盒子燈孔排列規則移動，小門視窗必須自動跟著移動。

## 保留的樣本形狀規則

樣本仍提供已確認的「視窗形狀／留量」，但不提供永久絕對位置：

### 一組

- 視窗寬：100 mm
- 圓角：R50
- 高度：實際燈孔中心 Y span + 上下各 30 mm

### 多組

- 視窗寬：實際燈孔中心 X span + 左右各 30 mm
- 圓角：R70
- 高度：實際燈孔中心 Y span + 上下各 30 mm

因此原本多組「每多一組 +90」仍會自然成立，但來源變成實際燈孔 span，而不是另一套硬公式。

## 與上一輪尺寸鏈的關係

尺寸鏈保持不變：

```text
指示燈層數/組數
→ 盒子展開
→ 盒子成品外尺寸
→ 盒子內部淨開口 = 主門盒子開孔
→ 四邊各留 3.5
→ 小門成品
→ 小門自己的折邊
→ 小門展開
```

視窗位置只是在這條尺寸鏈算出小門後，再套用「燈孔排列相對盒中心 offset」。

## 移除的舊邏輯

`ae.get_stretched_door_data()` 的指示燈小門路徑不再：

```text
由 H_val - 374 猜 layers
由 W_val - 324 猜 g_max
固定 win_x_min = 105
一組固定 win_x_max = 205
多組固定 75 + 90*g_max
```

也不再建立未被真正使用的 `x_holes=[155] / [135+90*i]` 來暗示位置。

## 新資料 ownership

### `DoorPartSpec`

新增：

```text
indicator_window_groups: tuple[int, ...] | None
```

放在 dataclass 最後，維持既有 positional 相容性。

### `manufacturing_api.indicator_small_door_spec()`

直接把原始 `layer_groups` 寫入 `DoorPartSpec.indicator_window_groups`。

### `_door_export()`

共用小門 baseline export 直接把 `indicator_window_groups` 傳進 AE；不再允許 AE 從 W/H 反推。

### GUI

單門預覽、多門 cell component editor、Door 內嵌小門頁、獨立小門開孔 editor 都直接把當下 `groups` 傳給 AE。

## 新幾何函式

`ae.indicator_small_door_window_geometry()`：

1. 呼叫既有 `get_indicator_box_data(layer_groups, T)`。
2. 從實際 `CUTTING` Ø31（R15.5）燈孔取得 bbox。
3. 用 bbox 中心作為整組燈孔排列中心。
4. 計算相對盒子展開中心的 offset。
5. 把相同 offset 套到小門成品/折彎面中心。
6. 由實際燈孔 span + 已確認 margin 算視窗 W/H。

這樣未來只要盒子的燈孔生成規則改變，視窗位置會跟著變，不需要同步修改第二套座標。

## 數值驗證

T=2、四邊門縫 3.5、小門折邊 19：

### 1 層 1 組

- 小門展開：253 × 372
- 實際燈孔排列相對盒中心：X +28、Y +1
- 小門視窗：100 × 240
- 新視窗中心：154.5, 187
- 新 bbox：104.5~204.5 / 67~307

舊樣本約為 105~205 / 68~308；新值不是硬改 0.5/1 mm，而是尺寸鏈修正後依同一中心規則自然產生。

### 多組 `(3,2)`

- 小門展開：413 × 652
- 實際燈孔排列相對盒中心：X +18、Y +1
- 視窗：240 × 520
- 視窗中心：224.5, 327

## 驗證

TDD RED：

- 舊 `DoorPartSpec` 沒有 `indicator_window_groups`。
- AE 沒有中心推導函式。

GREEN：

- 6 個新幾何/資料流測試通過。
- 實際 headless DXF：一組視窗 100×240，多組 240×240（1 層 3 組）可被解析。
- 人工平移盒子實際燈孔 `(+7,-3)`，小門視窗中心同步平移 `(+7,-3)`，證明不是新硬座標。
- 實際 Tk GUI component context：一組與 `(3,2)` 多層多組皆讀到新的視窗中心。
- 相關 GUI/startup/factory-reset 回歸 26 passed；另 4 個舊 Fold Designer integration 測試在修改前同一版本已可重現相同失敗，與本次變更無關。

## 不變更事項

- 盒子與小門仍為全域共用件，不分 PW / PSR / RF。
- 一組盒子寬 326 的特殊尺寸規則保留。
- 2 組以上盒子排列規則保留。
- 盒子 → 淨開口/主門開孔 → 小門 policy 門縫（目前預設 3.5 mm）的單一尺寸鏈保留。
- 指示燈孔、名牌孔、MARKING 的既有生成規則本輪不改。
- 視窗一組 R50、多組 R70 與既有留量規格保留。


## Follow-up：小門門縫顯示不得寫死

- `small_door_gap` 的計算來源仍是 `ManufacturingPolicy.indicator_small_door_gap`。
- 設定來源為 `[INDICATOR_BOX] small_door_gap`，缺省才 fallback `3.5`。
- GUI 小門尺寸鏈說明改為讀取同一 policy 動態格式化；例如設定 `4.0` 時顯示「四邊各留 4 mm」。
- 本 follow-up 不改任何盒子、小門、視窗或指示燈幾何。

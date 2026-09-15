# Phase6 3D 設定中心設計

## 目標

將會影響板金製造尺寸、加工幾何與預設值的設定集中到 FoldDesigner 3D 視窗右側圖形上方。`config.ini` 繼續作為啟動預設值與「儲存為預設值」的持久化來源；主 GUI 現有全域 W/H/D/T/FW 與 CornerType 控制先保留並雙向連動；主 GUI 內的折彎尺寸/板件專屬數值輸入直接移除。

## 邊界

### 納入設定中心

- 全域：W/H/D/T/FW、DRAW_STOCK、RELIEF、NOTCH 相容參數。
- 箱身：zl1/zl2/zr1/zr2/z_comp。
- 封頭/封尾共用：yl1/yr1/ytop1/ybottom1、掛孔與方孔規格；封尾額外底孔。
- 門：door_gap_w/h、四邊 fold。
- 底板：四邊 shrink、bend。
- 指示燈盒：fold。
- 指示燈小門：fold。
- Unknown 模式板件 CornerType/左右相同狀態：主 GUI 與 3D 雙向共用。

### 不納入預設值

- 當次輸出勾選、目前選取板件、視窗位置、3D 相機/透明度。
- 當次新增孔實例座標、多門此次分割配置、目前選取孔等工作狀態。

## 單一資料來源

執行期間以 `settings_state` 字典作為統一設定狀態；主 GUI Tk 變數、3D 設定面板與 PartSpec 皆讀寫這份狀態。`config.ini` 僅在啟動讀入以及使用者按「儲存為預設值」時寫入。

資料流：

`config.ini -> load settings -> settings_state -> main GUI / 3D / PartSpec`

3D 與主 GUI 的全域欄位使用 callback + trace 雙向連動，並以 guard 避免遞迴。

## UI

- FoldDesigner 右側 renderer 上方新增「設定中心」。
- 開啟 3D 時預設顯示「全域設定」；目前板件仍繼續在 renderer 顯示。
- 點左側板件按鈕時，設定中心切到該板件設定。
- 設定中心提供「全域設定」按鈕，可隨時回首頁。
- 每個 context 最下方有「儲存全域預設值」或「儲存此板件為預設值」。
- 設定修改即時套用目前工作，不自動寫檔。

## INI 相容

- 不刪除、不替換 `config.ini`。
- 保留現有 section/key。
- 底板四邊 shrink 為了支援獨立預設，新增可選 `shrink_top/bottom/left/right`；舊版只有 `shrink` 時仍回退到共同值。
- 指示燈小門預設新增 `INDICATOR_SMALL_DOOR/fold`；不存在時回退 19。
- CornerType 預設使用 `CORNER_<PART>` section；不存在時沿用核心預設。
- 寫入設定同時更新目前執行中的 `ae_engine.ae` runtime default/RELIEF_CONFIG，避免存檔後本次工作仍使用舊值。

## 主 GUI 移除項目

- 左側「進階參數設定（板厚/折彎）」整個折彎數值區不再建立。
- 箱身預覽頂部保留全域 FW/T，移除 z_comp。
- 底板預覽頁移除 shrink/bend Entry，只保留畫布與非設定操作。
- 其他已存在的 W/H/D/T/FW 與 CornerType 先保留，並與 3D 共用狀態。

## 製造邊界

- 不修改 `fold_designer_original.py` Renderer。
- 不修改 `ae_engine` API/PartSpec/manufacturing_api。
- FoldDesigner 仍只是 UI adapter；正式 DXF 仍由現有 `manufacturing_api.generate_part()` 路徑輸出。

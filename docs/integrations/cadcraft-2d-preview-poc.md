# WHD × CADCraft：原 2D 開孔編輯器的可選試看原型

**狀態：PoC／試驗功能；不取代 WHD 現有 2D 編輯器。**

## 使用方式（Windows）

1. 從官方 https://getartcraft.com/apps/cadcraft 安裝 CADCraft 獨立桌面版；不需安裝整套 ArtCraft Launcher。
2. 若 `cadcraft.exe` 不在 PATH，於啟動 WHD 的同一個命令視窗設定：
   - cmd：`set "WHD_CADCRAFT_GUI=C:\\Program Files\\CADCraft\\cadcraft.exe"`
   - PowerShell：`$env:WHD_CADCRAFT_GUI = 'C:\\Program Files\\CADCraft\\cadcraft.exe'`
   - **請以實際安裝的 .exe 完整路徑取代範例**。
3. 在 WHD 開原本的「開孔編輯」，按工具列 **CADCraft 試看**。
4. CADCraft 開啟目前板件的**獨立暫存檢視 DXF**。未找到 CADCraft 或孔位無效時會提示錯誤，原 WHD 2D 編輯仍正常使用。

## 已做與尚未做

- 現有 2D 開孔定位、拖拉、撤銷、畫布、儲存與 3D/製造流程均**不變**。
- 按鈕只在使用者點擊時，透過 WHD 原有 `resolve_surface_features` 的定位結果產生檢視副本，**不重新推導折彎或製造幾何**。
- 有權威 `DrawingScene` 時保留其已存在的圖層／線條；目前編輯孔位額外標在 `CHECK`，不輸出為製造用 `CUTTING`。若沒有圖面，僅以 `CHECK` 畫出工作板面外輪廓與孔位。
- 暫存 DXF 明確設定 `$INSUNITS=4`（毫米）；真正 CADCraft CLI 往返測試同時驗證座標、圖層及單位，避免外部 CAD 把毫米當成公尺。
- CADCraft 是**外部獨立視窗**，不是內嵌在 Tkinter；CADCraft 改的暫存檔**不會回寫** WHD、專案、任何基準 DXF 或製造結果。暫存檔留在系統 Temporary 目錄供外部程式讀取。
- 沒有裝 CADCraft 時不必下載、安裝，也不會在 WHD 啟動或一般 2D 操作時執行外部程式。
- 目前只有 Python/Tk 接線與模擬啟動測試；**真正的 Windows CADCraft GUI、複雜圖塊顯示、編輯後雙向導回、效能優劣尚未驗收**。
- 若要正式雙向開孔編輯，需要獨立的 import→geometry/feature validation→差異預覽→使用者確認→WHD Session commit 交易，不能直接覆寫 DXF。

## 回歸判準

`tests/test_cadcraft_hole_editor_preview.py` 檢查 DXF 真正序列化、原板面／孔位座標、獨立 `CHECK` 預覽層、基準物件不變、未安裝可安全退出、外部程序啟動失敗不影響既有基準檔。納入 `tools/product_ci_regression.py` 必跑選擇器。

這不是 #1820 的效能採用結論；首次載入、平移縮放、程序啟動與 RSS 對照仍依 #1820 獨立量測，Windows UAT 待驗。

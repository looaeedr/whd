# WHD × CADCraft：原 2D 開孔編輯器的可選試看原型

**狀態：PoC／試驗功能；不取代 WHD 現有 2D 編輯器。**

## 使用方式（Windows）

1. 從官方 https://getartcraft.com/apps/cadcraft 取得 CADCraft Windows 免安裝版（Portable），保留其必要附屬檔案。
2. **不用設定 Windows 環境變數，也不用 PATH。** 將免安裝版的內容放在 WHD **主程式同層**的 `cadcraft` 子資料夾，預設採用固定相對路徑 `./cadcraft`：

   ```text
   WHD/
   ├─ gui.py                # 以 Python 執行時
   ├─ WHD.exe               # 打包執行檔時（若有）
   └─ cadcraft/
      ├─ cadcraft.exe
      ├─ cadcraft-cli.exe
      └─ ...原版附屬檔案
   ```

   - 來源碼啟動：相對於 `gui.py` 所在 WHD 根目錄（即使從其他工作目錄啟動也一樣）。
   - 打包 EXE 啟動：相對於 WHD 執行檔所在目錄。
   - 兩個實體路徑必須存在；找不到會提示 `<WHD 程式目錄>/cadcraft`。
   - `cadcraft/` 屬使用者本機第三方免安裝工具，已加入 Git 忽略清單，不會被版控或打包程式自動下載。
3. 在 WHD 開原本的「開孔編輯」，按工具列 **CADCraft 試看**。
4. CADCraft 開啟目前板件的**獨立暫存檢視 DXF**。未找到 CADCraft 或孔位無效時會提示錯誤，原 WHD 2D 編輯仍正常使用。

## 已做與尚未做

- 現有 2D 開孔定位、拖拉、撤銷、畫布、儲存與 3D/製造流程均**不變**。
- 按鈕只在使用者點擊時，透過 WHD 原有 `resolve_surface_features` 的定位結果產生檢視副本，**不重新推導折彎或製造幾何**。
- 有權威 `DrawingScene` 時保留其已存在的圖層／線條；目前編輯孔位額外標在 `CHECK`，不輸出為製造用 `CUTTING`。若沒有圖面，僅以 `CHECK` 畫出工作板面外輪廓與孔位。
- 暫存 DXF 明確設定 `$INSUNITS=4`（毫米）；真正 CADCraft CLI 往返測試同時驗證座標、圖層及單位，避免外部 CAD 把毫米當成公尺。
- CADCraft 是**外部獨立視窗**，不是內嵌在 Tkinter；CADCraft 改的暫存檔**不會回寫** WHD、專案、任何基準 DXF 或製造結果。暫存檔留在系統 Temporary 目錄供外部程式讀取。
- 沒有裝 CADCraft 時不必下載、安裝，也不會在 WHD 啟動或一般 2D 操作時執行外部程式。
- 本次預設路徑改為 `./cadcraft`，但只有既有 CUTTING 孔「平移」的 CADCraft 回傳通過部分 Windows 整合 UAT；全板件、改孔型／新刪孔、設備製造及其餘 GUI UAT 不在此路徑變更的驗收範圍。
- 若要正式雙向開孔編輯，需要獨立的 import→geometry/feature validation→差異預覽→使用者確認→WHD Session commit 交易，不能直接覆寫 DXF。

## 回歸判準

`tests/test_cadcraft_hole_editor_preview.py` 檢查 DXF 真正序列化、原板面／孔位座標、獨立 `CHECK` 預覽層、基準物件不變、未安裝可安全退出、外部程序啟動失敗不影響既有基準檔。納入 `tools/product_ci_regression.py` 必跑選擇器。

這不是 #1820 的效能採用結論；首次載入、平移縮放、程序啟動與 RSS 對照仍依 #1820 獨立量測，Windows UAT 待驗。

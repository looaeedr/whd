---
whd_doc_role: REFERENCE
whd_contract: reference-performance-issue1820-cadcraft-native-gui
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1820 CADCraft 真正桌面 GUI 顯示階段（Linux Xvfb）

此測試**不會**取代 WHD 原始 2D 開孔編輯器，也不會改動正式製造 DXF。#1911 已建立同 DXF 的 WHD Tk 元件與 CADCraft CLI 觀測；那不是桌面互動速度比較。

本 leaf 使用上游 CADCraft **v0.7.0 原始 Linux 桌面程式**，並依 upstream SHA256 校驗。Xvfb 模擬一個真的可顯示視窗，程式必須經過 `--control PORT` 提供的 localhost JSON 控制協定回答：

1. 真正 GUI 程序啟動並回覆 ping（不能以 CLI info 當成 GUI 啟動）。
2. 用 `app.open` 開啟同一份 WHD 2D 暫存 DXF，檢查 `drawing.inspect`。
3. 用 `ui.inspect` 確認目前 egui 狀態，再由 `ui.screenshot` 截取真正已呈現的桌面首幀。時間計算包括 GUI 啟動／開檔／首次畫面可見。
4. 用真正 GUI session 的 `engine.execute(zoom window)` 改變視圖，儲存之後的 `ui.inspect` 和桌面截圖。**這是引擎視圖指令，不冒充實體滑鼠滾輪／中鍵平移。**
5. 從同一 GUI 進程以 50ms 取樣真 RSS，保留原始截圖、執行 LOG、JSON、SHA256；任何控制或 screenshot 失敗，工作流直接紅燈，不能假成功。

局限：這是 Linux Xvfb 的原生 CADCraft UI，可用於確認真正桌面首幀和讀圖管線；**不是 Windows 實機**，與 WHD Tk 不同 UI 事件的時間不能直接評比。下一步仍需在同一台 Windows 裝置對相同實際受電箱 DXF，記錄 WHD 原編輯器啟動／平移／縮放／RSS 及 CADCraft GUI 相同真實指標與 DXF 準備、程序啟動、通訊額外成本。未取得等價資料前，#1820 不下 CADCraft 採用或全面內嵌結論。


## 已取得的原始 Linux GUI 實測（2026-10-18）

- Actions：https://github.com/looaeedr/whd/actions/runs/39095732711
- Artifact：`whd-1820-native-cadcraft-desktop-frame-and-zoom`，完整 `native-gui.json`、原 DXF、兩個 **真正桌面截圖**、GUI 日誌、私有沙盒設定。
- GUI upstream 0.7.0; Linux Xvfb 1600×1000、Mesa llvmpipe 軟體 OpenGL（**不是實機硬體 GPU 效能**）。
- CADCraft 程序啟動至 localhost 控制器成功 ping：約 **1936 ms**；到第一個成功的桌面 `ui.screenshot`：約 **2522 ms**（包括啟動、載入 4 個 DXF 圖元與保存畫面）。
- `app.open` 真正桌面開圖控制請求：約 **43.8 ms**；`drawing.inspect` 驗證真正的 4 個圖元、`dirty=false`。
- `engine.execute(zoom window)` 真正桌面視圖指令約 **33.7 ms**；下一個 `ui.screenshot` 約 **272 ms**。前後截圖已人工核對確實放大，沒有變造 source DXF。
- 50ms RSS 取樣 57 筆，最大約 **178.6 MiB**；最終 GUI 程序 RSS 約 **184.6 MiB**。
- 特別注意：其中的 Zoom 是命令／視圖 API，**不是滑鼠滾輪或中鍵拖曳**；圖面只有四個圖元、沒有複合受電箱生產圖。這些 CPU 軟體渲染結果不能拿來宣稱 CADCraft 比 WHD Tk 原畫布快。

下一步必須先在 Windows 同一機器做完整 WHD 和 CADCraft 真實 GUI 比較：相同一份 DXF 的首次可用時間、真實 pan／zoom、畫面圖元幾何完整性、程序啟動＋暫存 DXF 準備＋通訊總耗時、RSS 與運行穩定性。#1820 仍 OPEN，不得由這個 Xvfb 軟體渲染結果下採用結論。

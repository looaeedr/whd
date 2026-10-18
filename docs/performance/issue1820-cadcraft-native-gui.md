# #1820 CADCraft 真正桌面 GUI 顯示階段（Linux Xvfb）

此測試**不會**取代 WHD 原始 2D 開孔編輯器，也不會改動正式製造 DXF。#1911 已建立同 DXF 的 WHD Tk 元件與 CADCraft CLI 觀測；那不是桌面互動速度比較。

本 leaf 使用上游 CADCraft **v0.7.0 原始 Linux 桌面程式**，並依 upstream SHA256 校驗。Xvfb 模擬一個真的可顯示視窗，程式必須經過 `--control PORT` 提供的 localhost JSON 控制協定回答：

1. 真正 GUI 程序啟動並回覆 ping（不能以 CLI info 當成 GUI 啟動）。
2. 用 `app.open` 開啟同一份 WHD 2D 暫存 DXF，檢查 `drawing.inspect`。
3. 用 `ui.inspect` 確認目前 egui 狀態，再由 `ui.screenshot` 截取真正已呈現的桌面首幀。時間計算包括 GUI 啟動／開檔／首次畫面可見。
4. 用真正 GUI session 的 `engine.execute(zoom window)` 改變視圖，儲存之後的 `ui.inspect` 和桌面截圖。**這是引擎視圖指令，不冒充實體滑鼠滾輪／中鍵平移。**
5. 從同一 GUI 進程以 50ms 取樣真 RSS，保留原始截圖、執行 LOG、JSON、SHA256；任何控制或 screenshot 失敗，工作流直接紅燈，不能假成功。

局限：這是 Linux Xvfb 的原生 CADCraft UI，可用於確認真正桌面首幀和讀圖管線；**不是 Windows 實機**，與 WHD Tk 不同 UI 事件的時間不能直接評比。下一步仍需在同一台 Windows 裝置對相同實際受電箱 DXF，記錄 WHD 原編輯器啟動／平移／縮放／RSS 及 CADCraft GUI 相同真實指標與 DXF 準備、程序啟動、通訊額外成本。未取得等價資料前，#1820 不下 CADCraft 採用或全面內嵌結論。

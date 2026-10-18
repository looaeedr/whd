# #1820 CADCraft 與 WHD 2D 效能評估：階段一

## 基準

前置 #1819 已完成 GitHub localX 測試及 R5-2600 的 Windows 1/3 連各 30 輪驗收。保留 WHD 原本 2D 開孔操作、定位、撤銷、製造幾何及 DXF 權威。CADCraft 目前是**選擇性外部試看**，非取代編輯器。

## CADCraft 版本與授權

來源為 storytold/cadcraft，上游程式採 MIT 或 Apache-2.0 雙授權，字型圖示和品牌需要分開注意。工作流固定 v0.7.0 Linux release，透過上游 SHA256SUMS.txt 校驗。現有整合走暫存 DXF 加獨立桌面程序，不內嵌、不回寫。

## 量測方法

工具：`tools/issue1820_whd_cadcraft_dxf_benchmark.py`

專用 CI：`.github/workflows/whd-issue1820-dxf-renderer-evidence.yml`

- 由真正 WHD 開孔模型輸出相同一份檢視 DXF，保留原始 SHA256、毫米單位、孔位、輪廓、折線與圖層。
- WHD 路線以真 Tk 畫布、`Phase6HoleEditorCanvasView.render()` 和實際 DrawingScene 元件渲染，記錄首次與暖機時間、程序時間及 RSS。
- CADCraft 路線以原版 CLI 的實際子程序量測 DXF 載入、全圖 PNG 及指定視野圖像，記錄程序啟動＋操作耗時和 RSS。
- 3 次獨立樣本與完整數據／圖片上傳 artifact。遇到不支援的幾何立即失敗，不得忽略未畫的弧線、板件或圖層。

## 不能由這份數據推論

WHD Tk 畫布繪圖和 CADCraft CLI 的 PNG 生成**不是等價 GUI 操作**。CLI 的指定視野不是實際滑鼠縮放／平移，WHD 元件級首次渲染不是整個 WHD 開啟流程；因此本輪**不排名、不下導入結論**。

## 第二階段硬閘門

在同一台 Windows 主機、同尺寸視窗、同一份實際受電箱 DXF 上，量測完整 WHD 開孔操作與 CADCraft 桌面視窗的首次可用時間、pan/zoom、RSS、DXF 準備、外部程序啟動與通訊。CADCraft 提供 `--control PORT` 的 JSON 控制通道，可觀察 `app.open`、`ui.inspect` 與 UI 操作，但這些控制需要真正桌面 GUI，不能拿 Linux CLI 的結果替代。

比較前需核對圓弧、孔位、折線、顏色、圖層、座標、毫米單位。只有效益明確且正確性通過時才考慮獨立實作工單；沒有明確好處就只保留可選試看，原 WHD 2D 必須保留。

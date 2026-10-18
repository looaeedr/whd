# #1820 — CADCraft v0.8.0 / R5-2600 Windows GUI 實測（2026-10-18）

## 版本校正

上游 `storytold/cadcraft` 官方 GitHub `releases/latest` 已確認 **v0.8.0**、`prerelease=false`，發布於 2026-10-17 23:35:10 UTC。既有 #1911/#1913/#1916 使用 v0.7.0，**僅能作歷史基準**，不得稱最新版成果。本次測試採官方 `cadcraft-0.8.0-windows-x64-portable.zip`（60,173,938 bytes），以對應的官方 `SHA256SUMS.txt` 校驗 SHA256：

`939f970955653720558a90b0c788a356903fbe3b085e1bfb33fb67441957f92d`。

安裝位置僅在 R5-2600 的 `C:\Users\looae\Documents\WHD_1820_CADCraft_UAT\`；沒有 MSI、PATH、全域 Python、WHD 功能或正式 X 變動。

## Windows 真實 GUI，同 DXF 三輪

測試固定 R5-2600 `Z:\localX` HEAD `9fc85f93ec0f882562bc84824cd5a41f32daec57`（**不是後續 GitHub localX 最新 SHA，不能冒充已驗證所有新提交**），三次 WHD 原生主程式→原統一開孔 GUI 與 CADCraft v0.8.0 原生桌面 GUI 同 DXF、交錯順序。

測試用 WHD 原 Feature 輸出隔離的單一暫存 DXF，SHA256：

`3586b3afd6409001001cc1764fc4a31f585f06695f433a5fe25fee7c860c9c55`。

| Windows 第一張真正 GUI 可見畫面 | 第 1 次 | 第 2 次 | 第 3 次 | 中位數 |
|---|---:|---:|---:|---:|
| WHD 原主程式→原開孔編輯器 | 9512.74 ms | 9548.93 ms | 9683.12 ms | **9548.93 ms** |
| CADCraft v0.8.0 獨立檢視器 | 1337.05 ms | 1366.14 ms | 1313.91 ms | **1337.05 ms** |

**這不是等價的替換評分**：WHD 載入有編輯功能的主程式，CADCraft 只是獨立 Viewer；沒有計入 WHD 使用者切至 CADCraft 的 DXF 匯出、程序切換、控制通道、返回 WHD 繼續開孔等端到端成本，亦沒有同一操作的滑鼠 pan/zoom、編輯和製造反寫。

## Windows 進程樹 RSS 修正

舊 `tools/issue1820_whd_real_editor_gui_probe.py` 的 `psutil.Process(proc.pid)` 在 Windows venv 路徑只抓到**約 6.8 MiB 的 Python redirector**，並未量到真正 Tk GUI 子程序，這個數值不可引用。現已改成 50ms 取樣父進程及所有遞迴子進程 RSS，並分別報告 process-tree / descendant 數據。

隔離的 Windows 實測三次真正 WHD GUI 進程樹峰值為 **145.691 / 146.105 / 146.160 MiB**，中位 **146.105 MiB**；發現實際 2–3 個程序。CADCraft v0.8.0 三次 GUI 單進程原始取樣峰值 **300.07 / 289.70 / 284.34 MiB**。這是不同工作量的程序資源觀察，不是硬體或 UI 效率的公平排名，且未測整套 WHD 加外部 CADCraft 同時運行的增量峰值。

## 實際 DXF 負載（Windows CADCraft v0.8.0）

以下為使用者 R5-2600 Downloads 的**唯讀檔案**；測試先複製到隔離資料夾、絕不覆寫原圖，原 DXF **不提交 GitHub**。

| 原圖 | ezdxf modelspace 圖元 | CADCraft `drawing.inspect.entityCount` | CADCraft 首幀 |
|---|---:|---:|---:|
| `400_cn.dxf` | 81 | 81 | 1753.53 ms |
| `800x3.dxf` | 54 | 54 | 1380.62 ms |
| `士林中底板(1).dxf` | 8620 | 8620 | 1650.77 ms |

圖元總數吻合只驗證成功載入數量，**不等於**逐一驗證 ARC／CIRCLE／DIMENSION／INSERT／字體、顏色、標註與尺寸完全正確。特別是 `800x3.dxf` 和大型板件 `$INSUNITS=0`（來源未指定單位），不能偷偷假定毫米並把換算當驗收通過。`400_cn.dxf` 是毫米單位。

## 測試原始檔與門檻

完整來源／LOG／截圖／量測資料保留在 R5-2600：

`C:\Users\looae\Documents\WHD_1820_CADCraft_UAT\`

包括 `DC_actions.log`、`WINDOWS_080_SUMMARY.json`、`cadcraft_version.txt`、原生 GUI 及縮放後截圖、各 worker JSON，及隔離校驗程式。GitHub 倉庫僅記錄**結果與工具修復**，不包含使用者 DXF。

**階段判斷：保留 WHD 現有 2D 編輯器為唯一正式開孔入口；CADCraft v0.8.0 僅為可選外部試看。** #1820 仍需比較完整 Windows 端到端操作、實際大圖幾何／單位驗證、開孔互動、pan/zoom、回寫／製造安全性與維護成本；沒有證據前不採用 CADCraft 替換原本 2D，正式 X 不變。

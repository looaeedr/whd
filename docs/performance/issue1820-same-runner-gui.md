# #1820：同一 runner 真正 WHD 與 CADCraft GUI 配對觀測

本階段前已完成：#1911 同源 DXF 的 WHD Tk/CADCraft CLI、#1913 真 CADCraft 原生桌面首幀、#1914 真 WHD 主程式到原 2D 開孔視窗首幀，各自測試均全綠。它們過去分別使用不同 runner，不能直接用耗時排名。

這次固定 upstream CADCraft v0.7.0 的 SHA256 release，在同一台 Ubuntu 24.04 runner、同一個 Xvfb 1600×1000 畫面與 Mesa 軟體 OpenGL 上，將 WHD 原始開孔與 CADCraft 原生 GUI 用**完全相同來源 SHA256 的 DXF**各測三次，執行順序 A→B、B→A、A→B。兩者都是實際 GUI、都必須有可讀的第一張呈現畫面並保留原始 PNG、JSON 和 stderr。

WHD：隔離 Python 程序 → 正式 `Phase6PrimaryApplication` → 原 `_open_unified_hole_editor` → Canvas 內容存在及顯示／首幀擷取。CADCraft：獨立桌面程序 → 真本機控制通道 → 開啟相同 DXF → 真 `ui.screenshot` 首幀 → 引擎縮放後第二張真畫面。比較的主數值為「各自程序啟動 → 首次呈現原生 GUI」及同程序 RSS；不得拿元件重畫的 1ms 與另一邊完整啟動的幾秒比較。

### 不代表產品選型的限制

- 同 Linux runner 和相同 DXF，解決了不同 runner 的部分差異；但 **WHD 是啟動 3D 主程式再進入具編輯能力的開孔器，CADCraft 是獨立 CAD 檢視程式**，使用者任務仍不相同。
- CADCraft 即使較快，WHD 外掛還需產生暫存 DXF、啟動外部程序、切換視窗與通訊；這些都要算進真正 WHD 使用者等待時間。
- CADCraft zoom 是桌面應用的控制 API，仍非實際滑鼠；WHD 相同平移／縮放／選取／開孔操作尚未在此同一腳本量測。
- 這是 4 個圖元的簡單孔圖，不是具多圖層、折彎、弧線和大量孔的真實受電箱成品圖。不能用小型檢視圖取代大圖正確性與效能驗收。
- 樣本數三次，runner 的記憶體配置器與 OS 快取不可完全消除，保留全部原始值而不是只提供優勝宣言。
- 真 Windows 同機、同大型受電箱 DXF、完整原 WHD 開孔、CADCraft 外掛全部成本、滑鼠縮放平移與最終 DXF/單位/圖層驗證仍是 #1820 最終採用判定的門檻。

如果最終效益不夠，就保留現有可選「CADCraft 試看」而不取代 WHD 原本操作。**正式 X 不動，也不額外授權 DC 操作 Windows。**

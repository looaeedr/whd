# #1820：WHD 真正主程式到原 2D 開孔視窗的首幀基準

前置 [#1819](https://github.com/looaeedr/whd/issues/1819) 已完成。此測試與 #1911 的 Tk Canvas 元件基準不同：**直接執行 WHD Production `Phase6PrimaryApplication`、呼叫現有原始 `_open_unified_hole_editor`，等待畫面真正出現**，然後從 Xvfb 截取實際開孔編輯視窗。

使用和 CADCraft 原測試同源的 WHD 開孔特徵與基準 DXF，原始 CHECK 編輯孔由原 Feature 渲染（而不是把檢視 DXF 的 CHECK 與 Feature 雙重畫上），保留 CUTTING/BEND 基準線與原視窗控制。

工具：`tools/issue1820_whd_real_editor_gui_probe.py`。流程用兩個隔離 Python 進程測得完整程序啟動到原開孔視窗首次可見、主程式啟動後開編輯視窗的時間與 RSS，驗證 Canvas 項目、原特徵與真 screenshot。每項皆保存原 JSON、Xvfb 首幀 PNG 及 traceback（如有）。

此 Linux 真實 GUI 結果不能假稱 Windows 使用者滑鼠操作，也不能拿它和 CADCraft 另一台 runner 的軟體 OpenGL 結果做精確速度排名。CADCraft 需要另外計入外部程式／暫存 DXF／畫面／通訊的總成本。

**WHD 原有 2D 開孔、撤銷、定位及製造權威全部保留。** 此測試不改產品功能，不修改正式 X；#1820 採用與否仍待同 Windows 實機大圖與真實縮放／平移比較。

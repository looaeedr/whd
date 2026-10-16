# #1816｜士林 NFB 原始 DXF 真圖預覽效能（2026-10-16）

> **部分驗收證據。** 此處是真正的士林來源 DXF，使用 WHD 原始 NFB 真圖預覽程式，在隔離 Linux/Tk/Xvfb 測得。**不等於 Windows 實機 UAT、製造孔位來源認證，亦非整體 GUI 效能改善百分比。** 原始 CAD 不放入本公開 GitHub repo，也不放入公開 Actions Artifact。

## 權威來源與隔離

- 當輪 GitHub `localX` 基準 `022b9b22bebf1ff628e5483c658eb67c26d5bd34`；臨時 [PR #1829](https://github.com/looaeedr/whd/pull/1829) 的 source-only staging SHA `d18c89ea6450fa0a66939e267c8c79e366f69991` **只新增源碼打包 workflow，沒有更動產品模組**。取回已在 GitHub 公開追蹤的真實程式後，私人原圖只存在隔離的雲端測試副本。
- 真圖：`士林/400_140X257_107.dxf`，來自使用者原有私人檔案庫，123,089 bytes，SHA-256 `8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3`。沒有複製到 GitHub。
- 索引：既有 `基準檔/開孔/NFB/開關索引.csv`，`士林` 欄中 2P400／3P400SN 等行確實指向上述原檔；未替換索引、沒有虛構模型。
- 原圖模型空間 41 個圖元（22 LINE、8 CIRCLE、6 LWPOLYLINE、5 ARC）。每筆成功樣本都核對 SHA、41 個來源圖元、41 個實際 Canvas 圖元、縮放比例或平移後視口中心的有效變更、無 Tk grab。
- WHD 真實呼叫鏈：`NfbDxfSourcePreviewPanel.show/zoom/_move/paint` → `NfbDxfPreviewCache.load` → `inspect_indexed_nfb_preview` → `inspect_nfb_dxf_source` → `ezdxf.readfile`；測量 Tk `update_idletasks()/update()` 三輪提交後的操作耗時，不是只量 Python 控制器返回。
- Linux/Xvfb 1600×1000×24；Tk 視窗 1100×720；Python 3.13；ezdxf 1.4.4；每個工作者全新 Python 程序，OS filesystem/page cache **沒有清除**。不同於先前 GitHub Actions Ubuntu 24.04／Python 3.12 主效能基準，**不能跨機直接比較改善比率**。

## 真實量測（ms）

每個 fresh worker 第一次載入一次，之後在同一程序重複 20 次暖載入、縮放與平移。5 個程序順序完成，共 305 筆，失敗 0。P95 為 nearest-rank。

| 操作 | n | Median | P95 | 本批 `ezdxf.readfile` 次數 |
|---|---:|---:|---:|---:|
| 新 Python 程序首次載入 DXF | 5 | 53.82 | 69.10 | 5 |
| 暖快取重複載入同一來源 | 100 | 4.23 | 19.58 | **0** |
| 真圖縮放，畫布更新完成 | 100 | 3.07 | 10.61 | **0** |
| 真圖拖曳／平移，畫布更新完成 | 100 | 2.91 | 11.69 | **0** |

**結論：** 本測試已直接證實現有 `NfbDxfPreviewCache` 在相同來源、同進程暖載入與視口互動時不會重新解析 DXF；來源圖元確實更新至 Tk Canvas。這不是連續滑鼠高頻拖曳 FPS 測試，也不能推論其他 DXF 型號同速。

## 完整產品 GUI 交叉驗證（較弱證據）

同一隔離原始碼與同一真圖下，已執行正式 `tools/whd_performance_baseline.py --worker --bays 1 --cycles 2 --dxf-index <private-index> --brand 士林 --filename 400_140X257_107.dxf`；在正式受電箱單連 GUI 的 JSONL 取得 **23 筆 status=ok**，包含：
- 第一次 DXF source load 39.95 ms，`ezdxf.readfile` 1 次。
- 兩次暖載入 2.62 / 3.94 ms，兩次 zoom 約 2.06 / 2.40 ms、pan 約 2.26 / 1.55 ms，均無額外 `readfile`。
- 但外層執行命令遭逾時回報中斷，**未取得可信的成功 process exit code**；只能列為補充交叉證據，不能用作正式成功的整批 product run。主要接受的 DXF 數值是上表的 305 筆正常完成樣本。

## 重現與檔案保護

正式基準工具本來就支援 `--dxf-index`：`python tools/whd_performance_baseline.py --samples 3 --cycles 10 --output work/perf/with-dxf.json --dxf-index <private-index> --brand 士林 --filename 400_140X257_107.dxf`。只允許在隔離 checkout、原圖可讀、索引與 DXF 名稱相符的前提下執行。測試紀錄、雜湊、median/P95 與取樣數可以保存；不得把原始 DXF、原圖截圖、座標點資料或包含原始 CAD 的壓縮檔上傳到公開 GitHub/CI artifacts。原始測試資料由當次執行環境另行保留，GitHub 文件不冒稱私人檔案可由 public URL 取得。

## 尚未完成的完整驗收

- Windows `Z:\\localX` 實機 GUI 使用者驗收未執行，不能以 Linux Xvfb 代替。
- 更細的實際物理板件／拆片重算次數與 cache hit/miss，不能拿 `_domain_inputs_for_part` 的原始輸入建立呼叫冒充。
- 準確瞬間記憶體峰值、比 30 輪更長的實機穩態，以及連續拖曳畫面 FPS 未證實。
- 任何製造幾何／孔位／NC 權威仍必須走獨立來源認證；本次只證明原圖的 read-only 預覽速度。
- #1816 保持 OPEN；依賴其完整驗收的 #1817 不因本項先完成而自動放行；正式 `X` 仍須使用者另行驗收及 `/推推`。

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

## v0.8.0 開孔試看獨立交叉驗證補充

原本的 `.github/workflows/whd-cadcraft-hole-preview-crosscheck.yml` 先前仍固定 v0.7.0，並非只靠 #1926 更新的三套 #1820 工作流就全數對齊。這次另外升級該工作流至 **v0.8.0**：官方 SHA256SUMS 下載校驗 → WHD 原 Hole Editor Feature 產生非製造用 CHECK 暫存 DXF → CADCraft 真正 CLI 讀取／另存 → 使用獨立 `ezdxf` 逐圖元比對孔位 XY、圓半徑、折線、CUTTING/BEND/CHECK、顏色和 mm 單位。這是 CLI DXF 載入與重存的幾何相容性測試，**不是 Windows GUI 實體縮放／平移、文字及所有複雜圖元的渲染驗收**。

## 測試原始檔與門檻

完整來源／LOG／截圖／量測資料保留在 R5-2600：

`C:\Users\looae\Documents\WHD_1820_CADCraft_UAT\`

包括 `DC_actions.log`、`WINDOWS_080_SUMMARY.json`、`cadcraft_version.txt`、原生 GUI 及縮放後截圖、各 worker JSON，及隔離校驗程式。GitHub 倉庫僅記錄**結果與工具修復**，不包含使用者 DXF。

**階段判斷：保留 WHD 現有 2D 編輯器為唯一正式開孔入口；CADCraft v0.8.0 僅為可選外部試看。** #1820 仍需比較完整 Windows 端到端操作、實際大圖幾何／單位驗證、開孔互動、pan/zoom、回寫／製造安全性與維護成本；沒有證據前不採用 CADCraft 替換原本 2D，正式 X 不變。

---

## R5-2600 完整實機續驗：2026-10-18（台灣時間）

### 證據界線

使用者明確允許 DC 進入 **R5-2600** 測試 #1820。Windows `Z:\localX` 在測試開始時真實讀回 `d986089f85feb48356b0aaaeaaae7e8e22972e34`（PR #1927 已合併）；操作僅在既有 `C:\Users\looae\Documents\WHD_1820_CADCraft_UAT\` 隔離寫出。原始 DXF、正式 X、WHD 製造圖、`Z:\localX` 追蹤程式碼均**未被測試改寫**。Windows 工作區原有兩個未追蹤檔亦保留。後來 GitHub `localX` 有其他提交，**此 UAT 不涵蓋這些較新 SHA**。

本次新增的可重現工具與原始 JSON：
- `r5_1820_preflight.py`、`r5_1820_geometry_check.py`、`r5_1820_deep_semantics.py`、`r5_1820_gesture.py`、`r5_1820_win32_mouse.py`、`r5_1820_concurrent.py`；位於上述 Windows 隔離資料夾，沒有提交含客戶 DXF 的檔案。
- `final_1820_v080/geometry_results.json`、`deep_semantics.json`、`cadcraft_gesture_results.json`、`win32_pointer_results.json`、`concurrent_results.json`、`concurrent_rss_50ms_samples.json` 和 Win32 實際截圖。
- 每項執行操作追加到原有 `DC_actions.log`；沒有偷偷重用先前的量測成為這次結果。

### Windows 原生滑鼠操作（真 OS 輸入）

CADCraft v0.8.0 原生 GUI 真正載入 8,620 圖元大圖，`app.open` 成功，`drawing.inspect.entityCount=8620`。只用控制協定合成的 `ui.drag(button=middle)` **未改變 view**，不得冒充 PASS。接著透過 Windows `user32` 對真實 CADCraft 視窗送出**中鍵按下、滑鼠移動、放開、滾輪**，並以原生 `ui.inspect.view` 獨立回讀：

| 操作 | 前 → 後（CADCraft 真實 View） | 結果 |
|---|---|---|
| 中鍵平移 | center `[10978.676, -24804.845]` → `[-3052.061, -16620.248]` | **PASS** |
| 滾輪縮放 | height `71556.760649` → `62624.567717` | **PASS** |
| 同 DXF 不變 | 原始 SHA256 `c53d1977ef65362ab4c02fa3504df8702c399d429a9b3596523f011b73951dd0` | **PASS** |

實際桌面畫面 `final_1820_v080/cadcraft-win32-physical-input-after.png` 已保存；執行結束後還原游標和原先焦點，關閉測試開啟的 CADCraft 程序。

### 真正 WHD 開孔編輯器與 CADCraft 同時運行

在同一台 R5-2600，以同一 `d986089f...` WHD 程式開啟真正 `Phase6PrimaryApplication` → 原統一開孔視窗（94 個 Canvas items）；保留原編輯器運作時，用目前正式 `build_hole_editor_cadcraft_scene`／`save_cadcraft_preview_dxf` 產生一次性 CHECK 暫存 DXF，再啟動 v0.8.0 真正 CADCraft 桌面，載入同圖、查圖元並截取首幀。50ms 樣本同時採計兩者完整程序樹 RSS。

| 觀察項目 | R5-2600 單輪實測 |
|---|---:|
| WHD 原主程式 → 真正 Hole Editor 顯示 | 9,695.25 ms |
| WHD resolved CHECK DXF 準備 | 10.09 ms |
| CADCraft 啟動 → 載入／原生首張截圖 | 1,291.84 ms |
| 準備 DXF ＋ CADCraft 首幀 | **1,301.93 ms** |
| 同時 WHD process-tree RSS peak | 142,270,464 bytes |
| 同時 CADCraft process-tree RSS peak | 298,008,576 bytes |
| **同時合計 process-tree RSS peak** | **440,279,040 bytes（約 419.9 MiB）** |
| CADCraft 原生載入圖元 | 4/4 |

這是已開啟 WHD 開孔視窗後的**程序準備＋外部 GUI**成本；並**沒有**量到人手點擊工具列按鈕、桌面視窗切換及返回 WHD 重新編輯。小圖僅 4 圖元，不能把 1.30 秒直接宣告大型專案的端到端回寫速度。測試沒有回寫 WHD，沒有以 CADCraft 改寫製造資料。CADCraft 測試程序以 `terminate()` 主動結束（回傳碼 1），非測試途中閃退；WHD worker 正常 exit 0。

### 真正 DXF read→resave：比圖元數量更嚴格的驗證

對已隔離的四份圖，執行**官方 v0.8.0 CADCraft CLI 真實開啟及另存**至 `final_1820_v080/roundtrip_*.dxf`；原檔全程 SHA256 一致。使用獨立 `ezdxf.readfile()` 比對 DXF header、modelspace 幾何和屬性，並額外查圖塊定義及標註欄位（不把此步當 CADCraft viewer「回寫 WHD」功能）。

| 圖面 | 圖元數（前→後） | `$INSUNITS`（前→後） | 嚴格語意結果 |
|---|---:|---:|---|
| WHD 4 圖元 CHECK 試看圖 | 4→4 | 4→4（mm） | **PASS** |
| `400_cn.dxf` | 81→81 | 4→4 | **NOT EXACT：6 筆 INSERT/DIMENSION 屬性差異；區塊數 13→9** |
| `800x3.dxf` | 54→54 | 0→0（未指定） | **NOT EXACT：4 筆 DIMENSION 屬性／量測欄位差異** |
| `士林中底板(1).dxf` | 8620→8620 | **0→1（未指定→inch）** | **FAIL：單位改變、723 筆複合物件屬性差異** |

8,620 圖元檔的 723 筆差異以嚴格屬性簽章計算，涉及 **205 TEXT、29 INSERT、489 DIMENSION**。進一步分流發現部分 TEXT 轉成 DXF `\\U+XXXX` 字元編碼後經 `decode_dxf_unicode` 還原仍相同；INSERT 主要被補寫 1.0 scale／0 rotation；DIMENSION 的測量值、text midpoint 等屬性出現變化，不能直接標為等價。ARC 的少量原始浮點角度序列化差異已另記錄，六位小數正規化後與 LINE/CIRCLE/POINT 比對未發現 modelspace 基本圖元遺失。另存在圖塊定義數差異（大圖 520→522），且尚未證明所有標註渲染／布局像素一致。

**重要：DXF `$INSUNITS=0` 是「未指定單位」，不可在 CADCraft 另存後自動改成 `1`（inch）仍宣稱原圖單位完全保存；此例已構成保真驗收 FAIL。** 圖元總數一致只是載入數量觀察，絕非完整安全證據。

### #1820 決策與剩餘驗收

1. **確認保留 WHD 原 2D 開孔編輯器，CADCraft 只能作使用者選用、唯讀、單向試看。** 不取代 WHD 製造幾何，不用 CADCraft DXF 回寫 WHD。Windows 原生滑鼠 pan/zoom 已 PASS，並已取得真實同時 RSS 和可重現的 DXF 開圖成本。
2. **CADCraft 作為製造或完整保真編輯器的整合判斷為 NO-GO / DEFER**：目前有實際單位和標註語意的差異；不能將 `entityCount` 或 CI 的 4-entity roundtrip 當作全圖合格。若未來評估整合／回寫，須先修正、再重新驗證這三份真 DXF、DIMENSION/INSERT/TEXT、區塊和單位，並核實視覺等價。
3. 本次實機已確認上述特定版本；後續 GitHub `localX` 新施工需另驗差異。本報告是 CADCraft 採用評估的負面決策證據，**不是 CADCraft 替換驗收通過，也不是正式 X 發布證據**。


## #1820 後續：R5-2600 真圖保真，版本與字碼頁契約

歷史表格為官方未修補 v0.8.0 的首次觀測，**不得代替後續隔離修正版結果**。截至第三階段 #1944，官方來源 patch 的 Linux/Windows 原生 CLI 與 R5 三份真實 DXF 已確認單位與量測設定、已有的 DIMENSION group11/42，以及原本缺失的 489 筆 group42 全部保留；但仍未取得完整幾何與文字保真資格。

第三階段 R5 獨立比對（隔離資料夾 `unitless_native_1941/group42_real_1944/`，詳見 `R5_remainder_field_triage.json`、`R5_block_entity_field_triage.json`、`R5_dxf_codepage_provenance.json`）另揭露：

| 原始 DXF | 原 $ACADVER → 另存 | 原 $DWGCODEPAGE → 另存 |
|---|---|---|
| 81 圖元 | AC1032 → AC1032 | ANSI_950 → ANSI_1252 |
| 54 圖元 | AC1032 → AC1032 | ANSI_950 → ANSI_1252 |
| 8,620 圖元 | AC1009 → AC1015 | ansi_950 → ansi_950 |

CADCraft v0.8.0 `crates/io/src/dxf_write.rs::code_page` 針對 2007 以後版本寫出 `ANSI_1252`；`crates/io/src/lib.rs::save_version` 對舊版 DXF 使用所支援的最接近版本，寫入器則使用 R2000 結構。因此**這些是可定位的輸出格式變更**，不是只看圖元數能偵測到；R2018 的 codepage 宣告差異不能逕認中文字損壞，也不能在未驗證前逕認完全等價。另有圖塊內 264 處 TEXT 轉碼差異，部分原檔在 ezdxf 解碼時出現替代字元，尚缺 byte-level／正確 CP950 解碼的可核對證據。

`tools/issue1820_cadcraft_dxf_fidelity_gate.py` 除 `$INSUNITS`、`$MEASUREMENT` 外，新增 `$ACADVER` 和 `$DWGCODEPAGE` 作為 **嚴格保真硬閘門**；僅作 fail-closed 診斷，不擅自重寫來源檔頭，不把 CADCraft 另存結果回流 WHD 製造。後續真正修復文字／圖塊時應另設明確證據，若需刻意升版或改字碼頁，應視為版本轉換工作，與「原 DXF 無損另存」分別驗收。


---

## #1820 第五階段後的 R5-2600 實測結論（2026-10-18，台灣時間）

**這一節是 #1941、#1942、#1944、#1948、#1951、#1953 之後的最新事實。** 上文官方未修改 CADCraft v0.8.0 CLI 的 read→save FAIL 表格是歷史 RED，不能繼續當成修正版的現況，也不能因為修復單項後便宣稱全圖保真合格。

各版都是以官方 `storytold/cadcraft` v0.8.0 原始碼在隔離環境內施加小範圍實驗修補，Linux／Windows x64 原生 Rust CLI RED→GREEN；修補工具與 CI 工作流整合至 GitHub `localX`，**並非將修改後的 CADCraft 發布成官方版本，也沒有替換 Windows 上原 CADCraft 安裝**。

| 實圖／R5 隔離 read→save | 官方 v0.8.0 首輪 RED | 目前修正版 R5 結果 |
|---|---|---|
| 81 圖元、13 個圖塊 | 未引用 `*D1`～`*D4` 消失，13→9；`ANSI_950`→`ANSI_1252` | **81→81；13→13，零圖塊遺失；字碼頁 ANSI_950 保留；單位及既有標註位置/值不變** |
| 54 圖元、6 個圖塊 | 部分 DIMENSION 資料改寫，字碼頁改為 ANSI_1252 | **54→54；6→6；ANSI_950 保留；4 筆尺寸標註位置與明示值不變** |
| 8,620 圖元、520 個圖塊 | 單位未指定被改成 inch；489 筆原本缺失 DIMENSION group42 被新增 | **8,620→8,620；520→522 且零舊圖塊遺失；單位未指定仍未指定；489 筆 group42 缺失狀態保留；205 筆 model TEXT 和 823 筆 block TEXT 邏輯內容相同** |

修正版的 Windows x64 test-only CLI 由 [PR #1953](https://github.com/looaeedr/whd/pull/1953) 的 exact SHA `a1286d66b67fc44de180721e70c66dbe31eeff28` GitHub Actions 產出，七項 CI 全部 SUCCESS；PR 已合併 GitHub `localX`，squash SHA `f561be45aebc0c029fbf0cc0b6c85426557e0bc8`。實際 R5 驗證包括三組合成中文 TEXT 的官方版 RED／修正版 GREEN，以及三份原始真實 DXF 的修正版讀存；來源雜湊均不變。驗證檔案：
`C:\Users\looae\Documents\WHD_1820_CADCraft_UAT\unitless_native_1941\codepage_native_real\R5_codepage_native_real_results.json`；全操作紀錄在 `WHD_1820_CADCraft_UAT\DC_actions.log`。所有原始使用者 DXF 留在 R5，**未提交 GitHub**。

### 仍然不能核准 CADCraft 製造圖回寫

- **DXF R12 格式不保真**：8,620 圖元原圖 `$ACADVER=AC1009`，CADCraft 另存升級為 `AC1015`（R2000），並新增 `$MODEL_SPACE`／`$PAPER_SPACE` 結構圖塊；這是 DXF 版本轉換，沒有原格式輸出與跨 CAD 工具相容的證據。不可只改檔頭冒稱「保留 R12」。
- **嚴格 gate 仍然 FAIL_CLOSED**：`MODEL_DIFF / BLOCKS_DIFF / LAYERS_DIFF` 類型與預設屬性、資料序列化可能不同。限定座標與文字解碼比較未見漂移，不代表材質、字型視覺、全部圖層、layout 或其他 CAD 讀取器的完整語意通過。
- **效益不足以取代既有 2D**：R5 的既有 WHD 真開孔主程式約 9.55 秒與 CADCraft 只有 Viewer 首畫面約 1.34 秒，不是同工作量；WHD 已開啟後另起 CADCraft 的 DXF 準備＋首幀約 1.30 秒、雙程式同時峰值約 419.9 MiB，並增加視窗切換與回到 WHD 編輯的步驟。未有可比的端到端開孔工作流改善與全圖保真證據。

**現階段決策：CADCraft 僅保留可選單向唯讀試看，原 WHD 2D 編輯器與製造資料繼續為唯一權威；不啟動取代編輯器或回寫製造圖的整合。** 若以後真的需要 CADCraft 修改 DXF，必須將 R12 writer／文件版式轉換做為獨立產品需求並跑三份真圖、真 GUI 與第三方 CAD 相容驗證。此結論只完成目前評估所能支持的 NO-GO 判斷，**不等於宣稱完整 DXF 保真通過**，也不等於使用者已下 `/推推` 發布正式 X。

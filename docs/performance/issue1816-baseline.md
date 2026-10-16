# WHD 效能基準（#1816）

本工具只觀測產品呼叫，不替換幾何、不修改 Scheduler、不清快取、不變更製造規則。原 `phase6_gui_perf_stress.py` 包含固定等待及推算計數，不作本工單的延遲基準。

## 重現

在 **隔離 checkout** 安裝產品既有 GUI 依賴及 pytest，使用固定的 `config.ini`。不得對使用者工作目錄執行壓測。Windows 使用實際桌面；Linux 使用固定解析度 Xvfb（本輪 1400×900 視窗）。

```sh
python tools/whd_performance_baseline.py --samples 3 --cycles 10 --output work/perf/baseline.json
```

Linux 須提供有效的 `DISPLAY`。工具逐一建立新 Python 子程序（1 連、3 連各 samples 次），不並行搶 CPU。每個程序重複 cycles 輪。每筆操作立即保存 JSONL；程序錯誤、Tk 對話框、callback exception、無法收斂或幾何驗證失敗，皆記錄 failed 並停止，不能算成快速成功。

要測 DXF，指定真實來源索引及索引中的檔名：

```sh
python tools/whd_performance_baseline.py --samples 3 --cycles 10 --output work/perf/with-dxf.json --dxf-index /path/to/開關索引.csv --brand 士林 --filename 400_140X257_107.dxf
```

來源檔須與索引位於產品支援的相對位置。工具使用正式 `NfbDxfSourcePreviewPanel` 的 show、zoom、drag 路徑；缺檔或空圖元會失敗。不傳索引則明列 DXF pending，不使用合成輪廓替代真圖。

## 操作與統計定義

- `open_multi / first_entry`：新程序完成主 GUI 與受電箱切換後，第一次開啟單連的多連設定；不包含 Python import 或主程式啟動。
- 3 連必須先經正式「＋連／套用／關閉」建立拓撲，因此首次量測標 `first_after_topology_setup`，**不是冷啟動**。真正三連冷開啟需另固定保存專案並走正式載入流程，仍待補驗。
- `edit_one_bay_in_modal`：800／820 往返，H1400、D350，確認一連至設定視窗更新。確認後程式可能移到下一連，工具在計時外重新選取原連。
- `close_after_edit`：另外量關閉至組合體完成更新；驗證製造 receipt、可見 mesh 與實際 X 寬。此數值與編輯延遲分列，不能只報較快的一段。
- `add_bay_apply_close / remove_bay_apply_close`：正式按鈕、套用、關閉的完整操作。1 連情境往返 1↔2；3 連情境往返 3↔4。
- `open_true_2d / return_3d`：設定視窗的真實封頭 2D 預覽、關閉後返回組合體。這是具體操作路徑，不代表所有 2D／3D 切換入口。
- `dxf_load / dxf_zoom / dxf_pan`：原始 DXF 真圖面板。第一次與暖載入分組；縮放、平移為逐次完成延遲，不等於持續拖曳 FPS。
- 計時到 Tk idle draw、產品 Scheduler dirty／after／flushing 都完成。驗證成本不加入成功延遲。這是應用程式畫布提交完成，不是螢幕掃描或 OS compositor 呈現時間。
- `calculation_flushes` 讀正式 Scheduler 計數差值；`manufacturing_solve` 包裝真正 service.resolve；`scene_render` 包裝 FinalSceneRenderer.render；`canvas_draw` 包裝 TkAgg.draw；`dxf_readfile` 包裝 ezdxf.readfile。皆呼叫原函式並保留例外。
- `part_materialization / materialized_parts` 是 adapter 原始板件輸入建立呼叫與 key 分布，**不等於每個實體子片的完整重建次數或快取 miss**。箱身拆片須在後續局部重算工單補充更深層辨識。
- `inclusive_ms` 為各層 inclusive 時間，可能互相包含，**不可相加當總時間**。
- median 與 nearest-rank P95 只收成功樣本，失敗數另外保留。少量樣本的 P95 常等於最大值，不能當穩定 SLA。
- `rss_before / rss_after` 為每步實際 RSS；只能報操作邊界觀測最大值，不能冒稱採到瞬時峰值。長期穩態、峰值與 Windows 記憶體驗收仍需更長測試。
- 冷程序不代表冷 OS 檔案快取；工具不清作業系統快取。metadata 保存來源 SHA、工具 hash、config hash、Python／套件版本及主機資訊。

## 後續門檻

先保留每筆原始資料，再比較同主機、同 config、同來源檔、同樣本數、同 cache_state 的 before/after。若中位數或 P95 變差超過 10%，觸發調查並重複配對量測；這是暫定回歸警戒線，**不是宣稱統計顯著或使用者接受門檻**。

結構驗收依 GUI 效能完整性規則：單一幾何 transaction 目標 calculation≤1、FinalScene rebuild≤1、render≤1、相同 DXF disk reread=0、live-state echo=0。現有基準可能不符合，必須如實記錄，不能為讓基準通過而降低產品檢查。不同操作（編輯、關閉）分別計數，不合併偽造一次更新。

本輪不涉及製造算法修改。Save→Reload、2D／3D、板件與 DXF 正確性由既有正式產品回歸驗證；基準工具自身不能取代這些回歸或 Windows 人工驗收。原始 DXF、真正多連冷載入、記憶體長時間穩態未完成前，#1816 保持開啟，不解鎖依賴其完整驗收的後續工單。

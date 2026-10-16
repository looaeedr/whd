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


## 同程序記憶體取樣（#1816 後續增補）

新工具以獨立 daemon sampler **僅讀取目前 Python 程序 RSS，不操作 Tk**，預設每 50ms 取樣，可用 `--memory-interval-ms 50` 調整（合法 10–1000ms）。每筆操作新增：

- `rss_peak_sampled_bytes`：該操作期間 **有實際讀到的 RSS 最大值**，不是精確瞬間峰值。操作短於取樣間隔時可能為 `null`，絕不偽造零或用操作前後值冒充取樣峰值。
- `rss_samples_in_operation`：實際落在操作時間窗內的取樣數，取樣不足的結果不可聲稱已覆蓋尖峰。
- `rss_sample_error`：讀取失敗原因，不能把缺測當成正常零。
- `worker_sample`：單一程序的樣本編號；產生 `memory_trends` 以該程序每一輪 `return_3d` 之 `rss_after` 作 checkpoint，記錄首末值、最大 checkpoint、差值與完成輪數。

`memory_trends` 只能陳述同一程序跨輪次記憶體觀測，不得把不同程序的 RSS 串成成長曲線，也不得以差值直接宣稱 memory leak／穩態。若要評估長時間穩態，可在**隔離 checkout**用固定 `--samples 1 --cycles 30` 進行，仍需記錄 GUI 操作一致、程序是否完成、採樣間隔與執行環境；短時間雲端 Runner 不取代 Windows 使用者實機驗收。

## 真正 world-skin 拆片重建觀測（#1816）

為避免把 `_domain_inputs_for_part` 原始輸入計數冒充實體重算，新的 `Probe.observe_world_skin` **只包裝現行 Receiving 製造服務真正呼叫的 `_phase6_build_joint_world_geometry`**，且保留原函式與其例外、結果不變。每筆操作新增：

- `counts.world_skin_builds`：真正建立 world skin 圖的次數，0 代表該操作未進這個製造階段。
- `world_skin_physical_pieces`：實際返回 `world_triangles_by_part` 中非空 world-mapped physical key 的次數；若存在 `box_body:left`／`box_body:back`／`box_body:right` 等拆片，`box_body` 總合圖只算展示集合，不額外算成另一塊板件。
- `world_skin_physical_rematerializations`：上述 keyed world-coordinate 實體表面重新產出的總數（同一操作再次建圖會再計一次）。`inclusive_ms.world_skin_builds` 為建圖呼叫 inclusive wall time。

**層級界限：** 這是依真正 Returning mapping 見證的 world-coordinate skin rematerialization，**並不直接等於原始板件 2D 下料幾何重新求解、DXF export 次數、mesh cache miss 或 CNC physical output**。不能將其冒稱完整的「子板件求解數」；仍須沿每個 source-to-blank/geometry cache seam 補足實際命中或失效的證據。若實際 mapping 欄位缺失，觀測器 fail-closed，不得用預期數量填補。

此測試只改觀測程式／測試，不修改任何製造演算法。原本的 `part_materialization`／`materialized_parts` 欄位維持原語意且獨立計數。


## Linux 核心 RSS 最高水位（VmHWM，不等於單一操作內峰值）

原先的 `rss_peak_sampled_bytes` 是取樣到的 RSS 最大值，50 ms 之間的尖峰可能漏掉。此次新增從 Linux `/proc/self/status` 讀取 OS `VmHWM`，每筆記錄：

- `rss_highwater_before_bytes`：操作開始前，**整個程序自啟動以來**的 Linux kernel 高水位 RSS。
- `rss_highwater_after_bytes`：操作結束後，程序**累積最高水位**；它是進程級統計，含 Python/Tk 初始化與前面操作，不是該操作的獨立瞬時峰值。
- `rss_highwater_increment_bytes`：該操作是否提高了進程累積高水位，`max(0, after-before)`。若前次操作已推高峰值，後續操作即使短暫接近也可能得到 0，不可解讀為未配置記憶體。
- 不支援 `VmHWM` 的平台可按 psutil `peak_wset` / `peak_rss` 可用性回傳，否則是 `null`，不可回填當下 RSS 或預設 0。

此欄位與原來的每 50ms 採樣、每循環 checkpoint 並行，不改製造服務、實體板件或 UI 更新行為。每 worker 的最高 HWM 需獨立比較，不可跨程序直接串成單一記憶體走勢。

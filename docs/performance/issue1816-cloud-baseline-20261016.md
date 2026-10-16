# #1816｜WHD Phase6 效能基準：Linux 雲端參考量測（2026-10-16）

> **證據狀態：部分基準已取得，Issue #1816 尚未完成驗收。** 本報告是 Linux Runner 的 *before* 觀測，不代表 Windows 實機效能，也不是改善後的百分比。真正的 NFB DXF 封閉環境預覽、長期記憶體及 Windows UAT 仍待驗；已另外完成正式三連專案 fresh-process 重開的雲端量測。

## 來源及可重複方法

- 權威操作方法：[`docs/performance/issue1816-baseline.md`](issue1816-baseline.md)；工具 `tools/whd_performance_baseline.py`。
- 量測提交 `42d7c2cde0bd8bb3b21bb7460de593b92011e8d7`，原始 [GitHub Actions run 38907462644](https://github.com/looaeedr/whd/actions/runs/38907462644) 完成 **success**。
- Artifact：`whd-issue1816-tk-baseline-raw`（ID `12048759261`，當次 retention 14 天）。包含 `baseline.json`、每 topology × process JSONL/日誌及 `environment.txt`；若 artifact 過期，應依本報告指定的版本、環境與命令重新量，**不能假稱原始資料仍可取回**。
- 固定本次 runner image Ubuntu 24.04／Python 3.12／Xvfb 1600×1000×24，視窗 1400×900，DISPLAY=:99。實際執行為 Linux Azure x86_64、4 vCPU；GitHub hosted runner **不保證不同執行間相同實體 CPU**。
- 套件：matplotlib 3.11.2、numpy 2.5.4、shapely 2.2.0、ezdxf 1.4.5。
- `config.ini` SHA256：`980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`；工具 SHA256：`6fe7c7e3cfb7800ecaba8652ea2e1acf29ee23386843189dd1f66904ee665cee`。
- 每 topology（1 連、3 連）各 3 個全新 Python 子程序、每程序 5 輪暖操作；依序執行、非平行。**共 222 筆操作成功，0 筆失敗**。統計為成功樣本的 median 與 nearest-rank P95（小樣本 P95 偏向最大值，不當作 SLA）。
- 同機重現指令（需真 GUI/Xvfb 與正確專案依賴）：`python tools/whd_performance_baseline.py --samples 3 --cycles 5 --output work/perf/baseline.json`。
- 量測涵蓋實際 GUI 互動到 Scheduler dirty/after/flushing 清空、Tk idle draw 提交後，不是單純函式返回；不保證螢幕掃描／compositor 完成。3 連先用正式 UI 建構，第一次開啟只是 `first_after_topology_setup`，**不是冷啟動**。

## 操作 wall time（毫秒）

下表每格為 **Median / P95**，皆為暖快取、每 topology 的 n=15：

| 操作 | 1 連 Median / P95 | 3 連 Median / P95 |
|---|---:|---:|
| 開啟多連設定 | 25.6 / 96.9 | 25.9 / 28.1 |
| 確認單連尺寸（設定視窗更新） | 374.0 / 2119.6 | 418.3 / 2177.3 |
| 修改後關閉設定 → 組合體完成 | 2239.7 / 2313.6 | 2286.1 / 2334.1 |
| 增加連數 → 套用 → 關閉 | 2299.3 / 2369.1 | 2343.7 / 2407.3 |
| 減少連數 → 套用 → 關閉 | 2219.4 / 2287.1 | 2296.8 / 2356.2 |
| 開啟真實封頭 2D 預覽 | 379.7 / 1459.8 | 393.2 / 1526.8 |
| 關閉 2D → 返回 3D 組合體 | 695.0 / 768.4 | 717.7 / 789.8 |

其他入口：1 連 `open_multi/first_entry` n=3、Median 2227.0ms、P95 2287.4ms；3 連 `first_after_topology_setup` n=3、Median 28.8ms、P95 29.0ms。首次程序 **未清除 OS 檔案快取**，不能等同完全冷機。

**關鍵事實：** 三連單次尺寸確認約 0.42 秒（median），但關閉後組合體更新約 2.29 秒（median）。兩段需分開分析，不能只用設定視窗更新時間代表操作完成。尺寸確認自身亦有長尾（P95 約 2.18 秒）。

## 真實求解、重畫與材質輸入觀測

| 操作類型（每 topology 暖樣本 n=15） | 兩個 Scheduler 的計算 flush 合計 | `service.resolve` 呼叫 | `FinalSceneRenderer.render` 呼叫 |
|---|---:|---|---|
| 尺寸確認 | 每筆 2 | 6/15 筆為 1 次，其餘 0 | 6/15 筆為 1 次，其餘 0 |
| 修改後關閉 → 3D 完成 | 每筆 2 | 每筆 1 | 每筆 1 |
| 增連／減連套用關閉 | 每筆 2 | 每筆 1 | 每筆 1 |
| 開真 2D | 每筆 0 | 6/15 筆為 1 次，其餘 0 | 0 |
| 返回 3D | 每筆 1 | 0 | 每筆 1 |

- `calculation_flushes` 是 Main GUI 和 Designer **兩個 Scheduler 的計數加總**，不代表兩次完整製造求解。是否有多餘提交與 anti-echo，須由後續 #1818 沿真實呼叫鏈判斷。
- 修改後關閉的 `service.resolve` inclusive median：1 連約 1192ms、3 連約 1286ms；FinalScene render inclusive median：約 405ms／407ms。這些 inclusive 時間可能互相包含，**不可加總**當 wall time。
- 真 2D 預覽的 TkAgg `canvas_draw` median 每筆 5 次；0 次 FinalScene render。某些尺寸確認與 2D 預覽有 manufacturing resolve，值得後續按 canonical state 差異調查是否必要。
- `part_materialization` 是 `_domain_inputs_for_part` 原始輸入建立計數／key 分布，**不是**每個實體子片的完整幾何重建次數，也不是 cache miss 數；#1817 必須建立更深的依賴／重算證據才能驗收。

## 記憶體觀測（不是峰值或長期穩態）

| topology | 每次操作 `rss_before / rss_after` 邊界觀測中位數 | 全部邊界值最大 |
|---|---:|---:|
| 1 連 | 約 173.66 MiB | 186.14 MiB |
| 3 連 | 約 174.76 MiB | 182.08 MiB |

新程序之間不可串成同一條記憶體增長曲線。這是操作邊界 RSS，**沒有**記錄任意時刻的瞬時峰值，也沒有長時間穩態／洩漏結論。

## 回歸比較門檻與未完成項

暫定同硬體、同來源 SHA／config、同 cache_state、相同操作序列之配對比較：Median 或 P95 惡化超過 10% 即啟動調查及重測。**這是警戒線，不是統計顯著性或使用者接受 SLA**。局部重算／快取優化仍必須保持 Save→Reload、板件清單、2D／3D 及 DXF 製造結果一致。

未驗項目：

1. 正式三連 `.p6fold` 保存與新 Python 程序載入已由後述 2026-10-16 補充證據完成（未清 OS cache）；Windows 完全冷機仍未驗。
2. 真實士林 NFB `400_140X257_107.dxf` 的 `dxf_load/dxf_zoom/dxf_pan`：GitHub 索引存在而 public repo 沒有原始檔。使用者私人 ChatGPT 檔案庫已核實擁有同名原件（123,089 bytes，41 modelspace entities），**不得為了公用 CI 自動公開上傳**；需受控私有 GUI 環境測。
3. 已有 30 輪同程序 RSS 趨勢（見下），但**準確瞬間峰值、更長時間穩態與 Windows 實機 UAT**仍未完成；跨 Runner 樣本不可當成受控前後對照。
4. 本輪沒有量到完整 Save→Reload／DXF 匯出的耗時，其製造正確性由現行正式產品回歸另行驗證；不可冒稱本基準工具涵蓋所有入口。

**結論：** 已有可重現的第一版 Linux 雲端 before 基準與 222 筆成功樣本，最明顯的成本落在關閉設定後重新產出組合體（約 2.2–2.3 秒 median）。完整 #1816 未完；不得以此直接核准 #1817 或當成正式 X 發布驗收。正式 X 須另有當次 `/推推`。

## 2026-10-16 後續實證：RSS 取樣與真三連專案讀檔

### RSS 原位取樣（PR #1825）

- 量測 HEAD `0b919cd12a475fd5e9d83597af8f96ba52093a5b`，正式 [Tk run 38909856648](https://github.com/looaeedr/whd/actions/runs/38909856648) SUCCESS、[Canonical Product Regression 38909856417](https://github.com/looaeedr/whd/actions/runs/38909856417) SUCCESS；原始 Artifact ID `12049667974`，均為雲端 Linux 參考值。
- 222 筆操作成功、失敗 0；200 筆操作有時間窗內 RSS 取樣，22 筆短操作取樣數為 0，工具正確保留 `null`，不編造峰值；讀取錯誤 0。
- 所有 worker 的最大 **已取樣** RSS 約 186.58 MiB，這不是準確瞬時峰值、不是 Windows 峰值。六個獨立程序各包含五輪，成長幅度不能被當成同一程序延伸的洩漏訊號。
- 指標 `rss_peak_sampled_bytes`、`rss_samples_in_operation`、`rss_sample_error`，`memory_trends` 的首／末／最大 RSS checkpoint 將作長循環對照；詳細取樣定義請見量測操作文件。

### 真正三連 .p6fold 載入（PR #1826）

- 量測 HEAD `65fbb4502ea3d22ec6d574642483323e10114af0`，[Actions run 38910700963](https://github.com/looaeedr/whd/actions/runs/38910700963) SUCCESS，原始 Artifact `12049623168`。
- 經正式受電箱 UI 新增兩連、以 `Phase6ProjectController.save` 保存 `phase6-fold-project-v2` 專案，回讀核對保存內容有三連；以 **三個獨立的新 Python 程序** 分別走官方 `load_phase6_project(open_designer=True)`、確認三連與非空 3D mesh，待 Tk scheduler/畫布提交完成後再開一次多連設定；無失敗，n=3。
- 專案 SHA256 `c0563f1cd72e679815db5988f1fa5c5f1c201117cda7cbe9f32ee7c694dc6146`；所有程序使用同份檔案，但 OS 檔案快取未清，不能稱為完全冷機。

| 三連真專案重開階段（n=3） | Median | P95 |
|---|---:|---:|
| 主 GUI 初始化 | 870.1 ms | 945.1 ms |
| 正式讀檔到 3D 更新完成 | 2209.7 ms | 2258.7 ms |
| 讀檔完成後首次開多連設定 | 18.8 ms | 19.1 ms |

**此讀檔測試不是上方舊壓測的 topology-setup first open**：前者確實跨越正式儲存與新 Python 程序。主要耗時出現在實際讀檔與 3D 建立階段，而非資料已載入後再次開啟多連設定；不同 CI Runner 的絕對延遲不應直接當成前後改善比較。

### 資料保密邊界

`looaeedr/whd` 為 PUBLIC GitHub repository。私人檔案庫中發現士林同名原始 DXF，與 `開關索引.csv` 士林欄對應，可用正式 `NfbDxfSourcePreviewPanel.show/zoom/_move` 路徑驗證。但原 DXF 並未存在 GitHub `基準檔/開孔/NFB`，不應為方便公開 CI 而 commit 原始製造 CAD。**2026-10-16 補充：** 已用相同索引與私人原圖於隔離 Linux/Xvfb 真正量測 `dxf_load/dxf_zoom/dxf_pan`，**305 筆全成功**，證據見 [`issue1816-private-nfb-source-preview-20261016.md`](issue1816-private-nfb-source-preview-20261016.md)。原圖並未公開上傳；此結果不取代 Windows UAT。

### 30 輪連續操作之同程序記憶體趨勢（PR #1827）

- 專項量測 HEAD `dd39c26bd77de0fe08d2e254f63242540a39d82d`，[Actions 38911264600](https://github.com/looaeedr/whd/actions/runs/38911264600) `completed / success`，GitHub artifact `whd-issue1816-extended-rss`（ID `12050663455`，14 日保留）。僅雲端 Linux Runner，比對必須固定同一真實機器、樣本與狀態。
- 受電箱 1 連、3 連**各一個獨立持續執行的 Python 程序**，每個跑完 30 輪修改、增減連數、2D/3D 預覽；全程 424 筆真 GUI 操作，失敗 0。與既有 5 輪 run 使用不同 worker/Runner，故不計算跨 runner 的百分比改善。
- 下表為相同程序在每輪 `return_3d` 完成後的 RSS checkpoint（MiB），不是瞬間最高水位、不是被宣告的 memory-leak verdict：

| 同程序、30 次 checkpoint | 1 連 | 3 連 |
|---|---:|---:|
| 第一輪 RSS | 181.125 MiB | 171.918 MiB |
| 第三十輪 RSS | 184.980 MiB | 183.742 MiB |
| 首十輪 RSS 中位數 | 183.436 MiB | 182.230 MiB |
| 末十輪 RSS 中位數 | 184.975 MiB | 183.736 MiB |
| 末十輪最大－最小 | 0.316 MiB | 0.016 MiB |
| 首末差值 | +3.855 MiB | +11.824 MiB |

- 在本次程序的**末十輪**中，RSS 變動範圍很小，表示該測試期間接近平台期；三連的首末累積增長更多，但在最後十輪也沒有持續線性累增的直接證據。此結論嚴格限定本次 30 輪、同一程序的觀測窗，並不證明不會有更長時間洩漏或 Windows 狀態相同。
- 取樣值、操作檢查點、測試源 HEAD、環境 metadata 及工作日誌保留於 GitHub Artifact。原始 ZIP 過期後不得只根據本文冒稱原始資料尚可取得。


## 2026-10-16｜真實士林 NFB DXF 原始檔預覽補充

使用使用者私有的 `400_140X257_107.dxf`（SHA-256 `8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3`），在隔離雲端執行 GH `localX` 原版 NFB 真圖 Tk 面板：新程序首次載入（n=5）median/P95 **53.82/69.10ms**；暖載入（n=100）**4.23/19.58ms**；zoom（n=100）**3.07/10.61ms**；pan（n=100）**2.91/11.69ms**。合計 **305 操作成功，0 失敗**，相同原圖的暖載入／縮放／平移磁碟重讀 **0 次**。每次核對 41 真實來源圖元有繪製進 Tk Canvas。原圖未納入公開 GitHub 或 GitHub Artifacts；完整流程／限制見[補充報告](issue1816-private-nfb-source-preview-20261016.md)。

**本項 DXF private cloud benchmark 已補齊，#1816 仍 OPEN**：Windows 本機 GUI 驗收、物理子板件重算層數／快取 miss 精確度、瞬時峰值與長期實機穩態仍缺，不能誤記成全工單完工。原始原圖預覽不構成開孔位置或下游製造認證。

## 2026-10-16｜實際 world-skin physical piece 建圖數（PR #1831）

量測 HEAD `9dfc8d94c53db68e93331eaf790aa702ebda9ddd`，真實 [Tk run 38917466465](https://github.com/looaeedr/whd/actions/runs/38917466465) `completed/success`，正式 [Product Regression run 38917466357](https://github.com/looaeedr/whd/actions/runs/38917466357) `completed/success`，原始 [Actions Artifact 12053726898](https://github.com/looaeedr/whd/actions/runs/38917466465)；1／3 連各 3 個 fresh Python worker × 5 次操作輪，共 222 筆成功、0 失敗。source SHA、原始 JSONL 與 per-worker log 在該 artifact；14 日後可能過期。

此次在真正 `phase6_manufacturing_service.resolve → _phase6_build_joint_world_geometry` 的 mapping 返回後，直接計算 `world_triangles_by_part` 中非空 physical keys；箱身拆成 `box_body:...` 時不將 aggregate `box_body` 當成另一塊板件。本表每 topology 各 n=15 暖樣本，單位為**每操作實際 world-coordinate physical skin rematerializations**，不是原始材料幾何 cache misses。

| 操作 | 1 連 physical world-skin 次數分布 | 3 連 physical world-skin 次數分布 | 真 world-map 函式執行 |
|---|---|---|---|
| 開啟多連設定 | 0 × 15 | 0 × 15 | 0/15 |
| 視窗內確認單連尺寸 | 0 × 9、13 × 6 | 0 × 9、13 × 6 | 6/15 |
| 修改後關閉設定 | 13 × 9、15 × 6 | 13 × 9、15 × 6 | 15/15 |
| 增連套用關閉 | 13 × 9、15 × 6 | 13 × 9、15 × 6 | 15/15 |
| 減連套用關閉 | 13 × 9、15 × 6 | 13 × 9、15 × 6 | 15/15 |
| 開真實封頭 2D 預覽 | 0 × 9、13 × 3、15 × 3 | 0 × 9、13 × 3、15 × 3 | 6/15 |
| 返回 3D | 0 × 15 | 0 × 15 | 0/15 |

- 13 件是目前作用連的 world-skin 有效實體鍵；其中常見為底板、箱身左／背／右、水平中隔、上下門板、內門板與各框件、封頭、封尾等。部分樣本多出 `base_plate:fixing_plate:left/right` 兩個真實 physical keys 而成 15，不能以固定 13 件覆蓋此差異。
- 1 連與 3 連的分布相同**不是三連總裝只有 13 件**：此段真實製造呼叫是目前選定連的作用視圖，不能拿來代表整個多連專案所有 Bay 的總實體數。
- 相同 runner 的 `close_after_edit` 操作中位，1 連 `manufacturing_solve` inclusive 約 **1345.66 ms**、`world_skin_builds` inclusive 約 **51.97 ms**、`scene_render` inclusive 約 **450.27 ms**；3 連依序約 **1376.35 / 50.01 / 463.15 ms**。不同計時層級可能巢狀包含，**不可相加**。數據意味 world-skin stage 並非此筆操作全部耗時；其餘成本須沿真實請求構建、幾何求解、渲染階段分別取證。
- `part_materialization` 仍只代表 adapter 輸入建構。world-skin 的返回 physical keys 證明了重新產生 world-coordinate 表面，但**不能直接當作 2D 下料圖板件重新求解或 mesh cache miss**。下一階段 #1817 應另建材質依賴／快取 miss 的精確鑑別器，且不修改幾何準確性。

**驗收狀態：** #1816 對 DXF 私人原圖及 world-skin 重建數均已有真實測試；完整 Windows UAT、比 30-cycle 更長的穩態、瞬時真峰值及精確 flat-material cache miss 仍未證實，#1816 保持 OPEN，正式 X 不發布。

## 2026-10-16｜真實 2D 材質工廠執行與整組製造快取（PR #1834）

- 精確量測 HEAD `a8c5a6dcb8c93743ca3c65b5e40ae088ec494911`，[Product Regression run 38922927630](https://github.com/looaeedr/whd/actions/runs/38922927630) SUCCESS（所有 shards 與 canonical aggregator）、[真 Tk baseline run 38922927376](https://github.com/looaeedr/whd/actions/runs/38922927376) SUCCESS；原始 artifact ID `12055552909`（14 日保留），內含 JSON/JSONL、worker log、environment metadata。固定這次 GitHub Linux Runner 環境；**不可和不同 Runner 的其他輪次當作配對加速改善證據**。
- 1 連與 3 連各 3 個新 Python 程序 × 5 輪暖 GUI 操作，總計 **222 筆成功／0 失敗**；`material_factory_rebuild_calls` 合計 2,106 次。此總數為五類主要 2D 材質**工廠成功呼叫**，不是 2,106 塊不同實體板件，也不是每次都寫 DXF。
- 真實 `ManufacturingCacheService.lookup` 回傳的 receipt 共 **177 次 hit、141 次 miss**；兩種計數為不同層級與觸發條件，**不能拿 miss 與工廠呼叫數相減**或把每個 miss 說成只重建一片。工具包裝原函式，未停用或更動任何快取、幾何、鈑金製造。
- 以下暖樣本每 topology 各 n=15；由於 1 連與 3 連結果分布相同，合併顯示每操作 n=30 分布，不代表整個三連專案所有 Bay 的板件都已逐一計數。

| 真 GUI 操作 | 主要材質工廠呼叫數（n=30） | 製造 cache lookup hit 合計 | 製造 cache lookup miss 合計 |
|---|---|---:|---:|
| 開啟多連設定（暖） | 0 × 30 | 0 | 0 |
| 在設定視窗確認一連尺寸 | 13 × 12、19 × 18 | 12 | 48 |
| 修改後關閉、更新組合體 | 16 × 30 | 30 | 30 |
| 增加連數套用關閉 | 16 × 30 | 30 | 30 |
| 減少連數套用關閉 | 16 × 30 | 30 | 30 |
| 開啟真實封頭 2D 預覽 | 0 × 18、7 × 12 | 0 | 0 |
| 從 2D 返回組合 3D | 1 × 30 | 60 | 0 |

**五類工廠成功呼叫的整體分類（所有 222 操作）**：

| 工廠＋實際輸入 Spec | 執行次數 |
|---|---:|
| `build_part_render_data:EndCapPartSpec` | 555 |
| `build_inner_door_frame_render_data:InnerDoorFramePart` | 459 |
| `build_box_body_structure_render_data:BoxBodyPartSpec` | 417 |
| `build_part_render_data:DoorPartSpec` | 246 |
| `build_box_body_divider_render_data:BoxBodyDividerPart` | 153 |
| `build_inner_door_panel_render_data:InnerDoorPanelPart` | 153 |
| `build_part_render_data:BasePlatePartSpec` | 123 |
| **合計** | **2,106** |

### 觀測修復與精度界限

- 最初 PR #1834 HEAD `358d202b08375982af3887d026f460469ca08eaf` 真 Tk 失敗：測試工具錯認 `_authoritative_render_data` 位於 Designer 實例；現行架構已將該方法移至 GUI manufacturing projection，不能直接掛到 Designer。本次刪除該無效觀測 seam，不改產品程式；測試經修正到上述 HEAD，重跑並成功，舊失敗結果未重用。
- **未取得可證實的第二級 authoritative render-cache hit/miss**：不能把不存在的觀測欄位說成 0 命中，也不以 manufacturing cache receipt 冒充每一個 PartSpec cache。
- 部分獨立 fixing-plate、特殊衍生來源、service collision relief replay 路徑可能不由上述五個 `manufacturing_api` 工廠產生，故 **2,106 是這五種工廠的真實執行數，不是 100% 系統所有原始 2D 空白重算數**。上述 13/19/16 等值也不代表同樣多的*不同*物理板件。
- 這些結果已提供 #1817 對實際回傳、快取 ownership 與重建依賴進一步切分的基準，但**不解鎖 #1817 的產品施工門檻**：完整 Windows GUI 人工 UAT 與未經量測的特定製造來源仍須依 #1816 驗收；正式產品 `X` 需當次使用者 `/推推`。

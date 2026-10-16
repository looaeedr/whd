# #1816｜WHD Phase6 效能基準：Linux 雲端參考量測（2026-10-16）

> **證據狀態：部分基準已取得，Issue #1816 尚未完成驗收。** 本報告是 Linux Runner 的 *before* 觀測，不代表 Windows 實機效能，也不是改善後的百分比。真實 NFB DXF、三連冷載入、長期記憶體及 Windows UAT 仍待驗。

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

1. 正式保存並重開三連專案之真冷程序量測；本次三連僅 topology setup 後 first open。
2. 真實士林 NFB `400_140X257_107.dxf` 的 `dxf_load/dxf_zoom/dxf_pan`；GitHub `基準檔/開孔/NFB/開關索引.csv` 有索引，該資料夾未見原始 DXF，不能假圖代測。
3. 真正的記憶體操作間峰值、長時間穩態與 Windows `Z:\\localX` 實機 UAT；雲端樣本不得跨實體 Runner 當成受控 before/after。
4. 本輪沒有量到完整 Save→Reload／DXF 匯出的耗時，其製造正確性由現行正式產品回歸另行驗證；不可冒稱本基準工具涵蓋所有入口。

**結論：** 已有可重現的第一版 Linux 雲端 before 基準與 222 筆成功樣本，最明顯的成本落在關閉設定後重新產出組合體（約 2.2–2.3 秒 median）。完整 #1816 未完；不得以此直接核准 #1817 或當成正式 X 發布驗收。正式 X 須另有當次 `/推推`。

# #1819 — 真實 GUI 長循環 RSS 驗收（Linux 雲端觀察）

## 目的
既有 #1872、#1874、#1876、#1877、#1893 測試已覆蓋快取容量、跨專案清理、完整製造結果／DXF 一致與服務層記憶體回收。**服務層 RSS 穩定不等於 GUI／3D 長時間操作 RSS 穩定**。

這裡不另建幾何、計時器或假 GUI。沿用 tools/whd_performance_baseline.py 的真實 Tk 操作、Scheduler settle、真正製造與 FinalScene 指標、50ms RSS sampler。

## 雲端重現

    xvfb-run -a -s "-screen 0 1600x1000x24" python tools/whd_performance_baseline.py --samples 1 --cycles 30 --memory-interval-ms 50 --output work/issue1819/longgui.json

專用 GitHub workflow .github/workflows/whd-issue1819-long-gui-memory.yml 只在自己的 PR 變更時執行，不在一般功能 PR 的每次產品回歸增加長時間壓測。

工具對 3 連與 1 連各使用獨立 Python worker，每個 worker 30 次操作循環；記錄原始 JSONL、分項完整等待時間、快取 hit/miss、實際材料工廠呼叫、return_3d 各輪 RSS、Linux VmHWM 及失敗訊息。不得把跨 worker RSS 串成同一條曲線。

報告列每一 worker 第 6–15 次與最後 10 次 RSS 中位數、差值、可用 checkpoint 次數，以及觀測到的最高 RSS。**先量測再確立合理的產品允收門檻，不因 Linux allocator 上下波動就虛稱不存在 memory leak**。缺少成功的操作／循環或 RSS checkpoint 時不可認列此輪有效。

## 驗收邊界

- **雲端**：僅代表該 exact HEAD、固定 runner、Xvfb、受電箱 1／3 連場景的實測，不可冒稱 Windows GUI UAT、所有板件類型、真實操作十幾小時的記憶體穩態。
- **使用者端**：Windows Z:\\localX 需確認原 2D 開孔、受電箱、連數／尺寸切換、DXF、3D 仍可正常操作。只有 /推推 才能發布正式 X。
- **資料可重現性**：工作流上傳真正報告、worker JSONL、日誌和環境版本。若 runner 失敗，保留最後可用的失敗紀錄，不把未跑完的操作計為正常成功。

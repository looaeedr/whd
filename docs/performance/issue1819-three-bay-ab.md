---
whd_doc_role: REFERENCE
whd_contract: reference-performance-issue1819-three-bay-ab
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1819：三連真實 GUI 記憶體持有修復前後驗證

## 核心問題

#1903 已修正 `phase6_settings_panel.py` 對同一批設定元件重複執行 `bind(add="+")`、持有大量 Tcl `CallWrapper` 和 Python bound method 的真實記憶體問題。1 連 12 輪同 runner 對照，暖機後 RSS 增量明顯下降。這份驗收不以該結果代表三連狀況。

## 直接量測，不改製造引擎

專用 PR 工作流 `.github/workflows/whd-issue1819-three-bay-ab.yml` 使用同一台 GitHub Actions Linux runner、同版依賴及同一份 `tools/whd_performance_baseline.py`：

- **Before**：固定未修復 commit `7e03ff36bc27ab02cb54cf205dd21e6cd95aab28`，避免日後 localX 前進改變對照意義。
- **After**：本 PR exact HEAD，必須包含合併後 #1903，不接受舊版綠燈。
- 兩個獨立 Python 子進程依相同順序操作 **3 連、12 輪**；包含新增／刪減連數、關閉設定、真實 2D 預覽、回到 3D 及快速 2D／3D 切換。
- 每輪讀取 `rss_after`，同狀態比較第 4–7 輪與第 9–12 輪的 RSS 中位數；另外保留首末 RSS、所有操作狀態、原始 JSONL 及 worker 日誌。
- 若任何操作失敗、幾何簽名錯誤、缺少 12 輪資料，工作流必須失敗，不能只畫出好看的數字。
- 報表 `work/issue1819-three-bay/comparison.json`，使用 GitHub workflow artifact 保存；前後執行順序固定，結果為一次觀察，不能排除 runner 配置器／執行順序的所有影響。

## 不可偷渡的結論

CI 成功代表測試有效完成，不等於 RSS 無洩漏。必須比較各操作的真實增量；若仍持續增長，繼續定位下一個 owner、修復後重測。此工作流只驗收 Linux 3 連；Windows `localX` 真機驗收仍是獨立待辦。未收到使用者 `/推推` 不發布正式 X。

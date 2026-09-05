---
name: phase6-release-packaging
description: Use when preparing, rebuilding, validating, or delivering Phase6 FULL/UPDATE ZIP packages, especially after code, geometry, GUI, registry, AI/SOP, or release-policy changes.
---

# Phase6 正確打包交付

## 核心原則
Phase6 出包不是「把這輪改到的幾個檔案壓起來」。**FULL 是可獨立使用的完整專案；UPDATE 是相對指定原始基準的累積覆蓋包。** 缺依賴、缺 AI/SOP、拿錯基準、改到 `config.ini`、中文路徑壞掉、只驗工作目錄，都算交付失敗。

## 必要輸入資料
1. **目前工作樹**：本輪已完成的 production / tests / docs / skills / registry / AI/SOP 全部真值。
2. **本輪 UPDATE 基準**：由本次 release 呼叫以 runtime 參數明確傳入的原始 FULL ZIP。不得從歷史檔名、聊天記憶、上一個 ChatGPT FULL/UPDATE 或 manifest 內的時間戳檔名猜測。
3. **Release policy**：`release_required_artifacts.json`，是 machine-readable Source of Truth。
   - `update_baseline_mode` 固定為 `explicit_runtime_archive`。manifest **禁止保存任何具體 FULL 檔名、日期或時間戳 baseline**；每輪由 release controller / durable state 明確提供 `baseline_archive`。正式 UPDATE 只相對該 runtime baseline 計算。若 baseline 未明確提供、ZIP 無效或 provenance 無法確認，fail closed，不得自動挑「最新」或歷史包頂替。
4. **原始 `config.ini` SHA256**：除非使用者明確要求，交付前必須與基準完全相同。
5. **本輪實檔與 regression fixtures**：例如使用者本輪實際提供的 `.p6fold`，只作驗證輸入；沒有明確需求不得塞進正式包。**永久 suite 禁止硬編碼 ephemeral `/mnt/data/自訂*.p6fold` 路徑**。使用者已不再提供某實檔時，不得保留 `exists() → pytest.skip` 的 conditional skip 測試；仍有長期價值的 oracle 必須轉成 repo 內 canonical/synthetic fixture，否則移除該外部實檔測試。

## FULL 契約
FULL 收目前專案完整檔案樹；排除 `__pycache__`、`.pytest_cache`、`.pyc`、本輪輸出 ZIP，以及**版本控制／工作暫存根目錄 `.git/**`、`.scratch/**`**。`.git/**` 不只是多餘檔案，若使用者直接覆蓋可能污染或改寫其本機 repository metadata；`.scratch/**` 則屬測試 journal/checkpoint/debug 中繼證據，兩者在 FULL 與 UPDATE 都永遠禁止收檔。全域封包排除根目錄必須由 `release_required_artifacts.json:excluded_package_roots` 驅動，不得只在某一個 collector 手寫例外。不得因「這輪沒改」省略 production、tests、docs、skills、`個人AI檔案庫/**`、基準資料或工具。FULL 可包含 `config.ini`，但內容必須保持原始 SHA256。

## UPDATE 契約
UPDATE = **目前工作樹相對唯一原始基準的所有新增/變更檔** + manifest 的 `mandatory_update_files` + `mandatory_update_trees` 全樹。
- `個人AI檔案庫/**`：每次 UPDATE **強制全收**，即使 SHA256 與基準相同。
- `config.ini`：永遠禁止進 UPDATE。
- `.git/**`、`.scratch/**`：屬全域 `excluded_package_roots`，FULL / UPDATE **一律禁止**；不能因為與 baseline 不同就被 collector 當成正常差異檔。
- `BACKUP/**`、`BACKUP_*/*`、快取與 `.pyc`：禁止進 UPDATE。
- Archive root 必須直接是專案根目錄；不得多包一層 `新WHD/` 或其他外層資料夾。
- 禁止手工挑「我覺得有改到的檔案」取代 collector。
- 若相對基準存在會影響執行的**刪除/改名**，單純覆蓋 ZIP 無法正確表達；必須提供可執行清理機制或改交 FULL，不能假裝 UPDATE 能完成刪除。
- 刪除/搬移清單的 Source of Truth 是 `release_required_artifacts.json:update_cleanup_paths`；清理工具固定為 `tools/apply_phase6_update_cleanup.py`，Windows 入口固定為 `APPLY_PHASE6_UPDATE_CLEANUP.bat`。
- `update_cleanup_paths` 必須依**本次 runtime baseline → 目前 source** 的真實刪除/搬移差異維護；不得因某一個歷史 baseline 曾經需要或不需要 cleanup，就把歷史狀態永久寫死在 Skill。若本輪沒有刪除/搬移則為空；有差異才加入。
- cleanup path 必須是專案根下安全相對路徑；禁止 absolute path、`..` traversal，且不得刪除目前 source tree 仍存在的路徑。

## 中文與檔案完整性
ZIP entry 必須保留真實 Unicode/UTF-8 名稱；任何 entry 含 literal `#U` 絕對拒絕交付。所有本輪 `.md/.py` 必須 UTF-8 strict decode，且不得含 U+FFFD replacement character。解壓後必須能找到 `個人AI檔案庫/README.md` 與中文 SOP 路徑。

## 長回歸的可續跑硬閘門
Release QA 禁止再用人工記憶切 `pytest` 批次、等外層工具 timeout 後猜哪一段跑完。長回歸固定使用 `tools/phase6_release_test_runner.py`，每批結果立即 fsync 到 JSONL journal，並寫對應 state JSON。

- `--budget-seconds` 必須小於外層執行時間窗；runner 會在預算耗盡時主動以 **exit 75** 結束。`exit 75` 代表「安全 checkpoint / 尚有 pending tests」，不是測試 failure。下一次用**同一 journal**執行同一命令，必須只跑未完成 nodeid。
- journal 會綁定 pytest collection SHA256/count；收集清單改變時禁止沿用舊 journal，必須開新 journal，避免把 1270 顆的舊證據套到 1275 顆新 suite。
- `--reset` 是破壞性 journal 操作，**必須先取得該 journal 的 run lock，再刪除/重建 journal 與 state**。若同一 journal 已被另一 runner 持鎖，第二個 `--reset` 必須 fail closed，且原 journal 的 collection header/bytes 必須完全保留；禁止「先 unlink、後搶 lock」。
- 每個 pytest batch 必須由獨立 process group 執行；batch timeout 時 runner 必須終止整個 process group，避免殘留 pytest/Xvfb 99% CPU 污染下一批。
- runner 自管 Xvfb 時，正常 `finally` cleanup 只覆蓋可攔截退出；Linux 外層若對 runner 送 `SIGKILL`，Xvfb child 必須另有 kernel parent-death guard（`PR_SET_PDEATHSIG`/等價機制），並由真 hard-kill regression 驗證不會留下 orphan display。
- timeout/failed batch 不得標記 complete；多顆 batch timeout/fail 時下一次自動二分縮批，直到定位到單顆。只有單顆 failure / timeout 才視為真正阻塞並回 root-cause/TDD。
- 若 pytest 已輸出完整 summary，且 `passed + skipped + xfailed + xpassed == batch nodeid count`、`failed=0`、`errors=0`，但 interpreter / GUI teardown 沒有退出，runner 必須 kill process group 並記為 `complete_teardown_timeout`；此狀態算測試完成，但保留 teardown 證據，禁止誤報成 production failure。
- Headless 與 Xvfb 使用不同 journal，不得混用；正式 GUI gate 必須用 `--mode xvfb`。

### Targeted gate / GUI teardown 與 source-tree provenance 雙重硬閘門（2026-09-04）
- targeted gate 只看到點號、局部百分比、scene dump 或 wrapper output，**一律不能宣告 PASS**；必須有 pytest 完整 summary 才能把未退出程序分類為 `complete_teardown_timeout`。
- 多顆 Assembly/Tk probe 串跑 hang、拆成單顆全部 PASS 時，分類為 harness/order-dependent teardown；保留證據、kill process group、另追 teardown，不得把 production geometry 判成 failure。
- 正式 release gate 的 completed set 只能來自 journal 中有完整終態的 nodeid；沒有完整 summary 的 nodeid 仍 pending。
- fresh extraction、checkpoint restore、工具回合重建或手動複製後，release runner 啟動前必須驗證 **execution-tree provenance/fingerprint** 與最近已驗收 checkpoint 一致。
- pytest collection SHA/count **不能代替 source-tree fingerprint**；collection identity 與 execution-tree provenance 兩者都一致，才准 resume 同一 durable state。
- 若 fingerprint 不符或偵測到部分舊檔/部分新檔，禁止 patch-by-eye；必須在乾淨目錄從最近已驗收 checkpoint 完整恢復，驗 fingerprint 後再重放未驗收變更。

### 合批 timeout 判定：先算「總耗時」，不要先怪 production
GUI/Tk/Matplotlib 測試的 batch wall-clock 近似為各 nodeid 執行時間加上 setup/teardown。**多顆 batch 超過 `--batch-timeout`，只代表這一批在時間窗內跑不完；不代表其中任何單顆測試失敗、卡死或 production regression。**

2026-09-02 實測曾出現：4 顆 GUI 測試合批在 25 秒 timeout，但四顆拆成單顆後分別約 `7.18s / 12.22s / 9.15s / 7.44s` 全部 PASS；單顆總和約 `38s`，因此 4 顆合批超過 25 秒是必然的 batch-budget 現象。**16 → 8 → 4 都 timeout 仍不能判定真阻塞；必須繼續縮到 2 → 1。**

判定順序固定如下：
1. 先看 journal/state：timeout batch 的 nodeid **不得算 completed**；只相信已 fsync 的 durable completed 數。
2. 保持同一 collection SHA 與同一 journal，讓 runner 依 timeout 記錄自動二分：`N → N/2 → ... → 1`。禁止靠對話記憶手工跳過 nodeid。
3. 若縮到單顆後每一顆都能在 `--batch-timeout` 內 PASS，分類為 **aggregate batch-budget timeout**；這不是 production failure。讓這些單顆/小批 PASS 正式寫回同一 journal，離開慢區後再恢復正常 batch size。
4. **只有單顆仍 timeout 或 assertion/error fail**，才升級成真正阻塞，回 `diagnosing-bugs` / TDD 做 root-cause。
5. 若 stdout 已有完整成功 summary，只差 interpreter/Tk/Matplotlib teardown 沒退出，分類為 `complete_teardown_timeout`，與「未跑完的 aggregate batch timeout」分開記錄。
6. 外層工具若先殺 runner，只能從 journal/state 判斷最後 durable checkpoint，並檢查 orphan pytest/Xvfb；**不得從進度點數、終端輸出長度或「看起來都跑完」推算 PASS**。

調參原則：優先縮 batch，不要為了讓慢 GUI 合批一次塞完就任意提高全域 `--batch-timeout`。只有在外層 budget 仍能保證 `batch_timeout + safety margin`、且有明確單顆需求時才調整 timeout；否則會把 teardown/orphan 問題重新藏回長時間窗。

建議正式 gate：

```bash
python tools/phase6_release_test_runner.py --mode headless --journal logs/release_headless.jsonl --budget-seconds 18 tests
python tools/phase6_release_test_runner.py --mode xvfb --journal logs/release_xvfb.jsonl --budget-seconds 18 tests
```

重複執行到 exit 0；若 exit 75，直接續跑同一命令；不得從頭重跑或靠對話文字記錄 completed index。

## 出包流程
1. 記錄目前 `config.ini` SHA256，與原始基準比對。
2. 驗證 runtime 傳入的 baseline ZIP provenance、檔案存在性與 CRC；**不得用 manifest 檔名比對或自動搜尋歷史包**，再解壓到全新目錄。
3. 跑完整相關 regression matrix：registry 自動列舉所有 Assembly Intent；Head/Tail；求解前碰撞顯示；求解後零穿透；2D / 單板3D / 組合圖尺寸一致；Save/Reload；以及使用者實檔。
4. 使用 `tools/phase6_release.py` 依 policy 自動收 FULL/UPDATE。Asia/Taipei 時間只取得一次，格式 `YYYYMMDD_HHMMSS`，兩包共用同一時間戳。
5. 對 FULL/UPDATE 跑 ZIP CRC、entry policy、UTF-8 路徑、逐檔 SHA256；各自解壓到全新目錄再比對來源。entry policy 必須明確斷言 `excluded_package_roots`（目前至少 `.git/**`、`.scratch/**`）在兩包都是 0 entry，不能只靠 pristine parity 間接推論。
6. UPDATE 額外驗證：`個人AI檔案庫/**` 全數存在、`config.ini` 不存在、archive root 可直接覆蓋專案根目錄。若 manifest 有 `update_cleanup_paths`，必須把 UPDATE 覆蓋到本次 runtime baseline 的 fresh extraction，執行 `python tools/apply_phase6_update_cleanup.py`（Windows 等價 `APPLY_PHASE6_UPDATE_CLEANUP.bat`），再驗證刪除/搬移後的實際樹。
7. **打包後不重跑完整 GUI gate。** 只有在封裝流程本身改變執行環境或交付內容（例如 Python runtime、DLL、啟動腳本、資源載入方式、插件、解壓後檔案結構）時，才追加一次針對該風險的 package GUI Smoke；單純 ZIP/CRC/UTF-8/逐檔 SHA256 驗證與 pristine fresh extraction，不要求再次跑完整 GUI。正常情況下，以第 3 步的正式 regression/GUI gate 加上第 5、6 步的封包完整性、pristine extraction 與逐檔 SHA256 證據，確認「打包內容 = 已驗證來源樹」即可。

## 禁止交付
以下任一成立就禁止交付：基準錯、`config.ini` 被改或混入 UPDATE、`.git/**` 或 `.scratch/**` 混入 FULL/UPDATE、mandatory 檔/樹缺失、FULL/UPDATE 時間戳不同、ZIP CRC/解壓/SHA256 不一致、中文路徑出現 `#U`、相關回歸有新增失敗、本輪明確提供且列為 required fixture 的使用者實檔無法重現驗證結果。

**完成定義：不是 ZIP 建好了，而是「正確基準 + 正確收檔 + 封包完整性/來源樹一致性 + 必要的功能 gate」全部有證據。**

## Durable checkpoint 與 runner cleanup（2026-09-03 補強）

長回歸、profiling、GUI stress 的續跑點不得只存在對話或臨時工作樹。每個長任務都要有 **durable checkpoint**，至少保存：來源 archive、工作樹/patch hash、collection SHA/count、journal/state 路徑、completed/pending/failed、最近效能數據與下一步命令。外層 timeout 後只讀 durable state，不從聊天文字推算進度。

Process cleanup 的完成條件是**整個 process group 消失**。送 TERM 後即使父程序先退出，也不得立刻 return；仍要確認 descendants/process group 已消失，必要時送 KILL。測試必須先確認 child tree 已建立，再驗 timeout 後 child 真正消失，避免把環境啟動速度誤當 cleanup oracle。

## pristine 封包比對（2026-09-03 補強）

FULL 與 UPDATE overlay 的最終樹比較必須使用兩個 **pristine fresh extraction**：兩邊都未跑過 Python、pytest、compileall 或 GUI。禁止拿已產生 `__pycache__`、`.pytest_cache`、`.pyc` 的測試目錄與 pristine overlay 直接比檔案數，否則會製造假 missing/extra。

正確順序：ZIP CRC/entry policy → pristine FULL extraction → pristine baseline + UPDATE overlay → cleanup policy → 逐檔 missing/extra/SHA256。測試 gate 另用其他 extraction 執行，不污染封包完整性比較目錄。

---
whd_doc_role: CURRENT
whd_contract: audit116-original-six-rounds-readback
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 原始 116 項深度查核：來源範圍對照與尚待實機驗收

**審核日期／時區**：2026-10-27 Asia/Taipei  
**工作權威**：GitHub `looaeedr/whd`，原查核 `5702703c95c9f216f62c1553288de49a9cba8b61`，來源 `localX@a3147c9950e4d6de5a93577f0cf22c9ca2a7b610`；本文件的正式整合 SHA 須以 PR merge readback 更新。  
**不變界線**：這是原始 #1～#116 的六輪清點；後加第 7～9 輪不抵充原 116 條任何一條。不要把原修復 branch `fix/deep-audit-14-bugs-20261023` 整批 merge（相比本輪 localX 落後 823 commit、仍有 210 個差異檔案），先逐項驗現行來源，必要時單項或批次最小回補。

## 已驗證的「原始回歸收據」：不等於 116 項真人 UAT

| 原始缺陷 ID | 原回歸檔（`tests/`） | 原函式數 | 現行 `localX` |
|---|---|---:|---|
| #1～#14 | `test_deep_audit_14_bugs_regression.py` | 13 | 13/13 原函式仍在 |
| #15～#32 | `test_deep_audit_round2_bugfixes.py` | 14 | 14/14 原函式仍在 |
| #33～#50 | `test_deep_audit_round3_bugfixes.py` | 12 | 12/12 原函式仍在 |
| #51～#70 | `test_deep_audit_round4_bugfixes.py` | 18 | 18/18 原函式仍在；#69/70 另加現行測試 |
| #71～#95 | `test_deep_audit_round5_bugfixes.py` | 20 | 20/20 原函式仍在；#73/93 等有補強來源 |
| #96～#116 | `test_deep_audit_round6_bugfixes.py` | 10 | 10/10 原函式仍在 |

- 直接讀取六份原始基準與 `localX` 版本比對：**共 87/87 原函式名稱仍保留，87/87 原函式的斷言與預期例外數量均未減少**。六份仍在 `tools/product_ci_regression.py::PYTEST_PATHS`，是完整 Product CI 的實際測試，不是只存在於舊 branch 的檔案。
- 以原測試的 `assert` 與 `pytest.raises` 簡式逐行核對共 **329 處**，327 處原行可在現行函式中逐字（忽略空白）找到，兩處診斷條件調整仍保留拒絕能力：`_factor_or_override(True,...)` 依現行 `bend_factor must be finite` 精確拒絕；`_phase6_signature_canonical_value(float("nan"))` 現明確拋 `ValueError` 防止 NaN 與字串 sentinel 的 cache-key 混淆，不再使用早年的 `"__NaN__"` 輸出。這個 327/329 是**文字檢查位置**，不是 327 個獨立 AC 或對全部測試內容逐 byte 一致的主張。
- 另查現行 #96～#116 來源：`assembly_marking_geometry`、`baseline_source`、`receiving_nfb_persistence`、`phase6_box_body_structure` 的原六輪正反條件目前由各自的現行實作保留／擴大防護；舊 `phase6_manufacturing_geometry` 對非整箱側板借用 bounding-box 重新覆蓋實際折形的期待已退役，當前測試明確保留物理側板的自身折彎與分割幾何，僅允許整箱或缺軸來源走必要推導。
- 2026-10-27 此前 `localX` 合併 `#2337` 和 `#2338` 的是額外 Round9 當期合法來源修正；**不得算成原 116 項新簽核數字**。
- 現行原生 GUI、2D→3D→2D、Save→Reload、接收門板 DXF、製造輸出與 GUI 交易另有六支完整測試套件列入 canonical `PYTEST_PATHS`；仍需區分原生 Linux/Tk 自動操作與 Windows 人工觀察。
- 前一筆 fully verified Product Regression `#40461263884` 原五工作 SUCCESS，且 `localX` 合入後四個修改 blob 與受測 SHA 一致。**本次新增來源完整性防退化測試，須另外等本 PR exact HEAD 五工作 SUCCESS 並合併回讀，才能記為此版已驗收**。

## 本次新增反退化保護

`tests/process/test_audit116_original_six_round_witnesses.py` 與 canonical `PYTEST_PATHS` 一起驗：
1. 六輪編號 #1～#116 範圍不中斷，不能把第 7～9 輪填回原始缺陷數；
2. 87 個原始測試函式必須由六份現行檔案完整執行，不可從 CI 選單移除；
3. 每個原始測試函式的 `assert` / `pytest.raises` 證據數量不得少於原始基準；
4. 不得對原始測試函式直接標記 skip/skipif/xfail；六支端到端 GUI／DXF 原生測試仍須列入同一 Product CI。

這是**防偷改、漏跑或減測的守衛**，不是以程式碼宣告取代每個使用者可見功能的實際驗收。

## 尚未核銷／禁止冒稱

- **116/116 人工實機驗收：尚未成立。** 現行 GitHub CI 能證明對應自動化斷言在受測原始碼執行成功；不能憑測試名稱或 Linux runner 認定使用者目前 Windows `Z:\localX` 所見的 GUI、組合 3D、打標、輸出 DXF 與保存流程都正確。
- 最近最新版的 Windows `Z:\localX` SHA 與完整 116 條逐項操作／圖片／stdout、stderr／DXF entity 比對尚無本次授權與收據；不得拿過去 #1503、#1504 局部 GUI 收據當新版本 116 項全套。
- 按使用者流程：程式先 GitHub `localX`；之後由使用者在 Windows localX 實機驗收；**正式 X 僅在使用者當次 `/推推` 後才可發布**。無 DC/RC 授權，本輪沒有使用 DC、沒有操作 Windows，不允許强推、重設或覆蓋現有本機更動。
- 新的 116 個別項目如需簽核，必須列出原 BUG 身分、現行產品函式、直接人工 GUI／物理 DXF 證據及其適用 scope；不得把單一 pytest 函式（尤其 R6 10 個綜合測試）假稱 21 個獨立真人已簽。


## 2026-10-28 — 原始 116 項：受電箱門格開孔權威提交的增補驗證規格（不抵充實機簽核）

**問題與事證**：早期 `tests/test_phase6_receiving_multipart_integration.py` 只以 Linux `DISPLAY` 決定是否執行，又將 `BoxCalculatorGUI.surface_features["door_c1_r1"]` 視為受電箱的權威門格開孔來源；Windows R5-2600 解除 skip 後觀察到 3D 為空。最新產品正式啟動入口實為 `Phase6PrimaryApplication`；受電箱 `open_door_layout_cell_editor()` 則由當前 Designer workspace 提供門格特徵、使用 `sync_callback` 傳回 WHD 專案來源。直接改舊欄位不等於孔位編輯器已確認。

**本批可在 CI 完成的測試**：在真實原生 Tk／Xvfb 建立 `Phase6PrimaryApplication`，切換受電箱、選擇第一個門格，透過 `open_door_layout_cell_editor` 的正式呼叫取得原編輯器 `feature_list_override` 及 `sync_callback`；以真正 `Phase6HoleEditorSession` 插入一個 Ø12 CUTTING 圓孔並確認，再走相同回寫回呼；必須同時出現在 Designer 工作區、主工作區、專案快照，並且 `.p6fold` 磁碟存檔重讀後仍相等。取消交易則必須沒有新增孔。所有斷言保持嚴格，要求程序正常退出。

**驗收界線**：測試使用真實產品 Tk、實體 Session 與原生編輯器的提交回呼，但以隔離的 callback capture 取代 CADCraft 視窗本身及人工滑鼠操作，**不能當成 Windows CADCraft 外部程式實際畫孔→回傳、肉眼 3D 或 NC 正式製造輸出的證據**。R5-2600 離線時只能取得 GitHub CI 的測試收據；不得更新為 116／116 或使用者正式人工 PASS。修正先保留於隔離 PR，Product Regression 五組全部綠且完成核對才考慮合回 `localX`；沒有使用者 `/推推` 不發布 X。


## 2026-10-28 — BUG #2 原生 Receiving 門格刪孔防回魂（候選，未簽真人 UAT）

- 對照最初的 BUG #2（多門格 2D 新舊來源相互覆蓋），新增 `test_audit116_bug2_primary_door_hole_delete_does_not_resurrect_stale_source` 的原生 PRIMARY Tk 雙向驗證。沿用產品 `open_door_layout_cell_editor(0,0)` 提供的正式 feature list 與 `sync_callback`，先真 Session 新增 Ø13 CUTTING 孔並確認，再重新開啟同一門格，透過 `HoleEditorAction.delete_selected()`，分別確認刪除與取消刪除。
- 正向：刪除確認後不得由先前 `surface_features`、Designer、主工作區或專案快照回填舊孔；反向：取消刪除則原孔須完整保留。兩種結果都要寫入真正 `.p6fold` 並重讀比較，所有斷言不得放寬。
- 這是在現有 #2361 測試基礎上加強原始 BUG #2 的**現行來源自動化證據**，不改產品幾何或權威，不抵充原始 116 條人工實機簽核，未測外部 CADCraft GUI 滑鼠、真 Windows 2D/3D 畫面或 NC。
- 必須等本獨立 PR exact-head 完整 Product Regression 五組成功及合併後 exact blob 回讀，才可將此增補來源證據記為通過；失敗就保留待修，正式 X 仍需獨立 `/推推`。

# WHD 116 項歷史編號修復及來源核銷更正（2026-10-30）

> **本文件是來源錯帳修正，不是新製造放行。** 目標：不再讓沒有原始獨立定義的 21 個數字欄位永久阻塞當年的 BUG 行為查核；同時**絕不把沒有原文與獨立測試的欄位假簽成 PASS**。只能把「116/116 帳本有處置」與「116/116 獨立缺陷 PASS」分開說明。

## 來源權威與可覆核證據

- 原始使用者報告：2026-10-23 上傳的 `貼上的文字 (1)(3).txt`，原始內容第六輪標頭宣稱「Bugs #96–#116，共 21 項」，實際下列 **六個功能群組**，沒有 21 個唯一的逐號缺陷名稱、觸發條件與逐項斷言。
- 第三輪原始程式：[tests/test_deep_audit_round3_bugfixes.py@9baee365](https://github.com/looaeedr/whd/blob/9baee365/tests/test_deep_audit_round3_bugfixes.py) 開頭宣告 R3-1…R3-14；[PR #2083](https://github.com/looaeedr/whd/pull/2083) 正文最多聲稱 R3-1…R3-16。**沒有任何原始 R3-17 或 R3-18 定義可對應總帳 #49、#50**。
- 第六輪原始程式：[tests/test_deep_audit_round6_bugfixes.py@5702703c](https://github.com/looaeedr/whd/blob/5702703c/tests/test_deep_audit_round6_bugfixes.py) 僅 **10 個綜合測試函式**，對應六群組。不能把函式順序、每個 `assert` 或六組功能任意拆成「當年的 #97、#99～116」。
- Windows R5-2600 `Z:\localX` 的追溯總帳 `logs/DC_116_REAL_WINDOWS_UAT_20261027/AUDIT116_PER_ITEM_LEDGER_20261029_V68.csv`：**95/116** 已有來源限定簽核，另 **21/116** 不具逐號來源（#49、#50、#97、#99–#116）。
- 真 Windows 回歸：2026-10-30 本機 `e09996ccc0219dc3d1f416bc5883be6cd29c4e20` 原始六輪測試 `AUDIT116_V85_R1_R6_E09996.xml` **436 PASS、0 FAIL**；NFB、墊高片、底板、GUI、儲存重開跨組 `AUDIT116_V85_NFB_GUI_PAD_FACTORY_E09996.xml` **230 PASS、6 DISPLAY SKIP**；這六項在 Tk 可視環境 `AUDIT116_V85_NATIVE_WIN_GUI_6_SKIPS_E09996.xml` 補驗，該檔 **7 PASS、0 SKIP**。先前 31→26 mm 自訂框寬問題另有 `AUDIT116_V84_FINAL_MERGED_WINDOWS_GUI_E09996.xml` **4 PASS**。
- 第六輪功能群組另在 Windows `localX@1df0805de4a22ebf97efe109262e1999ed9f1b41` 具有六組獨立收據，共 **38 PASS**：`AUDIT116_R6_GROUP_01_MARKING_1DF080.xml` 至 `AUDIT116_R6_GROUP_06_STRUCTURE_1DF080.xml`。這些收據支持六群組限定來源行為，**不是 19 個未知編號的各自驗證**。
- 本輪遠端修訂從 GitHub `localX@8300613b5b84b7d037ac81995326983d093ec854` 建分支。上面 Windows 收據鎖在各自 exact HEAD，**不把舊 HEAD 的 PASS 說成新 HEAD 的同版實測**。

## 重新核銷的帳務口徑

| 類別 | 數量 | 判定 | 是否可稱逐項 BUG PASS |
|---|---:|---|---|
| 已有來源限定逐號簽核 | 95 | `SIGNED_SCOPE_*`，沿用原收據及其實測版本限制 | **是，但只限簽核範圍** |
| R3 無 R3-17/18 原始定義（#49/#50） | 2 | `PROVENANCE_RECONCILED_NO_PER_ID_ATTESTATION`；註銷原報告缺乏依據的「另有 2 個獨立 BUG」數量主張 | **否** |
| R6 原始只按六組、10 個綜合測試列示（#97、#99–116） | 19 | `PROVENANCE_RECONCILED_NO_PER_ID_ATTESTATION`；改由下方六組實際功能證據驗收，不虛構 19 個歷史編號 | **否** |
| **所有原數字欄位均有明確處置** | **116** | **95 範圍限定簽核 + 21 原始編號證據錯帳更正** | **絕非 116 PASS** |

逐號更正紀錄見同目錄 `audit116_legacy_unmapped_21_disposition_20261030.csv`，21 個欄位逐一列明「不具獨立來源」及原始群組證據，不是將未測項目偷改為通過。不得再把這 21 個當成「等待人工 UAT」或「必須取得不存在的原文」的無限期阻塞項。若後來找到可核對的當年逐項原文，應新增版本化對照及對應失敗/通過實測，不能覆蓋此證據邊界。

## R6 六群組按*實際可判斷行為*追溯

| ID | 原始修復群組 | 直接正反驗證入口 | Windows 群組收據 |
|---|---|---|---|
| R6-G01 | MARKING 世界座標→展開與錯誤座標/面片的 fail-closed | `test_assembly_marking_geometry_normalization_and_backprojection_guards` | `AUDIT116_R6_GROUP_01_MARKING_1DF080.xml` |
| R6-G02 | DXF 損毀後僅預覽可用 last-good；負半徑及非有限 CUTTING 邊界 | `test_baseline_source_dxf_error_fallback_and_cutting_bounds` | `AUDIT116_R6_GROUP_02_DXF_1DF080.xml` |
| R6-G03 | Assembly/Joint/MaterialSegment 型別及累計展開溢位拒絕 | `test_contracts_and_material_segment_reject_bool_and_nonfinite` 及後續細分契約測試 | `AUDIT116_R6_GROUP_03_CONTRACT_1DF080.xml` |
| R6-G04 | NFB V5 深度／CSV 身分／PAD 規則／持久化／EAR-Z 來源防護 | `test_receiving_nfb_depth_surface_policy_v5_brand_and_bool_guards` 等四個 NFB 測試 | `AUDIT116_R6_GROUP_04_NFB_PAD_1DF080.xml` |
| R6-G05 | 固定孔、EAR 避讓、截角與孔位數值不合法時拒絕 | `test_receiving_weld_ear_and_sheetmetal_corner_features_geometry_guards` | `AUDIT116_R6_GROUP_05_CORNER_1DF080.xml` |
| R6-G06 | 三件式箱身、Fold/FinalScene 和 EndCap 防護 | `test_phase6_box_body_structure_string_bool_and_three_piece_guards`；`test_phase6_manufacturing_geometry_and_endcap_guards` | `AUDIT116_R6_GROUP_06_STRUCTURE_1DF080.xml` |

## 防止再次卡關的結論

1. **不再等待不存在的原始逐號 BUG 定義**。將這 21 個歷史數字定位為「原文未證實的計數欄位」，其行為內容按原始六輪可辨識的修復群組、函式及正反回歸核查。
2. 維持 **95 個已驗原始條目的限定技術證據**；另 **21 個欄位完成來源帳務處置**，不得聲稱「116 個獨立 BUG 全 PASS」。驗收報表須同時呈現這兩個數字。
3. 有實際可重現功能故障，就以當下的程式入口、配置、expected/observed、精確 SHA 開獨立 BUG 並修復，不因歷史編號不完整就停止；不拿製造安全限制或未執行的人工 UAT 當籠統藉口。
4. 正式工廠 MFG-2／NC、CSV V5 真實板件製造放行，**不在本次原始 BUG 行為複驗範圍內**。正式 X 未收到當次 `/推推` 不可發布；`config.ini`、Windows 驗收日誌及本機未提交修改不得覆寫。

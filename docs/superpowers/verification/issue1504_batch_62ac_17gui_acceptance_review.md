---
whd_doc_role: REFERENCE
whd_contract: issue1504-acceptance-review
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #1504｜62 項候選／#1502 已交付實際斷言稽核＋17 項 GUI 串行驗收

## CURRENT｜2026-10-22 exact runtime 補正（不重新施工、不冒充完整 AC）

- [PR #2046 Product Regression #39723294524](https://github.com/looaeedr/whd/actions/runs/39723294524) exact tested HEAD `2b0a9db8f57f86f91c291b6c46f58d93d6b4e021`：Preflight、Shard0／1／2、Canonical 均 SUCCESS；合計 **1625 passed／0 failed**。已依 [#1504 實際執行核對](https://github.com/looaeedr/whd/issues/1504#issuecomment-6333263717) 確認 62 項 primary witness 的匹配執行：選型開孔 29／29、提交保存 19／19、板件組合 9／9、DXF 數量 5／5，44 個去重函式。機器稽核 JSON 已同步移除 62 筆錯誤的「等待該次完整 CI」標籤，改存 **run ID + exact SHA**。
- **這只是 62 項 primary witness PASS，不是 62 項完整 AC 通過。** 完整斷言、跨步驟操作與 17 項 GUI 真正同案串行仍應分開核對；原 88 AC matrix 不因此升級簽核、Windows UAT 沒有被聲稱完成。
- #1503 已在 PAD 專項 [#39717486059](https://github.com/looaeedr/whd/actions/runs/39717486059) 取得 **190 passed／0 failed**，包含單層及雙層 PAD＋對應 Base PART-ONLY DXF/CHECK Q/BOM；不再沿用「PAD 只有預覽」的過期說法，也不得冒充整櫃 MFG-2。#2047 把 PAD workflow 中 14 個過去未進主 PR CI 的檔案補進 canonical regression，須另以 **#2047 exact HEAD** 的全量 CI SUCCESS 為整合條件。
- 真實倉庫專案 A 已有部分 Linux 真 Tk 開啟／Cancel／Save／Reload 實測；專案 B 原始位元組尚未有合法 GUI/UAT 執行來源，**17 項完整 GUI AC 仍為 0／17 signed**。


> 2026-10-22（Asia/Taipei）。這是 **查核與缺口表，不是放行表**。來源為 #1504 綁定原 88 AC 文字及 PR #2045 的實際 Python 測試函式。每列精確連回既有測試，已讀取測試內容而非僅比對檔名；完整 CURRENT AC 的端到端條件尚須獨立判定。

## 判定口徑

- 共 62 項＝原 48 項候選（含本 PR 中 AC-25 暫列候選，不能當成第六項正式通過）＋14 項 #1502 已交付但未完全簽核；不對這 62 項整批修改 accepted 欄。
- 函式存在、有 `assert` 或 `pytest.raises`，只證明找到具體斷言；**不等於 AC 的所有使用者操作與物理／製造條件完整**。函式內容概要列在下方，每項保留 source-only/real-GUI/DXF 條件缺口。
- #2045 舊 RED（PAD 共用方孔與舊 CHECK/Q 衝突、主 2D 舊 CENTER 期待）已有現行修復，#2046 完整 CI SUCCESS；**舊失敗不能繼續當最新阻擋**。但 primary witness PASS 仍不等於全部 AC 完整通過。
- #1502 已交付 14 項繼續標 `SCOPED_LOCALX_1502_DELIVERED_AWAITING_FULL_AC`；本表不重寫原 88 AC，也不宣告 #1500 真 GUI／PAD 完整製造／Windows 驗收。

## 選型與開孔（29 項）

檢查型號身份、完整來源、名義與真座標、原特徵去重；缺實際面板互動和逐顆核准幾何者仍不升格。

| AC | 原始要求 | 實讀斷言函式 | 觀測／缺口 |
|---|---|---|---|
| NFB-AC-01 | 受電箱才看見 NFB UI；其他箱型既有 Hole Editor 不變。 | \`tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields\`（3 條直接斷言） | 候選未簽核；實際斷言：\`assert name not in d\`；舊專案 GUI 未跑 |
| NFB-AC-03 | 真實廠牌 DXF 列表、右側預覽、縮放／平移／重設；選檔不污染正式狀態。 | \`tests/test_issue1492_nfb_real_dxf_preview.py::test_pan_zoom_reset_never_reopens_source_or_changes_manufacturing\`（8 條直接斷言） | 候選未簽核；實際斷言：\`assert len(original)==4\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |
| NFB-AC-05 | 整層預設與單顆角度覆寫互不混淆；0/90/180/270 正確、禁止鏡像；更換型號保留設定。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_angle_inherit_explicit_same_override_no_mirror\`（9 條直接斷言） | 候選未簽核；實際斷言：\`assert effective_nfb_rotation(changed,0,0)==90\`；仍需完整端到端交叉核對 |
| NFB-AC-11 | 真實來源 ARC、CIRCLE、多 layer／entity color、上下資料組皆完整識別；主開孔 pivot 正確。 | \`tests/test_issue1496_nfb_dxf_source.py::test_color_sources_preserve_entity_layer_and_block_inheritance\`（22 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert by_handle[upper_h].layer == "BASE_CUT"\`；仍需完整端到端交叉核對 |
| NFB-AC-15 | 僅選取與高亮不重建整箱 3D、不反覆重讀全部 DXF；UI 互動不卡頓。 | \`tests/test_issue1492_nfb_real_dxf_preview.py::test_cache_changes_with_real_source_identity_and_bounded_memory\`（6 條直接斷言） | 候選未簽核；實際斷言：\`assert cache.load("士林",source.name,index_path=index) is first\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| NFB-AC-18 | 層數只有 NFB 配置一處可編輯；本套開關旁只保留廠牌＋入口；單顆 X／整排 X 基準未知、非 1100 Y 未知，均顯示未定且禁止偽製造定位。 | \`tests/test_issue1491_nfb_ui1a.py::test_nominal_pitch_exact_but_never_absolute_x\`（5 條直接斷言） | 候選未簽核；實際斷言：\`assert r["layers"][0]["adjacent_x_mm"]==pitch\`；實際輸出／重開仍需對帳 |
| NFB-AC-20 | 改本套／本配置／層預設品牌前正確預告將待重選顆數；取消狀態完全不變，確認才套用；同值明確覆寫仍維持覆寫身份。 | \`tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides\`（9 條直接斷言） | 候選未簽核；實際斷言：\`assert same_layer["layers"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}\`；舊專案 GUI 未跑 |
| NFB-AC-25 | 「型號待重選」仍可依已核准名義表顯示相對中心距；實際 X 定位、碰撞、越界各自未驗證，沒有憑空置中。 | \`tests/test_issue1504_ac25_reselection_nominal_x.py::test_nfb_ac25_reselection_preserves_approved_relative_pitch_no_fake_x_checks\`（13 條直接斷言） | 新修候選，待 CI；實際斷言：\`assert draft == before and stale == snapshot\`；真板件連動待完整對帳、PR2045 exact CI + merge 尚未完成 |
| NFB-AC-26 | 儲存單顆 90° 等旋轉設定並重載；主開孔中心未驗證時不產生假旋轉放置／已驗證顯示。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_angle_inherit_explicit_same_override_no_mirror\`（9 條直接斷言） | 候選未簽核；實際斷言：\`assert effective_nfb_rotation(changed,0,0)==90\`；兩案重讀未跑 |
| NFB-AC-27 | Q16 型號變更／待重選恢復不改已知名義中心距，保留位移並重驗整層實際幾何；具完整資料且非法時全筆原子回滾。 | \`tests/test_issue1497_nfb_cutting_preflight.py::test_q16_invalid_model_change_blocks_whole_batch_without_moving_other_hole\`（6 條直接斷言） | 候選未簽核；實際斷言：\`assert initial.status == PREVIEW_ONLY\`；仍需完整端到端交叉核對 |
| NFB-AC-28 | 未驗證位移至少可按 Bay／配置批次重新確認，先提示條件差異與受影響清單；逐顆非法者不能批次放行。 | \`tests/test_issue1497_nfb_cutting_preflight.py::test_two_independent_upper_units_require_unique_physical_claims_and_no_overlap\`（9 條直接斷言） | 候選未簽核；實際斷言：\`assert batch.status == PREVIEW_ONLY\`；仍需完整端到端交叉核對 |
| NFB-AC-37 | 同位置既有 Hole Editor Feature 與 NFB 來源先識別後關聯／排他，來源不明 fail-closed；沒有重複孔，還原後舊特徵完整恢復。 | \`tests/test_issue1497_w800_three_canonical_cutting.py::test_legacy_same_location_or_same_physical_owner_blocks_atomic_export\`（2 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="blocked"):\`；仍需完整端到端交叉核對 |
| NFB-AC-48 | MFG-1 缺 X 單顆／整排、Y 局部投影或主孔中心任一證據時，不得讓未知配置成為「可製造」；四組已知名義中心距不自動等於已驗收可製造。 | \`tests/test_issue1494_nfb_x_shadow_projection.py::test_no_unapproved_size_or_single_unit_center_defaults\`（1 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError, match="OPEN-X"):\`；實際輸出／重開仍需對帳 |
| NFB-AC-49 | W800×3 的 723/361.5 個案須核對來源 DXF 左輪廓、真正下料 CUTTING 左緣及下料→門面→箱體 X 映射；未證實前不得以此個案推導其它組合。 | \`tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly\`（17 條直接斷言） | 候選未簽核；實際斷言：\`assert [r.revision for r in rows] == [W800_THREE_DATUM_REVISION] * 3\`；實際輸出／重開仍需對帳 |
| NFB-AC-50 | 1100 名義 550／290／790 從箱體外頂投影到內門成品與展開 Y 具可重現雙向測試；非 1100 標「Y 基準未定」，不猜。 | \`tests/test_issue1495_receiving_nfb_y_projection.py::test_approved_nominal_box_top_y_maps_to_real_1075_blank\`（15 條直接斷言） | 候選未簽核；實際斷言：\`assert state == raw_before  # no change of any prior Hole Editor feature\`；仍需完整端到端交叉核對 |
| NFB-AC-51 | DXF 主 CUTTING 中心、ARC/CIRCLE、來源顏色及旋轉 pivot 經真圖認證；選型列表逐組正確顯示「可製造（內門）」／「僅預覽」，不可因型號孤立合格便全範圍放行。 | \`tests/test_issue1496_nfb_dxf_source.py::test_unsupported_not_silently_treated_as_certified\`（4 條直接斷言） | 候選未簽核；實際斷言：\`assert any("UNSUPPORTED:ELLIPSE" in note for note in inv.diagnostics)\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |
| NFB-AC-52 | MFG-1 輸出合法內門真實 CUTTING、消除與 legacy 相同物理孔的重複加工來源；缺必要幾何 fail-closed，MFG-1 未通過時 UI-1B 不准提交。 | \`tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes\`（11 條直接斷言） | 候選未簽核；實際斷言：\`assert result.manufacturing_ready\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |
| SWT-AC-01 | 單一可寫 NFB 安裝層數入口，與既有本套品牌 UI 一致；金庫型不出現 NFB 專屬規則。 | \`tests/test_issue1491_nfb_ui1a.py::test_no_unapproved_geometry_or_persistence_fields\`（3 條直接斷言） | 候選未簽核；實際斷言：\`assert name not in d\`；舊專案 GUI 未跑 |
| SWT-AC-03 | 每層多顆有獨立身份與型號、順序、X 位移及旋轉設定；既有中心距只於有效規格組合使用。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_insert_delete_reorder_reset_only_touched_layer_x\`（10 條直接斷言） | 候選未簽核；實際斷言：\`assert [s["unit_id"] for s in swapped["layers"][0]["slots"]]==old_ids[::-1]\`；仍需完整端到端交叉核對 |
| SWT-AC-05 | 每顆來源 DXF 原圖預覽、確認／取消、主開孔中心未驗證標示清楚；不冒充可製造定位。 | \`tests/test_issue1492_nfb_real_dxf_preview.py::test_native_arc_circle_bulge_and_aci_preserved_in_real_source_strokes\`（13 條直接斷言） | 候選未簽核；實際斷言：\`assert result.status==PREVIEW_ONLY and result.source_sha256\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |
| SWT-AC-06 | UI 的 Q5／Q6／Q7／Q16 行為只驗收 NFB-AC-04／19／27；本件查核名義中心距不受型號改變、非法實際幾何不得放行，Undo／取消保留既有加工。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry\`（8 條直接斷言） | 候選未簽核；實際斷言：\`assert new["unit_id"]==old["unit_id"]\`；舊專案 GUI 未跑 |
| SWT-AC-13 | 變更上游品牌前顯示待重選顆數，確認後更新跟隨者，取消時品牌／型號／位移／旋轉／覆寫狀態完全不動。 | \`tests/test_issue1491_nfb_ui1a.py::test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name\`（5 條直接斷言） | 候選未簽核；實際斷言：\`assert all(x["status"]==NEEDS_RESELECTION for x in selected["layers"][0]["slots"])\`；舊專案 GUI 未跑 |
| SWT-AC-16 | 新 X 基準定案，既有未知基準位移必須逐顆或按 Bay／配置批次重新確認；確認後仍逐顆驗證，不能批次跳過干涉檢查。 | \`tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero\`（4 條直接斷言） | 候選未簽核；實際斷言：\`assert good["holes"][0]["manual_x_mm"] == 0\`；仍需完整端到端交叉核對 |
| SWT-AC-17 | 型號待重選時已知名義中心距仍可顯示，實際幾何／碰撞保持未驗證；旋轉角度可存但主孔中心缺乏時不產生假放置。 | \`tests/test_issue1492_nfb_real_dxf_preview.py::test_missing_and_unindexed_dxf_cannot_show_fake_contour\`（6 條直接斷言） | 候選未簽核；實際斷言：\`assert missing.status==MISSING\`；真板件連動待完整對帳 |
| SWT-AC-23 | 一個舊式 Feature 與 NFB 孔應相同物理位置時完成來源關聯／排他且不重複；未驗證阻斷該片正式加工；還原未配置不失原特徵。 | \`tests/test_issue1497_w800_three_canonical_cutting.py::test_existing_legacy_circle_is_preserved_exactly_once_in_real_nfb_dxf\`（7 條直接斷言） | 候選未簽核；實際斷言：\`assert ready.manufacturing_ready\`；仍需完整端到端交叉核對 |
| SWT-AC-27 | 單顆 X／整排 X 的內門／箱體 datum 與來源 DXF 有正式核准測例，沒有的組合不得冒稱可製造，W800×3 不能替其他箱寬解除 `OPEN-X-ROW`。 | \`tests/test_issue1494_nfb_x_shadow_projection.py::test_w800_three_canonical_x_comes_from_actual_whd_cutting_and_assembly\`（17 條直接斷言） | 候選未簽核；實際斷言：\`assert [r.revision for r in rows] == [W800_THREE_DATUM_REVISION] * 3\`；實際輸出／重開仍需對帳 |
| SWT-AC-28 | 1100 上層的外頂 Y=550／290／790 正確投影到形成內門及展開局部 Y，非 1100 不猜座標。 | \`tests/test_issue1495_receiving_nfb_y_projection.py::test_non_1100_upper_y_is_unapproved_not_silently_scaled\`（1 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError, match="unapproved cell height"):\`；仍需完整端到端交叉核對 |
| SWT-AC-29 | 每顆 NFB 的主 CUTTING 開孔中心、輪廓與旋轉有真實 DXF／Feature 測例；與既有中間孔加工來源排他、不重複、不刪 legacy Feature。 | \`tests/test_issue1497_configured_nfb_manufacturing_release.py::test_legacy_same_physical_hole_fails_no_duplicate_cutting\`（1 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="blocked"):\`；實際輸出／重開仍需對帳 |
| SWT-AC-30 | 已知四組相鄰名義孔距不是可製造清單；只對逐組核准的 W×N×Y×型號×內門 datum 顯示可製造（內門），範圍外僅預覽。 | \`tests/test_issue1498_nfb_part_readiness.py::test_wrong_approved_inner_source_or_wrong_part_is_not_a_manufacturing_capability\`（1 條直接斷言） | 候選未簽核；實際斷言：\`assert result.for_part("inner_door:upper:panel").status==BLOCKED\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |

## 提交與保存（19 項）

檢查草稿原子性、版本隔離、schema／Save→Reload；只有單函式斷言時，尚缺兩份真舊工程操作與重讀證據。

| AC | 原始要求 | 實讀斷言函式 | 觀測／缺口 |
|---|---|---|---|
| NFB-AC-04 | 配置卡重排序與 2D 位移明確分離；mm 欄位精確；Q5／Q6／Q7 清除受影響層全部位移；Q16 保留位移、名義孔距不動，重新驗證非法回滾。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_insert_delete_reorder_reset_only_touched_layer_x\`（10 條直接斷言） | 候選未簽核；實際斷言：\`assert [s["unit_id"] for s in swapped["layers"][0]["slots"]]==old_ids[::-1]\`；真板件連動待完整對帳 |
| NFB-AC-06 | 離開／取消／Undo 不漏出暫存變更；範圍／碰撞非法時保留上次合法配置。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions\`（10 條直接斷言） | 候選未簽核；實際斷言：\`assert session.dirty\`；舊專案 GUI 未跑、真板件連動待完整對帳 |
| NFB-AC-08 | 數量模式不同 `version_id` 可保存不同 NFB；版本增刪／切換／深複製／重讀均保持身份。 | \`tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate\`（7 條直接斷言） | 候選未簽核；實際斷言：\`assert q.snapshot()["schema"] == SCHEMA_V2\`；舊專案 GUI 未跑 |
| NFB-AC-09 | 已經合法提交但後續因板件未完成或來源失效而未驗證的草稿可 Save→Reload；只阻斷真正依賴 NFB 缺項的物理板件，列明 Set／Bay／版本／層／顆與原因；不連坐同 Bay 無關板件。 | \`tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache\`（3 條直接斷言） | 候選未簽核；實際斷言：\`assert approved.for_part("inner_door:upper:panel").status==READY\`；兩案重讀未跑、真板件連動待完整對帳 |
| NFB-AC-19 | Q5／Q6／Q7 只清受影響層全部手動位移，對應狀態改 NONE 並清舊快照；Q16 保留位移／名義孔距，重驗整層非法原子回滾；操作 Undo／Cancel 可完整還原。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_q16_replace_model_preserves_x_and_identity_but_unverifies_geometry\`（8 條直接斷言） | 候選未簽核；實際斷言：\`assert new["unit_id"]==old["unit_id"]\`；仍需完整端到端交叉核對 |
| NFB-AC-21 | 數量模式每個版本的本配置預設廠牌與三級繼承獨立；深複製後修改甲不影響乙；套／連本套品牌僅既有控件可寫。 | \`tests/test_issue1491_nfb_ui1a.py::test_single_set_brand_owner_and_explicit_same_value_overrides\`（9 條直接斷言） | 候選未簽核；實際斷言：\`assert same_layer["layers"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}\`；舊專案 GUI 未跑 |
| NFB-AC-22 | X datum 未定仍可輸入含明確 0 的位移，Save→Reload 保存 UNVERIFIED_BASIS、箱寬／層／顆 ID 順序／名義規則版本；沒有位移用 NONE；不保存衍生製造通過狀態。 | \`tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero\`（4 條直接斷言） | 候選未簽核；實際斷言：\`assert good["holes"][0]["manual_x_mm"] == 0\`；兩案重讀未跑、實際輸出／重開仍需對帳 |
| NFB-AC-23 | 新 X 基準確立後，舊位移不能自動生效，須比較條件並經使用者重新確認；受影響顆未確認前維持草稿與製造阻斷。 | \`tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate\`（7 條直接斷言） | 候選未簽核；實際斷言：\`assert q.snapshot()["schema"] == SCHEMA_V2\`；實際輸出／重開仍需對帳 |
| NFB-AC-24 | 逐顆「已驗證／未驗證」及原因正確；已提交配置由當前來源推導 DRAFT／CONFIGURED；DRAFT 只阻斷 NFB 依賴未完成的物理板件，不阻斷無關片／Bay／版本，列受阻身份。 | \`tests/test_issue1498_nfb_part_readiness.py::test_each_set_bay_version_independent_and_no_cross_scope_ready_cache\`（3 條直接斷言） | 候選未簽核；實際斷言：\`assert approved.for_part("inner_door:upper:panel").status==READY\`；真板件連動待完整對帳 |
| NFB-AC-29 | Save→Reload／來源 DXF 變動後重新推導主孔中心、位置、越界及草稿結論，不信任專案舊衍生驗證旗標。 | \`tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback\`（4 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="derived"):\`；兩案重讀未跑、實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| NFB-AC-32 | 清除位移後可觀測是哪層、幾顆受影響；Undo 恢復位移／基準條件快照，沒有殘留過期暫存。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions\`（10 條直接斷言） | 候選未簽核；實際斷言：\`assert session.dirty\`；仍需完整端到端交叉核對 |
| NFB-AC-33 | 新專案／新增 Bay／版本初始 UNCONFIGURED；未提交不需槽位，舊式 DXF 產出不變。 | \`tests/test_issue1499_nfb_persistence.py::test_unconfigured_bay_and_quantity_keep_legacy_schema\`（5 條直接斷言） | 候選未簽核；實際斷言：\`assert raw["schema"] == PROJECT_SCHEMA_V2\`；實際輸出／重開仍需對帳 |
| NFB-AC-47 | UI-1A 關閉有未提交變更的 NFB 面板須確認；取消關閉時保留編輯會話，確認捨棄不寫權威配置且舊式 DXF 不變。 | \`tests/test_issue1493_nfb_draft_transactions.py::test_cancel_escape_undo_restore_stable_unit_ids_brand_x_and_conditions\`（10 條直接斷言） | 候選未簽核；實際斷言：\`assert session.dirty\`；舊專案 GUI 未跑、實際輸出／重開仍需對帳 |
| NFB-AC-54 | 有已提交 scope 時升根 `.p6fold` 與 quantity payload schema；舊版依凍結支援 schema 清單拒載新版本，不吞未知欄位後產出完整 DXF；全部未提交工程仍保留本功能無關的舊 schema 相容。 | \`tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope\`（2 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="old schema"):\`；實際輸出／重開仍需對帳 |
| SWT-AC-14 | 套／連本套預設只能由既有本套品牌控件寫入；數量模式各版本 NFBConfig 自有預設品牌，新增版本深複製且修改互不污染。 | \`tests/test_issue1499_nfb_persistence.py::test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate\`（7 條直接斷言） | 候選未簽核；實際斷言：\`assert q.snapshot()["schema"] == SCHEMA_V2\`；舊專案 GUI 未跑 |
| SWT-AC-15 | 按 NFB UI v1.4 §2.3.1 的單一 `manual_x_state`、快照、基準版本保存未知基準位移；Save→Reload 不自動升格製造偏移（UI-1B 才可持久化）。 | \`tests/test_issue1499_nfb_persistence.py::test_confirmed_x_zero_is_not_missing_and_none_is_not_zero\`（4 條直接斷言） | 候選未簽核；實際斷言：\`assert good["holes"][0]["manual_x_mm"] == 0\`；舊專案 GUI 未跑、兩案重讀未跑、實際輸出／重開仍需對帳 |
| SWT-AC-19 | 重載／來源更新重新推導實際位置、主孔中心、碰撞與草稿，不把過期驗證狀態當存檔真值。 | \`tests/test_issue1499_nfb_persistence.py::test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback\`（4 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="derived"):\`；兩案重讀未跑、真板件連動待完整對帳 |
| SWT-AC-25 | 未選型與缺來源不導致既有 UNCONFIGURED 箱體任何新增阻斷；已提交之內門及真實存在的底板／中板依保守基線阻斷，側板不憑 EAR 延期受阻。 | \`tests/test_issue1498_nfb_part_readiness.py::test_unconfigured_preserves_legacy_even_when_nfb_source_absent\`（3 條直接斷言） | 候選未簽核；實際斷言：\`assert not result.can_submit\`；真板件連動待完整對帳 |
| SWT-AC-31 | 未提交保持既有 schema 與 DXF；已有提交 scope 須根專案與 Quantity schema 升版，凍結舊版 schema 清單的舊 reader 拒載；不能對不認識新 schema 的舊版 silent export。 | \`tests/test_issue1499_nfb_persistence.py::test_old_schema_reader_must_not_silently_strip_new_nfb_scope\`（2 條直接斷言） | 候選未簽核；實際斷言：\`with pytest.raises(ValueError,match="old schema"):\`；實際輸出／重開仍需對帳 |

## 板件與組合體（9 項）

檢查板件所屬身份、真 FinalScene 幾何與 2D／3D／打標一致；source-scoped 交付≠整箱 MFG2／焊接放行。

| AC | 原始要求 | 實讀斷言函式 | 觀測／缺口 |
|---|---|---|---|
| NFB-AC-12 | 同顆跨板件孔／打標有穩定關聯，所有合法製造圖元位於正確實體板件，不被當成一張板。 | \`tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks\`（11 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert not result.manufacturing_ready\`；實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| NFB-AC-14 | 2D／3D／DXF／Save→Reload 使用同一已解析製造資料；相同加工片合併，不同 NFB 加工不得誤合併。 | \`tests/test_issue1502_nfb_ear_base_assembly_contract.py::test_ear_mounting_does_not_invent_base_or_change_verified_inner_NFB\`（11 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert ear.slot_pair_indexes == slot_pair\`；兩案重讀未跑、實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| NFB-AC-38 | 已提交配置對應內門必相依；可信 DXF 依 Color 30／150 判定底板／中板；型號未選或無法解析時阻斷實際存在的底板／中板，可信證明無相依則恢復匯出；EAR 延期不單獨阻斷側板，不連坐其他件／Bay。 | \`tests/test_issue1498_nfb_part_readiness.py::test_real_base_color30_and_marking212_have_specific_base_dependency\`（3 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert result.for_part("base_plate:upper").status==BLOCKED\`；實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| NFB-AC-44 | 已提交但空槽／待重選／來源解析失敗時，對應內門與實際存在的底板／中板均不可出完整製造 DXF；來源可信且確認未使用 Color 30／150 時，底板／中板不因 NFB 被阻斷；左右側板不因尚未批准的 EAR 需求被阻斷。 | \`tests/test_issue1498_nfb_part_readiness.py::test_missing_real_plate_id_is_scope_blocker_not_an_invented_part\`（6 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert result.for_part("inner_door:upper:panel").status==READY\`；實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| SWT-AC-08 | 沒有可信來源、主孔中心或合法世界定位時，按實體物理件相依阻斷完整 NFB DXF，逐件列出來源／缺項；不阻斷可證明無依賴片。 | \`tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero\`（5 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert result.for_part("inner_door:upper:panel").status==BLOCKED\`；實際輸出／重開仍需對帳 |
| SWT-AC-10 | 真實內門開孔與 NFB 個別中心一致，不以銘牌孔／假矩形替代；左／右耳朵真焊接接觸與打標同源。 | \`tests/test_issue1497_w800_three_canonical_cutting.py::test_w800x3_uses_whd_723_blank_x_for_three_real_holes\`（11 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert result.manufacturing_ready\`；真板件連動待完整對帳 |
| SWT-AC-11 | 2D／3D／DXF／Save 從同一解算來源一致；受電箱 NFB 衍生切孔不同的料件不能錯誤合併。 | \`tests/test_issue1502_nfb_base_source_projection.py::test_one_door_nfb_owner_projects_corresponding_base_cutting_and_marks\`（11 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert not result.manufacturing_ready\`；兩案重讀未跑、實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| SWT-AC-12 | 不破壞內門框末段 22 mm、46＋2T、門縫、底板原幾何、背孔／中隔與金庫型回歸。 | \`tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom\`（31 條直接斷言） | 候選未簽核；實際斷言：\`assert set(main._baseline_model_choices()) == {"金庫型", "受電箱", "自訂"}\`；真板件連動待完整對帳 |
| SWT-AC-21 | 已提交配置內門必相依；空槽／待重選或來源解析失敗保守阻斷實際底板／中板，可信來源依 Color 30／150 的正式類別分流且已證明無相依者可正常匯出。 | \`tests/test_issue1498_nfb_part_readiness.py::test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero\`（5 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert result.for_part("inner_door:upper:panel").status==BLOCKED\`；真板件連動待完整對帳 |

## DXF 與數量（5 項）

檢查原子 DXF、版本 Q 群組、物理片數、重開與防誤合併；原型／單測結果不代表兩份舊工程 GUI 批次輸出。

| AC | 原始要求 | 實讀斷言函式 | 觀測／缺口 |
|---|---|---|---|
| NFB-AC-31 | 量產版本不同 NFB 導出不同實際加工幾何時，不得錯誤合併 DXF；同加工者仍依既有 CHECK `Q{加工片數}` 正確分組。 | \`tests/test_issue1502_nfb_base_batch_export_gate.py::test_one_unreleased_base_rejects_entire_multi_bay_export_before_io\`（3 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`with pytest.raises(ValueError, match="NFB_BASE_MFG2_NOT_RELEASED_FOR_BATCH_EXPORT"):\`；實際輸出／重開仍需對帳 |
| NFB-AC-39 | 明示部分匯出產生實際可出／受阻清單與原因、版本、件數差異；不留混淆的完整批次舊 DXF，CHECK `Q{加工片數}` 只算實際合法匯出且幾何相同片。 | \`tests/test_issue1501_nfb_export_manifest.py::test_shihlin_color150_partial_only_counts_real_pieces\`（14 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert status=={"inner1":READY,"base1":UNAFFECTED,\`；實際輸出／重開仍需對帳 |
| NFB-AC-55 | 逐型號盤點真實 NFB DXF 的 Color 30／150／212 與來源可解析狀態，交付有／無／未知數量（未取得原 DXF 前不得填 0）；MFG-2 未完成時 Color 30／150 受影響底／中板保持阻斷並列於提交提醒與部分匯出清單。 | \`tests/test_issue1496_nfb_source_inventory_report.py::test_complete_per_brand_audit_has_exact_links_and_null_unknown\`（18 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert report["schema"] == "WHD_NFB_INDEXED_SOURCE_COLOR_COVERAGE_V1"\`；實際輸出／重開仍需對帳、真板件連動待完整對帳 |
| SWT-AC-20 | 數量模式 NFB 衍生孔型不同時不誤合併加工料件；相同實際加工幾何依既有 CHECK `Q{加工片數}` 規則合併。 | \`tests/test_issue1502_existing_base_nfb_assembly.py::test_two_real_NFB_heights_cannot_share_one_assumed_ear_group\`（1 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`with pytest.raises(ValueError,match="distinct actual ear/base groups"):\`；仍需完整端到端交叉核對 |
| SWT-AC-32 | 真 DXF Color 30／150 盤點件數與解析狀態逐檔可追溯；未取得源檔前不得假報 0。MFG-2 未完成的相依底／中板阻斷、其他無相依板件照常出圖，manifest／CHECK 計數不受污染。 | \`tests/test_issue1496_index_color_evidence.py::test_unique_model_links_keep_missing_unknown_distinct_from_real_zero\`（18 條直接斷言） | #1502 已交付，原 AC 尚未簽核；實際斷言：\`assert catalog.records_read==2\`；實際輸出／重開仍需對帳、真板件連動待完整對帳 |

## 17 項 #1500 GUI：兩份舊專案一次串行覆蓋

**專案 A（GitHub 真檔）**：`tests/fixtures/issue1503_legacy_receiving_without_nfb_base.p6fold`，`phase6-fold-project-v1`、W800×H1600×D350、T2、無持久化 NFBConfig。

**專案 B（使用者 Library）**：`/WHD/受電箱.p6fold`，同為 `phase6-fold-project-v1`、W800×H1600×D350、T2；與 A 為不同來源檔案，B 含獨立的已保存配置資料。已以 Files 解析原始 JSON，**但 raw-byte materialization 返回 `not authorized`**，目前不可將 B 傳給 GitHub Actions，也不能聲稱在真 GUI 中已跑過。

### 一條完整操作鏈（A、B 分別實際操作，各保留原始檔案及輸出）

1. **開啟／身份基準**：記錄原始 SHA256、schema、W/H/D/T、原板件與既有 Feature／主品牌；未提交時 UI-1A 開啟後取消，舊式 2D／3D/DXF 不應回退。覆蓋 `NFB-AC-02/16/42/46`、`SWT-AC-24/26`。
2. **修改 NFB**：第一層／第二層、品牌、真 CSV 型號、單顆位移含 0、旋轉 90°、待重選、取消／確定。確認不經 guard 不得偷提交。覆蓋 `NFB-AC-02/34/40/42/47/53`、`SWT-AC-26`。
3. **複製／Undo**：把已提交 Bay 複製到未配置 Bay，先取消覆寫，再確認深複製；兩邊分別修改確認不共用引用。執行「還原未配置」再 Undo，確認來源／目標、品牌、legacy Features 皆恢復。覆蓋 `NFB-AC-07/35/36/43/45/56`、`SWT-AC-07/24`。
4. **儲存重開**：Save→關閉→重載兩份 .p6fold，記錄已提交旗標、版本件數、X 0/NONE、品牌、層、Unit ID、過期來源重新驗證、未提交保持舊 schema。覆蓋 `NFB-AC-16/40/46/53`、`SWT-AC-07/18`。
5. **2D／3D／打標**：同一實體內門、分層底板、固定片、左右側板來源比對位置、孔數、透明度、BEND/CUTTING/MARKING。分別擷取前／後快照、同源 ID、尺寸。覆蓋 `NFB-AC-16/34/46`、`SWT-AC-18/24`。
6. **DXF／數量**：沿原 GUI 按鈕輸出合法／受阻清單，逐 DXF 以外部 DXF reader 重開核對孔位、耳固定孔、打標和來源；Q3＋Q2 同加工合併、不同版本不誤合併，失敗需整批 rollback。覆蓋 `NFB-AC-34/46/53/56`、`SWT-AC-18/24/26`。

### 每一專案一次操作的最小收據欄位

`project_sha256`, `localX_sha`, `app_build`, `runner_os`, `gui_display`, `opened_at_tw`, `step`, `before_state_digest`, `after_state_digest`, `button_enabled`, `guard_reason`, `2d_snapshot`, `3d_snapshot`, `marking_count`, `dxf_files`, `dxf_reopen_result`, `rollback_result`, `pass_or_fail`, `screenshot_paths`。*沒有真 GUI 操作與這些可查證結果，17 項全部維持 BLOCKED，不用單純 Tk unit GREEN 代替*。

**現階段 GUI 結果**：兩份來源檔案已定位且 JSON 結構可查；實際完整操作鏈 **0/2 executed**、GUI 簽核 **0/17**。B 原始位元組無權限交給容器；Windows `Z:\localX` 未獲當次 DC 授權、也未操作。此項明確延期，不應阻擋 #1504 已可自動化獨立驗證的非 GUI AC。

## 最終交付規則

將 88 項明確分為 `SIGNED_CURRENT_AUTOMATED`／`PARTIAL_ASSERTIONS_DELIVERED`／`PRODUCT_DEFECT_RED`／`GUI_UAT_DEFERRED`／`MFG_SOURCE_DEFERRED`。每一項只附精確來源、測試／真操作證據和不符合的斷言，**不為數量湊全綠、不無限擴施工**；#1504 以查明狀態及限制為收尾口徑。正式 X 仍需使用者 `/推推`。

### 2026-10-22 Linux 真 Tk 舊專案補證（尚待 exact CI）

- 新增 `tests/test_issue1504_legacy_fixture_real_gui_gate_cycle.py`：使用 GitHub 內原始 `issue1503_legacy_receiving_without_nfb_base.p6fold` 透過 `BoxCalculatorGUI` 真實執行 `load_project_file`、Receiving 原始多連視窗、NFB 未具來源時 disabled 提交／複製／還原／Undo、取消、`save_project_file_as`、重新載入及 legacy Features 保持，印出附 fixture SHA 的 `ISSUE1504_LEGACY_GUI_SOURCE_RECEIPT`。
- 此測試只是**專案 A 的部分真 Tk 操作證據**，尚待完整 CI；沒有程式捏造來源確認、沒有操作專案 B，也沒有聲稱完成 2D/3D/打標/DXF GUI 檢查或 17 項 AC 人工簽核。未獲完整 GUI 收據前原矩陣保持 17 項 BLOCKED。

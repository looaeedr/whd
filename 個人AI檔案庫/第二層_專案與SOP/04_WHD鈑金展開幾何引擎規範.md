---
whd_doc_role: CURRENT
whd_contract: manufacturing-architecture
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 🔩 04. WHD 鈑金展開幾何引擎規範（ae_engine）

## [CURRENT] #2517 箱身面板 2D Feature／CUTTING／MARKING 圖元只由公開 Engine 投影（2026-11-07）

- 原主 GUI `Phase6ApplicationHost._box_body_face_baseline_scene` 從 Engine 取得已解析的 BoxBody 面板孔位後，仍直接呼叫私有 `sheetmetal_drawing.resolved_features_to_primitives` 轉為 2D 圖元。此 Owner 含正式 Circle／Rect／Profile、`BLIND_HOLE` 中心線、`CUTTING` 主輪廓、外部 DXF process layers 與避免重複切線的語意；GUI 不可重算或默默遺漏。
- `manufacturing_api.project_operator_resolved_feature_drawing_primitives` 與根包 `ae_engine` 公開**同一原函式** `sheetmetal_drawing.resolved_features_to_primitives`。GUI 只把既有 resolved Features 交給 API，將回傳 `DrawingPrimitive` 加入顯示 `DrawingScene`；無第二份 CUTTING／MARKING 演算法，也不以示意圖承諾正式 DXF 製造。
- `tests/test_issue2517_box_body_resolved_primitives_public_api.py` 逐一驗證 `BLIND_HOLE`、`DATUM`、`CUTTING`、`MARKING`、`FROM_DXF` 不重複切線、原 Engine parity、GUI 一次委派與無效 Feature fail-closed；來源 Feature 不變。此純 2D readback 不改 PartSpec、FinalScene、儲存或 DXF writer；仍須 exact-SHA canonical Product Regression，Windows UAT 未藉此完成。

## [CURRENT] #2517 工程標註 2D 預覽只消費公開 Engine projection（2026-11-07）

- 原 `gui.py`、`gui_modules/application/door_render_host_adapter.py` 及 `gui_modules/rendering/overlays.py` 直接匯入 `ae_engine.engineering_drawing.build_engineering_drawing_projection` 與 `sheetmetal_features.CanvasTransform`，雖然只是工程標註的 2D 呈現，仍把 GUI 接在非公開的 Engine 內部投影來源上。
- 現由 `manufacturing_api.project_operator_engineering_drawing_annotations`／根包 `ae_engine` 以**同一 callable**公開既有 `engineering_drawing.build_engineering_drawing_projection`；主 GUI 與模組化 GUI 只傳入已解出的 canonical `PartRenderData`，從同一 Engine 取得尺寸／文字標註，`CanvasTransform` 使用原已有的公開 API。保留原來源有效性拒絕、`strict` 與碰撞診斷、`DIMENSION/TEXT` 限制及原 `DrawingScene` 不可變檢查。
- 此為 annotation-only readback，**不新增** material／CUTTING／BEND／孔位或 DXF export 資格；正式 2D／3D／DXF 仍需 consume 同一 canonical 製造來源。定向測試 `tests/test_issue2517_operator_engineering_drawing_public_api.py` 核對 callable identity、annotation parity、非法來源拒絕不污染、GUI adapter 委派與公開 CanvasTransform；GitHub exact-SHA 完整產品回歸另驗。

## [CURRENT] #2517 Receiving 解除連動須由公開 Engine 回傳原共享實體 Bay 身分（2026-11-07）

- 原 `ReceivingSetBayAdapter.unlink_setting(kind)` 已使用公開 `unlink_receiving_shared_setting` 進行單 Bay 來源更改，但不問是否實際解除，就只對當前 Bay 標 `session_dirty`；而原本共享同一參照的其他 Bay 沒有被列入當次來源關聯變更保護。原 `receiving_settings_ports.unlink` 對已獨立的 Bay 也照常提交 geometry intent，造成無變更的假 dirty／重算。
- 保留既有唯一 `receiving_shared_settings.unlink_setting` 與舊公開 API 全部相容；新增同 owner 的 `unlink_setting_with_affected_ids(layout, *, set_index, bay_index, kind)`，先以原 `normalize_receiving_layout`、`normalize_set_settings` 驗證實體 Set／Bay／Setting，再沿**同一份 canonical refs** 擷取解除前的實體共享 Bay 群組；以原 `unlink_setting` 原子建立 detached 候選。回傳 `(candidate, affected_ids)`：只有 ref 確實分離才返回原共享群組中的完整實體 IDs（包含本次操作者 Bay），已獨立 no-op 返回空 tuple，輸入來源不變。相同設定值但不同 refs 不算連動，不製造新的幾何或 NFB model。
- `manufacturing_api.unlink_receiving_shared_setting_with_affected_ids` 與根包 `ae_engine` 匯出同一 Engine 函式；GUI 只在 affected 非空時儲存候選、標記 Engine ID 及提交 geometry intent；錯誤／no-op 不寫來源也不觸發假提交。測試 `tests/test_issue2517_receiving_unlink_affected_ids_public_api.py` 驗 Root／Facade、既有 unlink 等價、非連續共享群組、no-op／非法來源不變、GUI 真實 port 與 Project Save→Reload。這是 Set/Bay 實體來源參照權威，不新增任何 CUTTING、BEND、FinalScene、DXF 或未認證的製造能力。


## [CURRENT] #2517 Receiving Joint 對齊只標記真正改變的實體 Joint ID（2026-11-07）

- 舊 ReceivingSetBayAdapter.update_joint_alignment 雖經原 Engine update_receiving_joint_alignment 驗證並執行 FRONT／REAR、TOP／BOTTOM，但 GUI 無條件把選中 Joint stable_id 放入 session dirty。當相鄰 Bay 的 D/H 相等導致對齊軸不可編輯、或操作者提交相同值時，Engine 並未更改 Joint，GUI 卻製造「待保存實體」及後續刪除保護假訊號。
- 唯一現有 ae_engine.receiving_layout Owner 新增 update_receiving_joint_alignment_with_affected_ids(layout, *, set_index, joint_index, depth_alignment=None, height_alignment=None)，由 manufacturing_api 和根包 ae_engine 原 callable 公開。先規範來源，復用原 Engine update_receiving_joint_alignment 全部尺寸／相鄰 Bay／合法方向硬閘門，僅比較同一 canonical Joint 交易前後物理 row；回傳 (detached_layout, tuple(changed_joint_stable_id))，相同或不可編輯的軸返回空集合。非法方向／失效 ID 必須拒絕，輸入 Layout 不可更動。
- GUI 只提交操作者方向及目標 joint index，消費 Engine 決定的受影響 ID；有真實變更才更新 layout 與 session dirty，不再由 UI 假定任何點擊都改造 Joint。未觸及 Receiving Bay 包外尺寸、FRONT=+Z／TOP=+Y 3D 座標公式、BEND/CUTTING 或 DXF 製造權限；2D／3D／FinalScene 仍由既有 canonical source 解析。測試核對不可編輯 no-op、重複提交 no-op、真實 Joint ID、非法輸入 failure isolation、Assembly offset 同源及 Project Save→Reload，完整 GitHub exact-SHA regression 尚須驗收。




## [CURRENT] #2517 手動 CornerType 縮圖 canonical CUTTING／BEND 來源只經公開 Engine（2026-11-07）

- 原 `gui_modules/parts/panels/assembly_corner.draw_corner_type_icon` 直接匯入內部 `corner_type_ui.build_corner_type_preview_geometry` 取得真實 EndCap CUTTING／BEND 的語意預覽。這不是 GUI 可再算一份的截角幾何，且不代表出圖准入。
- `manufacturing_api.project_operator_corner_type_preview_geometry` 與根包 `ae_engine` 以相同 callable 身分公開原 `corner_type_ui.build_corner_type_preview_geometry`；直接保留 CornerType legacy C01–C04 正規化、裁切現有 canonical CUTTING 與 BEND 的唯一來源，輸入錯誤由既有 Owner 拒絕，輸入 selection 不變。GUI 只將回傳的 `cut_paths`／`bend_paths` 繪製成縮圖，無第二套加工公式。
- 測試 `tests/test_issue2517_corner_preview_public_engine_api.py` 驗證 root/facade/原 Owner identity、四種現行 CornerType 和 C02 legacy 的原始路徑 parity、真實 GUI delegate 與線數／層分色、不合法輸入不修改來源；原 `tests/test_corner_type_ui.py` 的 CUTTING/BEND 含義維持。完整 2D／3D／DXF Product Regression 與 Windows GUI UAT 仍需各自驗收，#2517 不因縮圖公開就結案。


## [CURRENT] #2517 Receiving 跨套 +/- 連數必須使用同一公開 Engine 候選，不得先切換 GUI 套數（2026-11-07）

- 原 `ReceivingSwitchProjectionAdapter.resize_connections` 由 GUI 自行 `max(1, current+delta)` 決定實體連數，然後先 `adapter.select_set(index+1)` 再 `set_bay_count`。即使 Engine Family 預設／來源校驗失敗或被保存 Bay 刪除確認拒絕，原 Layout 不變但 GUI `selection` 已移到其他 Set；違反同一操作者動作的全有或全無來源／選取語意。單獨 `set_bay_count` 與 `set_set_count` 已經有保留原子候選的 API，不重做其幾何／孔位。
- 新增現有 `ae_engine.receiving_layout` 的 `resize_receiving_operator_connections_by_delta_with_removed_ids(layout, *, set_index, delta)`，由 Engine 嚴查真實零基 Set／整數 delta、沿 canonical Layout 算新連數（最少一連）、委派既有 `resize_receiving_operator_topology_with_removed_ids` 原子確認真實刪除 Set／Bay／Joint ID，回傳 `(detached_candidate, removed_ids, changed)`。No-op 的候選仍 detached 且不遷移 GUI 選取；原非法 Layout、無效增減、Family 預設拒絕不更動輸入。
- `ReceivingSetBayAdapter.resize_connections` 先讀完整 Engine 候選，必要時詢問原保存／dirty 刪除確認，全部合法才更新 layout、protected IDs 與一次性 Set／Bay selection；`ReceivingSwitchProjectionAdapter.resize_connections` 只轉交操作者數字，不自行算連數、也不先選 Set。原絕對連數 API 與其他 GUI 入口相容。這是操作交易與實體身分保護，**不**改 Family W/H/D、NFB、AssemblyJoint、PartSpec、FinalScene、2D／3D／DXF 出圖，也不授予新製造資格。測試 `tests/test_issue2517_receiving_operator_delta_resize_public_api.py` 驗證 Engine parity、合法舊文字操作、跨套取消／Engine failure 不改 Layout/selection/dirty、被刪除真實 IDs、原 UI 傳遞；完整回歸依 GitHub exact-head CI。

## [CURRENT] #2517 Receiving 實體 +套／−套改為公開 Engine Set 數量交易（2026-11-07）

- 舊 ReceivingSwitchProjectionAdapter.add_layer/remove_layer 在 GUI 使用 len(layout["sets"]) +/- 1 直接推導正式物理 Set 數量、最低 Set1 限制，再叫絕對數量 Engine API。這項正式 Set/Bay/Joint 拓樸規則應由 Engine 決定，GUI 只提交 +/- 操作及確認被移除的已保存來源。
- 新增 ae_engine.receiving_layout.adjust_receiving_operator_set_count_with_removed_ids(layout, *, delta)，從 manufacturing_api 與根包 ae_engine 公開同一 callable。完整驗證 canonical layout 與純整數 delta，原子投影 max(1, count+delta) Set1 最小數量，復用原 resize_receiving_operator_topology_with_removed_ids 的正式新 Set 來源、真實 removed Set/Bay/Joint IDs 與不可重用的盤名序號；回傳 detached (layout, removed_ids, changed)，沒有變化不留假 dirty，原來源不改。
- GUI ReceivingSetBayAdapter.apply_set_delta 先取 Engine 完整候選及真實 removed IDs，沿既有 persisted／session dirty 刪除確認；確認後才一次提交 layout、protected IDs、現在 selection。原 ReceivingSwitchProjectionAdapter.add_layer/remove_layer 只委派這個動作，沒有第二套業務件數算法。刪除拒絕或 Engine 失敗不影響選取、保存狀態或原始工單。
- 同時期 PR #3033 正在處理跨 Set +/- Bay，這批 Set 專項不實作第二份 Bay delta；現有 Bay 改動與絕對 resize 原子契約不受此變更影響。無新增 Family W/H/D、NFB 孔、PartSpec／FinalScene 或 DXF 製造資格。驗收使用 Engine Set resize 實體 ID 對照、盤名單調遞增、no-op、拒絕保護、GUI 真按鈕接線與 Save→Reload，再由 exact-SHA GitHub CI 完整回歸。



## [CURRENT] #2517 封頭／封尾 FW 操作候選對來源有效性 fail closed（2026-11-07）

- 原公開 `operator_endcap_fw_override` 仍透過 `_num(value)` 將非法操作者 FW 預設為 0，對 `NaN`／`Inf` 也未阻擋；`operator_endcap_fw_follow` 對字串 `"false"` 使用 `bool(...)` 造成錯誤跟隨，且兩者都在已確認 Settings box-FW 欄位缺失／損壞時套入預設 25。這些都可能污染 Head/Tail 的正式四態製造來源，不符合操作者 FW＝包外尺寸的 CURRENT 07。
- 由原 `operator_endcap_settings_transactions` 公開 API owner 先驗證 input snapshot／settings／existing EndCap FW state 是 Mapping；由原 Engine `normalize_operator_source_dimension(field="fw")` 要求箱身 FW 與輸入 Head/Tail FW 為有限正數、拒絕 bool 和非法字串；由原 Engine `normalize_operator_settings_boolean` 正確解析 follow 開關。全部在 detached state 完成，成功仍委派原 `endcap_factory_fold.commit_endcap_fw`／`set_endcap_fw_follow` 的四態語意，不新增截角、BEND、CUTTING 或 DXF 公式。
- Fold Designer 封頭／封尾 GUI `on_endcap_fw_value_selected` 只傳原操作員輸入，由 Engine 決定是否接受，非法輸入不觸發 state commit 或 linked geometry refresh。驗收對照兩 Family 的原 Engine 狀態、非法輸入 source isolation、legacy 未載入四態、直接 GUI event、真正 .p6fold Save→Reload、2D/3D/DXF canonical Product Regression；完整驗收及 Windows UAT 另依實證，不以本 API 存在推論 #2517 結案。


## [CURRENT] #2517 Receiving 實體底板型式選項必須取自公開 Engine（2026-11-07）

- 原 `phase6_settings_panel_owned_render._render_owned_receiving_base_plate` 由 GUI 事件內直接匯入私有 `sheetmetal_part_adapters.RECEIVING_BASE_PATTERN_LEFT/CENTER/RIGHT`，然後自行建立三種實體板件的選型值。這些是底板 `pattern` 製造來源識別，不是 GUI 可定義的新物理型式。
- 原 Engine 唯一製造 owner `sheetmetal_part_adapters` 新增只讀 `project_operator_receiving_base_plate_pattern_choices()`，在**原三個 pattern 常數**的正式 LEFT／CENTER／RIGHT 順序返回 immutable `(role, pattern_id)` tuples；`manufacturing_api` 與根包 `ae_engine` 公開**同一 callable**。GUI 只對應中文顯示標籤與操作選取，不再 import 內部幾何模組、也不製造 pattern ID。
- 實體底板套用／取消、真實 EAR 孔及面積來源仍走既有 `commit_operator_receiving_base_plate_settings`／`validate_receiving_base_plate_settings`；此新 API 不認證任何尚未提交的板件來源，不變更 shrink、BEND、CUTTING、DXF 及 2D／3D 正式幾何。驗收 `tests/test_issue2517_receiving_base_plate_pattern_choices_public_api.py` 對照 owner pattern 集合、GUI 真實函式委派、合法來源原驗證與輸入不變；仍需 exact SHA GitHub 回歸與 Windows UAT。

## [CURRENT] #2517 NFB 品牌交易須回傳受影響的真實 Set／Bay dirty IDs（2026-11-07）

- 原 Receiving GUI 的 `set_brand`／`set_global_brand` 雖然使用 Engine 原子 Parent Brand 更新，卻沒有把改品牌的實體 Set 與各繼承品牌 Bay 記入 session dirty。未保存的來源在縮減 Bay／Set 時可能略過刪除保護；Switch GUI 還自己比較前後品牌來推測變更，重複了 Engine 的權威狀態。
- 在唯一 `receiving_nfb_brand_transition` Owner 新增 `update_receiving_one_set_nfb_parent_brand_with_affected_ids` 和 `update_receiving_all_set_nfb_parent_brand_with_affected_ids`，沿用原公開 Brand Transaction 完整來源驗證及不可逆 CONFIRMED X 失效處理，回傳 `(detached_layout, changed, affected_stable_ids)`。後者只列實際改變品牌的 Set 與旗下全部實體 Bay 的 canonical 身分；無變更則空 tuple，非法來源無輸出／不寫回。原舊二元回傳 API 完全相容；`manufacturing_api` 與根包公開同一 Engine callable。
- GUI 只消費 Engine 回傳的 affected IDs 更新 dirty，且 Switch 操作直接取 Engine changed，禁止自行逐 Bay 推斷孔位、來源或狀態。此為來源／刪除保護 API，不新產生 NFB 世界 X、CUTTING、FinalScene、DXF 或 MFG-2 資格。新增 `tests/test_issue2517_receiving_brand_affected_ids_public_api.py` 與原 NFB 品牌操作測試覆蓋新版 headless／GUI 同源、非法來源失敗不變、no-op、未保存的實體 Bay／Set 刪除保護；完整回歸由 GitHub exact-head CI 驗證。

## [CURRENT] #2517 Box FW 接管 Head/Tail 的兩個 GUI 寫入入口統一公開 Engine 交易（2026-11-07）

- Phase6 Settings Controller 的 `commit_editor_fw_takeover` 與 Fold Designer `settings_application_project_ui_values` 原先先在 GUI 呼叫 `float(value)`，再直接套用舊式 `commit_box_fw` 到 live `_phase6_endcap_fw_state`。原 Engine 遺留函式是就地寫入，沒有物理有限正數硬閘門；布林、NaN／Inf、零或負值可能經 GUI 先轉型而污染 Head/Tail FW，已有 malformed Tail 的來源也可能在 Head 被修改後才拋錯。
- 新公開 `manufacturing_api.commit_operator_box_fw_takeover(state, value)`（根包 `ae_engine` 同一 callable）由原 `endcap_factory_fold` 負責，先用既有 `normalize_operator_source_dimension(field="fw")` 核實操作員輸入的正值、有限數字及 bool 拒絕，再把原 `commit_box_fw` 在完整 detached state 上預先跑通，最後由同一原 owner 就地提交；保持 Head/Tail live nested dict 身分、FOLLOW_BODY 語意與原有合法輸出完全相同。舊 Engine 低階函式供原有合法相容呼叫繼續保留，不使 GUI 擁有任何新 FW 公式。
- 兩個 GUI 入口只傳原操作員 FW 及共用狀態給公開 API，無 GUI 先做 `float` 的物理來源轉型；不合法來源不可改變 mode、Head、Tail 或 input snapshot。定向測試涵蓋兩箱型、Engine root/facade/原 owner parity、全套非法值／晚期壞 Tail、同物件 identity、Controller 與 Shell GUI 接線、實體 EndCap FW 投影及 Save→Reload；2D／3D／DXF Product Regression 須驗 exact SHA。此提交不宣稱 Windows R5 或整箱 NC 已驗收。




## [CURRENT] #2517 主 GUI／Fold Designer 箱身 FW 即時修改統一由公開 Engine 四態投影（2026-11-07）

- 原 `gui_modules/application/state_sync.on_main_setting_var_changed` 與 `gui_modules/application/lifecycle._apply_fold_designer_live_settings` 在操作者改箱身邊框寬度 FW 時，仍由 GUI 對封頭／封尾 `endcap_fw_state.setdefault` 自行依 `follow_box` 更新值。這條路徑可能保留已失效的 FOLLOW_HEAD／FOLLOW_TAIL／INDEPENDENT 物理 ownership；原主 GUI 另有明確 `on_fw_selected("z")` 使用 Engine `commit_box_fw` 的一致語意。
- 新公開 `manufacturing_api.project_operator_box_fw_live_state`（`ae_engine` 根包同函式）先以原 Engine `normalize_operator_source_dimension(field="fw")` 驗證變更前後包外 FW，複製已保存四態來源，**只有 FW 數值實際變動**才委派原 `endcap_factory_fold.commit_box_fw`，讓 BoxBody 重新控制 Head／Tail；相同 FW 的同步回放不得意外重置既有封頭／封尾獨立設定。非法 bool、零、負數、NaN／Inf 或非 Mapping state 一律拒絕且不修改來源。這是既有四態製造來源轉移，沒有另建 FW 補償公式。
- 主 GUI 與 Fold Designer 的 live commit 均先取得 detached Engine 候選，在既有 `SettingsService.update` 成功且 FW 實際被接受變更後才替換來源並同步 UI。Fold Designer 單次多欄送來非法 FW 時，不阻擋其他合法 Settings 更新。原 `.p6fold` EndCap FW 四態持續由 `normalize_endcap_fw_state`／`resolve_endcap_fw` 重開；單筆有效操作在 GUI／headless Engine 得到相同 Head/Tail FW。現有幾何、2D／3D、DXF、CUTTING 和權限不變；本批需要 exact HEAD Product Regression、GUI API Gate 和 Windows GUI 人工驗收，並不等於 #2517 全面完成。




## [CURRENT] #2517 FinalScene 實體折後包外量測統一公開 Engine（2026-11-07）

- 原 `phase6_final_scene_projection._phase6_folded_outside_envelope` 為 FinalScene 2D／3D 操作量測的 GUI 相容入口，直接匯入 `ae_engine.display_dimensions.folded_outside_envelope`。該內部 owner 根據**已成形實體三角網格與板厚**回傳 dimensions/world bounds；這是物理尺寸 readback，不可由 GUI 再算一套，也不得回寫原 Fold material `len`、BEND 或正式 CUTTING。
- 公開 `manufacturing_api.project_operator_folded_outside_envelope` 與根包 `ae_engine.project_operator_folded_outside_envelope` 指向原本**同一個 `display_dimensions.folded_outside_envelope` callable**。GUI 只能送 mesh 和原始 T；原封不動沿用有限 world XYZ、完整三角面與合法板厚 fail-closed gate、法向厚度外擴及空網格 `None` 語意。此項為來源量測 API，沒有新尺寸公式或製造認證。
- 驗收 `tests/test_issue2517_final_scene_folded_envelope_public_api.py` 核對公開 identity、真正 world 三角網格尺寸與 FinalScene GUI 一致、無效 mesh/T 不修改來源及既有 2D/3D finished dimensions readback。完整 GitHub exact-HEAD Product Regression 必須通過，Windows UAT 與 #2517 不因此結案。

## [CURRENT] #2517 一般實體板件 Hole Editor 孔型保存前須經公開 Engine 全量驗證（2026-11-07）

- 原 `gui_modules/application/physical_part_hole_editor.py::open_workspace_sheet_editor.commit` 在獲得引擎核准的 physical sheet editor context 後，仍直接把可變 Hole Editor Feature 草稿 `stash_features` 寫入 workspace，缺少提交**當刻**對整批已編輯孔位的實際物料面重驗；無效 Feature 可能先存成專案來源，直到日後 2D／3D／DXF 再拒絕。
- 新增 `manufacturing_api.propose_operator_physical_sheet_hole_features(part_key, context, features)`（根包 `ae_engine` 同一 callable）到原 `physical_sheet_editor_context` owner。Engine 的 `PhysicalSheetEditorContext` 保留物理 `part_key` 身分；先驗證 context 真實角色／Features 完整清單，透過原 `legacy_hole_to_feature` 及 `resolve_surface_features` 對全部物料面孔位、形狀輪廓進行原算法檢查。返回 detached、原格式（legacy dict／typed Feature）的完整候選，GUI 只有驗證成功才寫入 workspace；非法資料、錯誤板件、越界一次拒絕，不先寫入任何孔位。
- 這不是新的孔位公式或製造認證，不修改 `with_physical_sheet_features`、CustomFold PartSpec、CUTTING／BEND／MARKING／DXF Writer。此入口只處理已開啟的實體板件 Hole Editor 提交源，後續 canonical 2D／3D／DXF、Save→Reload、來源授權仍按原 Engine Gate；不能以候選有效取代正式 DXF 加工驗證。測試 `tests/test_issue2517_physical_sheet_hole_commit_public_api.py` 覆蓋 Engine／GUI 同源、兩種 CustomFold 軸、legacy/typed 特徵、非法／越界不改來源和既有 context API。

## [CURRENT] #2517 Receiving Set/Bay 縮減候選及被移除實體 ID 由公開 Engine 單次交易（2026-11-07）

- 原 `ReceivingSetBayAdapter.set_bay_count/set_set_count` 在取得預先刪除 ID 並確認後，**先**從 GUI 已保存 ID 與 session dirty 集合刪除，**後**才做 Engine Resize。若物理 Layout／Family 新 Bay 預設錯誤使 Engine 拒絕，正式 Layout 未改但已失去重做時的刪除保護。
- 公開 `manufacturing_api.resize_receiving_operator_topology_with_removed_ids(layout, *, set_index, bay_count)` 或 `(..., *, set_count)` 直接輸出 `(detached_layout, tuple(removed_physical_ids))`；根包 `ae_engine` 同一函式。唯一 `receiving_layout` Engine owner 先完成原 Family 新 Bay 預設／Set resize，再以原 `receiving_destructive_tail_ids` 與前後 canonical Set/Bay/Joint stable ID 差集交叉確認。兩種操作混用、非法來源或任何不一致全數拒絕，輸入 Layout 不動。
- GUI 僅在**完整 Engine 候選成功後**提示操作者批准移除；批准才一次套用 candidate、保護集合與 selection。取消／Engine 拒絕不得失去任何 protected ID。原 `resize_receiving_bays_with_family_defaults`、`receiving_destructive_tail_ids` 與 `resize_receiving_sets` 維持相容。新增 `tests/test_issue2517_receiving_operator_topology_atomic_api.py` 覆蓋來源不動、刪除真實 physical IDs、不同尺寸、新增及拒絕／失敗之 UI 原子性；無新幾何、NC 或 DXF 製造資格。

## [CURRENT] #2517 數量模式版本新增／刪除／選取／件數只經公開 Engine（2026-11-07）

- 原 `gui_modules/application/quantity_version_ports.py::quantity_ports` 四個按鈕動作直接呼叫 live `QuantityModel.select/add_version/delete_selected/set_piece_count`，讓 GUI 而不是 Engine 提交數量版本身分與件數。
- `manufacturing_api.commit_operator_quantity_version_action(snapshot, quantity_model, *, action, version_id, piece_count=None, confirmed=False)`（根包 `ae_engine` 同一 callable）要求 Quantity 模式、live `QuantityModel` 與一致版本來源；在 detached model 執行既有四個操作，再檢查來源漂移。新增／刪除／件數變更沿用全部版本既有 finished-face 孔位檢查，錯誤或通知失敗不留下部分提交。選取只是導覽／修復入口，舊非法孔位不能阻擋進入編輯。
- GUI 只提交 action、ID、件數或刪除確認，保留原工作區 `changed()` 投影；版本 ID、NFB 來源複製、孔位及件數規則仍屬 Engine。無第二套 Set/Bay／製造幾何／DXF 授權。必須核對兩種 Family、非法輸入隔離、callback rollback、GUI port、Save→Reload 與 GitHub exact-SHA 產品回歸。



## [CURRENT] #2517 Receiving Head/Tail 候選數量草稿增減只由公開 Engine 管理（2026-11-07）

- 原 `ReceivingQuantityAllocationUI._count` 在 GUI 自行取草稿數量並以 `max(0, current + delta)` 決定 Head/Tail 候選版本的下限，繞過統一的 Engine 編輯來源判準。此規則不應留在操作畫面。
- 新增 `manufacturing_api.adjust_receiving_candidate_draft_quantity(draft, role, version_id, delta)`（根包 `ae_engine` 同 callable），直接在原 `receiving_quantity_allocation.AllocationDraft` owner 僅接受真實 draft、合法 role／版本、恰好單步 +1 或 -1、已存在的非負整數數量。Engine 對零下限處理，並復用既有 `set_quantity` 清除過期 Bay 指派、返回第一步；非法輸入或零時減一不更動任何草稿狀態。
- GUI 只送操作者增減事件，既有確認配置仍走原公開 `validate_receiving_candidate_quantity_preview` 與 `apply_receiving_endcap_quantity_configuration` 的全 Bay 驗證／原子提交。這是未提交候選 draft 的編輯 API，不更改已保存 Bay、PartSpec、FinalScene、CUTTING、2D／3D／DXF 或製造資格。負向 source isolation／GUI/headless API 一致性由 `tests/test_issue2517_receiving_allocation_draft_count_public_api.py` 檢查，完整回歸仍交 exact-SHA GitHub Actions。

## [CURRENT] #2517 數量模式封頭／封尾孔型版本提交只經公開 Engine（2026-11-07）

- 原 `gui_modules/application/quantity_version_ports.py::holes.commit` 將編輯中的孔清單複製進 GUI 自建 `QuantityModel`，再由 GUI 將 `candidate["quantity"]` 覆寫、呼叫 `require_valid_operator_quantity_features`，最後另一次修改 live Model。這使版本身分、完整孔型合法性與提交順序被 UI 分兩段主導，模型無通知 rollback 保證。
- `manufacturing_api.commit_operator_quantity_version_holes(snapshot, quantity_model, *, version_id, role, features)`（根包 `ae_engine` 同一 callable）在既有 `receiving_quantity_box` Engine owner 內先要求 Quantity 模式、真實 live QuantityModel 與完整一致版本來源；在 detached 版本中以捕捉的 version_id 設定 Head/Tail Features，再對**全部版本**重用原 `require_valid_quantity_features` 成品面孔位檢查，完全通過才提交到 live Model。刪除的版本、錯誤 role／非法特徵、來源版本漂移在提交前拒絕；通知失敗回滾原 Model，不重複通知，不更動 detached input snapshot。
- GUI 只收編輯器操作者 Features、captured version ID，呼叫公開 API 後沿原 `changed()` 傳播；僅當實際修改且當前選中版本相同才觸發 2D geometry refresh，跨版本 modeless editor 的 inactive 修改不多算一次幾何計算。既有金庫型／受電箱 Quantity 都走同一入口，沒有新增孔位公式、實體 Bay、出圖或 NC 製造資格。測試覆蓋 root/facade、非法來源與版號不修改、跨版本保存、callback rollback、GUI 真實 port 及 Save→Reload；完整 2D／3D／DXF exact-SHA 回歸仍需 GitHub Actions 驗證。



## [CURRENT] #2517 Registry 候選保存／認證的 GUI 私有 Engine 匯入收斂為公開 API（2026-11-07）

- Fold Designer Registry 的公式預檢、九組條件矩陣、候選保存及驗證後升級原由 `gui_modules/application/fold_designer_composition_registry_edges.py` 在事件函式內直接匯入 `ae_engine.certified_relief_registry`，包含私有 `_validate_editable_rule_record` 與兩個會寫入 Registry 的 backend。
- `manufacturing_api` 與 `ae_engine` 根包現公開 `validate_operator_relief_registry_rule_record`、`evaluate_operator_relief_registry_formula_record`、`save_operator_relief_registry_candidate`、`promote_operator_relief_registry_candidate`，**全部為原 Engine callable 的 identity-preserving aliases**，沿用原候選隔離、公式白名單、回歸證據與 candidate-specific 3D 證據、版次認證、原子 JSON 寫入規則。GUI 原 Controller 僅安排時序、傳入操作者資料和可見狀態，不再引用 Registry 私有實作。無新截角公式／Policy／幾何／DXF 輸出。
- 驗收 `tests/test_issue2517_relief_registry_candidate_public_api.py` 核對公開 callable identity、原候選的真實檔案存取、非法公式及不具完整證據無候選／認證寫入、GUI 實際委派函式；最終 canonical Product Regression 在 GitHub Actions 上核對。#2517 與 Windows UAT 不因此結案。

## [CURRENT] #2517 單只尺寸 W/H/D＋數量版本件數由公開 Engine 完整交易（2026-11-07）

- `fold_designer_composition_receiving` 的單只尺寸設定舊路徑：GUI 直接引入 `phase6_quantity_model.QuantityModel`，自己讀選中版本數量，接受操作者 W/H/D/件數後自行 `set_piece_count`、`update_common_box`、覆寫 `candidate["quantity"]`，再做 `require_valid_operator_quantity_features`。這些版本與實體尺寸關聯的結果是製造來源，不能讓 GUI 擁有跨兩個 Engine 入口的交易順序。
- 新正式 `manufacturing_api.project_operator_receiving_quantity_size_count(snapshot)` 只從 Receiving Quantity 的 `receiving_quantity_box` 和 `QuantityModel` 讀取目前 selected 件數、所有版本總件數與物理 W/H/D；`manufacturing_api.apply_operator_receiving_quantity_size_count(snapshot, *, width, height, depth, count)` 以同一來源驗證 Family／模式／完整版本／共用箱體／真實 T，使用原 `positive_piece_count` 更新 detached selected 版本、原 `update_common_box` 更新物理 W/H/D，再 `require_valid_quantity_features` 檢查所有版本的封頭尾 CUTTING 孔是否仍在實體 finished-face 之內。未全部成功就不返回可提交的候選；輸入 snapshot 不改動。根包 `ae_engine` 亦公開同一 Engine callable。
- GUI 僅送操作者四個欄位並用既有 `_apply_mode_snapshot` 刷新工作區，沒有第二份 QuantityModel 操作、物理計算或新製造預設。Set/Bay、NFB CSV、共同箱體的保存權威不變；非 selected 版本件數不可被目前編輯污染，真實 W 變更時 NFB datum recheck 與孔位越界仍服從既有 Engine Policy，並非輸入成功就獲 DXF 放行。
- Headless 對照原 Engine `QuantityModel + update_common_box + require_valid_quantity_features`、非法件數/Family/模式/W/H/D/T/Quantity/Box 不改來源、選中與其他版本獨立、Save→Reload 及相關 2D/3D/DXF exact-SHA Product Regression 全部須驗證。


## [CURRENT] #2517 Quantity 實體底板共用箱體的 W/T 與焊耳孔由公開 Engine 一次投影（2026-11-07）

- Fold Designer 原 `receiving_base_plate_for_current_mode` 在 Quantity（單只／數量模式）分支先以 GUI 的 `_settings_values` 暫時驗底板，再以另一個 `manufacturing_api.update_common_box` 寫入 `receiving_quantity_box`。其中 GUI Settings W/H/D 是開新專案用的**預設種子**，可與當前保存的共用箱體 W 不同；兩段式驗證會以錯誤 W 檢查焊接 EAR 孔，並把尚未綁定此實體箱寬的 config 當成有效來源。
- 新正式 `manufacturing_api.project_operator_receiving_quantity_base_plate_settings(snapshot, config)`，亦從 `ae_engine` 根包公開同一 callable。Engine 先要求正確 Receiving／Quantity Family、明確 `receiving_quantity_box` 與真實 `QuantityModel`、明確有限正數 T，再依已保存共用箱體重投影 W/H/D／單 Bay 假別名；重用原 `validate_receiving_base_plate_settings` 的原始 CENTER／LEFT／RIGHT 實體板、真實 EAR 孔及原製造幾何，以共用箱體 W、來源 T 驗證，且只用 validated accepted config 經 `update_common_box` 生成完整 detached 來源。
- GUI 僅交目前模式 snapshot 和操作者 config，消費 Engine 回傳結果供原 `_apply_mode_snapshot` 同步畫面；禁止把 GUI Settings default W 當成 Quantity 實體箱寬。未保存 Quantity／共用箱體、非法 Family／T／EAR 孔距、錯誤實體板型，均不得改動呼叫者來源。非 Quantity 單板仍走已存在的公開 Engine 原子提交，無新製造公式／DXF Writer。
- 需核對 headless API 與原 Engine 同源，顯式取消、舊 root 寬度和 Settings default 漂移、負向拒絕及 Quantity Save→Reload；這個 API 成功不代表 FinalScene／DXF MFG-2 加工放行，仍需 exact-SHA Product Regression 及適用時的 DXF Save→Reload。


## [CURRENT] #2517 同源分組另存 CHECK-only debug 檢查圖及真實孔型 Q（2026-11-07）

- 受電箱的 `emit_debug=True` 僅允許透過已通過逐片物理 FinalScene 與原始 DXF/CSV source guard 的 `manufacturing_api.export_grouped_receiving_multibay_dxf` 既有交易。加入同一 staged 原子提交的一張 `YYYYMMDDHHmm_p1~p16debug.dxf`；所有內容在 CHECK 層並標明 DEBUG ONLY／NOT FOR NC，不可當作 CUTTING/BEND 正式加工圖，不推導新工藝或形狀；未要求 debug 時原本所有 3 種分組交付數量不變。
- debug 用原實體板件的 DrawingScene 平移排版：左側／後面／右側、後板上方封頭與下方封尾、上門／下門、上框、左框／內門／右框、下框／中隔、最下底板，每盤顯示盤名，最上方依同**角色加上完整 CUTTING／BEND／MARKING／BLIND_HOLE 幾何局部座標**簽章計 Q。不同側板角色、相同尺寸但任何一顆孔／加工層不同都不合計；來源的物理出圖與鎖孔不改。
- 原基準 `基準檔/受電箱/左側板.dxf` 與 `右側板.dxf` 的 9 個圓特徵本就不同：左 8 CUTTING + 1 BLIND_HOLE，右 6 CUTTING + 2 MARKING + 1 BLIND_HOLE。現有 `receiving_bay_joint_face_features` 僅對相鄰 Joint 兩個實體參與面投影相鎖孔；最外側面不得繼承相鎖孔。這是來源差異／回歸與 debug 可視化，不代表未知現場 CNC 錯孔已修復，必須再取得缺陷的物理孔位比較證據，不准把 Q 合併當成幾何修補。
- 測試包含真 DXF Save→Reload、debug 全 CHECK audit、原始 FinalScene 完全不變、來源缺口／非法旗標拒絕、實體側板孔層分組與 Join 邊界 3 Bay。Windows 現場原圖與整箱 MFG-2／NC 需獨立驗收。





## [CURRENT] #2517 CornerType INI 保存／重開語意由公開 Engine 管理（2026-11-07）

- 主 GUI `phase6_settings_center.load_corner_defaults_from_ini/save_corner_defaults_to_ini` 原在讀寫 `config.ini` 時自行組出每個 CornerType 的旋轉、CROSS 模式、方向和 `*_t` 製造來源欄位。這些來源會由 EndCap/其他 PartSpec 和 FinalScene 消費，不應在 GUI 保留第二份物理轉換邏輯。
- 公開 `manufacturing_api.project_operator_corner_ini_load_section`、`project_operator_corner_ini_save_options`（`ae_engine` 根包同 callable）由原 `corner_state_transactions` owner 投影單一 INI section，不讀寫檔案、不依賴 Tk。C02 舊式旋轉、非 C02 旋轉歸零、成對布林、有限數值的 skip/reject、沒有參數時清除舊 option，延用原行為；非法來源須在存檔前拒絕、不得改寫既有 INI。
- GUI 只做 `ConfigParser` 檔案傳輸與已保存 part section 的選擇；Engine 返回 detached 欄位映射。測試覆蓋舊 Corner 類型、完整 INI Save→Reload、非 Corner section 保持、原始來源不變與非法資料失敗隔離。不新增截角幾何、Relief、CUTTING、DXF 製造公式或新 Family 加工資格；受影響產品回歸依 GitHub exact-SHA 驗收。






## [CURRENT] #2517 主 GUI 專案讀回與 Legacy 基準箱型身份全面經公開 Engine（2026-11-07）

- `gui_modules/application/lifecycle.py::_current_cabinet_type_name` 原在 GUI 自行調用私有 Family Registry 及自訂型號正規化，決定已註冊箱型／舊版未知基準目錄的 Legacy Family；`_apply_phase6_project_snapshot` 與 Live FoldDesigner 更新也直接調用私有自訂型號 codec。
- 現由公開 Engine `manufacturing_api.operator_resolve_legacy_baseline_manufacturing_family` 封裝**現有** `normalize_custom_model_name`＋`resolve_cabinet_type` 的 Family 身分選路，連同原有「未註冊或自訂目錄使用舊金庫型基準」相容語意一起移出 GUI；已註冊但未實作的 `RO` 仍保留 RO 身分，不能偽裝金庫型進製造。兩個 Project／3D 保存模型讀取直接走既有 `operator_normalize_custom_model_name`。
- 此 API 只投影既有 Legacy Family 身分，**不是**未知型號製造許可；Family Registry、Factory Policy、未實作 Family 的 fail-closed 製造閘門原封不動。新測試覆蓋 aliases、舊自訂名、未實作 Family、GUI 實際呼叫與非法公開 Engine 拒絕不改來源；無新板件公式、幾何、2D／3D／DXF exporter。#2517 全面驗收與 Windows R5 UAT 仍 OPEN。

## [CURRENT] #2517 主 GUI 已保存手動截角快照完整還原只由公開 Engine 原子候選（2026-11-07）

- 原 `gui_modules/application/lifecycle.py::_apply_manual_corner_snapshot` 在 Project／Family runtime 恢復時由 GUI 逐角解析 raw `CornerTypeSelection` 並原地寫入 `manual_corner_state`／`manual_corner_pair_same`，再用已認證 Family 修正；後段來源或 Registry 錯誤可能留下前段已寫入的實體截角。
- 唯一 Engine typed Corner owner `corner_type_ui.propose_operator_saved_manual_corner_snapshot`（透過 `manufacturing_api` 與根包公開同一 callable）以深複本保留舊專案 `dict`／舊字串 CornerType ID、逐角非法值忽略、配對 bool、同類型人工參數、已認證 Family 不重設等原語意；最後呼叫原 `propose_operator_known_model_corner_draft`，完整成功才返回候選。無效整份來源、不可遍歷的晚期部分與 Registry 錯誤拒絕，呼叫者保存狀態不動。
- GUI 僅接收完整候選並在相同巢狀 dict 身分下同步，不再持有 decode 與先寫後驗的製造來源邏輯。Save→Reload／已知與自訂 Family／舊資料相容與非法來源隔離須通過 exact SHA full regression；無新 CUTTING、Relief/Corner 公式、2D／3D／DXF exporter，Windows R5 UAT 和 #2517 全面驗收仍待完成。

## [CURRENT] #2517 Quantity 內門 NFB 確定全部必須同時提交版本與保存來源（2026-11-07）

- 正式的單只／Quantity 受電箱內門「確定全部」，包含原 Fold Designer 設定入口及 3D 直接雙擊內門，原先雖由 `manufacturing_api.preview_quantity_inner_door_confirm` 先驗證 Factory Box 和 NFB CSV 實體來源，但接著在 GUI 分別 `quantity.set_version_nfb_config` 與 `_phase6_input_snapshot.clear/update`。任何中途失敗都有可能留下版本已提交、專案尚未對應的半交易；GUI 不可決定兩份製造來源的提交順序。
- 新公開 `manufacturing_api.commit_receiving_quantity_inner_door_confirm`（`ae_engine` 根包相同 callable）重用原 Engine 全量 preview；以目前 QuantityModel 的 selected version 重新推導應提交的版本快照，核對正式 projected `quantity` 身分一致後，才在同一 Engine 函式內提交專案快照及原 QuantityModel NFB。原 `QuantityModel` 僅新增 Engine 內部無通知 rollback，若版本 on_change 中途失敗，兩份原始來源完整還原；非法 Family／Box／型號、非 CSV CUTTING、扭曲輪廓、錯誤模式、版本漂移都 fail closed。
- GUI 的兩個「確定全部」入口只消費此交易結果並同步 workspace／畫面快取；既有 `include_missing_heights=True` 的 3D 直接進入語意與單只設定不強制清除舊層高的語意維持。Native-only Feature 確認不得虛構 NFB submitted；CSV 模型、原始 source SHA、physical CUTTING 及 `manual_x_state=UNVERIFIED_BASIS` 仍由既有 Engine 驗證，不因提交成功而給予加工放行。
- 正反測試需覆蓋實際雙層 CSV Source、選中版本／其他版本不互借、原快照不被 preview 寫入、非法輸入不改來源、變更通知失敗無第二次通知且同時 rollback、兩條 GUI 路由無來源寫入；完整 Product／2D／3D／DXF Save→Reload 以本批 exact-HEAD CI 驗收。這個來源提交 API 不是全盤 MFG-2 認證或 #2517 整體完工。


## [CURRENT] #2517 使用者最新確認：合併 DXF 母盤完整盤名＋底線（2026-11-07）

- 2026-11-07 使用者明確修正先前各群各取局部盤號規則：所有正式合圖檔案**共同使用整份已確認母盤 Set/Bay 的完整盤名跨度**，不是各組 subset 範圍。台灣時間 12 碼之後要有**一個底線**。例如 `202611071258_p1~p16全部.dxf`、`202611071258_p1~p16第1套.dxf`、`202611071258_p1~p16第2套.dxf`、`202611071258_p1~p16頭尾盤.dxf`、`202611071258_p1~p16中間盤.dxf`（第3套同規則）。分組內容的 Bay 身分和實際數量不變；僅名字共同引用母盤總範圍。自訂盤名仍保留真實資料，不得偽造連續 P 身分；其他未確認幾何不得因命名放行。

## [CURRENT] #2517 受電箱合併加工 DXF 日期時間與盤名範圍命名（2026-11-07）

- 使用者確認正式輸出 DXF 的檔名要包含**台灣日期時間 YYYYMMDDHHmm + Engine 已保存盤名範圍 + 合併模式**，例如 202611071258p1~p16全部.dxf。這是原 DXF Save→Reload 核心製造交易的檔案命名，不得由 CADSplit 自行改名或重寫檔內 CUTTING/BEND。
- Engine `receiving_dxf_groups.commit_verified_receiving_groups` 在一次多盤原子交易的開始取**同一個台灣分鐘時間**；`plan_receiving_grouped_dxf(layout, mode, file_stamp=...)` 用原 canonical Set/Bay 實體盤名推導每個群組的檔名；無 file_stamp 的既有唯讀分組計畫回傳未加日期的標準分組名稱，維持既存分組 API 相容。每套或頭尾／中間盤仍依該群實際參與的盤位，不從母圖名稱或文字預覽猜數量。
- 標準 P 數字盤名按當群最小至最大編號命名（例如 p1~p16）；自訂盤名保持實際已保存標籤並依原規範檔名檢查，無效時間與過長檔名須在 Engine 提交前 fail closed。DXF 的幾何、NFB 原生孔位、成品／組裝 Topology、分組資格、來源 guard、完整重開與原子 rollback 不得因檔名改變。
- 使用者另要求**獨立 debug 排列／同板同孔統計 DXF** 與**修正左右側板相鎖孔源頭**；此為相互關聯但未因改名就獲認證的獨立驗收範圍，不能把既有固定命名的 CADSplit 測試當成新版本實機驗收。




## [CURRENT] #2517 Fold Designer 快照的折邊／門縫預設值改由公開 Engine 投影（2026-11-07）

- 主 GUI `fold_designer_snapshot_projection._snapshot_base_state` 原在準備保存快照時直接讀 `ae.zl1_def` 等 14 類 Fold／Gap 常數，並在指示燈折邊讀 `ae.indicator_*_fold_def` 伴隨 GUI 硬編 `49.0`／`19.0`。這些設定會寫入 persisted source 並由原 Engine PartSpec／FinalScene 消費；GUI 不應複製預設製造數值。
- `manufacturing_api.project_operator_fold_designer_snapshot_numeric_defaults`（`ae_engine` 根包同公開 callable）直接重用 Engine `operator_fold_designer_numeric_source._legacy_defaults` 的現行執行期來源，加上原 UI 舊式底板收縮／折邊和指示燈盒相容預設；所有預設在公開 Engine 以有限數值守衛，`nan` 等非法執行期來源 fail closed。此投影**完全不包含 W/H/D/T/FW**；原 GUI 的 W/H/D/T/FW 必須由操作者實際輸入經 `normalize_operator_source_dimension` 驗證，不能使用任何 Engine 常數填補。
- GUI 只將原有數值控件與 Engine 當下回傳的完整預設值配對，保留舊表單空缺時的呈現語意及 Settings／INI 其他流程；GUI 不增 Formula、成品尺寸推導或 FinalScene，且不改現有 `load_factory_defaults_from_ae` UI Schema 相容呼叫。Headless 測試核對兩 Family 共用的原執行期 defaults、動態更新、非法預設拒絕、root/facade API 同源、GUI 不再私讀製造數值以及原物理 W/H/D/T/FW fail closed；完整 2D／3D／DXF／Save→Reload 仍交 exact-SHA 回歸。


## [CURRENT] #2517 主 GUI 多門格實體 Feature 讀回只透過公開 Engine（2026-11-07）

- 原 `gui_modules/application/lifecycle.py` 的 `_apply_phase6_project_snapshot` 與 `_apply_fold_designer_live_snapshot` 在重開正式專案、同步 Fold Designer 實體門板時直接呼叫私有 `sheetmetal_part_adapters.door_part_features_to_layout_feature_map`，將已保存的 `door_cN_rN` 孔位來源映回 `col:row` 的主 GUI 2D 門格編輯儲存。這是實體來源 ID 轉換，不得由 GUI 另造規則。
- `manufacturing_api.project_operator_door_layout_cell_features_from_parts(columns, part_features)` 與根包 `ae_engine` 都公開**原 Engine `door_part_features_to_layout_feature_map` 的同一 callable**，保留一基實體門板、零基操作格、原始孔位 List 與空格 readback 的既有語意。兩個主 GUI 還原入口只委派此公開 API，未知部件不當作合法 Door、非法門格由原 Engine fail closed，不修改輸入來源。
- 本次沒有增補 Feature/孔位幾何、CUTTING、BEND、DXF 或 Family 加工權限；既有 Fold Designer `project_fold_designer_snapshot_part_features` 仍負責反方向「操作者格 → 實體 Part Features」的提交。正反向 ID 等價、主 GUI 真實讀回委派、非法來源不改與 `.p6fold` Save→Reload 由 `tests/test_issue2517_main_gui_door_layout_feature_readback_public_api.py` 驗證；完整產品回歸及 Windows UAT 依原有驗收路徑。

## [CURRENT] #2517 主 GUI 頭／尾盤舊版 2D 孔位讀回必須為同一 Engine 原子投影（2026-11-07）

- 原 `gui_modules/application/lifecycle.py` 在 .p6fold 專案載入、Quantity 版本切換、Fold Designer 同步三條路徑各自以私有 `feature_to_legacy_hole` 逐一轉換 `head`／`tail` 已保存實體 Feature，轉成主 GUI 舊版 2D 用的 `head_holes`／`tail_holes`。若第一個板件成功、第二個板件轉換失敗且被既有相容捕捉吞下，兩份快取可能被部分提交、與同一保存來源失配。
- 正式 `ae_engine.operator_legacy_endcap_hole_projection.project_operator_endcap_legacy_hole_rows(source_features, *, width, depth)` 在 Engine 先驗證 operator finished-face W/D，再沿原 `sheetmetal_features.feature_to_legacy_hole` 權威轉換兩個物理角色，檢查非有限 finished-face 座標、完整建構 detached candidate，任何非法角色來源／孔型都拒絕整份候選，絕不修改輸入。未提供的 Head/Tail 角色不產出；明確空清單用於舊專案清孔。 `manufacturing_api` 與根包 `ae_engine` 公開同一 callable。
- 主 GUI 三條路徑只收 Engine 結果，Head/Tail 成功後才一起更新快取；原數量模式缺失角色與舊專案資料相容的例外處理維持。此 API 是**舊 2D 顯示快取 readback**，不是獨立 Feature/CUTTING/孔位、FinalScene 或 DXF 製造資格；任何正式加工仍走原 Engine 製造鏈。驗收 `tests/test_issue2517_endcap_legacy_hole_atomic_public_api.py` 包含直接 Owner 相等、真 GUI 專案還原、頭合法尾非法不得部分提交、非有限尺寸／座標拒絕與實際 `.p6fold` Save→Reload；需 exact-head Product Regression 與 Windows UAT。

## [CURRENT] #2517 受電箱實體底板設定改由公開 Engine 原子提交（2026-11-07）

- 原 GUI `receiving_base_plate_settings_transaction.commit_receiving_base_plate_settings` 已經先調用 `manufacturing_api.validate_receiving_base_plate_settings` 驗證實體底板收縮、折邊與焊接 EAR 孔，但隨後在 GUI 直接修改已保存 `receiving_base_plate` 並執行失敗回滾。這個來源交易會影響 PartSpec／FinalScene／CUTTING，不該由 UI 決定寫入。
- 正式 `manufacturing_api.commit_operator_receiving_base_plate_settings`（`ae_engine` 根包亦公開）委託原 `receiving_base_plate_settings_validation` owner：先驗證 Family／底板配置／真實焊耳孔，再於原專案 snapshot 提交或移除這一個物理選擇。Headless 客戶端可不傳通知；GUI 僅傳已存在的 update callback，若 callback 失敗則還原原本欄位存在性與原物件身分，非法 callback／Family／EAR 來源在寫入前拒絕。回傳 detached 接受結果，不把 GUI 視為第二份幾何權威。
- 舊 GUI 入口維持同一參數以相容原 3D 設定按鈕，但僅 forwarding。測試涵蓋直接 API／GUI 成功提交與明確取消一致、非法輸入未改來源、callback 失敗且 rollback 不破壞原物件及 GUI AST 無物理設定寫入。底板材料尺寸、LEFT／CENTER／RIGHT 焊耳座標公式、2D／3D／DXF 真實製造與驗證條件未修改；仍需 exact-SHA Product Regression。#2517 全功能／Windows GUI 操作 UAT 仍未結案。


## [CURRENT] #2517 FinalScene 使用者新增 Joint 實體板件資格改由公開 Engine 投影（2026-11-07）

- Fold Designer 的 `FinalSceneCompositionPorts.user_joint_parts` 原在 GUI 取已遷移快照後自行比較 `AssemblyJointSource.USER_ADDED` 並解析 subject／target。這決定哪個實體板件進入正式 resolved geometry，屬 Manufacturing Joint 來源資格，不是 GUI 呈現邏輯。
- 原 AssemblyJoint owner `ae_engine.assembly_joint.project_operator_user_assembly_joint_parts` 在既有 `migrate_legacy_snapshot_joints` 後投影不可變 `frozenset`，只包含已保存的 USER_ADDED 兩端有效實體板件；未支援未來 schema 使用原 Engine 錯誤拒絕，快照不寫回。公開 `manufacturing_api` 和 `ae_engine` 根包為同一 callable，GUI 不再解析私有 Joint enum。
- 不增加 Joint 關係、裝配/Relief/Corner 新公式或 FinalScene 第二套 resolver；正常、舊 schema、其他來源類型、錯誤版本和 GUI 路由有正反 headless 測試，製造 2D／3D／DXF 仍需 exact SHA 完整產品回歸。Windows R5 UAT 與 #2517 全面接線尚未結案。



## [CURRENT] #2517 同一已確認 NFB 來源中的「獨立核心板件＋成對 NFB」合圖（2026-11-06）

- CADSplit 新建受電箱由來源 DXF／CSV 建立同一份 WHD 核准 Layout，Engine 正式 grouped DXF 使用該已提交 NFB 的保存 Layout，重新衍生每個 Bay 的完整 immutable pair Request 並比較 manufacturing fingerprint。不可僅看相同 stable ID／W/H/D，也不能讓外部輸入以未核准來源或預覽繞過 #2987 防混圖閘門。
- 同一來源內原 DXF／CSV／Engine PartSpec 已確認的 BoxBody、外門、封頭、封尾是獨立核心製造板件；它們不應因為該 Project 已提交 NFB 就被錯誤要求取得另一範圍的 EAR／PAD 整箱 MFG-2 放行。只在 nfb_pair_requests 存在、只選 box_body/door/head/tail、同一保存 Layout 的每個 NFB pair 逐一重新驗證且原子批次重開時，允許原核心板件的原有獨立 Save→Reload 閘門。base_plate／inner_door／PAD／EAR、未配置底板與未核准 NFB 不能藉此取得整櫃資格；不允許未知選取 flags。
- 保留 COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH 跨專案拒絕、原 CSV SHA 與工程 source guard、每片真實 identity、2D／3D／DXF／整組 Save→Reload 與 staging 原子性。#2692 三模式：預設 ALL 全部.dxf、明確 PER_SET 第N套.dxf、明確 END_VS_MIDDLE 頭尾盤.dxf＋有中間盤時 中間盤.dxf。
- R5-2600 於隔離工作目錄，以正式 A-PT1～A-PT16 DXF 與現場 CSV 覆核本修復候選版本：ALL 1 張／16 Bay、PER_SET 3 張／4-3-9、END_VS_MIDDLE 2 張／6-10，NFB Door/Base 每 Bay 各一、各模式物理 CHECK 清單一致、DXF audit 0、來源 SHA 不變。此為隔離環境實機驗收，不代表正式 Windows 工作目錄已同步，也不代表整箱 MFG-2／NC 放行。




## [CURRENT] #2517 主 GUI 合併出圖自動納入同源已確認 NFB pair（2026-11-06）

- 之前的 Engine `export_grouped_receiving_multibay_dxf(nfb_pair_requests=...)` 已能驗證並排入每 Bay 內門＋底板；但主 GUI 的選取出圖按鈕沒有傳入 NFB Requests，造成使用者必須額外呼叫獨立 NFB 出口，不能以主按鈕得到一份已確認板件的 DXF。
- 本次主 GUI 只傳 `include_saved_nfb_pairs=True` 給原有公開 Engine grouped 出口，絕不在 GUI 建構 X、PartSpec、孔位、幾何或決定實體 Bay 身分。Engine 僅在操作者**同時選擇 Door＋BasePlate**且存在已提交 NFB 的同一份已保存 Layout 時，要求**每個 Bay 都已確認**；部分確認直接整批拒絕，全數確認則用既有 `receiving_committed_nfb_pair_request_for_bay` 重建原始不可變請求，並由原有 `_verified_nfb_composed_pair_rows` 逐個比對最新來源 SHA／PartSpec、DXF Save→Reload。
- Engine 在配對出圖時只從核心預覽排除將由該 pair 取代的 NFB 內門／底板物理鍵，避免同一板件在合併檔中重複；HEAD、TAIL、外門、箱身與 EAR/PAD 的既有製造政策不放寬。未選內門＋底板的 Head-only 不會偷偷輸出 NFB，未提交 NFB 的歷史 Legacy 行為不變。原子合併仍只寫正式分組檔，沒有獨立 NFB 生產資料夾。
- 以上仍是已核對的 NFB PART_ONLY 併排，不代表軟體 MFG-2 完整箱體認證；Quantity 與 CADSplit 對同一主出圖入口的接線仍需各自驗收。


## [CURRENT] #2517 單 Bay 受電箱 ALL 合併不再退回逐板件（2026-11-06）

- GUI 原本已將受電箱 DXF 合併預設設為 `ALL`，但 `plan_receiving_multibay_export_source` 針對只有一個 Bay、且不是僅 Head/Tail/Outer Door 的選取，仍回傳 `use_multibay=False`，因此可能退回逐板件 DXF；使用者要求所有盤體預設合併，受電箱另可選 `PER_SET` 或 `END_VS_MIDDLE`。
- 公開 Engine 來源路由現在對一個真實 Bay、明確選定任一合法 group mode 也使用既有 `export_grouped_receiving_multibay_dxf`；未選 group mode 的歷史單 Bay 呼叫仍保留舊路徑。僅 Head/Tail/Outer Door 的 NFB-independent 預覽資格不變；其他板件使用**未遮蔽**的同一份保存 NFB／CSV／PartSpec／FinalScene，原 Engine EAR/PAD、來源 SHA、逐片與單檔 DXF Save→Reload、原子批次提交與拒絕仍不可跳過。
- GUI 的合併選項僅顯示於 Engine Registry 確認的受電箱（包括小寫別名），不由 GUI 寫死 Family 字串；金庫型仍維持既有單 DXF。正反驗收涵蓋單 Bay BoxBody＋Head 合併單檔、缺實體來源零輸出、單 Bay NFB 不被預覽快取遮蔽。Quantity 版本出圖仍走現有獨立 Engine 數量流程，**不得宣稱已使用此 Set/Bay grouping**；#2517 整體和 Windows UAT 尚未完成。


## [CURRENT] #2517 NFB 併入每 Set DXF 必須與同一份保存來源完全同義（2026-11-06）

- 原 `export_grouped_receiving_multibay_dxf(nfb_pair_requests=...)` 的 Engine 私有驗證只對照 Set/Bay stable ID、W/H/D 和 Request 內自行核准的 NFB source；不同 Project 若同樣有預設 stable ID、尺寸，可能拿「別的 Bay 核准 Request」併入本 Project 核心出圖，形成同檔但不同源的 CUTTING。
- `receiving_csv_multibay_manufacturing._verified_nfb_composed_pair_rows` 現從**本次保存的 Receiving Layout 和原始厚度**，重新呼叫已存在公開 `receiving_committed_nfb_pair_request_for_bay`，以 Engine `manufacturing_request_fingerprint` 比對完整 immutable Request 語意（已保存 NFB 槽、孔、門、CSV 身分及 PartSpec）。任何重建失敗或 fingerprint 不同，整組 `RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH`、正式 DXF 零輸出。不得以 Set/Bay 名稱或尺寸相同取代來源一致性。
- 此為同源製造放行安全閘門；仍用原 Engine 單 Bay pair FinalScene／Save→Reload、每 Set 原 grouped composer，無第二份幾何、不增加 MFG-2 認證。正向測試必須提交同一份 Engine 已確認 Layout；負向測試固定「相同 ID／尺寸但不同保存的 NFB」零輸出。#2517 全面 GUI API 和 Windows R5 UAT 仍未結案。


## [CURRENT] #2517 主 GUI 箱身折後外高只消費公開 Engine（2026-11-06）

- `gui.py::_box_body_finished_height` 原讀 h/t/FW、私有 `sheetmetal_geometry.box_body_vertical_offsets` 後在 GUI 自算 `h - bottom - top`，缺角落 Policy 時還另寫 `h - 2T`；這是製造成品外高而非 UI 展示排版。
- `manufacturing_api.project_operator_box_body_finished_height` 和 `ae_engine` 根包直接公開 canonical `sheetmetal_corner_policy.box_body_height_from_corner_policies` **同一 callable**，沿用該 owner 的未提供 Policy 預設、EndCap 裝配高度語意及有限／正值拒絕。GUI 只傳已選原始 h/t/FW 和既有 Policy，不再重算物理高度；不動 Registry、Fold、PartSpec、FinalScene、CUTTING／BEND、DXF。
- 測試覆蓋原 owner 等價、兩 Family 的 Head/Tail 配對、預設、非法高度／板厚／非有限值、零來源變動與 GUI AST 公開 API 接線；exact SHA Product Regression 必須成功，Windows R5 UAT 與 #2517 全功能仍未完成。

## [CURRENT] #2517 Door 指示燈定位的門框四邊來源嚴格交易（2026-11-06）

- `DoorFrameEdges` 的四個 `left/right/top/bottom` 旗標只允許原 Engine typed DTO 的真布林；原公開 `door_indicator_position_transactions` 若遇 malformed Frame Source 會被內層 `getattr(..., True)` 視作四邊都有框，GUI 也用 `params.get("frame_edges") or DoorFrameEdges()` 把 `False`、空容器等來源無聲改成預設。此錯誤會改變指示燈 finished-face 量測基準和 CUTTING 位置。
- 公開 `project_operator_door_indicator_position` 和 `propose_operator_door_indicator_offset_candidate` 在使用原量測／clamp owner 前先驗證 `DoorFrameEdges` 型別及四個欄位；非法來源 fail-closed 且 GUI 不開編輯視窗、不改 offset。合法 `None` 仍代表原有的四邊框預設，沒有建立新幾何／距離公式。
- 測試覆蓋 GUI 與直接 Engine 不合法來源、可選缺省和合法測量等價；完整產品回歸與 canonical 2D/3D/DXF 持續驗證，#2517 仍 OPEN。


## [CURRENT] #2517 Door 指示燈雙擊編輯不再以 GUI 偽造板厚／FW 預設（2026-11-06）

- 主 GUI `on_double_click_indicator` 原在無效 `t_var`／`fw_z_var` 時吞掉例外並改送 `2.0`／`62.0`，違反現有公開 `project_operator_door_indicator_position` 的 fail-closed 來源契約。此入口已由 Engine transaction 擁有距離計算／candidate 產生，僅需把板厚、FW、Door gaps 的**原操作輸入**傳給該同一公開 API。
- 取消 GUI 的板厚／框寬無效 fallback；無效或非有限來源由 Engine 拒絕且不開輸入對話框、不改動已保存 offset。有效字串數值仍由 Engine 嚴格轉換，正式幾何、2D／3D／DXF 與 Save→Reload 使用既有 `door_indicator_position_transactions` 與 canonical Door Feature 解算，沒有 GUI 第二套公式。負向與 GUI 來源逐字 forwarding 見 `test_issue2517_main_gui_indicator_position_public_transaction.py`。


## [CURRENT] #2517 Fold Designer Registry 規則載入與舊專案自訂型號正規化只經公開 Engine（2026-11-06）

- `fold_designer_bridge._phase6_registry_load_rule_rows` 原直接匯入內部 `certified_relief_registry.load_external_relief_rule_records`，取得 Certified Relief 原始規則資料供 Registry diagnostics；`_phase6_prepare_predecessor_init` 原直接使用 `corner_type_ui.normalize_custom_model_name` 決定舊專案／新模型的基準型號。兩者涉及認證來源或 persisted baseline identity，不應由 GUI 私接內部模組。
- 公開 `manufacturing_api.operator_load_certified_relief_rule_records`、`operator_normalize_custom_model_name`（`ae_engine` 根包同名）是原 Engine owner 的**相同 callable**；Registry loader 仍用 CURRENT `certified_relief_rules.json`，未知／損壞 schema 由原 Registry error 拒絕。GUI Registry Controller 仍維持原先全部成功才更新規則快照的交易；舊 `未知類型` 仍正規化為 `自訂`，不改原始保存檔。
- 回歸驗證原 owner/API/GUI 來源等價、原 JSON Registry 現行 records、損壞來源不更新 Controller、型號 snapshot 不改、GUI AST 無私有呼叫；此批未改任何 Certified rule、Corner/Joint/2D/3D/DXF 幾何或輸出資格。整體 #2517、Windows R5 UAT 與正式 X 未結案。

## [CURRENT] #2517 主 GUI 已認證 Family 固定截角改為公開 Engine 原子草稿（2026-11-06）

- `gui.py::_enforce_known_model_corner_types` 原由 GUI 直接調用私有 `corner_type_ui.known_model_corner_state`，再逐角對 `manual_corner_state` 原地寫入固定 `CornerTypeSelection`；來源若缺角或不合法，中途可能已有部分角被更改。既有 `corner_state_transactions.commit_corner_*` 走 raw JSON state，不可直接替代 typed Live Corner state。
- 原 `ae_engine.corner_type_ui` owner 新增 `propose_operator_known_model_corner_draft`：先複製 typed 四角／pair state，在副本上用**原有** Registry `known_model_corner_state` 與 `normalize_corner_selection` 套用固定已認證 CornerType，保留原本「同類型人工參數不重置；reset_all 才還原類型及左右同參數」語意。任何來源錯誤皆不修改呼叫者。原 `known_model_corner_state` 也直接以 `operator_known_model_corner_state` 公開同一 callable。
- 主 GUI 透過 `manufacturing_api` 取得完整成功候選才套入原 Live state，保留既有 nested dict 身分與 Saved CornerType 表示；自訂／未知模型維持不變。無新增 Family 製造公式、Relief Registry、Joint、PartSpec、2D／3D／DXF exporter。對照原 GUI/Engine 語意、非法不改、資料保存／回讀與現有產品完整回歸；#2517／Windows R5 UAT 仍 OPEN。


## [CURRENT] #2517 Fold Designer 已認證截角基準只經公開 Engine（2026-11-06）

- `fold_designer_bridge._phase6_known_model_corner_state` 原直接呼叫內部 `corner_type_ui.known_model_corner_state`，以已確認 Family 與現存 part keys 讀取正式截角起始狀態。這是製造 CornerType 來源權威，即使 GUI 當下只顯示編輯資料也不得私接。
- 公開 `manufacturing_api.operator_known_model_corner_state`（`ae_engine` 根包同名）直接 re-export **原** `corner_type_ui.known_model_corner_state` callable；原 owner 仍唯一委派 Certified Relief Registry 的 `lookup_certified_corner_state`。GUI 只提交 Family／part keys 並顯示同一 typed state；沒有新 Policy、CROSS/Relief 公式、Join/Fold/2D/3D/DXF 路徑或保存格式。
- 定向測試核對兩 Family 原 Registry／公開 API／GUI 完全等價、未知 Family／part 不生造 Certified CornerType、輸入未變更與 GUI AST 公開入口。完整回歸仍由 exact-SHA GitHub Product Regression 驗證；#2517、CADSplit 整箱與 Windows R5 UAT 未據此結案。

## [CURRENT] #2517 主 GUI 指示燈雙擊距離編輯使用公開 Engine Fail-Closed 候選交易（2026-11-06）

- `gui.py::on_double_click_indicator` 原直接呼叫私有 `sheetmetal_features.measure_door_indicator_position` 和 `door_indicator_offset_for_position`。後者對雙擊視窗傳回的 `NaN`、`Inf`、布林或錯誤字串未先驗證，可能產生非法指示燈 X/Y 偏移，並由 GUI 原地提交、影響其後 Door 的 2D／3D／DXF 孔來源。
- 公開 `manufacturing_api.project_operator_door_indicator_position` 與 `propose_operator_door_indicator_offset_candidate` 接受原有 DoorIndicatorContext/Layout/Groups、框寬、板厚、門縫與操作者距離；Engine `door_indicator_position_transactions` 僅驗證合法有限數值與來源型別，沿用**原** `sheetmetal_features.measure_door_indicator_position`／`door_indicator_offset_for_position` 作為唯一距離、座標、夾界算法，無第二套孔位／CUTTING。雙擊視窗資料無效則拒絕，GUI X/Y 舊值不變；合法候選才一次提交兩個現有偏移欄位。
- Headless 與 GUI 測試核對原 Engine 完全相同位置、不同量測基準、來源不改動、非法負向不寫入、GUI 成功後新偏移經原 Hole Editor 儲存驗證；原 Door PartSpec／FinalScene／DXF 寫入器與封閉驗證未改。此批不代表 #2517、CADSplit 全 Bay 或 Windows R5 UAT 已完成。


## [CURRENT] #2517 主 GUI 新建受電箱 Set/Bay＋CSV NFB 實體來源經公開 Engine（2026-11-06）

- `gui_modules/application/cabinet_controller.py::_apply_cabinet_family_for_current_model` 在首次切換 Receiving 時，原直接呼叫私有 `cabinet_types.policy.apply_fresh_family_defaults/resolve_box_body_structure_state/endcap_bottom_selection`、`receiving_layout.new_receiving_layout`、`receiving_fresh_nfb_defaults.seed_fresh_receiving_nfb_source` 以建立 Family 設定、三片箱身、Head/Tail 下截角、Set1/Bay1 及真實 CSV NFB source；`_restore_cabinet_family_runtime` 另直接呼叫私有 Joint v2 migration。這些都是製造資料權威，不應由 GUI 隱藏取用私有 Engine module。
- 現由 `manufacturing_api.operator_apply_fresh_family_defaults`、`operator_resolve_box_body_structure_state`、`operator_endcap_bottom_selection`、`operator_new_receiving_layout`、`operator_seed_fresh_receiving_nfb_source` 及已有 `migrate_operator_assembly_joint_snapshot` 呼叫；前五者與各自原 Engine owner 是**同一 callable**，`ae_engine` 根包亦公開。保留原先初始化時序、CSV `士林 2P400`、NFBConfig/part_features 的唯一 Engine 結果、不重算內門或孔位。
- 公開 owner 與原 owner 等價、合法第一次建立和已確認 source 再呼叫不改、非法 Bay W/H/D、非 Set/Bay 模式與將來 Joint schema 不修改輸入快照，以及 `.p6fold` 真實 source Save→Reload 皆有定向測試。現有 Tk Family 切換、2D／3D／DXF 既有產品回歸不可跳過；本批未宣稱 GUI 整個切換過程在 CSV 故障下具備全 UI 原子交易，也未完成 CADSplit 整箱製造／Windows R5 實機驗收，#2517 OPEN。

## [CURRENT] #2517 Fold Designer 剩餘 Receiving Family／WRAP 可用性接入原公開 Policy（2026-11-06）

- `fold_designer_composition_state.build_capability_owners` 原直接把內部 `cabinet_types.policy.canonical_family_name` 注入 ReceivingCapabilityOwner，`fold_designer_composition_settings` 的 bottom-wrap 控制則直接讀私有 `supports_bottom_wrap_controls`；兩者決定實體箱型操作准入／Joint WRAP 操作可用性，不是純展示數值。
- 已有 `manufacturing_api.operator_canonical_family_name` 與 `operator_supports_bottom_wrap_controls`（`ae_engine` 根包同名）直接公開原 Family Policy 同一 callable；GUI 兩處只替換公開入口，無新 Family、無第二套 Policy、無保存 Schema／Joint／Corner／CUTTING／2D／3D／DXF 公式變更。能力 Owner 的真呼叫與 owner 等價及非法/未知來源不改動快照由原 #2517 Family Policy 回歸擴充覆蓋，另受 exact-SHA Product Regression 驗證；#2517／Windows R5 UAT 保持 OPEN。


## [CURRENT] #2517 GUI 啟動手動截角／Joint 快照公開 Engine（2026-11-06）

- `gui_modules/application/state_sync.py` 的初始手動截角與已存 INI 恢復沿用原 `CornerTypeSelection` 型別：`new_manual_corner_state`、`new_manual_corner_pair_same_state`、`assembly_type_from_corner_state`、`apply_box_assembly_type` 原先全部從內部 `ae_engine.corner_type_ui` 直接匯入並使用；原 `migrate_legacy_snapshot_joints` 則直接從私有 `assembly_joint` 匯入。現在四個 typed Engine owner 以 `manufacturing_api.operator_new_manual_corner_state`、`operator_new_manual_corner_pair_same_state`、`operator_assembly_type_from_corner_state`、`operator_apply_box_assembly_type`（根包亦公開）同一 callable 引出；Joint 直接復用已有 `migrate_operator_assembly_joint_snapshot`。GUI 不重寫預設值、Factory／Joint 拓樸、既有保存格式或截角幾何。
- 既有 `corner_state_transactions.commit_corner_*` 是另一種持久化 raw payload 的公開交易，不會直接改當前 live `CornerTypeSelection` State；本次只釋出原 typed Engine owner，不複製方法或製造公式。測試覆蓋公開與內部 owner identity、GUI 啟動初始化／手動狀態投影 parity、invalid assembly type 與 future Joint schema 不變更來源、保存 codec roundtrip。HEAD／TAIL 真實 2D／3D／DXF 與 Save→Reload 由 exact-SHA 完整產品回歸核對；Windows R5 UAT 仍待人工執行，#2517 仍 OPEN。

## [CURRENT] #2517 GUI 手動截角編輯公開 Engine 與失敗隔離（2026-11-06）

- `gui.py` 手動截角面板的「左右共用開關」及「截角類型／CROSS 模式／參數」原有四處直接呼叫 `ae_engine.corner_type_ui` 的原地寫入函式。由於這裡的 live state 持有 `CornerTypeSelection`，而既有 `corner_state_transactions.commit_corner_*` 服務的是序列化 raw state，不可不經轉換直接換成不同表示；此批讓 GUI 改呼叫 `manufacturing_api.operator_set_manual_corner_pair_same`、`manufacturing_api.operator_apply_manual_corner_selection`（根包亦公開），兩者與原 Engine owner 是**同一 callable**，不新增製造公式或第二套交易推導。
- 原 owner 的 pair rejoin 在來源缺少 `top_left`／`bottom_left` 時，曾先寫入 `pair_same[pair]` 再讀左角，導致 `KeyError` 後來源被部分修改。現先讀取並驗證必需左角，再一次提交配對旗標與右角；無效 pair／target／selection 拒絕且來源不變。合法的 Head／Tail／其他實體角落左右拆分／合併與左角優先關係保持原語意。
- 測試含 GUI 接線、公開與 Engine 原 owner 直接呼叫 parity、非法輸入未提交、截角原始 selection 存取與既有 raw codec Roundtrip；CUTTING／BEND／FinalScene、2D／3D／DXF 出口無任何算法變動，必須以 exact-SHA 產品回歸驗收。Windows R5 實機 UAT 與 #2517 全面 GUI 接線仍未結案。

## [CURRENT] #2517 Receiving BoxBody 保存 Finished-Face 孔來源公開 Engine 交易（2026-11-06）

- WHD 主 GUI 原正式專案保存路徑是 `lifecycle._compose_phase6_project_snapshot_from_main_gui → workspace.part_face_features → snapshot.part_face_features["box_body"]`；`left`、`right`、`back` 是 **成品面座標**，不是 `physical_piece_features` 的板件材料 UV。Factory 原本只消費實體 UV 的 `confirmed_box_body_piece_features`，漏掉真實保存的 Finished-Face Hole Editor 孔。這會製造出三片沒有 operator 保存孔的 DXF。
- 原 `manufacturing_api.build_receiving_factory_confirmed_parts(..., confirmed_box_body_face_features={"left":(...),"right":(...),"back":(...)})` 與 `ManufacturingResolvedBayInput` 增加明確確認來源；只接受 typed `CircleFeature`/`RectFeature`/`ProfileFeature`、合法 `FeatureAnchor`（包含 `PANEL_CENTER`）、層 `CUTTING`、有效實體尺寸、有限座標與非巢狀輪廓。`saved_operator_confirmed` 若 `part_face_features["box_body"]` 有任何非空已保存面孔，確認來源必須逐 Feature 一致，不可漏掉或竄改。若保存面未產生孔，CADSplit 已獨立確認的合法來源仍可透過相同 Engine API。
- 來源經原 `build_box_body_operator_part_spec(face_features=...) → build_box_body_structure_render_data → resolve_box_body_piece_face_features`，唯一 Engine owner 用真實 Fold／T 決定三片 side/back 成品面轉展開孔位、截裁；不在 Factory、GUI 或 CADSplit 重新計算。與材料板 UV 的 `confirmed_box_body_piece_features` 分開、兩者可同時存在。回歸 `tests/test_issue2517_receiving_factory_confirmed_box_body_face_features.py` 覆蓋 GUI 等價 PartSpec、三張真 DXF 的孔及獨立 Save→Reload、來源不改、錯誤來源零輸出。此為已確認部分板件，不表示 NFB/PAD/EAR／全櫃／Windows R5 UAT 完成；#2517 繼續 OPEN。


## [CURRENT] #2517 Fold Designer Family Policy／Registry 呼叫改走公開 Engine（2026-11-06）

- Fold Designer 主 Bridge 與 Corner Data 原直接 import `ae_engine.cabinet_types.policy`，用於 Family canonical name、三片箱身固定拓樸、BoxBody outside profile 與 WRAP availability。現改消費 `manufacturing_api.operator_canonical_family_name`、`operator_family_fixes_box_body_structure`、`operator_box_body_profile_uses_outside_dimensions`、`operator_supports_bottom_wrap_controls`（`ae_engine` 根包同名公開）。四者是現有 Engine Policy **同一 callable**，沒有新的 Family／製造公式、第二套投影或新持久化格式。非法／未知來源維持原 Owner 的 fail-closed／未支援語意，不得改動輸入。
- Assembly Corner 的 Relief promotion 候選 builder 原從私有 Registry 取用，改用公開 `manufacturing_api.build_relief_promotion_candidate`（原 Engine Registry 與根包相同 callable）；Bridge 的 `resolve_cabinet_type` 亦改用 `manufacturing_api.resolve_cabinet_type`，而不直接引用私有 Registry 模組。候選仍受既有 Controller 原流程與 Registry gate 控制，不因 UI 生成候選即取得 CERTIFIED 製造資格。
- Product Regression 原真 Tk `fold_designer_part_session.save_current_part` 仍經 `bridge.cabinet_family_policy.endcap_fw_profile_uses_material_dimensions` 讀取 EndCap FW 材料／外尺寸 Policy；現追加 `operator_endcap_fw_profile_uses_material_dimensions` 同一 Engine callable，Part Session 直接消費公開 `bridge.manufacturing_api`，無舊私有 Bridge 屬性依賴或 FW 公式複製。
- 回歸驗證 facade/root 與 owner 相同 callable、兩 Family 和未知來源輸入不變、GUI 不再直接讀這些私有模組；2D／3D／DXF 算法、AssemblyJoint 已保存交易與正式 Save→Reload 不更動。#2517 全功能與 Windows R5 UAT 仍 OPEN。


## [CURRENT] #2517 Hole Editor 孔位移動／基準定位／切穿盲孔切換只接公開 Engine（2026-11-06）

- `gui.py` 會以 `HoleEditorCompositionDependencies.from_namespace(globals())` 注入實體孔位操作到 `gui_modules/editors/hole_editor.py`：`feature_with_reference_anchor`、`feature_with_process`、`move_feature_by_reference_distance`、`feature_is_within_surface`、`move_feature_within_surface`。舊版直接從 `ae_engine.sheetmetal_features` 私有 re-export 匯入同一 Engine owner，讓 GUI 交易仍隱藏依賴內部幾何模組；這些實際編輯可改變孔位 finished-face 坐標、基準或 CUTTING／BLIND_HOLE，必須公開。
- 新的 `manufacturing_api.operator_hole_feature_with_reference_anchor`、`operator_hole_feature_with_process`、`operator_hole_move_feature_by_reference_distance`、`operator_hole_feature_is_within_surface`、`operator_hole_move_feature_within_surface` 與 `ae_engine` 根包均直接 re-export 原 `sheetmetal_feature_reference`／`sheetmetal_feature_surface` canonical callable；無新位置、輪廓、材料補償或流程。GUI 向 HoleEditorComposition 注入這五支公開 API 同名別名；物理特徵仍為 immutable Feature，Session 預覽／確定／取消負責提交，原 source 及無效索引／非有限距離／非法 process 不得變動，越界拖曳回傳原孔。
- Engine 2D／3D／DXF 與 Save→Reload 的 canonical Feature→FinalScene 路由不改；`Vec2`／`RectGuide`／顯示類型不是本次交易缺口。這批需 owner 等價、正反定位、非法操作保留來源、GUI 相依接線及 exact-SHA 完整回歸。尚不代表全部 GUI 私有 imports、CADSplit 全箱體 MFG-2 或 Windows 實機驗收已完成，#2517 OPEN。

## [CURRENT] #2517 圓孔中心距／孔邊間距來源與剩餘 Joint snapshot 統一公開 Engine（2026-11-06）

- Hole Editor 的圓孔排列本身已透過 `manufacturing_api.plan_operator_round_hole_preview`，但 `hole_editor_round_settings._sync_from_center/_sync_from_gap` 顯示與草稿欄位仍直接使用內部 `sheetmetal_features.circle_gap_from_center_distance/circle_center_distance_from_gap`。同一 canonical `sheetmetal_feature_reference` 的兩個純換算 callable，現在由 `manufacturing_api.operator_round_hole_gap_from_center_distance/operator_round_hole_center_distance_from_gap`（及根包）公開，同一幾何／無新公式。GUI 繼續於轉換前檢查有限、正值與非負間距；改值只涉及 GUI 草稿，實際實體 Feature／CUTTING 仍由已有 Engine preview + Hole Editor session Confirm 提交。
- `fold_designer_composition_state.corner_transaction_payload/collect_workspace_state` 原先尚直接呼叫 Joint v2 `migrate_legacy_snapshot_joints`；現在兩處都改走 #2970 原有 `manufacturing_api.migrate_operator_assembly_joint_snapshot`，沒有重新建議 Joint 關係、修改 schema 或改變 Save→Reload。
- 此批不把展示 `Vec2`、`CirclePrimitive`、`DoorFrameEdges` 當作新的製造缺口；孔位到 PartSpec／2D／3D／DXF 的原 Engine 路徑、CADSplit 公開契約、正式輸出權限均未改動。需 public-vs-owner 實際換算與 GUI 同值、非法值不提交或改變草稿、Joint source 不變性及完整 exact-SHA CI；Windows GUI 實機驗收另行，#2517 OPEN。

## [CURRENT] #2517 NFB 實體預設 X 可一次確認、無需逐顆輸入（2026-11-06）

- NFB 型號主孔、底板螺絲、間距與來源數值只讀 WHD 當前各品牌 NFB數值規格.csv；Engine 原生 Hole Editor 產生的 native_editor_initial X 在**未確認前**仍是編輯預覽，不直接授予實體 CUTTING。原 source-only Candidate Apply 保持 UNVERIFIED_BASIS、manual_x_mm=None，#2961 自動候選阻擋仍有效。
- 使用者明確決定採用 WHD **當前 Engine 預設位置**時，不必逐顆輸入 X。公開 manufacture API approve_receiving_nfb_csv_default_x(layout, *, set_index, bay_index, thickness_mm, source, confirmation="ACCEPT_CURRENT_WHD_NFB_DEFAULT_X")，一次確認同一實體 Bay 全部 NFB；必須由 Engine 依**本次** Set/Bay、已確認品牌、門拓樸、CSV SHA、型號、孔槽與實體幾何重新產生候選並逐位元比較。所有校驗與原子 Apply 成功後，才將 fresh_bay_auto_unconfirmed 移除、保存 fresh_bay_default_x_confirmed=True 的同源 Feature；不得從任意中心距公式、預覽外框、其他 Bay 或舊 CSV 直接推算／杜撰製造 X。無確認、改動原始資料或缺實體 Door 均拒絕且不修改來源。
- 核准後同一 Engine 的 _submitted_csv_holes 必須還能驗證真實原孔輪廓、Y、物理身份、角度／擺放；公開 receiving_committed_nfb_pair_request_for_bay(layout, *, set_index, bay_index, thickness_mm) 由 Engine 唯一輸出真正的 ManufacturingResolveRequest／原始內門和底板 PartSpec／RenderData，不能由 CADSplit 建造 ManufacturingPartInput 或平行幾何。現有 export_current_csv_nfb_pair_from_request／export_receiving_committed_nfb_csv_bays 才能產生實體 Door + Base DXF；所有獨立重新開檔與源碼 Guard 仍然必須通過，只有 PART_ONLY，非整箱／EAR/PAD 授權。
- 這是一個**額外的明確確認交易**，並未把 nominal_nfb_x_group 的相鄰距離 PREVIEW_ONLY 當成擁有一般性已認證的絕對 X 公式；超出現行 CSV／物理門板可驗範圍仍阻擋。WHD 原 GUI 原生「確定全部」既有確認路徑不改。



## [CURRENT] #2517 Receiving Bay 預覽尺寸與 NFB CSV 孔位分流只經公開 Engine API（2026-11-06）

- `gui_modules/application/fold_designer_composition_receiving.py::receiving_bay_preview_request` 原先直接 import `display_dimensions.resolve_operator_finished_dimensions`，而這個完成面尺寸投影本就已是公開 `manufacturing_api.resolve_operator_finished_dimensions`；GUI 現直接使用原公開入口，不另造尺寸或 DXF 幾何。
- 內門 NFB 即時孔位預覽的 `stage_live_nfb_openings` 原在 GUI 用內部 `receiving_nfb_model_identity.is_numeric_model_ref` 判定是否可由 CSV 生成孔；這是來源身份准入，現在由原 Engine 身份 owner 的 `can_stage_receiving_nfb_csv_preview_refs` 原子判定並透過 `manufacturing_api`、`ae_engine` 根包公開。維持空清單、舊 DXF 與 V5 identity 的原 UI 分流，非法型別直接拒絕且不動來源。真實 CSV 輪廓／孔位仍必須由既有 `editor_nfb_features_from_csv` 與 Hole Editor staging 驗證，不能把識別字串視為 CUTTING／MFG-2 認證。
- 型號顯示 `display_model_ref` 只透過公開 `manufacturing_api.display_receiving_nfb_model_ref` re-export 原 Engine 相同 callable；移除 GUI 未使用的 `INDEX_PATH` 與 `validate_stored_model_ref` 私有匯入。公開／owner 等價、非法來源不改動及 GUI 接線由新增回歸覆蓋，完整 Product Regression／Save→Reload 仍必須 GREEN；#2517／Windows R5 UAT 保持 OPEN。

## [CURRENT] #2517 Fold Designer Head/Tail 四邊 Joint Policy 與舊 Joint 啟動狀態共用公開 Engine（2026-11-06）

- 原 `fold_designer_bridge._phase6_endcap_joint_policy_rows` 在 GUI 直接將 `assembly_joint.migrate_legacy_snapshot_joints`、`assembly_intent.get_assembly_intent`、`assembly_joint.edge_relation_for_part` 組合成可編輯接合關係；`_phase6_bootstrap_authoritative_state` 也直接呼叫內部 Joint migration。這些是已保存物理 Joint 的解讀／遷移，不可由 GUI 持有其操作權威。
- 原 Engine `assembly_joint.migrate_legacy_snapshot_joints` 僅以 `manufacturing_api.migrate_operator_assembly_joint_snapshot`（根包亦同名）公開**相同 callable**，保留 schema-1→v2、已選組合型態、明確使用者 Joint 和 Save→Reload 語意；原 Engine owner 增加 `project_operator_endcap_joint_edge_policies(snapshot, part_key, *, fallback_intent)`，直接呼叫該 migration、原 `get_assembly_intent` Registry 與 `edge_relation_for_part`，對真實 Head/Tail 的 TOP/BOTTOM/LEFT/RIGHT 回傳候選 relation/allowed/editable，非法來源不修改原快照。GUI 只轉換 Engine relation enum 為既有中文標籤，不再組裝 Policy。
- 此為持久化來源與唯讀 Joint 控制項投影接線，不更動 Corner/Relief 的製造幾何、現有 Joint 提交交易、FinalScene 或 DXF。以 public-vs-owner 等價、四組 Assembly Intent、負向 source 不變性、GUI seam 及既有完整 CI 驗收；#2517/Windows R5 UAT 仍保持 OPEN。

## [CURRENT] #2517 Receiving Factory 保存的 Head／Tail 孔位不可在確認來源中消失（2026-11-06）

- `confirmed_endcap_features` 本來會對合法 Head/Tail finished-face typed CUTTING 做來源形狀驗證，卻沒有與 `saved_operator_confirmed` 原 `part_features["head"／"tail"]` 對照；因此已保存孔位可能在製造中被漏掉，或被另一份不符孔位取代。原 `receiving_factory_requests` 現在檢查：保存該角色有非空 Feature 時，對外確認必須逐 Feature 相同；保存角色的欄位不合法也拒絕 `RECEIVING_SAVED_ENDCAP_SOURCE_FEATURES_MISMATCH`，且不得先寫出部分 DXF。
- 若保存的 Head／Tail 沒有原孔，但 CADSplit 有另外已確認的合法 CUTTING Feature，仍沿用原 `confirmed_endcap_features` 入口（不要求先寫入 GUI 保存值），避免把外部合法來源當成偽造。`EndCapPartSpec → FinalScene → verified Batch DXF` 原 owner 及 2D/3D 幾何不變；不增加第二個輸出器或偷偷接入 NFB/PAD/EAR。
- 回歸 `tests/test_issue2517_receiving_factory_saved_endcap_cutting_source.py` 包含 Head/Tail 真孔→五張物理 DXF／Save→Reload、缺確認／保存衝突／非法保存欄位零 DXF，以及外部合法確認孔可用。#2517 全功能／整櫃及 Windows R5 UAT 仍未完成。



## [CURRENT] #2517 內門 NFB 舊來源恢復／新草稿預設／層高切換只經公開 Engine API（2026-11-06）

- Fold Designer `inner_edit` 原先仍直接引用內部 `receiving_legacy_nfb_editor_bootstrap.recover_submitted_nfb_models_for_editor`、`receiving_fresh_nfb_defaults.initial_fresh_receiving_nfb_models`；`change_layers` 也直接引用 `receiving_shared_settings.transition_receiving_nfb_layer_heights`。這三條操作影響可編輯的 NFB 型號／雙層 Y 草稿，不能由 GUI 直接依賴內部來源模組。
- 於既有 `ae_engine.manufacturing_api` 和 `ae_engine` 根包同名公開 `recover_receiving_submitted_nfb_models_for_editor`、`initial_receiving_nfb_draft_models`、`transition_receiving_nfb_layer_heights`，均為原 Engine owner 的相同 callable（無新資料格式／製造公式）。GUI 只提供原保存快照、當前品牌及操作者層高，保留 Cancel、Confirm、舊 NFB 專案和非士林品牌隔離；非法輸入不得改動來源。
- 這是草稿來源 API 接線；未變更實體孔輪廓、NFB 已確認 world X、FinalScene、CUTTING、DXF 或 Set/Bay MFG-2 資格。需定向比對 public/owner、負向來源無副作用、GUI boundary，正式製造維持原 Save→Reload 驗證；#2517 不因此結案。

## [CURRENT] #2517 受電箱三片箱身原始保存孔位經公開 Factory／FinalScene 驗證（2026-11-06）

- `build_receiving_factory_confirmed_parts` 的原 `BoxBodyPartSpec` 過去直接吃保存 `physical_piece_features`（可能未經正式來源資格確認），或遺失只存於 `part_features` 的三片實孔。向後相容的 `confirmed_box_body_piece_features` 必須與 `saved_operator_confirmed` 的原保存來源逐實體角色、逐 Feature 完全一致；角色限 `box_body:left_side`、`box_body:back`、`box_body:right_side`，均為材料板面 UV 的 typed `ABSOLUTE_FINISHED_FACE`／`CUTTING` Feature。`physical_piece_features` 與舊 `part_features` 若同時含實孔而不一致，必須拒絕，不可猜哪個版本為真。未提供確認但保存存在實孔，也拒絕製造而非靜默出無孔板。
- 新來源沿用唯一 `build_box_body_operator_part_spec` → `build_box_body_structure_render_data` → `with_physical_sheet_features` → `FinalScene` → 原 Verified Integration Batch DXF Save→Reload；不在 Factory／CADSplit 重算孔座標，不讓三片的分開實孔變成整體箱身一張製造圖。尚未確認的 BoxBody finished-face 特徵、非三片身份、超出物料輪廓與非法 Feature fail closed；保存來源不改寫。
- `ManufacturingResolvedBayInput.confirmed_box_body_piece_features` 與 `manufacturing_api.build_receiving_factory_confirmed_parts(..., confirmed_box_body_piece_features=...)` 共享此交易。回歸 `tests/test_issue2517_receiving_factory_confirmed_box_body_piece_features.py` 涵蓋三真 DXF 孔位／重開與 canonical RenderData、一批五張物理板件、錯誤來源零輸出；不代表 NFB/PAD/EAR／整櫃與 Windows R5 UAT 完成，#2517 保持 OPEN。



## [CURRENT] #2517 普通受電箱底板已確認 Hole Editor CUTTING 經公開 Factory API 真正出圖（2026-11-06）

- 現行原 `manufacturing_api.build_receiving_factory_confirmed_parts` 的選配普通底板原先直接拒絕所有已保存 `part_features["base_plate"]`，即使是完整可信來源，導致 GUI 有保存孔但 headless/CADSplit 只能製造無自訂孔底板或被阻擋。向後相容新增 `confirmed_base_plate_features={"base_plate": (原 typed Feature, ...)}`：僅 `saved_operator_confirmed`、`include_confirmed_base_plate=True`、普通 LEFT/RIGHT、未提交 NFB，且傳入 typed `ABSOLUTE_FINISHED_FACE` + `CUTTING` 實體 Feature 與原保存孔資料逐一相同，才由原 `build_base_plate_operator_part_spec` 建出帶完整實孔的 canonical BasePlatePartSpec。
- `ManufacturingResolvedBayInput.confirmed_base_plate_features` 經原 `export_verified_resolved_integration_bays` 轉入同一 Engine 工廠 builder，重用已認證物理 FinalScene、EAR slots、原子 DXF writer、獨立 Save→Reload；未提供孔位確認但原保存有孔、傳入未保存孔／不符孔、錯 role／layer／anchor、超出實體底板輪廓、未選底板或已提交 NFB 都完整拒絕，不靜默漏孔。沒有新增第二份底板幾何公式或 CADSplit 專用製造器。
- `tests/test_issue2517_receiving_factory_source_engine_part_specs.py` 包含真確認孔→六張實 DXF、原始孔 CIRCLE CUTTING 與 canonical RenderData 回讀一致、source guard 前後兩次，及負向拒絕／沒有部分 DXF。這是普通底板逐片製造，**不是** NFB CENTER/tier、PAD、焊 EAR 元件、16 Bay 全櫃 MFG-2 或 Windows R5 認證；#2517 保持 OPEN。


## [CURRENT] #2517 Receiving Factory EndCap 必須共享 GUI 原始 BoxBody Fold 裝配 FW（2026-11-06）

- `build_receiving_factory_confirmed_parts` 由已保存或已明確確認 Family 來源建立 Head/Tail PartSpec 時，必須將其同一 Engine `body_rows` 直接傳入原 `build_endcap_operator_part_spec(..., box_body_fold_profile=body_rows)`。原 Factory 之前雖已保留 BoxBody Fold 並確認 EndCap X/Y、Corner，但漏傳兩側成形 FW 的來源，使此 API 與 GUI 同一物理 EndCap 的 `box_body_formed_fw_left/right` 不同。現在由同一 Engine owner 根據真實相鄰 BEND/T 計算，不從 CADSplit／GUI 另算或猜測，且不改 Fold／CUTTING 公式。
- `tests/test_issue2517_receiving_factory_source_engine_part_specs.py` 覆蓋 fresh/saved 兩種合法來源、Head/Tail 與原 GUI Engine PartSpec 的完全等價、5 張實體 DXF 經原 verified batch 獨立 Save→Reload 且比對同源 RenderData。非可信 source-only、未確認 NFB、PAD/EAR、整櫃 MFG-2 與 Windows UAT 權限仍不開放；#2517 全範圍未因此結案。


## [CURRENT] #2517 多門格原始指示燈物理來源直接進公開 Engine Door PartSpec（2026-11-06）

- 多門格 `_door_layout_part_spec` 原先先呼叫 `project_operator_door_cell_indicator_manufacturing_source`，由 GUI 自行決定 `indicator_box` / `indicator`、裁切層數、取得開孔大小、選擇實體孔、傳入 offsets 與箱距旗標。雖然幾何 helper 屬 Engine，此段仍是 GUI 自己在拼裝正式物理 DoorPartSpec 的 source-to-manufacture 交易，容易出現不同 caller 的第二套組裝路徑。
- 原公開 `manufacturing_api.build_door_operator_part_spec(..., indicator_source_state=original_saved_cell)` 新增可選原始來源。Engine 直接復用 `fold_designer_snapshot_dimensions.project_operator_door_cell_indicator_manufacturing_source` 與原 `manufacturing_door_indicator.indicator_box_opening_size`，由同一已驗 source 決定物理 Mode/Groups/Opening/Offsets/Box-Distance；GUI 僅傳保存的原始 cell state、已存在的 Door 尺寸與原本身份，不再選出物理孔或修補 source。禁用模式不會補出製造孔，啟用但非法的原始 groups、layers、offset 立即 fail closed。
- 舊式直接 `indicator_hole`／`door_indicator`／offset 呼叫仍適用未帶原始 cell source 的單門或既有 adapter；若同時給新原始來源與預計算實體輸入，拒絕 `DOOR_OPERATOR_INDICATOR_DUPLICATE_SOURCE`。這是原 Door Engine API 的向後相容擴充，未新增幾何演算法、另一個 renderer 或 CADSplit 專用出口；`tests/test_issue2517_door_layout_indicator_source_public_api.py` 比對真兩箱型原舊 PartSpec 等價、正反例、舊 flags、原 source 不變與 GUI seam。DXF／FinalScene 資格仍由原下游 Engine 驗證，#2517 整體／Windows UAT 未因此自動完成。


## [CURRENT] #2517 EndCap 成形 FW 必須由 Engine 直接消費原始 BoxBody Fold（2026-11-06）

- `manufacturing_api.build_endcap_operator_part_spec(..., box_body_fold_profile=...)` 在原公開 EndCap PartSpec 建立契約上新增可選的已保存 BoxBody Fold 原始來源。由同一 Engine `box_body_editor_readback.formed_box_body_fw_widths` 對實際目前相鄰折彎與實體厚度計算左右 **formed** FW；不得在 GUI／CADSplit 先算製造 FW，再把失去 Fold 來源見證的兩個數字交給 Engine。箱身 Fold 完全無左右 FW 時保留 None，不能重生已刪實體 Fold；既存來源上的 stale `ui_len_add` 不得取代拓樸。
- 舊 `box_body_formed_fw_left/right` 參數在**不提供**新 `box_body_fold_profile` 時維持相容；若兩種來源同時提供，Engine 明確拒絕 `ENDCAP_OPERATOR_FORMED_FW_DUPLICATE_SOURCE`，禁止來源競爭。GUI `manufacturing_adapter._end_cap_part_spec` 改只採集原始保存 Fold，不再呼叫 `formed_box_body_fw_widths` 計算製造資料；原 `EndCapPartSpec`、組裝、角、Relief、2D／3D／DXF Owner 不變。
- 真正定向回歸 `tests/test_issue2517_endcap_formed_fw_source_public_api.py` 覆蓋兩 Family、Head/Tail、1T 邊界、stale UI metadata、已移除 Fold、原 source 不變、舊 API 相容、矛盾來源拒絕、GUI seam。formed FW 是裝配／碰撞 datum，不是獨立 CUTTING oracle；本修正不表示 #2517 全面、16 Bay 整櫃或 Windows UAT 完成。


## [CURRENT] #2517 已保存普通受電箱底板由 Engine 直接建立來源 PartSpec，並接入原 Verified Bay 出圖（2026-11-06）

- `build_receiving_factory_confirmed_parts(..., include_confirmed_base_plate=True)` 是原公開 Engine source→PartSpec 接口的可選向後相容擴充。僅在 `saved_operator_confirmed`、原始 W/H/D/T 與保存狀態一致，且明確有 `receiving_base_plate` 實體來源時，沿用原 `validate_receiving_base_plate_settings` 的 EAR pitch／真實輪廓預檢、`receiving_base_plate_values` 與 `build_base_plate_operator_part_spec` 生出 `("base_plate", BasePlatePartSpec)`。GUI／CADSplit 不必在 client 自組縮量、BEND 或 BasePlatePartSpec。
- `ManufacturingResolvedBayInput.include_confirmed_base_plate` 在同一原 `export_verified_resolved_integration_bays` 流程中向 Engine 傳遞此確認意圖；原 Engine FinalScene 生成、逐片 DXF 保存／獨立 Save→Reload 及原子提交不變。缺來源、非保存確認、非普通 LEFT／RIGHT、任何已提交 NFB 或未驗底板孔位一律拒絕，不得把 PAD/EAR/雙層 NFB 冒充普通底板。
- 預設 False 時原先 3 PartSpecs（五張箱身／封頭尾 DXF）及有已確認雙外門時七張輸出完全相容；顯式保存底板且合法時新增第六張原生物理底板 DXF。這是普通獨立板件製造能力，**不**宣稱受電箱整套 MFG-2、16 Bay 全件或 Windows R5 已驗收；#2517 仍 OPEN。




## [CURRENT] #2517 公開 NFB CSV Candidate Apply 必須連實體 Hole Editor 孔來源一起落地（2026-11-06）

- WHD `ae_engine.manufacturing_api.apply_receiving_nfb_csv_candidate(layout, *, set_index, bay_indices, source)` 原程式雖已公開，但只提交 `nfb_config_submitted/nfb_config`，丟失候選 `source["features"]`、層數、型號、原始 Y；`receiving_layout.project_receiving_bay_legacy_aliases` 的正式 `part_features` 來自各 Bay `settings["inner_door_features"]`，其後 `receiving_nfb_committed_final_scene._source_world_x_from_committed_editor_feature` 需要同一物理門的真 CSV `ProfileFeature` 才能回讀放置 X。只有型號及提交旗標，不等於有可製造實體來源，且不可讓 CADSplit 私下把世界 X 填入 NFBConfig。
- 此公開 Apply 現復用 **既有唯一 Engine Owner** `receiving_inner_door_pairing.apply_receiving_inner_door_candidate_to_bays` 作為整筆交易：先維持原 Set／Bay 選取型別、duplicate、來源 CSV SHA／原生孔輪廓與型號驗證，再一次提交每個已選 Bay 的 layer/models/heights/typed `inner_door_features` 與個別 Bay-namespaced NFBConfig。沿用既有 `unlink_setting` 隔離所選 Bay 共享 refs，不得把候選來源覆寫未選實體 Bay。舊呼叫簽章及 dict Layout 回傳不改；任何非法來源整筆拒絕。
- 新真實正向回歸 `tests/test_issue2517_receiving_nfb_csv_candidate_public_api.py` 覆蓋公開 Apply → Bay source projection → 現有 normal `apply_committed_csv_v5_to_canonical_parts` FinalScene → 實體內門 DXF Save→Reload 及一致性；並驗多 Bay 來源互不借用、舊已連動 unselected Bay 不遭修改、錯型/缺孔/過期來源 fail-closed。此流程只在現有已可信物理來源及相應幾何驗證下走適用 **PART_ONLY**；不藉 Apply 自動核准 X、底板/EAR/PAD、整櫃 MFG-2，亦不解除 source-only CLI 的保護。#2517 Windows 真圖整櫃/UAT 仍需獨立驗收。

## [CURRENT] #2517 immutable Engine Request → 受電箱已驗 NFB 成對 DXF 公開 API（2026-11-06）

- 既有 `export_current_csv_nfb_door_base_pair(snapshot, assembly_parts=..., output_directory=...)` 雖能由 headless 呼叫，仍要求 client 先提供已解析的整個 physical assembly parts。#2517 的 GUI 與 CADSplit 應共用同一 Engine request，不得由 CADSplit／GUI 自己重建已開孔的 2D／3D 板件或製造幾何。
- 新公開 `manufacturing_api.export_current_csv_nfb_pair_from_request(request, *, output_directory)`（同名根包 API）只收原 `ManufacturingResolveRequest`；要求有效 Receiving snapshot、已提交且符合當前真實 Set/Bay 身分的 NFB CSV 來源，呼叫原 `manufacturing_api.resolve_manufacturing_request` 建立唯一正常 FinalScene，再以**原** `export_current_csv_nfb_door_base_pair` 對單層（門＋1 底板）或雙層（門＋2 底板）做來源 SHA、原實體板件、安裝 XYZ、CUTTING、CHECK/Q、暫存 DXF Save→Reload 及原子發布驗證。任何缺失 source／Bay／底板／非 Receiving 類別均 fail closed。
- `ManufacturingResolveRequest.parts` 仍需傳入原始可信實體板件 render_data，不得從原圖缺位推算，尤其不得送「已套上 CSV 開孔的 GUI cache」作獨立來源。此 API **不**打開 `integration_cli` source-only export、不推估或確認 NFB world X、不證明 PAD/EAR 焊接、16 Bay 全櫃 MFG-2 或 Windows GUI UAT；#2517 保持 OPEN。
- 回歸：`tests/test_issue2517_nfb_pair_request_to_finalscene_dxf_public_api.py`，由已提交真實 1／2 層 NFBConfig 與原實體 Door/BasePlate 建完整 request，不提供 `assembly_parts`，檢核多片 DXF 獨立重開及缺來源／缺板拒絕。權威製造核心仍只在 Engine。


## [CURRENT] #2517 內門＋NFB 底板 PART_ONLY 出圖禁止非法真實內門 3D 安裝座標（2026-11-06）

- 原 `receiving_nfb_pair_export.export_current_csv_nfb_door_base_pair` 在單／雙層 committed CSV 的實體 FinalScene 和 CUTTING 比對後，只驗真實 BasePlate 世界 XYZ，卻沒有驗安裝在同一 3D Assembly 的內門 `AssemblyScenePart.offset`；本地 2D/CUTTING 可以完全一致，但失效 `NaN`、缺軸、字串、布林或無限大的內門座標仍能落入 DXF 部分出口。
- 原 Engine owner 直接重用已存在的 `_finite_installed_xyz`，對單層和雙層已確認內門實體 scene 的 world XYZ 要求三軸原生有限數字、拒絕無法安全轉浮點的超大整數；遇非法輸入分別回 `CSV_PAIR_REAL_DOOR_INSTALL_XYZ_INVALID`／`CSV_TWO_TIER_REAL_DOOR_INSTALL_XYZ_INVALID`，原子 writer 尚未啟動、不可留下任一板件 DXF。原 FinalScene/CUTTING 和真實底板安裝證明仍必須同時合格。
- 回歸沿用原真來源及真實 DXF Save→Reload 測試的同一場景，單／雙層各對上述七組失效座標確認無部分輸出；這僅確保內門 3D 安裝資料有效，**不**冒稱已校驗其絕對 XYZ 與裝配拓樸完全相符，也不認證 EAR/PAD 焊接、MFG-2、整套 16 Bay 或 Windows UAT；#2517 保持 OPEN。




## [CURRENT] #2517 Receiving 多連封頭／封尾 Hole Editor Save 必須同一原子 Engine 交易（2026-11-06）

- `fold_designer_composition_receiving.receiving_settings_ports::holes/save_features` 原先在選取多個實體 Bay 時，先於 GUI 切換到第一個 Bay、呼叫 `adapter.share_setting(kind, targets)`，再呼叫 `adapter.update_setting(kind, features)`。若第二步 Feature 類型或來源驗證失敗，前一步已修改 Adapter 記憶中的 shared refs／dirty IDs，但未觸發 GUI commit；下一次操作可能帶著半套連動來源。這違反一次操作者儲存必須全有或全無的規則。
- 既有 `ae_engine.receiving_shared_settings` owner 新增 `share_and_edit_setting_with_affected_ids(layout, *, set_index, bay_indices, source_bay_index, kind, value)`，在 detached canonical Layout 上先驗 Feature、再復用原 `share_setting_with_affected_ids`／`edit_setting_for_bays_with_affected_ids`，只有兩步均成功才回傳唯一候選 Layout 與所選目標＋原來源 linked siblings 的真實 stable IDs；任何非法孔／非法 Bay／非法來源不更改原 Layout。透過原 `manufacturing_api.share_and_edit_receiving_shared_setting_with_affected_ids` 與 `ae_engine` 根包同一公開函式，GUI 只保留操作選取、Editor 顯示與一次提交，無臨時 Bay 選取或重算 Feature。
- `tests/test_issue2517_receiving_set_bay_public_transactions.py` 直接走真 `receiving_settings_ports.holes → Hole Editor sync_callback`（僅 stub Engine-approved Editor context 的顯示承載），驗無效 Feature 後 Layout/dirty/selection/project snapshot 全不變、隨後有效 Feature 跨 linked 與選中 Bay 完整同源成功，及 generator、非法後續 Bay 原子拒絕。原單連 Editor/API 與 Family 幾何規則不變；不放行未確認 NFB、FinalScene／CUTTING／製造 DXF。Windows 真機／全櫃驗收、#2517 仍 OPEN。


## [CURRENT] #2517 Receiving 單連編輯／建立連動的完整 Bay dirty 身分須由 Engine 提供（2026-11-06）

- `ReceivingSetBayAdapter.update_setting` 對既有共享參照只標記當前 Bay dirty，實際 Engine `edit_setting` 會更改所有引用同一設定 ref 的 Bay；`share_setting` 會改選中目標的物理 refs，GUI 卻仍只標記來源 Bay。此時刪除尚未保存的目標 Bay 可能缺乏完整保護。即使設定值相同，共享 ref 變更也是實體設定來源變更，不可由 GUI 依值比對來判定。
- 單連編輯復用前已公開的 `manufacturing_api.edit_receiving_shared_setting_for_bays_with_affected_ids`，以一個 Bay 的 selection 執行相同原子 Apply，沿 canonical ref 回傳所有連動 Bay ID。建立連動改由原 `ae_engine.receiving_shared_settings` owner 新增 `share_setting_with_affected_ids`，公開 `manufacturing_api.share_receiving_shared_setting_with_affected_ids`／`ae_engine` 根包同一 callable，保留原 `share_setting` 完整驗證及回傳 Layout 契約，額外回傳操作所涉及的已驗證實體 Bay ID。GUI 只保存 Engine 候選、更新 dirty IDs，不能自行解讀 refs。
- 定向回歸 `tests/test_issue2517_receiving_set_bay_public_transactions.py` 驗非連續選取、相等值但不同 refs、共享 sibling 一次性 editor 更新、非法／無效 Bay selection 原子拒絕、UI 不自組製造身分；保留舊 API、工程 Schema 和既有 Head/Tail Hole Editor 工作流程。此修復不授權未確認的 NFB、FinalScene、CUTTING、DXF；Windows UAT 與 #2517 全範圍仍待驗收。


## [CURRENT] #2517 原生 NFB CSV Candidate Apply 與 FinalScene 共用四角輪廓來源驗證（2026-11-06）

- 原 `receiving_nfb_csv_committed_config.committed_csv_nfb_config` 在 CSV SHA、品牌型號、四個有限座標、CUTTING 與 finished-face Anchor 合法後即可提交 NFBConfig，但未證明四角實際幾何與現行品牌 CSV 的 `opening_corners_xy_mm` 相同。已提交的 Bay 來源可能隱藏變形、交叉或錯誤尺寸的原 Hole Editor 開孔，直到較後面的 FinalScene 才拒絕，破壞 source-only Apply 語意。
- 以原 `ae_engine.receiving_nfb_committed_final_scene.csv_editor_opening_matches_current_source` 作唯一四角輪廓同源比較，重用原 FinalScene 的旋轉、真實平移、循環及逆向頂點序列容忍與 1e-6 mm 頂點容差；非有限數值、錯誤長寬、斜四邊形、自交輪廓一律 fail closed。原 `_source_world_x_from_committed_editor_feature` 亦呼叫同一函式，非新增第二份製造形狀演算法。
- 同源驗證只證明已提交的 CSV 原始孔形，不代表世界 X 已確認；候選仍保存 `UNVERIFIED_BASIS`、`manual_x_mm=None`，不獲任意 Bay／Set 製造授權。兩個實體 Bay Apply 必須全有全無；新增變形反例及合法 90°、平移與循環點序正例。正式 FinalScene、2D／3D、DXF Save→Reload 與 Windows 實機整體驗收維持原 Gate，#2517 仍 OPEN。

## [CURRENT] #2517 NFB 全套品牌 Apply 必須是同一 Engine 原子交易（2026-11-06）

- Receiving Set/Bay Adapter 的 `set_global_brand` 曾由 GUI `deepcopy(layout)` 後自行遍歷全部 Set，各自呼叫單套 `manufacturing_api.rebase_receiving_set_parent_nfb_brand`，再由 GUI 計算 changed／組裝持久化版本；這是跨套已提交物理 NFB parent source 的交易所有權，不能分散在 UI。
- 原 Engine `receiving_nfb_brand_transition` owner 新增 `update_receiving_all_set_nfb_parent_brand(layout, proposed_brand)`；透過 `manufacturing_api` 與 `ae_engine` 根包重匯同一 callable。Engine 先查驗品牌與真實完整 Layout，使用原 `rebase_receiving_set_parent_nfb_brand` 一套套對 detached candidate 執行**全有或全無**的 Set 來源變更，回傳 `(detached_layout, changed)`。GUI 僅提交操作者品牌、保存 Engine 結果，不再自行遍歷實體 Set／推定 NFB 世界 X 是否失效。
- 舊單套、Quantity 版本及 impact preview 公開 API 不變；保持現行 CSV、INHERIT/OVERRIDE、已確認 X 撤銷保護及 Save→Reload Schema。回歸 `tests/test_issue2517_nfb_parent_brand_operations_public_api.py` 驗跨兩套真實已提交來源、與原 Engine 單套 transition 一致、非法後套原子拒絕、原始 Layout 不修改及 GUI API seam。此提交不製造 NFB 孔、CUTTING、FinalScene、DXF；#2517／Windows UAT 與全櫃製造驗收仍 OPEN。


- #2517 單套廠牌提交亦必須為整份 Layout 的公開交易：新增同一既有 Engine owner 的 `update_receiving_one_set_nfb_parent_brand(layout, set_index, proposed_brand)`，由 Engine 嚴格驗證零基底 Set index、原始 Layout 與品牌，再委派原單套 rebase；回傳 `(detached_layout, changed)`。GUI `ReceivingSetBayAdapter.set_brand` 不再自行複製、替換實體 Set，非法輸入無任何中途提交。與全套及 Quantity 版本品牌路徑並存，不新增製造孔、FinalScene 或 DXF 資格；驗收 `tests/test_issue2517_single_set_nfb_brand_atomic_api.py`。

## [CURRENT] #2517 NFB 成對部分出圖實體底板 XYZ 非有限與極大整數一律安全拒絕（2026-11-06）

- 受電箱單／雙層 NFB 的 `內門＋底板` PART_ONLY 正式 DXF，必須由 Engine 先驗證目前 FinalScene 所安裝的每一片真實底板 world XYZ，才能送進原子 DXF Save→Reload。已合併的 PR #2932（單層）和 #2936（雙層）阻擋 NaN、Infinity、布林、字串、缺失座標；但對 `10**1000` 類型的原生超大整數直接呼叫 `math.isfinite` 可產生未捕獲 `OverflowError`，且兩段驗證實作分離。
- 原 `ae_engine.receiving_nfb_pair_export` 增補同一個僅在 Engine 使用的 `_finite_installed_xyz`，同時驗實際與期望的三軸有限實數；無法轉成有限浮點數的原生整數也以正式來源拒絕回傳，不讓相同 local 2D 但失效 3D 安裝資料通過或發生未處理例外。保留 1e-6mm 容差、原真實 FinalScene 與既有 `CSV_PAIR_REAL_BASE_INSTALL_XYZ_MISMATCH`／`CSV_TWO_TIER_REAL_BASE_INSTALL_XYZ_MISMATCH` 錯誤碼。
- 回歸沿用 `tests/test_issue2517_two_tier_nfb_real_base_finite_xyz_export.py` 和 `tests/test_issue2517_single_tier_nfb_real_base_installation_export.py` 真來源／物理場景／DXF 輸出路徑，對每片／三軸超大整數驗拒絕無產物；既有合法三片與兩片 DXF 獨立回讀及 NaN/Infinity 閘門不變。此處不認證整箱 EAR／PAD／NFB MFG-2、Windows UAT，#2517 仍 OPEN。



## [CURRENT] #2517 Receiving 共用設定 Apply 受影響實體 Bay 身分由 Engine 返回（2026-11-06）

- 原 `gui_modules/application/receiving_set_bay_adapter.py::apply_setting_to_bays` 已使用 Engine 原子提交 `edit_receiving_shared_setting_for_bays`，卻仍於 GUI 展開持久化 `settings[kind].refs`，自行判定哪些未選取但連動的實體 Bay 必須標記為 dirty，違反 Set/Bay 來源身份只能由 Engine 擁有的契約。
- 原 `ae_engine.receiving_shared_settings` owner 新增 `edit_setting_for_bays_with_affected_ids`，並以公開 `manufacturing_api.edit_receiving_shared_setting_for_bays_with_affected_ids`（`ae_engine` 根包同一 callable）回傳 `(detached_layout, affected_stable_ids)`。完整選取、型別與 linked reference 仍由既有原子交易先驗證，影響範圍依驗證後**同一設定共享 ref**判定，非依相等設定值。GUI 僅保存 Engine 候選結果與標記回傳 ID；非法來源不可造成局部提交或 dirty 漏記。
- 原 `edit_receiving_shared_setting_for_bays` 回傳型態保持相容，未變更保存 Schema／真實製造尺寸、孔位／2D／3D／DXF。定向 `tests/test_issue2517_receiving_set_bay_public_transactions.py` 覆蓋非相鄰連動、相等但獨立的 ref、一次性 generator、無效選取原子拒絕與 GUI 公開 seam。#2517／Windows UAT 與全櫃驗收仍 OPEN。


## [CURRENT] #2517 Assembly Relief 來源 Joint/FW 簽章只能由公開 Engine 決定（2026-11-06）

- Fold Designer 的 `current_relief_source_signature` 原本在 GUI 直接呼叫私有 `resolved_joint_graph_fingerprint`、`migrate_legacy_snapshot_joints`，並把 box-body 成形 FW 與製造 replay source 的中間欄位自行組裝。這是持久化 Head/Tail 已認證 relief CUTTING 的來源資格，不應由 GUI 決定機械身分。
- 在原 `ae_engine.operator_relief_replay` owner 新增公開 `manufacturing_api.build_operator_current_relief_source_signature`（根包同一 callable）：只接收操作者目前的 scalar/Joint/structure/Fold/part-profile 資料，重用原 Engine Joint Graph 指紋、成形 FW 計算與 `assembly_relief_state.build_current_source_signature` 唯一持久化契約，GUI 只提交原資料／保存結果。既有 replay 資格和 `build_current_source_signature` 簽章保持不變，沒有新增幾何或 CUTTING 放行。
- 回歸 `tests/test_issue2517_operator_relief_signature_engine_public_api.py` 驗既有機械簽章等價、來源獨立、錯型拒絕、JSON Save→Reload 的 stale 失效與 GUI 公開 API seam。#2517、R5 Windows 人工 UAT／全箱製造仍 OPEN。


## [CURRENT] #2517 Quantity GUI 必須完整套用 Engine 投影而非殘留舊 Bay 身分（2026-11-06）

- Quantity 共用 W/H/D、Single 內門 Confirm All 與直接 3D 內門 Confirm All 的 `manufacturing_api.update_common_box`／`preview_quantity_inner_door_confirm` 原本均由 Engine 的 `project_common_box` 產生獨立完整投影，且已移除舊 `_receiving_runtime_selection`。GUI 卻對既有 dict `update(projected)`，不會刪掉 Engine 已移除的 keys，為避免 EAR Z 身分污染又私自 import `RECEIVING_RUNTIME_SELECTION_KEY` 做單鍵 pop。
- 三處 GUI 改以原 dict 身分 `clear()` → `update(projected)` 完整套入 Engine 已驗證的候選快照，不複製實體身分判準、不修改新 Set/Bay 演算法；若 Engine 預檢失敗則不進入這段寫入。回歸 `tests/test_issue2517_inner_door_quantity_confirm_api.py` 驗真 Quantity NFB／native-only 投影、舊 runtime 身分完整消失、原 snapshot 與版本模型均未變更及 GUI 無私有 import。
- 此為 operator snapshot 同步修正，未放行 NFB world X、FinalScene/CUTTING、DXF Save→Reload 或全 16 Bay 製造；#2517 與 Windows 人工驗收仍 OPEN。


## [CURRENT] #2517 Receiving NFB V5 CSV 型號清單更新必須驗實際來源位元組（2026-11-06）

- 原 `fold_designer_composition_receiving.inner_edit.refresh_source` 以 GUI 直接讀 `brand_csv_path(brand).stat()`，只比較 mtime_ns＋size；來源 CSV 替換成相同大小與時間戳的另一合法型號會把舊清單當作最新，且讀取失敗前若已更新簽章，後續可能不再重試。NFB 廠牌 CSV 真實內容與版本身分應由 Engine 唯一辨識。
- 原 Engine `receiving_nfb_v5_source_preview` 新增唯讀公開 `manufacturing_api.project_receiving_nfb_v5_model_catalog_snapshot(brand)`（`ae_engine` 根包同一 callable）；以 `receiving_nfb_numeric_catalog.brand_csv_path` 原來源，取真正 CSV 完整位元組 SHA-256；沿用既有 `numeric_model_refs`／CSV schema 解析，讀取前後位元組不同即拒絕。回傳不可變 `ReceivingNfbV5ModelCatalogSnapshot`，只包含廠牌／SHA／原本的型號參照與 `manufacturing_ready=False`。
- GUI 只消費公開來源快照以 `(brand, source_sha256)` 做 UI 快取；錯誤／缺失清空顯示清單及舊簽章，下次輪詢重試，不自造品牌、模型或 DXF。回歸 `tests/test_issue2517_receiving_nfb_catalog_content_sha_public_api.py` 使用真 CSV 同大小同 mtime 替換、錯誤表頭、解析中替換及 GUI 公開 API seam。此預覽資料不認證實體 NFB world-X、CUTTING／FinalScene、製造 DXF 或 Save→Reload；#2517 與 Windows UAT 仍 OPEN。

## [CURRENT] #2517 受電箱已確定實體 Bay W/H/D 同尺寸分組歸公開 Engine（2026-11-06）

- 原 `receiving_multi_settings_window.dimension_group_summary` 在 GUI 把持久化 Bay 的 W/H/D 轉成 float 並自行決定哪些真實盤為同尺寸，這是已保存物理來源的業務分類而非 Canvas 縮放規則。本次將該規則遷至原 `ae_engine.receiving_layout.project_receiving_bay_dimension_groups`，透過 `manufacturing_api` 與根包公開同一函式；GUI 僅提交原 Bay 清單、顯示已確定尺寸／數量。
- Engine 重用原 `_number` 查驗各實體 Bay 寬／高／深為正且有限、非布林的來源值；回傳依第一個出現順序排列的 `((W,H,D), (零起算真實 Bay 索引...))`，保留不相鄰的同尺寸不同盤身分，不修改持久化 Set/Bay。實際修改每連尺寸仍走原 Engine 寫入交易；分組投影不是 CUTTING／NFB／FinalScene／2D／3D／DXF 製造認證。
- 新 headless／GUI seam 測試涵蓋真三 Bay、同尺寸跨位置、不同軸分組、非法來源拒絕與無副作用。本項完成不代表 #2517 整體及 Windows 實機驗收結案。

## [CURRENT] #2517 Receiving NFB 內門型號層序列化與品牌選項共用公開 Engine（2026-11-06）

- Fold Designer 的 NFB 單／雙層 model-slot preview、Confirm、取消差異原直接匯入內部 receiving_shared_settings 的 switch_filenames_in_layer/pack_switch_layer。本次 manufacturing_api.receiving_nfb_switch_filenames_in_layer 和 pack_receiving_nfb_switch_layer 直接公開既有相同 Engine callable，ae_engine 根包也只重匯同一 owner；不新增任何 GUI 型號公式。
- 同一 Modal 的本層／單顆品牌 Combobox 使用既有 manufacturing_api.receiving_operator_switch_brand_choices()，不再讀私有 RECEIVING_SWITCH_BRANDS。保留原繼承文字、多顆 NFB occurrence、歷史 DXF 與原生 CSV 型號儲存型態，無效輸入仍由 Engine 拒絕。
- 先前 Quantity 舊版雙欄位高度預設仍直接依賴 GUI 所見內部 SETTING_DEFAULTS；本輪真 Tk CI 發現移除匯入會 NameError，因此由 manufacturing_api.receiving_inner_door_legacy_layer_height_defaults() 唯讀回傳原 Engine 預設的脫離副本（非新 Y 公式），保留舊專案相容。AC-47 取消編輯器的隔離回歸也必須注入真實公開 API，使用合法歷史 DXF 型號而非假來源字串。
- 此為來源序列化／選項的公開邊界，不認證 NFB 世界 X、正式 FinalScene、CUTTING、DXF Save→Reload 或整櫃製造；#2517 與 Windows UAT 未完成。

## [CURRENT] #2517 受電箱相鄰實體 Bay 接合對齊選項歸原 Engine Policy（2026-11-06）

- 原 `receiving_set_bay_controls._build_receiving_settings_editor` 在接合控制建立與刷新兩個時機，GUI 直接比較兩連 `depth`／`height`，決定可編輯的前後齊／上下齊選項；但真正 Apply 本來就使用 `receiving_layout.receiving_joint_alignment_editability`。兩份判斷不應分裂。
- 在原 Receiving Set/Bay/Joint Engine owner 新增唯讀 `project_receiving_joint_alignment_editability(set_row, joint_index)`，以已保存物理 Set row 查驗 joints/bays 真實相鄰身份、索引型別、正且有限的兩連 D/H，回傳 `depth_alignment`／`height_alignment` 是否可編輯；原完整 Layout `receiving_joint_alignment_editability(layout, set_index, joint_index)` 經 normalize 後委派**同一份** Engine 函式，GUI 也只消費公開 `manufacturing_api` 結果。不可讓 GUI 為判定接合而造假的 Set/Layout。
- 未認證或破損來源應 fail closed；Tk 的 disabled/readonly 只呈現原 Engine Policy，`update_receiving_joint_alignment` 唯一實體提交權威不變。此改動不產製 Join 幾何／CUTTING／FinalScene／DXF，不解除 NFB/Factory/Registry gate；#2517 與 Windows 實機總驗收維持 OPEN。



## [CURRENT] #2517 Receiving 內門候選型號與套連配置的單一公開 Engine 來源資格（2026-11-06）

- Fold Designer 內門候選 Apply／Quantity 配置原本在 GUI `verify_inner_models` 自行把舊版「開關索引.csv」DXF 檔名與原生 CSV `nfbv5:<brand>:<model>` 型號清單合併為來源白名單，逐層判定當前 Parent Brand。這是已保存實體 NFB 型號的來源資格，不是展示規則。現在由 `ae_engine.receiving_inner_door_candidates.validate_receiving_inner_door_source_models(config, parent_brand)` 作唯一 owner；`manufacturing_api`／根包公開同一 callable。Engine 先使用原 `validate_door_config` 正規化 detached candidate，再以原 `numeric_model_refs` 與 `model_filenames` 兩套正式來源核對，保留同層重複實體孔、兩層與舊專案相容，來源缺失／跨品牌／不合法拒絕且不變更呼叫者。
- Fold Designer 的候選 `inner_validate_quantity` 改用公開 `manufacturing_api.validate_receiving_inner_door_allocation`（原 `receiving_inner_door_pairing.validate_inner_door_allocation` 原件），版本標籤改用既有 `receiving_candidate_version_label`，GUI 不再直接 import 這兩個 Engine 內部 owner。單 Bay／數量 Apply 仍走原本 Engine 原子 Set-Bay 交易；未授權未確認 NFB world X／CUTTING／FinalScene／DXF、未放行 source-only CLI。驗收 `tests/test_issue2517_inner_door_candidate_source_public_api.py` 檢查 Vault 無關的 Receiving 舊 DXF／V5 型號、跨品牌失效、兩孔不去重、配置拒絕、GUI 同源，#2517／Windows 實機驗收仍未全部完成。


## [CURRENT] #2517 Receiving 共用設定相同 Bay 與品牌清單只由 Engine 投影（2026-11-06）

- 受電箱「每連設定／共用設定」GUI 原本 `receiving_set_bay_controls._build_receiving_settings_editor.refresh` 直接 import `receiving_shared_settings.setting_value`，自行逐 Bay 掃相同值，並從私有 `receiving_switch_layout.RECEIVING_SWITCH_BRANDS` 取得候選品牌。這類包含實體 Set/Bay 儲存值與連動共用設定來源的業務判斷必須由 Engine 直接提供；GUI 僅留中文標示、顯示高亮、待操作選取與 Call API。
- 在原 Engine 共用設定 owner 增加唯讀 `project_receiving_shared_setting_group(set_row, bay_index, kind, *, preview_value=未傳)`，回傳獨立已驗證值與**零起算真實 Bay 索引 tuple**，重用原 `setting_value`／`validate_setting`，只比較實際儲存參照／輸入值，不重建來源幾何或修改保存狀態。使用者暫選 `back_panel_mode`／`inner_door_layers` 時可提交明確 preview 值；不傳與明確傳 `None` 不可混淆。索引非法、錯型、未知設定均 fail closed，來源 dict 在任何預覽後不變。品牌欄使用 `manufacturing_api.receiving_operator_switch_brand_choices`，來源仍唯一為原 Engine `RECEIVING_SWITCH_BRANDS`。
- 正式 `edit_receiving_shared_setting_for_bays`、`share_receiving_shared_setting`、`unlink_receiving_shared_setting` 的實體 Bay 原子交易仍為唯一 owner，UI 不自行更改參照；維持原欄位預覽、中文索引及原操作。此唯讀投影不增加任何 NFB 來源認證、FinalScene／CUTTING、DXF、Save→Reload 放行；#2517 與 Windows 全範圍實機 UAT 尚未結案。


## [CURRENT] #2517 原生 NFB CSV 已提交來源的雙實體孔位身份不可矛盾（2026-11-06）

- `ae_engine.receiving_nfb_committed_final_scene._source_world_x_from_committed_editor_feature` 會從原 Hole Editor `NFB_CSV_SOURCE` 恢復操作者已放置的 world X，以相同正式 `FinalScene` 進行 2D／3D／DXF。既有合法來源可以**僅有**實體 `hole_id`，或僅有 `layer_index/slot_index`；但當兩組同時存在時必須指向**同一顆**實體孔，不能因 `hole_id` 符合就跳過另一組相反的來源槽位，更不能讓 bool、缺半組 tier/slot 借到相同數值的實體身分。
- 在原 Engine owner 增加 `NFB_CSV_EDITOR_PHYSICAL_SLOT_IDENTITY_CONFLICT` fail-closed，拒絕同孔 ID 指到別槽／同槽指到別孔 ID 的已提交混合來源，阻止跨槽 world X 污染實體內門／底板 CUTTING。未變更正式 CSV 尺寸、已確認 X、單一 Family／PartSpec／FinalScene 或製造放行。回歸 `tests/test_issue2517_nfb_csv_editor_hybrid_identity_gate.py` 使用原真實來源的多顆 NFB 和 `apply_committed_csv_v5_to_canonical_parts` 核對來源原子拒絕，並保留只帶一種身份的舊專案。






## [CURRENT] #2517 受電箱多連候選版本標籤使用單一公開 Engine（2026-11-06）

- `receiving_multi_settings_window` 中 2D 已套用 Bay 標籤、候選編輯器及操作按鈕都只呼叫既有 `manufacturing_api.receiving_candidate_version_label(version_id)`，不再 GUI 直接 import `receiving_hole_candidates.version_label`。版本 ID 語意與中文顯示名稱均由原 Engine owner 確認，GUI 不製造或解析新版本 ID。
- 只移動 UI 顯示責任，不動 candidate Source／Apply、Set/Bay、受電箱 Door/NFB、FinalScene 或 DXF 認證。#2517 尚未全部驗收。


## [CURRENT] #2517 Quantity 候選配置 2D 示意門縫不得由 GUI 硬編（2026-11-06）

- 受電箱封頭尾「數量配置」草稿只有連數與候選版本選取，尚無每一實體 Bay 的已確認 Door 拓樸。原 `receiving_quantity_allocation_ui.ReceivingQuantityAllocationUI.paint` 以 GUI 常數 `1100/1600` 決定上下門示意線；現須呼叫既有 `manufacturing_api.project_receiving_operator_bay_door_split_ratio(None)` 使用 Receiving Family 預設的純示意比例，不能在 GUI 重製製造尺寸推導。
- 已存 Set/Bay 的 2D 示意圖仍必須把實體 Bay 交給同一 Engine 公開 API；複雜門格不可假畫一條單純分割線。此批只更換 count-only 草稿的唯讀顯示來源，不更動實體 Door／NFB Features、Factory／FinalScene、3D、DXF 或 Save→Reload 放行；#2517／Windows 實機 UAT 維持未結案。


## [CURRENT] #2517 Receiving Head/Tail 候選數量配置預檢歸公開 Engine（2026-11-06）

- `receiving_quantity_allocation_ui._ready_to_apply` 只提交當前版本 inventory、Set/Bay 數量、Head/Tail role、數量與配置到 `manufacturing_api.validate_receiving_candidate_quantity_preview`；不得在 GUI 推算下一版本 ID、重組候選實體 Feature 來源，或捏造 `None` Bay 拓樸代替 Engine。
- Engine 仍以原本 `receiving_hole_candidates.normalize_candidates`、`receiving_quantity_allocation.validate_quantity_allocation` 和 `receiving_assignment_core.validate_positions` 驗來源／身份／套連／數量／配置，拒絕非法或 stale 來源，純唯讀且不變更 Project。GUI 原本可用的真實 `validate_quantity` port 維持優先；缺少時才用此唯讀預檢。版本 role 與顯示標籤改用 `manufacturing_api.validate_receiving_candidate_role` 和 `receiving_candidate_version_label` 同一 Engine owner。
- 正式 Head/Tail 版本 Apply 仍走既有 Engine 原子 Set/Bay 交易，候選預覽不能取得 CUTTING／FinalScene／DXF 或 Registry 認證資格。#2517 尚未結案。

## [CURRENT] #2517 NFB 原始 Hole Editor 實體孔位恢復須驗完整 CSV 輪廓（2026-11-06）

- 已提交的現行 CSV NFBConfig 若 `manual_x_state=UNVERIFIED_BASIS`，正常受電箱 FinalScene 的 `ae_engine.receiving_nfb_committed_final_scene._source_world_x_from_committed_editor_feature` 只有在**原實體內門**上找到本次來源 CSV SHA／品牌型號／實體層槽與 Hole Editor 已提交 `NFB_CSV_SOURCE`，且實際四角點經保存旋轉後仍為**同一份 CSV 矩形輪廓**、Y 基準一致，才可回收操作者已放置的 world X。原實作僅比四邊長，會錯認邊長相同的斜四邊形為原 NFB；現必須比整個四點順序（允許起點輪轉／順逆序）及 `rotation_deg` 與保存 NFB row 的一致性；僅允許正常位置平移，拒絕非矩形、錯角度、穿插線、非有限座標及來源變動。
- 原有 `_submitted_csv_holes → apply_committed_csv_v5_to_canonical_parts → trial_configured_nfb_v5_inner_door_render_data` 為唯一 Engine 真實 2D／3D FinalScene；輸出只可用已驗證的同一個 `PartRenderData` 經原 `save_scene_dxf`／`verify_saved_part_render_data_dxf` 回讀。不能將編輯器輪廓被改壞後，用 CSV 型號偷偷重畫一個似乎合法的孔／底板螺絲；來源錯即 fail closed，無任何非預期 DXF 產生。原已確認獨立 X 不借用此來源恢復路徑，不更改 NFB 產品尺寸或 Factory Rule。
- 對照回歸 `tests/test_issue2517_nfb_original_editor_contour_physical_source.py`：真實原 CSV 兩顆 NFB、合法平移及 quarter-turn、同長邊斜四邊形、旋轉資料分歧、同源 FinalScene 與 DXF Save→Reload。這是既有製造來源防護補強，不表示外部 CADSplit source-only export 已認證、整套 #2517／Windows UAT 已完成。


## [CURRENT] #2517 NFB Parent Brand 的單只版本／全 Set-Bay 來源交易改由公開 Engine（2026-11-06）

- 原 Receiving GUI `single_brand`／`set_single_brand` 自行讀取 `QuantityModel`、舊共用箱品牌及版本遷移，`preview_parent_brand_impact` 直接呼叫 `receiving_nfb_brand_transition.saved_parent_new_reselections`，並逐 Set/Bay 決定實體 NFB 受影響顆數。這些是已提交物理來源與版本權威，並非 GUI 展示規則。
- 既有 owner `ae_engine.receiving_nfb_brand_transition` 新增 `project_receiving_quantity_nfb_parent_brand(snapshot)`、`update_receiving_quantity_nfb_parent_brand(snapshot, proposed_brand)`（回傳獨立候選快照與 changed，支援舊 common-box→獨立版本品牌原子遷移）以及 `project_receiving_parent_brand_change_impact(source, proposed_brand, *, mode)`（只計被新品牌影響的已提交 INHERIT 實體孔；選定 Quantity 版本或全部已保存 Set/Bay）。
- `manufacturing_api` 與 `ae_engine` 根包匯出相同 Engine owner；GUI 只選作業模式、送目前儲存來源、顯示 warning，成功時才持久化 detached 候選。非法品牌／模式、破壞的 Quantity/Layout 資料均 fail closed。保持 NFB 已確認世界 X 撤銷保護／個別覆寫／版本與實體 Bay 隔離；此變更**不**產出新的孔位、PartSpec、CUTTING、FinalScene 或 DXF 製造資格。驗收 `tests/test_issue2517_nfb_parent_brand_operations_public_api.py`；#2517 整體與 Windows UAT 未因此結案。

## [CURRENT] #2517 Receiving NFB Confirm 來源／型號資格由 Engine 獨立驗證（2026-11-06）

- 原 `gui_modules/application/fold_designer_composition_receiving.py::inner_edit.confirm` 直接用 `is_numeric_model_ref/parse_numeric_model_ref`、`effective_nfb_slot_brand`、CSV 型號清單及草稿角度／X 旗標，判斷實體槽位與品牌是否相符、舊版候選是否會丟失逐顆資料。這些是 Engine 來源／儲存資格，不是 GUI 顯示判斷。
- `ae_engine.receiving_nfb_ui1a_edits.plan_receiving_nfb_editor_confirm(draft, current, chosen, *, layer_count, embedded, parent_brand)` 是唯一 owner，`manufacturing_api` 與 `ae_engine` 根包 re-export **同一函式**。回傳 immutable `ReceivingNfbEditorConfirmPlan(current_numeric_editor, has_source_models)` 只用於選擇原生 CSV Hole Editor 暫存或舊候選路由。保持既有 CSV 型號／有效品牌、實體層／slot 多重集比對、舊 DXF 名稱、Override／rotation／unverified-X 不得失真以及失效來源拒絕。
- GUI 僅提交目前操作選取及實際 Parent Brand，Confirm 仍由原 Hole Editor 採 `editor_nfb_features_from_csv` 產生可編輯來源草稿及原儲存交易。此計畫**不是**正式 NFB 世界 X、實體 CUTTING、FinalScene 或 DXF Save→Reload 的製造認證；不新增 exporter、Factory Rule 或另一份產品幾何。驗收 `tests/test_issue2517_receiving_nfb_confirm_source_public_api.py`；Windows UAT 與 #2517 全範圍仍需另外核對。

## [CURRENT] #2517 Fold Designer 內門 Single/Candidate Confirm 來源設定改走公開 Engine（2026-11-06）

- `fold_designer_composition_receiving.py::inner_edit` 的 embedded staged settings 回復只呼叫 `manufacturing_api.validate_receiving_inner_door_config`，不直接 import 私有 `receiving_inner_door_candidates.validate_door_config`；此公開入口仍委派同一 Engine 驗證 owner。
- `launch_inner_editor.confirmed` 針對 Set/Bay Single 與未套用 Candidate 皆使用既有 `manufacturing_api.prepare_receiving_inner_door_physical_confirm` 完整驗證實體內門 ID、來源設定、Feature，GUI 禁止自行複製／組合 `features[part_key]` 作為加工權威。Single 仍交原 Engine atomic Bay Apply；Candidate 只存獨立版本庫，未 Apply 不寫 Bay。Quantity 原預檢與 NFB CSV 確認交易不變，兩者均未授權 DXF。

## [CURRENT] #2517 內門直接 Confirm All 的實體設定組裝歸公開 Engine API（2026-11-06）

- 受電箱內門 Hole Editor `receiving_inner_door_hole_editor.open_inner_door_hole_editor` 在直接 Set/Bay Confirm All 不能私有 import `receiving_inner_door_candidates.validate_door_config`、也不能在 GUI 依 `part_key` 自行組合 `features` 製造設定。須交 `manufacturing_api.prepare_receiving_inner_door_physical_confirm(staged_config, part_key, final_features)` 用既有實體身份 `door_display_part_role` 與既有 `validate_door_config` 驗證、深複製並產出 detached config，GUI 只交回既有 `ReceivingSetBayAdapter.apply_inner_door_candidate_to_bays`。非法實體門板或非法設定拒絕；任何拒絕之前不可更動持久化 Bay。
- 此公開 API **只準備來源設定**，不授權 CSV NFB、FinalScene 或 DXF。已驗來源、已提交物理位置、Set/Bay／版本交易與製造 Save→Reload 保留原 Engine Gate；原 Quantity Confirm All `preview_quantity_inner_door_confirm` 不在本批重做。

## [CURRENT] #2517 Receiving 已驗來源 NFB Bay 提交／複製公開 Engine 接線（2026-11-06）

- GUI `fold_designer_composition_receiving.py::nfb_transaction_ports` 原直接引用 `receiving_nfb_ui1b_bridge` 的 `NfbVerifiedDraftSubmission`、`assert_live_verified_nfb`、`submit_live_verified_nfb`、`copy_live_verified_nfb`。今改用 `manufacturing_api` 公開原件，套件根 `ae_engine` 同一物件；原 Engine 世界 X、來源 DXF SHA、Set/Bay/version、實體 Door、來源變更撤銷、獨立目標檢驗及 #1500 原子 Submit/Copy 不變。
- GUI 只保留 transient proof 與 Confirm/Cancel/Undo，不能以暫存 READY 當製造核准或從來源連借目標連物理 X。正式 CUTTING／FinalScene／DXF Save→Reload 仍循既有製造 Gate；`tests/test_issue2517_nfb_verified_transaction_public_api.py` 加 #1500 原 Engine／Tk 測試覆蓋。#2517 全部 GUI 入口及 Windows UAT 尚未完成。

## [CURRENT] #2517 Receiving 原始內門 NFB CSV 開孔草稿沿用公開 Engine（2026-11-06）

- `gui_modules/application/fold_designer_composition_receiving.py` 的 NFB 即時加入預覽及內嵌確認原本直接 import `receiving_nfb_csv_editor_features.editor_nfb_features_from_csv` 私有來源。兩處改為 `manufacturing_api.editor_nfb_features_from_csv`，套件 `ae_engine.editor_nfb_features_from_csv` 與該公開函式同一物件；原本實體內門、CSV 型號、工作面、碰撞檢查仍由現存 `ae_engine.receiving_nfb_csv_editor_features` 唯一 Engine owner 執行。
- 回傳 `NFB_CSV_SOURCE` 是原始 Hole Editor 可編輯的 **DRAFT** `ProfileFeature`，initial X 僅作暫存排版，既有 Confirm／Cancel／Undo、已確認來源、世界 X、FinalScene、DXF Save→Reload 與製造資格守門不因改成公開匯出而解除。不得把可 import 及可預覽當成正式 NFB 加工認證。新邊界回歸 `tests/test_issue2517_receiving_csv_editor_public_engine_api.py`，原生 `tests/test_issue1504_live_second_nfb_main_canvas.py` 沿用。

## [CURRENT] #2690／#2692 受電箱多板件合併 DXF 使用原 Engine 箱身組裝拓樸（2026-11-05）

- 原 `ae_engine.composed_panel_dxf._source_rows` 在將 `BoxBodyStructureRenderData.pieces` 展成實體單片後，直接照任意傳入順序橫排。受電箱多連 `export_current_receiving_multibay_dxf` 甚至在驗證完 per-Bay 平板後只把 `(namespace, part_id, render)` 交給 `commit_verified_receiving_groups`，遺失原 `BoxBodyPieceRenderData.formed_w_start / formed_y_offset / role` 組裝 owner，可能造成順序或背板上下相對位置錯誤。
- 改為 Engine `composed_panel_dxf.save_composed_panel_dxf` 在有 `BoxBodyStructureRenderData` 時，依真實 `formed_w_start` 與 canonical role 順序排列箱身物理展開板；`formed_y_offset` 僅用於整片 flat 的剛體上下平移，其他非箱身板件仍放旁邊。各平板之間保留 60 mm 最小間距；**不能**把 3D/world XYZ 或已彎曲實體位置投影成製造 UV，也不重算任何 CUTTING／BEND／孔位或材質。
- Receiving group sink 將 `physical_bay_geometry_provider` 原件 `BoxBodyStructureRenderData` 作為唯讀拓樸 owner 與已驗證 flat 一併交給合併器；不可用 GUI 複製幾何或以 owner 取代實際已驗證的 FinalScene。owner 身分不吻合、位置非有限數等一律 fail closed，來源 SHA／NFB／EAR／PAD Gate、逐片及整組 DXF Save→Reload、原子提交／rollback 不放寬。原 `PER_SET`「第N套.dxf」、`ALL`「全部.dxf」、`END_VS_MIDDLE`「頭尾盤／中間盤.dxf」不變，Set/Bay 與盤名身分不變。
- Windows R5-2600 的 RED 原生重現與新候選 regression：`tests/test_issue2690_composed_panel_dxf.py`、`tests/test_issue2692_receiving_grouped_dxf.py`；獨立 Windows pytest 邊界 25 passed，後續 GitHub exact HEAD Product Regression 與 Windows 接線仍須全綠後才能合併。此排版修復不代表 16 盤來源完整製造放行，#2517 維持 OPEN。

## [CURRENT] #2517 已驗證 NFB 來源部分出圖清單只由 Engine 定義實體角色（2026-11-05）

- 原 NFB 多連 GUI `physical_manifest` 在已驗來源分支自行用 `NfbActualPart` 為 `scope.inner_door_part_id`／`base_plate_part_ids`／`middle_plate_part_ids` 分派物理角色，並呼叫內部 `derive_nfb_partial_export_manifest`、依 `manifest.whole_ready` 自行組顯示狀態。這些身份與部分製造資格是 Engine owner，不屬 GUI。
- 正式來源新增公開唯讀 `manufacturing_api.project_receiving_verified_nfb_partial_manifest(scope=..., saved_bay=..., set_brand=..., source_inventory=..., verified_inner_door=..., source_path=...)`，在原 `ae_engine.receiving_nfb_export_manifest` 內組裝**既存且經驗證** `NfbPhysicalScope` 指向的實體角色，仍由原 `derive_nfb_partial_export_manifest` 驗來源 SHA、NFBConfig、實體 `may_export` 和缺料狀態；只回原格式報告供 GUI 顯示，不新增第二條 DXF 管線、無其他板件推測，不變更正式 `require_export`。
- GUI 僅呼叫公開 API 並保留過期證據撤銷與失效阻擋；`WHOLE_READY` 只針對來源 NFB 清單，不聲稱整箱 PAD／焊接工藝驗收。對照測試 `tests/test_issue2517_receiving_verified_nfb_manifest_public_api.py` 驗報告與原 Engine 等價、真來源 SHA 過期拒絕，以及 GUI 無實體角色造表。#2517 全 GUI 入口仍未結案。

## [CURRENT] #2517 NFB V5 多連實體清單／獨立預覽來源改由公開 Engine（2026-11-05）

- `gui_modules/application/fold_designer_composition_receiving.py::open_receiving_multi_settings.physical_manifest` 原直接 import `receiving_nfb_v5_diagnostics` 與 Family／BasePlate 私有來源，依 UI 內的單層／雙層判斷編造物理依賴，並自行淺複製 Bay 強制 `nfb_config_submitted=False` 以預覽不受 NFB 影響的 Head/Tail／Door；GUI 不該決定實體板件身份與來源有效性。
- 原 `ae_engine.receiving_nfb_v5_diagnostics` owner 現提供公開 `manufacturing_api.project_receiving_current_v5_nfb_physical_diagnostics(saved_bay, physical_snapshot=..., set_id=..., bay_id=..., version_id=..., physical_parts=...)`，從 **既有** Family 內門／實體底板來源與同一 Bay 實際 render Scene 判定 dependencies／unaffected／missing roles，再交原 `current_v5_nfb_diagnostics` 做逐顆 CURRENT CSV source/revision 只讀狀態。沒有真實 Scene 或物理來源不得顯示 NFB 不受影響的可加工板件。
- `manufacturing_api.project_receiving_nfb_unsubmitted_preview_layout(layout, set_index=..., bay_index=...)` 在 Engine 先驗證真實 index、完整隔離複本，只為唯讀查核原本獨立板件。不得改動已存 Bay、取代 PartSpec、跳過 NFB 來源守門、將 DRAFT／RECHECK_ONLY 提升為出圖資格。GUI 原 `nfb_physical_bay_snapshot` 改用既有公開 `manufacturing_api.project_receiving_bay_legacy_aliases`。新測試 `tests/test_issue2517_receiving_nfb_v5_manifest_public_api.py` 與 AC-09/24 原測試一起核對；#2517 全入口／Windows UAT 未因此完成。

## [CURRENT] #2517 Receiving CSV NFB 內門＋底板部分出圖來源實體權威（2026-11-05）

- 受電箱多連 NFB GUI 的 `current_csv_pair_source` 原直接呼叫 `ae_engine.receiving_nfb_committed_final_scene._submitted_csv_holes/_existing_source_specs`，自行決定哪一組 `base_plate`／`base_plate:nfb_layer:N` 具備來源，並在 PART_ONLY 出圖入口再次私讀 `layer_count`。這是 Engine 物理板件身份判斷，不屬於 GUI。
- Engine 唯一 owner `ae_engine.receiving_nfb_committed_final_scene.project_receiving_committed_csv_nfb_pair_layer_count(snapshot)` 經公開 `manufacturing_api` 輸出 `1`／`2`（來源與每層實體 ID 完整匹配）或 `None`（未具備）。沿用原 `_submitted_csv_holes` 來源／Set-Bay 追溯及 `_existing_source_specs` 實體來源檢查；來源驗證例外原樣往外傳，不能退回空白孔或猜底板。
- GUI 只用該 API 決定來源狀態與單層既有 PartSpec 是否需要查詢；實際 `export_current_csv_nfb_door_base_pair` 仍重新驗證獨立來源、正式 FinalScene、CUTTING、DXF Save→Reload。此唯讀投影**不授權**全箱或 PART_ONLY 自動製造，不建立新底板、NFB 開孔或第二條幾何路徑。契約／GUI 邊界測試為 `tests/test_issue2517_receiving_committed_csv_pair_public_api.py`；#2517 全入口驗收仍未完成。

## [CURRENT] #2517 Receiving 封頭尾候選版本 Apply 高亮 Bay 原始身分不能被 GUI 去重（2026-11-04）

- `gui_modules/application/fold_designer_composition_receiving.py::apply_candidate` 原先先做 `tuple(sorted(set(highlighted)))`，會把 `(1, True)` 折成看似合法的 `(1,)`，導致既有公開 Engine `apply_receiving_endcap_candidate_to_bays` 的真整數 Bay／Set index 拒絕被 GUI 預處理繞過；含不可雜湊項目也在 GUI 層意外拋 `TypeError`。不准把操作選取預先去重當成實體來源驗證。
- GUI 現將原始 `highlighted` 與 Candidate Feature、版本 ID 不改寫地送交既有 `ReceivingSetBayAdapter.apply_candidate_to_bays` → `manufacturing_api.apply_receiving_endcap_candidate_to_bays`，由 Engine 一次檢驗 Set/Bay、bool、非整數與錯誤版本，再沿原 Head/Tail shared-ref unlink／Feature 孔位套用單一事務；成功後才更新來源快取／製造預覽。沒有建立第二條候選交易或製造 API。
- 測試 `tests/test_issue2517_receiving_endcap_single_apply_engine_api.py` 另外驗證真假 Bay 同時高亮、非法非可雜湊選取、Save→Reload／共享版本的原有契約與 GUI 不可靜默過濾。#2517 完整 GUI/CADSplit 製造驗收仍未完成，不發布 X。

## [CURRENT] #2517 Receiving 多連共用設定 Apply 必須為一筆 Engine 原子交易（2026-11-04）

- 實際查核：`gui_modules/application/fold_designer_composition_receiving.py::receiving_settings_ports.change` 原本依高亮順序直接 `adapter.select_bay`／`adapter.update_setting`，若第 N 連失敗，前面 N−1 連已改寫、dirty／select 狀態可能殘留，不符合同一次操作多實體 Bay 全有或全無契約。
- 改為公開 `manufacturing_api.edit_receiving_shared_setting_for_bays(layout, set_index=..., bay_indices=..., kind=..., value=...)` 由現有 `ae_engine.receiving_shared_settings` 在未改寫原值的候選版檢查全部真實 Set/Bay index（嚴拒 bool／float／重複／越界）、Setting 型別、shared references，再一次 normalize／commit。已連動的相同 ref 仍以原 Engine 模式同步變更；GUI adapter 僅記錄所有受同一 ref 影響的 stable Bay IDs 為 dirty，且失敗時 layout／selection／dirty 均不可動。
- 此改造不新增製造輸出、NFB／Door 幾何、CUTTING/BEND、DXF 或人工拆圖 API；現有單連、共享、解除連動契約保留。回歸 `tests/test_issue2517_receiving_set_bay_public_transactions.py` 核對合法批次與舊 Engine 單連等價、後段無效 Bay 全拒、linked setting、GUI 入口不再逐連寫入。正式放行仍需 GitHub exact-head 產品回歸及有授權的實機測試證據；不宣稱 #2517 全部完成。

## [CURRENT] #2517 NFB 跨 Bay Copy 路由與 EndCap Joint 摘要由 Engine 唯一投影（2026-11-04）

- NFB 的操作者高亮連選取（必須同一 Set 內兩個不同且有效的真實 Bay，布林／浮點／不可雜湊異常值拒絕）由現有 `ae_engine.receiving_nfb_ui1b_bridge` 的 `select_operator_nfb_copy_bays` 和 `plan_operator_nfb_copy_direction` 經公開 `manufacturing_api` 提供。GUI 只持有 transient `pending_verified_nfb` 並在每次檢視／點擊時呼叫既有 `assert_live_verified_nfb` 取得即時有效的目標 Bay 集合；**已提交來源、獨立驗證目標及唯一方向**的物理資格僅由 Engine 計畫決策，並保留 `copy_live_verified_nfb`／`copy_submitted_nfb_bay` 的原子交易、重新驗來源、Confirm/Cancel、Save→Reload、Undo。任何沒有獨立世界 X／實體孔 ID／原 DXF 驗證的目標都不可借來源連的 X，也不解鎖正式 DXF。
- 受電箱 EndCap 固定截角的螢幕摘要由公開 `manufacturing_api.project_operator_fixed_corner_summary` 向既有 Family Registry `canonical_family_name` 與 `assembly_joint.edge_relation_for_part` 投影，`受電箱`／`RECEIVING`／`receiving` 為同一個實體 Family，不因 UI 字串大小寫不同而誤顯金庫型固定截角；頭尾端 BOTTOM WRAP／INSERT 等文字必須隨當下 Joint source。非受電箱或非 Head/Tail 沿用原 GUI 的既有展示文案；此 API 僅提供 readonly 說明、不新增幾何公式、Corner Registry、PartSpec 或製造出圖通道。
- 這是 #2517 兩條已確定越界的 GUI 判斷移轉，**不是**全部 GUI 入口驗收完成，不發布 X。定向測試 `tests/test_issue2517_gui_nfb_copy_and_corner_owner.py` 加既有 `test_issue1500_nfb_operator_gui_transactions.py`、`test_receiving_cabinet_2d.py` 與一體 Engine 回歸；正式合併仍須 exact-HEAD GitHub Actions 全綠及 R5-2600 Windows 驗證。

## [CURRENT] #2517 CADCraft 隔離交換與數量模式 Head/Tail Hole Editor 的 Engine 單一來源（2026-11-04）

- 原 `gui_modules/editors/cadcraft_command_preview_bridge.py` 在空 Hole Editor 畫面直接使用 `ezdxf.new` 建立毫米 DXF 與 PNG，並在 GUI 呼叫 `resolve_surface_features` 自行核對正式孔位。現統一由既有 `ae_engine.cadcraft_exchange_proof` 公開 `manufacturing_api.project_whd_cadcraft_command_instructions`、`save_blank_cadcraft_exchange_drawing` 完成來源驗證／輸出；GUI 僅調度隔離文件和 CADCraft CLI。空白交換 DXF 僅含有效 mm 標頭且無製造圖元，搭配白色 PNG；使用 exclusive create 避免覆寫已存在輸出，任何半途失敗清理僅限本次新建交換檔。其結果仍是 CADCraft 未確認候選／CHECK，不是正式 PartSpec、CUTTING/BEND 或製造 DXF；既有 Hole Editor Confirm/Cancel/Undo 和 Manual Return 驗證仍為獨立門檻。
- 原 `gui_modules/application/quantity_version_ports.py::holes` 在 GUI 用 `resolve_endcap_finished_face_guide`、`feature_surface_from_rect`、`RectGuide` 直接構造受電箱／金庫型數量版本 Head/Tail 的物理編輯面，並直接 import `receiving_quantity_box` 驗證。現在統一走公開 `manufacturing_api.project_operator_quantity_endcap_hole_editor_geometry(snapshot, role=...)`，委派 Engine 既有 `project_operator_hole_editor_endcap` 及 `normalize_common_box`；Receiving Family 別名使用 Registry，缺少共用箱體仍由 Receiving Family 800/1600/350 預設，但不得借用過期 Set/Bay 或主 GUI W/D，明確損壞共用箱體、bool/NaN/Inf/非正 T/W/D 直接拒絕。版本 Hole Editor 提交前仍由公開 `manufacturing_api.require_valid_operator_quantity_features` 驗證，版本 ID、Cancel、Confirm、實際 DXF 都不建立第二條幾何權威。
- 定向驗收重用 `tests/test_issue1959_cadcraft_append_holes.py`、`tests/test_issue2517_fullscan_gui_source_projection_batch.py`、`tests/test_issue1465_quantity_ui.py`、`tests/test_issue2517_endcap_hole_editor_shared_engine_source.py`；等價 Engine 輸出與 GUI 入口、DXF Save→Reload、真實 Tk、壞來源拒絕均須通過。這只消去兩條已證實越界，不宣稱 #2517 整張完成。


## [CURRENT] #2517 受電箱 Set/Bay 2D 示意門分割由 Engine 已存 Door 拓樸投影（2026-11-04）

- `gui_modules/application/receiving_multi_settings_window.py::paint_connected_bays` 原本在已保存 Bay Door 600/1000 mm 時，仍以 GUI 固定 1100 mm 將輕量 2D 示意畫成 1100/500，且不同 H 的未確認示意沒有依 Receiving Family 預設等比縮放。這不是合法的 2D 顯示同源。
- 新公開唯讀 `manufacturing_api.project_receiving_operator_bay_door_split_ratio(bay)` 經 Engine `receiving_operator_projection` 讀取已存 `door_state.multi_door_enabled/door_layout_columns`，使用現存 `validate_door_layout_dimensions` 核對 Bay W/H；能唯一表示兩列共用分界時回傳高度比例。多欄不同分界、三列以上或已明確停用 Door 則回傳 `None`，GUI 不畫假分界或假 Door 孔位；非法來源 fail closed。沒有已存拓樸的輕量草圖僅按 Receiving Family `default_door_layout_columns` 顯示等比示意；不是獲認證的實體門尺寸。
- GUI 僅將 Engine 的比例換算成 Canvas 像素座標，不參與 DoorPartSpec、CUTTING、BEND、2D/3D 正式製造、DXF Save→Reload 或來源授權。金庫型原 GUI／Factory 出圖不改；`tests/test_issue2517_receiving_operator_projection_api.py` 及 `tests/test_receiving_multi_settings_stage_20261010.py` 驗證 Engine 已存來源、非法／多欄來源及原生 Tk 畫面。#2517 仍 OPEN。

## [CURRENT] #2517 Receiving CSV NFB 候選套用單一 Engine 交易（2026-11-04）

- CADSplit 的 `modules/receiving_api_bridge.py::apply_receiving_nfb_csv_candidate` 原自行串聯 WHD 的 `candidate_committed_csv_nfb_config`、`validate_candidate_nfb_replacement`、`replace_candidate_bay_nfb` 三個公開 API；WHD 現提供統一 `manufacturing_api.apply_receiving_nfb_csv_candidate(layout, *, set_index, bay_indices, source)`，由 `ae_engine.receiving_nfb_csv_committed_config` 的原權威實作完整校驗／原子來源交易。僅 Set/Bay 來源與已確認 NFB CSV 候選套用；保留 CSV SHA、孔位 stable ID、混合 CUTTING 拒絕及 `manual_x_state=UNVERIFIED_BASIS`，不可視作已核准 X、開孔或正式製造。
- API 校驗非 bool 的實際整數 Set/Bay、非空且不重複的有效選取；來源無效時不得局部改寫 layout。定向測試 `tests/test_issue2517_receiving_nfb_csv_candidate_public_api.py` 比對既有 Engine ports、跨兩 Bay 來源隔離、冪等、失效來源與混合 CUTTING。CADSplit 端目前仍有既有相同操作橋接，須另核對真正委派及 GUI／CADSplit 端到端 parity；不得把此 API 接口存在冒充 Windows UAT、DXF Save→Reload 或 #2517 完成。

## [CURRENT] #2517 Fold Designer 封頭／封尾成形 FW 與單只出圖來源檢查使用公開 Engine（2026-11-03）

- `gui_modules/application/fold_designer_manufacturing_projection.py` 建立 Head/Tail 物理 `EndCapPartSpec` 時，箱身折後 FW 寬度必須直接消費現行公開 `manufacturing_api.formed_box_body_fw_widths(profile, thickness)`，不通過 GUI Fold adapter 或建立第二套求解。
- 單只 Receiving quantity 孔位／保存來源正式出圖前保留 `receiving_quantity_box.require_valid_quantity_features` 既有真實檢查，GUI 只能透過公開 `manufacturing_api.require_valid_operator_quantity_features(snapshot)` 使用；不允許略過實體孔位失效的拒絕。
- 自訂／未知類型 baseline 操作導覽，沿用公開 `manufacturing_api.is_unknown_operator_model(model)` 委派既有 Engine 名稱判斷。移除 GUI 製造投影中的無用內部 `cabinet_types`／`sheetmetal_part_adapters`／`corner_type_ui` 引用。上述皆為現有 Engine 來源重接線，不改 Family、料長／折彎補償或正式 DXF 幾何。


## [CURRENT] #2517 Receiving 內門內退距離／啟用物理來源與 GUI finished dimensions 全由 Engine（2026-11-03）

- `gui.py` 內門啟用、已存內退距離讀取及編輯 commit 一律使用公開 `manufacturing_api.normalize_operator_receiving_inner_door_inward_offset`、`resolve_operator_receiving_inner_door_inward_offset`、`project_operator_receiving_inner_door_enabled_source`。後者由既有 `receiving_inner_door_stable_id_for_cell` 與 Family Policy 決定實體 ID、內門框既存邊、預設內退毫米值；GUI 不得自行決定、用 `float(True)` 偽造 1mm、讓 NaN/Inf 通過非負檢查，也不可把**存在但損壞**的已保存物理值默默回填 Family 預設。合法 0 mm／正小數與不同門格獨立保存保持原樣；UI commit 失敗不變更物理來源，不能因回復顯示而改寫損壞來源。
- 原 WHD 主 GUI 的 `_phase6_resolved_finished_dimensions` 只透過公開 `manufacturing_api.resolve_operator_finished_dimensions` 消費既有 Engine 成品 2D/3D 尺寸；`_endcap_depth_comp_t_for_family` 改透過 `manufacturing_api.project_operator_endcap_depth_comp_t`，不新增或複製第二套尺寸／Family 補償公式。上述只改 GUI/Engine 邊界，不變更既有 PartSpec／FinalScene、DXF Save→Reload 認證。
- 既有 `tests/test_phase6_t17_receiving_inner_door_80.py` 的實際 Tk/保存回讀契約保持；新 `tests/test_issue2517_receiving_inner_door_offset_public_engine_api.py` 包含金庫型／受電箱預設、非法值 fail closed、GUI 委派與來源原子性，經現有 canonical Product Regression 跑實測。


## [CURRENT] #2517 Main GUI 包外 T/FW 與 Fold Designer 舊版 Gap/Fold 參數單一 Engine 來源（2026-11-03）

- 主 GUI `_phase6_resolved_finished_dimensions` 的箱身 FW 及所有板件 T 必須用 `manufacturing_api.normalize_operator_source_dimension` 驗證 snapshot 原始來源，缺值、bool、零、NaN/Inf 不得退回 `ae.FW`／`ae.T` 製造出看似有效的成形尺寸。既有最終幾何仍用唯一 Engine finished dimension provider。
- Fold Designer 原本 `ae.door_gap_*_def`、`door_fold_*_def`、`zl*/zr*`、`yl*/yr*/ytop1/ybottom1`、`indicator_small_door_fold_def` 的舊版缺欄位相容數值，統一由公開 `manufacturing_api.resolve_fold_designer_legacy_numeric_settings(data, part_name=...)` 提供；BoxBody head/tail `ybottom1` 專屬覆寫優先序維持不變。只有**缺欄位**允許保留舊版 Engine 預設；欄位存在卻非法（bool、NaN/Inf、無法轉為有限值）一律拒絕，不得偷偷使用另一個折／孔來源。
- Divider/InnerDoor 舊路徑缺 D/T 的相容預設改經公開 `manufacturing_api.fold_designer_legacy_source_default("d"|"t")`，此項不得作為現行已確認製造請求 W/H/D/T/FW 缺值的授權。GUI 不直接引用 AE 工廠預設；已核准的 `PartSpec → FinalScene → 2D/3D/DXF Save→Reload` 及 Fold/Family 補償規則維持既有權威。
- 以 `tests/test_issue2517_fold_designer_numeric_defaults_single_engine_api.py` 核對金庫型／受電箱、相容缺欄位、真實小數來源、非法值、GUI 公開 API 委派，並納入既有 canonical pytest 自動收集，不新增獨立製造算法或外部 exporter。


## [CURRENT] #2517 Head/Tail Hole Editor 三入口同一公開 Engine finished-face 投影（2026-11-03）

- 主 WHD GUI 封頭／封尾、受電箱 Set/Bay 實體封頭／封尾及未 Apply 的受電箱候選版本編輯器，**同用**公開 `manufacturing_api.project_operator_hole_editor_endcap(role, width, depth, thickness)`。沿用既有 `resolve_endcap_finished_face_guide`、`feature_surface_from_rect`、`RectGuide`，由 Engine 產生可開孔面和 finished boundary；GUI 只傳原始操作／Bay 尺寸、選 Role、顯示和提交明確確認的 Features。
- Engine 對 W/D/T 共用 `normalize_operator_source_dimension`：bool、NaN/Inf、非正數、無法轉為物理尺寸的舊保存來源須先拒絕，不得 `float(True)` 變 1mm；Receiving Bay 維持直接選擇本 Bay 實體來源及舊專案缺 T 使用 2mm 的既有相容值。候選版本仍只在 Confirm 寫回，Cancel 不寫入。
- 主 GUI 舊孔位轉換走既有 `manufacturing_api.legacy_hole_to_feature`／`feature_to_legacy_hole`，不另算第二份座標。此 API 是唯讀操作編輯器投影，不自行認證製造，也不變更既有 `PartSpec → FinalScene → DXF Save→Reload` 權威。
- 產品回歸含 `tests/test_issue2517_endcap_hole_editor_shared_engine_source.py`、原 `tests/test_issue293_t5_hole_editor_routing.py`、`tests/test_issue2517_receiving_endcap_hole_context_api.py`；#2517 全產品總驗收仍需逐項真實證據。


## [CURRENT] #2517 箱身面 Hole Editor 可加工面及基準界線由 Engine 投影（2026-11-03）

- GUI 原箱身左／背／右面編輯器自行依 W/H/D/T、兩端 CornerPolicy 推出開孔面四角及 Reference Guide，透過低階 feature_surface_from_rect／box_body_vertical_offsets 組合實體範圍；現在委派 manufacturing_api.project_operator_hole_editor_box_body_face，沿用相同 box_body_face_dimensions、Corner vertical offsets 與現有 OperatorHoleEditorGeometry。
- UI 僅選 face key、操作值、已有 Engine Corner policy、提供基準唯讀場景並開啟 Modal；原 Feature 提交、同步與關閉刷新順序不變。主 GUI BoxBody render snapshot 的面尺寸也改用既有 project_operator_box_body_face_dimensions；沒有新增 DXF writer、幾何補償或改變 FinalScene 製造認證。
- tests/test_issue2517_box_body_face_editor_geometry_engine_api.py 比對金庫型和受電箱相同幾何、非法 face 拒絕與 GUI 真實委派；需完整 CI，#2517 整體結案仍以全入口驗收為準。


## [CURRENT] #2517 箱身三面基準固定特徵只經公開 Engine API（2026-11-03）

- GUI 的箱身左／背／右面 Hole Editor 原本直接透過 ae 模組查找「箱身.dxf」基準、source fingerprint 與低階固定特徵投影；現在由公開 manufacturing_api.project_operator_box_body_baseline_face_features 使用原有 Engine 映射，保留金庫型／受電箱既有 source-miss 三面空值語意，以及來源 fingerprint＋W/H/D/T/FW／Fold／Corner 快取鍵。
- GUI 只提交已選 model、操作值及原有公開 Engine Corner policy，並顯示 Engine 的面 Features；來源標籤透過 manufacturing_api.operator_box_body_baseline_source_label。仍是唯讀編輯器基準投影，不是新增製造工廠或 DXF 認證；製造 FinalScene／Save→Reload 保持原 Engine 路線。
- tests/test_issue2517_box_body_baseline_face_public_api.py 驗公開請求與現有真實金庫型基準面源等價、快取／無來源拒絕以及 GUI 委派。#2517 全功能總驗收未因此完成。


## [CURRENT] #2517 Door 2D Preview 使用原始指示燈實體來源，禁止偽孔（2026-11-03）

- `gui_modules/application/door_render_host_adapter._door_layout_cell_resolved_features` 以前會先將存檔的 `door_layout_indicator_states` 轉成展示相容預設，再交 Engine 畫實體指示燈孔；布林孔數、零／小數、過大層數或無效偏移有被改成合法預設而出現「預覽偽 CUTTING」風險。此 2D 入口改讀原始 cell row 且**不寫回**；缺 cell 不補建，只有完全沒有來源容器的舊 client 才保留展示 accessor 相容讀取。
- 公開 `manufacturing_api.project_operator_door_cell_features` 沿用原有 `ae_engine.operator_door_cell_projection` 幾何與容錯：有效來源先經同一 `project_operator_door_cell_indicator_manufacturing_source` 判定實際 layers／groups／offset；非法來源僅略過「指示燈／盒開孔」預覽，不得以 `int(True)` 等轉換畫出加工孔，其他已編輯的合法 Features 照舊顯示。正式 DoorPartSpec／FinalScene／DXF 的拒絕路徑不變。
- 現行 Door Hole Editor 已改用公開 `project_operator_hole_editor_door_cell` 和唯讀顯示 accessor、暫存 Feature 清單，不回退該新 API。測試 `tests/test_issue2517_door_cell_preview_engine_api.py` 包括原始狀態不變、缺 cell、非法層數／組數／NaN，以及既有金庫型／受電箱合法預覽；#2517 仍 OPEN，非整套製造認證。


## [CURRENT] #2517 Receiving 多門格開孔要使用已確認 Bay 尺寸與唯一實體 ID（2026-11-03）

原 `door_layout_host_adapter._receiving_live_door_layout_source` 僅認得「受電箱」與大寫「RECEIVING」，遇到 Registry 合法別名 `receiving`／混合大小寫／`cabinet_type` 會退回 GUI 主 Settings 舊尺寸，讓開孔編輯器選錯實體門格。現只經公開 `manufacturing_api.receiving_family_supports_back_panel_mode` 確認 Family，活躍 Receiving 的 `_phase6_box_whd` 或 `door_layout_columns` 缺失都直接拒絕，不得退回不相干 W/H。原 `manufacturing_api.project_operator_receiving_settings_live_dimensions(..., applying_settings=True)` 驗證所選 Bay 的 W/H/D 來源，拒絕 bool、非有限數及非正值；GUI `open_door_layout_cell_editor` 不再用 `float()` 把來源改型，只傳 Engine 已驗證數值。原 GUI 手拼 `door_cN_rN` 的 Workspace／Feature 實體鍵改走公開 `manufacturing_api.door_layout_part_key(cell)`，其實作仍為 Engine `sheetmetal_part_adapters.door_layout_part_key`，與 DoorPartSpec、Fold Designer、DXF 的實體 ID 一致。選錯或非法 Bay 在開 Editor 前顯示錯誤，不得寫入 Project；完全不改 Door／CUTTING／Fold／DXF 公式與 source-only 出口限制。回歸覆蓋 Vault／Receiving 別名、缺 Bay、非法 W/H/D、Door Editor 及 source key，同原 Save→Reload／2D／3D／DXF API Gate。#2517 保持 OPEN。

## [CURRENT] #2517 Receiving Bay 現場 Feature/內門 Panel 選擇/世界快取來源見證由 Engine（2026-11-03）

- 原 GUI `sync_receiving_current_bay` 自行用 `inner_door:`／`:panel` 字串識別需發佈的 Hole Editor 實體面特徵，並直接讀 `surface_features`、重建鄰 Bay Joint side-lock。現在全部透過 Engine 公開 `manufacturing_api.project_operator_receiving_live_bay_features` 取得 immutable `OperatorReceivingLiveBayFeaturePlan`，GUI 只 stash 到 workspace。
- 原 `current_inner_editor_part_key` 從 `derive_inner_door_panels` 自行以 Cell `:0` 選上層實體內門；改公開 `resolve_receiving_upper_inner_door_editor_part_key`，同原 Family 衍生 Part，缺失或多片 fail closed。Hole Editor 仍使用既有 `resolve_inner_door_hole_editor_context`，非自行計算 CUTTING。
- Receiving Bay LRU 原用 GUI `float(bay[width/height/depth])` 製造來源 prefix 和直接選世界錨；現在統一由 `manufacturing_api.project_receiving_bay_preview_cache_source_witness` 提供不可變 `ReceivingBayPreviewCacheSourceWitness`，錨點沿用既有 `receiving_bay_assembly_offsets` Joint 權威。此只是預覽快取證據，不是 DXF／外部 source-only 輸出資格。四連 Bay、Quantity、非法選取、Panel 唯一性由 `tests/test_issue2517_receiving_live_feature_and_cache_witness_engine_api.py` 驗收；#2517 OPEN。

## [CURRENT] #2517 原始製造請求與 Fold Designer 預覽共用單一 Engine 實體 Part source router（2026-11-03）

- GUI 原 `phase6_manufacturing_adapter._profile_inputs_for_part` 自行以 `custom:` 字串決定從 saved CustomFold Catalog 補建 Fold；`_domain_inputs_for_part` 與 `_materialize_committed_endcap_inputs` 自行以 `head/tail/custom:` 判斷需直接 PartSpec 與 committed relief 第二階段；`fold_designer_manufacturing_projection._query_fold_designer_render_data` 亦自行以多組實體 part_key 前綴／後綴決定 indicator/multipart/door 操作輸入和 NFB PAD／固定耳／Divider／InnerDoor panel/frame 使用哪個 Engine 製造來源。以上現在同批統一交 `ae_engine.manufacturing_request_parts.plan_operator_manufacturing_part_source`（公開 `manufacturing_api`）回傳不可變 `OperatorManufacturingPartSourcePlan`。
- GUI 只依 Engine 指定的 source plan 呼叫已存在 `build_operator_default_part_fold_profiles`、真實 Render／Spec Factory、NFB 2D source 和來源票據，不再自認實體 Part 身分；Panel LRU、Factory source SHA、EndCap committed pass 與 Family／Policy／Topology／2D／3D／DXF canonical 結果都沿用原邏輯。計畫只是 source/classifier，**不憑 part 名稱批准製造或啟用不完整 external export**。
- `tests/test_issue2517_shared_physical_part_source_route_engine_api.py` 涵蓋 15 種既有實體 Part identity、CustomFold 真實 catalog 預設、PartSpec provider 呼叫次序、Head/Tail 第二階段和 GUI 去除重複 key prefix。#2517 OPEN；正式 X 未發布。

## [CURRENT] #2517 .p6fold Feature/Vec2 實體孔位座標必須具備完整有限來源（2026-11-03）

- `phase6_project_file.read_project` 的 Feature／Vec2 還原只經公開 `manufacturing_api.decode_project_value`、`decode_project_feature`、`project_vec2_from_raw`，唯一實作在 `ae_engine.project_feature_codec`。有標記的實體 `Vec2` 及孔位 Feature 的明確 `offset`／Profile 頂點與輪廓座標均需提供完整 X/Y，且不得是 bool、NaN、Infinity、不可轉成有限數字或溢位來源；不可把遺漏的 X/Y 靜默補成 0，亦不得 `True → 1 mm`。外來損壞專案在回讀即拒絕，而非產出移位的 CUTTING 孔。
- 沿用舊專案合法數字字串、完整 X/Y 陣列、Vec2 原物件及**整個 Feature.offset 欄位缺席**時的既有明確零偏移預設；不更動已確認 Feature Anchor、Family、2D／3D／DXF 幾何算法或外部 source-only 認證。正常受電箱確認門孔沿原 `confirmed_door_features` → DoorPartSpec／FinalScene → verified DXF Save→Reload 測試；非法儲存來源 fail-closed，不宣稱整套 #2517 已完成。
- 同一 Engine `project_feature_codec._decode_feature` 的明確 Circle 直徑、Rect 寬高，只接受有限且非 bool 的數值來源（支援合法數字字串）；不可將 `True` 變成 1 mm 或把 NaN／Infinity 作為實體孔尺寸。保存的 Profile layered CUTTING 輪廓 `closed` 僅接受真正布林及舊 JSON 數字 0／1，不可由 `bool("false")` 偷轉成閉合切割。零／負數草稿尺寸保留原始數值，實際製造是否可用由既有幾何／Fit Gate 獨立審核，不在 codec 另造幾何。正常門孔沿原 verified DXF Save→Reload，非法已儲存 Feature 應在 `.p6fold` 回讀即拒絕。
- **保存與回讀必須同源**：`ae_engine.project_feature_codec._encode` 在序列化 typed `Vec2`／Circle／Rect／Profile Feature 前，直接共用現存 `_finite_saved_coordinate`、`_finite_saved_feature_dimension`、`_saved_profile_closed_flag` 和 `_as_vec2`；不是等 `.p6fold` 保存成功後在 `read_project` 才發現 bool 當毫米、NaN、Inf、缺失頂點或 `"false"` 偽閉合。非法來源在編碼時 fail-closed，原合法專案檔內容不得因失敗而被覆寫；舊合法有限數字字串、0／1 閉合及草稿零／負尺寸仍依既有回讀與下游製造 Fit Gate 分工。GUI 只負責檔案 I/O，型別與實體來源驗證只在 Engine 公開 `manufacturing_api.encode_project_value`／`decode_project_value`；既有受電箱門孔 verified DXF Save→Reload／source-only 限制不改。

## [CURRENT] #2517 Receiving Bay 3D 製造預覽 Fold／Joint／箱身結構種子移入公開 Engine（2026-11-03）

- GUI 原 receiving_bay_preview_request 在 cache miss 後自行決定從哪些來源建立 BoxBody Fold、Head/Tail 專用 Fold、所選 Bay 的相鄰接合 Joint lock 特徵與 workspace/root 的 BoxBody structure 優先順序，雖公式已存在 Engine 仍由 GUI 組裝多個製造物理來源。現統一委派 `manufacturing_api.project_receiving_bay_preview_physical_seed`（`ae_engine.receiving_bay_preview_source`）返回 `ReceivingBayPreviewPhysicalSeed`，沿用同一組 `merge_box_body_fold_profile`、`build_endcap_xy_fold_profiles`、`receiving_bay_joint_face_features` 原 Engine 來源；不引入新的補償或孔位規則。
- GUI 只在候選/已確認來源的隔離 workspace 內套用 Engine 返回值，沿用真實 `ManufacturingResolveRequest` → PartSpec/FinalScene。四連 Bay、不同 W/H/D、Joint lock 與 Head/Tail 原生方向、來源不變性、非 Receiving／Quantity fail-closed 由 `tests/test_issue2517_receiving_bay_preview_physical_seed_engine_api.py` 與既有回歸驗證。只改操作 preview source，不改正式 DXF／外部 source-only 認證、保存 schema 或 UI 排版。#2517 OPEN。

## [CURRENT] #2517 Receiving 指定 Bay 的全域 Settings／門分割／NFB 實體來源合併移入 Engine（2026-11-03）

- GUI `receiving_bay_preview_request` 原本從 global `app._settings_values` 覆蓋 Bay snapshot 前，自行維護 `RECEIVING_DOOR_STATE_KEYS`、`nfb_config`、`nfb_config_submitted`、`receiving_layout`、`_receiving_runtime_selection` 等例外清單，並決定重算 `part_dimensions`；此處能令舊根層 Door 拓樸污染所選盤位。現在一律呼叫 `manufacturing_api.project_receiving_bay_preview_operator_inputs(source_snapshot, settings_values, set_index, bay_index)`，Engine `ae_engine.receiving_bay_preview_source` 封裝 canonical `project_receiving_bay_legacy_aliases`、Bay 專屬尺寸優先、門／NFB／Selection 欄位保護及 `part_dimension_projection.project_part_dimensions` 。
- 返回 `ReceivingBayPreviewOperatorInputs(snapshot, settings_values)` 是**隔離操作資料**（不是已認證製造結果）；GUI 僅管理候選 Layout clone、preview workspace／cache、呼叫實體 ManufacturingResolveRequest。原此路徑的 global T／FW 等操作設定優先順序維持不變，Bay W/H/D 與保存之 Door layout 不可被舊根層覆蓋。Receiving 四連／不同 Bay／候選尺寸與 Stale Door／NFB 來源以 `tests/test_issue2517_receiving_bay_operator_input_engine_api.py` 保護；沒有加新 Door 分割、實體幾何、CUTTING／BEND／DXF 或外部 source-only 例外。
- Family／Topology／Set-Bay source → Engine request → canonical PartSpec／FinalScene 原鏈不變。#2517 OPEN；正式 X 未發布。

## [CURRENT] #2517 Receiving Bay 3D 物理世界裝配位置由 Engine 公開 API 唯一投影（2026-11-03）

- 原 GUI receiving_bay_preview_request 在 resolve 真實製造板件後，仍直接以 `if part.placement != "standalone"` 決定哪些實體要加入 Bay Assembly，並用 `tuple(a+b for zip(part.offset, bay_offset))` 計算世界裝配座標。這違反 GUI 只消費 Engine 製造物理結果原則；現在透過既有 receiving_bay_assembly_offsets（相鄰 Joint＋包外 W/H/D）及 Engine `receiving_bay_preview_source.project_receiving_bay_preview_assembly_members` 統一回傳不可變 `ReceivingBayWorldAssemblyProjection`（Bay origin 與已確認非 standalone 實體 Part＋world offset），經 `manufacturing_api` 公開。
- GUI 只將 Engine 已解析的物理 PartRenderData／Fold Profile 配上 Engine 投影位置組裝 `AssemblyScenePart` 作 Matplotlib 顯示。不存在的 Bay、缺少 placement、布林／NaN／Inf／錯誤三軸 offset 必須 fail closed，不得透過 `zip` 截斷或從 3D bbox 猜座標。單獨 CustomFold 不屬 Bay Assembly，仍保持獨立板件身分；基準源／Set-Bay/Factory／Save→Reload 原契約不變。
- 驗收 `tests/test_issue2517_receiving_bay_world_assembly_projection_engine_api.py` 搭配原 Receiving Bay Preview、Set/Bay Joint 與 Headless CI。此是已解析製造結果的 VIEW 位置投影，非新增 CUTTING、DXF、source-only external 製造認證；#2517 OPEN。

## [CURRENT] #2517 Receiving Bay 預覽快取准入及來源類型判準統一由 Engine（2026-11-03）

- 原 GUI receiving_bay_preview_request 自行以 model/active_mode/bay_index/custom Parts/Assembly Joints/Relief 決定快取世界座標平移及 suffix 裁剪，並以 custom: 前綴決定是否讀取 live CustomPartCatalog；現移至 ae_engine.receiving_bay_preview_source.plan_receiving_bay_preview_reuse_policy，透過 manufacturing_api 公開 immutable ReceivingBayPreviewReusePolicy。GUI 僅讀取 workspace live metadata、管理 bounded LRU 及顯示既有 FinalScene。
- GUI 原用字串判定 inner_door Frame 與 box_body Divider cache 分流，現使用既有 manufacturing_api.receiving_raw_source_cache_kind；typed Part／來源 DXF SHA／meta 檢查仍由既有 Engine raw-cache ticket 與 Factory 執行。Candidate Bay 不得重用 committed offset、跨板件 Joint/Relief/CustomPart 禁止平移；獨立 fingerprint projector 仍做保守 source-based 次級檢查，沒有擴增任何 manufacturing 資格。
- 新 tests/test_issue2517_receiving_bay_reuse_policy_engine_api.py 與既有 Receiving Bay/Raw Source Cache/Set-Bay 真實回歸交叉驗證。Preview 重用不代表 CUTTING／BEND／2D／3D／DXF Save→Reload 認證或 source-only external export，#2517 保持 OPEN。

## [CURRENT] #2517 Main GUI Settings W/H/D/T/FW 來源及布林轉換由 Engine API 驗證（2026-11-03）

- `phase6_settings_center._coerce` 不再以 Python `float(raw)` 接收金庫型／受電箱的 `W/H/D/T/FW` 實體輸入，也不再將無法辨識的 UI/INI 布林文字直接轉成 `False`；物理來源鍵以 `manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS` 公開的 Engine 唯一契約判斷，原始欄位值透過 `normalize_operator_source_dimension(raw, field=...)` 和 `normalize_operator_settings_boolean(raw)`。
- 這一移轉沿用既有 Engine 數值規則：原有合法小數與字串數字維持精度；`True/False` 不充當毫米、`NaN/Inf`、零與負包外 W/H/D/T/FW 不可被誤存到已提交 Settings 或 `config.ini`。既有 `SettingsService.update` 遇到不合法來源時延續 skip，不得將該欄位寫入 runtime；顯式 `apply_settings_to_ae`／INI 寫入則在變更前依現有呼叫方式拒絕。UI `ui_text_size` 仍由 GUI 處理，其餘未定義正負製造語意的舊 scalar 不擅改允許範圍。
- 驗收 `tests/test_issue2517_settings_center_physical_source_engine_api.py`，回歸 Settings 主 GUI、Fold Designer 共用物理來源、Save→Reload 和 DXF 正式 Engine 路徑。不新增 Family 公式、CUTTING／BEND 作業入口、替代 DXF exporter 或 source-only CLI 認證。#2517 OPEN。


## [CURRENT] #2517 固定孔／Relief／舊底板縮量 runtime 更新統一由 Engine 公開 API 擁有（2026-11-03）

- `phase6_settings_center.apply_settings_to_ae` 只負責 SettingSpec→AE 模組操作輸入欄位的寫入；原本在 GUI 層依 `RELIEF_CONFIG`、`VAULT_ENDCAP_FEATURE_POLICY` 重建正式製造特徵並決定 BasePlate 四邊同縮的舊版共用值，已原語意移至 `ae_engine.operator_settings_transactions.apply_operator_legacy_runtime_manufacturing_policies`，經 `manufacturing_api` 正式公開。金庫型固有 EndCap 掛孔、方孔、底孔從原 `ae_engine.sheetmetal_features.VaultEndCapFeaturePolicy` 來源讀回；Receiving 仍**不**套用 Vault 固定孔。
- `manufacturing_api.operator_legacy_shared_base_plate_shrink` 統一 runtime 與 `config.ini` 舊 `BASE_PLATE.shrink` 相容更新：原四方向全部存在、數值差距小於 `1e-9` 才維持 legacy 單值；分邊不同或缺任一欄時只保留個別設定，不臆造共用加工量。INI 寫入與 GUI 顯示由原 client 負責，不將檔案管理轉移 Engine。
- 原`RELIEF_CONFIG`、`VAULT_ENDCAP_FEATURE_POLICY` 的 dataclass/可變物件更新次序、讀回 fallback 與錯誤處理語意均保留，沒有新 Family、Cutting／BEND 公式、替代 DXF writer 或 source-only CLI 放行。驗收 `tests/test_issue2517_settings_runtime_manufacturing_policy_engine_api.py` 與既有 Settings、EndCap Features／DXF、Save→Reload 回歸，#2517 仍 OPEN。


## [CURRENT] #2517 GUI 殘留 Family／Corner／Receiving 導覽物理決策由 Engine 公開 API 擁有（2026-11-03）

- 原 GUI `phase6_settings_transitions.plan_external_model_change` 決定目標箱型變更；現在委派 `manufacturing_api.plan_operator_external_model_change`（同型別 `OperatorExternalModelPlan`，現行字串／空值與 change 判準原樣移轉），正式 Family 切換仍由既有 `plan_cabinet_family_model_transition` 執行，不能繞過 Factory／Registry。
- 原 GUI `phase6_settings_transitions.replace_corner_state` 的正式 Corner 保存態深拷貝改由 `manufacturing_api.replace_corner_state` 返回原 `CornerStateTransition`。不改使用者 Corner 選擇、對稱聯動、Registry 截角或製造幾何。
- 原中立同步 adapter `phase6_sync_envelope.navigation_only_change` 曾自行識別 Receiving Set/Bay、存在實體板件及完整 state 同源才能省略實體 publish。此物理判準原樣移到既有 `ae_engine.operator_part_session_profiles.operator_receiving_navigation_only_sync_change`，由 `manufacturing_api` 公開；GUI 僅送兩個 state、根據 Engine 判斷執行或跳過 UI 傳輸，不重新決定可否略過物理狀態。同源安全語意保留，Family 識別修正為既有 Registry `canonical_family_name`，合法 `受電箱`／`RECEIVING`／`receiving`／混合大小寫與舊 `cabinet_type` 均可在 `set_bay` 單純切換現有實體 active_part 時省略重複 publish；其他 Family、Quantity、未存在 Part 或任何 Payload 實體差異仍 fail closed。該判準不授權製造或完整 Set/Bay 認證。
- 驗收 `tests/test_issue2517_gui_residual_physical_state_engine_api.py` 與既有 Settings／live-sync／Receiving Part Session／Save→Reload 回歸；來源不修改、Headless=GUI、Vault 與物理差異 fail closed。此為 move-only，無新尺寸公式、2D／3D／DXF 資格、外部 source-only CLI 放行，#2517 OPEN。


## [CURRENT] #2517 Settings 標準／自訂 Part Fold 由同一 Engine API 路由（2026-11-03）

- GUI phase6_settings_profile_projection.build_standard_part_profiles 原本用 custom: 判斷製造身分，分別轉交 CustomFold／標準 Fold API。現在由既有 Engine operator_settings_fold_plan 中唯一的 build_operator_default_part_fold_profiles 統一決策，經 manufacturing_api 正式公開；GUI 只傳入 snapshot 和 part_key，Engine 的 Settings 整體計畫同樣改用這條 helper。
- CustomFold 必須保持既有持久化 CustomPartCatalog descriptor／合法 physical ID，缺資料 fail closed；不可降級成普通三片折邊。金庫型／受電箱標準 Door／BasePlate／Indicator 和自訂 X／Y 皆沿用原 Factory Fold、T 補償與 HEAD/TAIL 專用入口，不更動物理幾何、DXF 或外部 source-only 權限。
- 新 tests/test_issue2517_settings_default_part_fold_route_engine_api.py，與原 standard_part_fold_engine_api、operator_settings_fold_plan、CustomFold 保存／DXF 測試交叉驗證。#2517 維持 OPEN，正式 X 未發布。

## [CURRENT] #2517 FinalScene 實體 Mesh 的 3D 顯示邊界與折線改為 Engine 單一來源（2026-11-03）

- GUI Phase6FinalSceneRenderHelpersMixin 原本持有兩份 triangle 邊緣統計、法向量和物理折線判定，與 Engine 既有 solid_mesh_feature_edges 是重複權威。現在兩種 Legacy GUI 顯示都呼叫公開 manufacturing_api.project_physical_solid_mesh_display_segments(mode)，由同一 Engine 內核統一提供 boundary、crease、boundary_and_crease。
- crease 僅取合法非共面共享實體邊，拒絕三角細分對角線冒充物理 Fold；boundary 僅取非退化實體網格邊。原 physical_solid_mesh_feature_segments 與 VIEW 組合結果維持一致。這只是來源已確認的成形 mesh 視圖投影，不產生 CUTTING、BEND、DXF 或製造新認證。
- tests/test_issue2517_finalscene_mesh_edge_modes_engine_api.py 和既有 solid_mesh_feature_edges 測試對比 Headless/GUI、真實折面、退化輸入與非法模式；原 Save→Reload、Family、CURRENT 07 包外／料長語意保持不變。#2517 OPEN。


## [CURRENT] #2517 外部 Settings 同步來源與 Revision 判準由公開 Engine API 決定（2026-11-03）

- `ae_engine.operator_settings_transactions.plan_operator_external_sync` 經 `manufacturing_api.plan_operator_external_sync` 正式公開，回傳 immutable `OperatorExternalSyncPlan`。原 `phase6_settings_transitions.plan_external_sync` 只傳 `envelope`、`last_external_revision`，`ExternalSyncPlan` 保留 Engine 同型別相容別名；`phase6_settings_service` 僅依回傳 Plan 更新 session revision／transaction id。
- 將現行 `origin=main_gui`、revision 排序、`WRONG_ORIGIN`／`INVALID_REVISION`／`STALE_REVISION`／`OK` 原樣移轉，保持舊 GUI/Designer／存檔使用者已驗證行為；**不**用此操作新增 CUTTING、BEND、DXF 授權或 CADSplit 製造路徑。無 Tk／GUI 反向依賴。
- 驗收 `tests/test_issue2517_external_sync_engine_api.py`（headless Engine/GUI 同 Request→Plan、同一 immutable DTO、失敗不改 revision、Settings 複製隔離）。#2517 保持 OPEN、未發布正式 X。


## [CURRENT] #2517 已確認 Receiving Door 孔位來源沿用既有 Engine Feature／DXF（2026-11-03）

- `manufacturing_api.build_receiving_factory_confirmed_parts(..., confirmed_door_layout_columns=..., confirmed_door_features=...)` 及既有 `ManufacturingResolvedBayInput.confirmed_door_features` 讓明確已確認的 `door_cN_rN` 實體門格 CUTTING Feature 進入原有 `DoorPartSpec(feature_space="finished_face")`，由既有 Engine finished-face→材料投影、FinalScene、DXF Save→Reload/reopen 製造；**不建立 CADSplit 專用 exporter**。
- 僅接收合法 Door 實體 ID、typed Circle/Rect/Profile Feature、`ABSOLUTE_FINISHED_FACE` 來源座標及 `CUTTING` 圖層；未確認 Door 拓樸、非法／NaN 幾何、錯誤 Role、混入其他加工層／layered profile 均拒絕。舊 `confirmed_endcap_features` 使用相同 Engine finished-face 檢核語意，既有 Head/Tail API 保持相容。
- 已確認 EndCap／Door **共用** `ae_engine.receiving_factory_requests._confirmed_finished_face_cutting_features` 的來源准入：Profile 的 `layered_profiles` 會夾帶第二層未確認加工（即使主層為 CUTTING），一律拒絕；所有板件的 `rotation_deg` 必須是明確 int，不容 `True → 1°` 或非整數隱式轉換。原門孔驗證不能只套用 Door 而放過 Head/Tail；現有正規 EndCap／Door PartSpec、真實 DXF Save→Reload 及 source-only fail-closed 不變。
- `saved_operator_confirmed` 之已存 `part_features` 不允許被空 Features 默默取代：任何已存非空門孔必須與本次顯式確認的 typed Feature 逐件一致，否則先拒絕、不寫 DXF；沒有保存孔位的 Fresh／Saved 操作仍維持原本結果。
- 驗收 `tests/test_issue2517_receiving_confirmed_door_cutting_source.py`：確認門孔與 HEADLESS 同一 Spec／DXF 重開、保存態來源一致性、非法操作拒絕、Source-only 原拒絕保持。這只認證**實際出圖的板件**，不是完整 Set/Bay/NFB、外部 source-only CLI 或正式 X 的製造放行；#2517 OPEN。


## [CURRENT] #2517 .p6fold Feature／Vec2 序列化與來源還原由 Engine 公開 API 擁有（2026-11-03）

- `phase6_project_file` 原有 `_encode/_decode/_decode_feature/_as_vec2` 全部以**原語意**搬到 `ae_engine.project_feature_codec`，透過 `manufacturing_api.encode_project_value`、`decode_project_value`、`decode_project_feature`、`project_vec2_from_raw` 公開；舊 GUI 名稱僅是相同物件 aliases，GUI 只操作 FilePath/JSON 文字傳輸與 Windows 檔案關聯。Circle/Rect/Profile Feature 與 Vec2 的反序列化和 Anchor/offset/source_params/layered_profiles 語意不再由 GUI 定義。
- 原 `.p6fold` `__phase6_type__` wire 與既有專案 schema、Receiving/Vault 來源權威和 `project_operator_project_for_write/read` 的 Save→Reload 檢核保持完全相容；沒有從預覽重建未驗證 Feature，也未增加外部製造認證或修改物理公式。新測試 `tests/test_issue2517_project_feature_codec_engine_api.py` 與既有專案存讀整合回歸證明 UI/headless 同源及無逆向依賴；#2517 仍 OPEN。

## [CURRENT] #2517 Main／Designer 共享實體 Workspace 狀態由 Engine 公開 API 單獨擁有（2026-11-03）

- 原 GUI `phase6_workspace_state.SharedWorkspaceState`、`normalize_existing_parts`、`MANDATORY_PART`、`PART_ORDER`、`ACTIVE_REPAIR_POLICIES` 及 active-part 修復判定移入 `ae_engine.workspace_state`，透過 `manufacturing_api` 公開；舊 `phase6_workspace_state.py` 只保留相容 alias，不能維持第二份物理清單／CustomPart metadata／Profile stash 邏輯。
- Main `Phase6WorkspaceController`、Designer `Phase6DesignerWorkspace` 繼續各自持有**獨立** `SharedWorkspaceState` instance 與 GUI 生命周期；Main／Designer 的 present/dirty/switching／Save→Reload shell 行為不搬入 Engine。Engine 原用 `custom_part_catalog` 和 `box_body_structure_state` 的既有幾何／來源合法性，沒有新算製造公式、DXF 或未認證出口。
- `tests/test_issue2517_workspace_physical_state_engine_api.py` 與既有 workspace state/controller/designer 測試檢查 Engine/GUI 完全同一 callable/class、實體 presence/CustomPart ID fail-closed、無反向依賴及各 client 狀態獨立；原始 Project／2D／3D／DXF 輸入語意與持久格式保持不變。#2517 仍 OPEN。

## [CURRENT] #2517 Receiving 模式初始化與 Session 物理來源改由 Engine 公開 API（2026-11-03）

- `manufacturing_api.fresh_receiving_mode(mode, dimensions, *, thickness=2.0, auto_nfb=False)` 與 `manufacturing_api.ReceivingModeSession` 現由 `ae_engine.receiving_mode_session` 實作。新模式一 Set/Bay、門格分割、Quantity 版本、既有 CSV NFB 初始來源、跨模式 CustomPart ID 保留及 Project-global 候選資料移交仍沿用原 Engine／Family 驗證；GUI `phase6_receiving_modes.py` 僅保留相同函式／型別別名，不再執行物理來源組裝或自行維護第二套切換規則。
- Workspace 初始實體板件清單改用同一公開 `manufacturing_api.DEFAULT_OPERATOR_EXISTING_PARTS`，維持原 `box_body/head/tail/door/base_plate` 順序，不用 GUI 常數反向餵 Engine。首次切換的缺尺寸、非法尺寸、幾何驗證失敗及 inactive buffer 不得偷存；原 Session 僅為記憶體狀態，不改磁碟格式。
- `tests/test_issue2517_receiving_mode_session_public_api.py` 與既有 `tests/test_issue1463_receiving_modes.py` 覆蓋委派、無 Engine→GUI 反依賴、兩模式建置、失敗原子性、CustomPart 身份及 Save→Reload。這是來源／權責遷移，不新增 CUTTING／BEND／DXF 認證，#2517 仍 OPEN。

## [CURRENT] #2517 BoxBody 對稱折彎即時開關原始布林來源必須走 Engine API（2026-11-03）

- `phase6_settings_transitions.normalize_symmetry` 不再用 Python `bool(raw)` 代表製造對稱選項，直接委派公開 `manufacturing_api.normalize_operator_settings_boolean`；`phase6_settings_transaction_controller.commit_symmetry` 只在驗證成功後提交 `state.symmetric`，再標記 Workspace 變更。
- `gui_modules/application/fold_designer_composition_registry_edges.on_box_symmetry_changed` 只讀取原始 Tk／Project 值並將 Engine 回傳的 bool 作為畫面結果；例如 `"false"`／`"0"` 不得當 True，NaN／不明字串不可更新狀態或觸發製造預覽刷新。Family 已禁止對稱時仍由現有 Engine Family capability 及原本政策將開關固定 False。
- 不變更 BoxBody Fold、BEND、2D／3D／DXF 幾何、Save→Reload 或既有 Family/Registry；這是 GUI→Engine 同一原始來源契約的遷移，無新增對外製造准入。驗收 `tests/test_issue2517_box_symmetry_source_boolean_engine_api.py`，#2517 仍 OPEN。


## [CURRENT] #2517 Receiving 已確認上下門直接走同一 Engine API／verified DXF（2026-11-03）

- 現有 `build_receiving_factory_confirmed_parts(source_dimensions, confirmation=..., operator_snapshot=..., confirmed_door_layout_columns=...)` 是**加法擴充**，未確認門格時仍只產生 BoxBody／Head／Tail；有明確已確認的 `door_layout_columns` 才使用 Engine `door_part_projections` 建立 `DoorPartSpec(feature_space="finished_face")`，並且經現有 `export_verified_resolved_integration_bays` 的同一 FinalScene/DXF Save→Reload/reopen 出圖，不另建 CADSplit executor。
- 使用者確認的來源 W/H 必須與列寬及各列高度精確相容；`saved_operator_confirmed` 還須與實際已保存的多門格拓樸相同。Door 原始孔位若存在但尚未被此來源契約正式證明，**整批拒絕**，不能以空孔位出圖。參數來自已確認 Family 新建預設或保存狀態，不能以 DXF 盤名推造 Door／Fold／孔位。
- `ManufacturingResolvedBayInput.door_layout_columns` 對 source-only 已確認 Request 可明確啟用 Door；沒有製造確認／資料不符照舊 fail closed。這只證明指定實體板件的製造與 DXF reopen，**不代表完整 Set/Bay/BOM、NFB、CADSplit source-only CLI 或正式 X 已放行**。


## [CURRENT] #2517 WHD GUI／CADSplit 完全同一條 Engine 製造鏈（2026-11-02，使用者最高優先決策）

> **「WHD 的 GUI 怎麼取得 Engine 的製造結果，CADSplit 就應該怎麼取得；差別只有操作資料的來源。」這是強制、不可折衷的正式架構規則，不是提案、建議或可選實作。任何依 caller 區分正式製造路徑的設計都屬架構違規，必須修正。**

```text
GUI／CADSplit 操作來源（來源可不同、Engine 契約相同） → WHD 公開 Engine API〔Family／Policy／Topology／Set-Bay（需要時）〕 → PartSpec／FinalScene → 同源 2D／3D／DXF → 正式驗證

```

**五條不可違反的硬規則（使用者 2026-11-02 確認）**
1. **唯一製造權威**：GUI／CADSplit 只提供操作或來源資料，**絕不可自行決定製造幾何**；製造由 WHD Engine 負責。
2. **唯一製造結果**：同一 Family、Part、Operation 與等價可信來源，在同版 Engine 必須使用**相同適用公開 API 契約與 canonical 製造結果**；不可依 caller 分流。
3. **箱型差異只在 Engine**：Family／Policy／Topology／正式 Registry 決定金庫型、受電箱差異；**GUI、CADSplit、Bridge 禁止第二套公式／製造出口**。
4. **Set/Bay 按需存在**：涉及多盤或裝配的實體 Set／Bay 拓樸及身份由 Engine 管理；**獨立單板件不需也不得被強迫建立 Set/Bay**。
5. **輸出不可分裂**：2D、3D、DXF 必須由同一 canonical FinalScene／核准等價製造幾何衍生，**不可各算各的**；驗證幾何、來源、DXF Save→Reload／reopen（依操作適用範圍）。

**PartSpec 是製造資料契約而非固定呼叫時序。** 它可以由公開 API 接收為已確認輸入，也可以由 Engine 依來源、Family／Policy 解析建立；上方為**責任鏈，不是強制 API 先被呼叫、PartSpec 才能建立的執行順序**。單板和 Set/Bay／批次／NFB 按操作使用既有適用的公開 API，不強迫全用一個函式。合法板件逐件製造與驗證，缺資料逐件報錯，整套完整性再由 Engine 核對 Set/Bay／BOM／裝配。現行 source-only external CLI 的未認證拒絕維持，不能用它否決已具備的正式 Python Engine API，也不得繞過其資格保護。

**責任：來源由 GUI／CADSplit 提供；製造與 PartSpec 解算由 Engine；2D／3D／DXF 同源輸出並驗證。**

- **唯一差異只在來源收集。** GUI 由人工操作、當前 Project state 與已確認設定組合；CADSplit 使用原始 DXF、來源圖元／把手、CSV、尺寸、孔位／來源關聯、Set/Bay、source key／revision 及已確認 Project/Factory 資料自動取得**等價正式輸入**。CADSplit source label 不是 canonical physical-part identity；物理板件、實際 Factory/Fold/Corner/Topology 與製造准入由 Engine 正式 owner 決定。資料不足就報缺項，**不准**猜測、套金庫型參數、以 UI bbox 反推或要求日常另選外部 JSON／baseline 來湊出假資料。
- **同一套不代表同一個函式。** 針對**相同的 Part／Operation**，GUI 調用哪個已適用的公開製造 API，CADSplit 就調用**同一 API 與契約**；單板件用適用的 `generate_part`，組合／多板件／Set-Bay／Quantity／NFB 用其原有適用的正式 Engine API。**不准**為 CADSplit／Receiving 另外做製造 executor、重複 Fold、Corner、孔／CUTTING／BEND、組裝、DXF 公式，或讓 CADSplit 調用 GUI／Tk 的內部程序。
- **相同輸入必須有相同製造語意。** 在相同 Engine 版本／Registry／baseline、等價經確認 Request 下，GUI 和 CADSplit 必須有同一實體 ID、同一 canonical geometry／FinalScene／Features／BEND／CUTTING、相同 DXF 寫入與獨立 reopen 驗證，且成功、缺項和 unsupported 結果**不能因 caller 而不同**。不同 Engine 版本仍可使用各自既有功能，無需 lockstep SHA；不可宣稱不同版本 DXF bytes 必然相等，須記錄來源和版本分別驗證。
- **逐板件合法出圖與整套完整性分開。** 有完整合法資料的板件先走正式 API 並逐件 DXF Save／Reload／reopen 驗收；缺資料的板件單獨回報，不得阻礙其他合法板件。**完整 Set/Bay／成套成功**另由 Engine 實際 Set/Bay、physical-part inventory、BOM 和裝配關係驗證，不能拿部分成功冒充整套出圖。
- **source-only CLI 不能凌駕原本的製造 API。** `integration_cli/cadsplit_worker.py` 目前仍是未認證的 source-only wire，`WHD_OPERATION_NOT_IMPLEMENTED`／`EXTERNAL_EXPORT_NOT_CERTIFIED` 等拒絕保留，**不得刪除保護偽造對外製造成功**；但也**絕不能**要求具備完整正式 `PartSpec`／Engine Request 的 CADSplit 內嵌 Python 製造流程改走這個未認證 `dispatch_manufacturing_integration(export)`，再以拒絕結果說 WHD Engine 無法製造。真正缺 API 就回既有 Engine／Family 擴充並認證，**不可再開平行通路**。
- **驗收不是比畫面。** 後續施工須以 GUI／CADSplit 來源 adapter 建立等價的真實 Engine Request，確認**同一正式公開 API**、真實 DXF reopen、Save→Reload、各種 Family／Part、缺項逐件隔離與整套組裝判斷；未執行不可宣稱通過。**此文件寫入只確認架構要求，不能聲稱 CADSplit 已全面接線、外部 export 已認證或 #2517 已完成。**

本節為 `manufacturing-architecture` 唯一 CURRENT；API REFERENCE 與 Skills 必須服從，**不得再建立第二份製造 authority／新 SOP／平行 API**。


## [CURRENT] #2517 Settings Fold Profile 計畫由同一公開 Engine API 決定（2026-11-02）

- `ae_engine.manufacturing_api.plan_operator_settings_fold_profiles(...)` 為 Settings 包外尺寸 → 物理板件 Fold 計畫的唯一計算／保留權威，Head/Tail X/Y、Door／BasePlate／CustomFold、BoxBody，與 derived physical IDs 遵循同一實體 identity policy。
- GUI `phase6_settings_profile_projection.build_settings_profile_projection` 只把不可變操作輸入轉送 Engine，將回傳值裝回唯讀 `SettingsProfileProjectionPlan`；不得再自算 reset、keyed merge、Tail 裝配 Fold 順序或 active physical profiles。
- Engine 單獨接受無 Tk 的 source snapshot/settings/profile，返回 detached snapshot、part_dimensions、box_body_profile、part_profiles、active_profiles 與 derived_sync_required；既有專案的自訂 Fold/保存後回讀必須保留，invalid CustomFold metadata 必須拒絕。此投影不是正式 DXF 製造放行。


## [CURRENT] #2517 BoxBody 即時 2D 面尺寸由公開 Engine 單一來源投影（2026-11-02）

- 原 `gui_modules/application/render_snapshots.box_body_render_snapshot` 直接引用 `ae_engine.sheetmetal_features.box_body_face_dimensions`，沒有遵守 GUI 只使用公開 `manufacturing_api` 的設計。現在一般箱身 2D 面預覽把 W/H/D 交由 `manufacturing_api.project_operator_box_body_face_dimensions(w=...,h=...,d=...)`；接收箱實體 SIDE 的 FinalScene 路徑維持不變。
- 公開 API 先沿用 `normalize_operator_source_dimension`，拒絕 bool、非有限、零／負的物理尺寸，再委派原 Engine `sheetmetal_feature_core.box_body_face_dimensions`；不另寫或改變面尺寸公式，左／背／右面 tuple 及順序一致。保留測試可注入的 `face_dimensions_fn` 相容 seam，正常 GUI 預設固定走 Engine。
- 驗收 `tests/test_issue2517_box_body_face_2d_render_engine_api.py`；不影響 DXF 認證，正式 X 未發布。

## [CURRENT] #2517 即時 2D 指示燈盒／小門／主門與保存快照同一群組來源 Engine API（2026-11-02）

- 原 `gui_modules/application/render_snapshots.py` 三條 live 2D 預覽路徑（獨立指示燈盒、指示燈小門及主門的兩種指示燈）仍以 `max(1, int(...))` 自行解釋層數／組數。這會在即時預覽將 `0` 靜默補成一層，將 `True` 轉成 1，或把非整數 float 截去小數，與已修好的 Fold Designer project snapshot 保存來源不一致。
- 現改為所有啟用的 live 2D 指示燈先交由既有公開 `manufacturing_api.normalize_fold_designer_indicator_groups` 處理層數及每層組數；GUI 只收集原始控制值，任何缺列、bool、無效字串、零／負數、小數來源均 fail closed。無效來源不可以通過 `_indicator_box_part_spec`、`_indicator_door_part_spec_from_values` 或 `_single_door_part_spec`，避免 2D 空洞錯漏與製造投影不一致。
- 保留不啟用時的原有空指示燈語意、合法整數群組、既有 Family 幾何、Save→Reload 與 DXF 認證；沒有另設 Engine／GUI 版本化製造入口。驗收 `tests/test_issue2517_live_indicator_render_groups_engine_api.py`。

## [CURRENT] #2517 Fold Designer 上游 W/H/D/T/FW 實體操作讀取不得掉回 AE 預設（2026-11-02）

- `gui_modules/application/fold_designer_snapshot_projection._snapshot_base_state` 原本用 `float(var.get())`，遇到 W/H/D/T/FW 控制值無效／讀取異常會無聲退回 `ae.W/H/D/T/FW`，令實際操作來源被預設值替換後繞過下游製造檢查。現在 GUI 只負責讀值，傳至 `manufacturing_api.normalize_operator_source_dimension(value, field=...)` 與 `normalize_operator_source_dimensions(snapshot)`（Engine 公開 API），統一拒絕來源缺失、bool、NaN/Inf、零或負值。
- `_collect_main_setting_values()` 回傳的已套用 Settings 若覆蓋了原物理欄位，在完成快照前亦由 Engine 全面驗證；合法的 W/H/D/T/FW 保留原小數精度，Snapshot 與其中的 Settings payload 不得不一致。其他非實體 UI 欄位延用原容錯，GUI 不新增幾何公式。
- 此更改只消除入口的假預設和保存不一致；不是把未認證的 CADSplit source-only 視為正式製造輸入，不增加 CUTTING／BEND／DXF 認證，也不發布正式 X。測試 `tests/test_issue2517_fold_designer_snapshot_source_readback_engine_api.py`。

## [CURRENT] #2517 Fold Designer 指示燈操作來源／快照物理尺寸不得靜默降級（2026-11-02）

- 原 `ae_engine.fold_designer_snapshot_dimensions.project_fold_designer_snapshot_dimensions` 遇到指示燈盒群組或製造 policy 異常，會默默替換成 `groups=(1,)`／預設 `ManufacturingContext()`，讓專案快照看起來像有效的製造來源；現改成 Engine 直接驗證並拒絕無效的層數／組數／成品尺寸，不得把 `bool`、小數群組、零／負數變成實體孔位。既有 public `manufacturing_api.project_fold_designer_snapshot_dimensions` 保持同一入口；新增共享的 `normalize_fold_designer_indicator_groups` 供 GUI 操作來源消費。
- `gui_modules/application/fold_designer_snapshot_projection._snapshot_part_dimensions` 只讀取啟用中的兩類指示燈操作欄位（盒體與門板直裝），兩者都完成 Engine 驗證後才一次寫入 snapshot。啟用時組數失敗不可偷偷寫 `[1]` 或 `[]`，不得遺失 CUTTING 孔位；停用時沿用既有一層的純顯示預覽種子（不構成實際製造要求）。
- Engine 投影不再將門板／底板物理尺寸以 `max(1, …)` 捏造 1 mm；非法尺寸 fail closed。正式 CUTTING／BEND／DXF 權威與原認證狀態不變；未發布 X。回歸 `tests/test_issue2517_fold_designer_snapshot_dimensions_engine_api.py`。

## [CURRENT] #2517 Settings 外部布林同步與包外 W/H/D 交易一致性 Engine API（2026-11-02）

- `ae_engine.manufacturing_api.normalize_operator_settings_updates(settings_values, updates, external_apply_guard=...)` 由 Engine 統一轉換外部操作的布林值（`"false"` 不再被 `bool(raw)` 當成 true），以及 W/H/D 等保存實體欄位。無法辨認的明確布林輸入直接拒絕；W/H/D 必須為正、有限、非 bool 的包外尺寸。舊版非物理數值欄位的未知 key／無效字串仍可略過，但 NaN/Inf 不得污染值。純視覺 `ui_text_size` 選擇維持 GUI owner，不在 Engine 生產值中判斷。
- `commit_operator_settings_state(settings_values, input_snapshot, box_whd, values)` 在同一不可變交易裡先驗 W/H/D，再將完全相同且保留小數的包外值提交至 Settings、保存 Snapshot 和 `box_whd`。原 `_ui_len` 會 round(abs(...))，可能將負尺寸變成正尺寸／將小數折後包外值改掉，已禁止用於實體 W/H/D 交易；Fold Editor 純顯示整數規則不變。無效來源不可部分提交，也不能拿預覽反推正式製造尺寸。
- `phase6_settings_transitions.normalize_updates/commit_settings` 現僅負責 GUI 選項及委派 Engine；`SettingsCommitTransition` 保留型別相容別名。涵蓋金庫型／受電箱、Save→Reload、非法文字／零／負數／NaN／Inf／bool、精度與無變異驗收 `tests/test_issue2517_operator_settings_transactions_engine_api.py`；不新增 DXF 認證或正式 X 發行。


## [CURRENT] #2517 EndCap Relief 3D fallback 選項由 Engine 型別驗證（2026-11-02）

`phase6_manufacturing_adapter.build_manufacturing_request` 與 `ae_engine.manufacturing_contracts.ManufacturingResolveRequest` 原分別對 `assembly_ignore_fixed_corner_var`／`allow_3d_fallback` 呼叫 Python `bool(...)`，導致舊字串 `"false"` 被誤當成 True，繼而將錯誤的 3D fallback 允許選擇傳到 `manufacturing_resolver.solve_endcap_assembly_relief`。新增 `manufacturing_api.normalize_operator_3d_fallback_flag(raw)`：原生 bool、0/1 整數與浮點及明確文字 `true/false/1/0` 可正確正規化；空字串或 None 為 False，不明文字／非 0/1 數字／物件拒絕。GUI 只讀取操作值；Engine Request 在 immutable fingerprint 前再次驗證。原 EndCap relief 幾何、實際 source/certification、Joint solver、CUTTING、DXF 皆不改，也不新增外部製造授權。#2517 OPEN。


## [CURRENT] #2517 Assembly Joint relief clearance 製造 Request 單一 Engine API（2026-11-02）

`phase6_manufacturing_adapter._relief_clearance` 原在 GUI 側將操作欄位 `max(0, float(...))` 並在無效文字時回退 0，造成實體 Joint clearance 的裁切、壞資料處置不一致。現由 `manufacturing_api.normalize_operator_relief_clearance(raw)`（`ae_engine.manufacturing_contracts`）作唯一數值權威：空欄／缺值 0、有限非負值保留、負數歸零、非法／非有限／布林來源明確拒絕。`ManufacturingResolveRequest.__post_init__` 重用同一函式並保留既有十二位小數正規化，使 GUI 與 headless request 一致。GUI 僅讀 Tk 欄位、呼叫公開 API。本批不改 Joint 工廠幾何、補償、碰撞或退讓算法，無新增 CUTTING、DXF 製造放行或外部 export 認證。#2517 OPEN。


## [CURRENT] #2517 箱身分片設定物理值與鎖定切換統一 Engine API（2026-11-02）

- `ae_engine.manufacturing_api.project_operator_box_body_structure_settings(state, total_w, snapshot=...)` 直接由 canonical `ae_engine.box_body_structure_state` 和 Family policy 回傳箱身四種結構的實體 ID、二片／三片 W 包外值、受電箱側板後折 OUTSIDE／MATERIAL datum、後板寬補償和避讓留肉設定。保存 W 矛盾立即拒絕，GUI 不得自行計算另一份。
- `operator_toggle_box_body_structure_lock(state)` 先由 Engine Save→Reload normalization 解碼歷史文字 `locked="false"`／`"0"`，再不可變地切換，禁止以 `bool("false")` 誤判鎖定。原公開 `activate_structure_with_defaults`、`reconcile_box_body_structure_for_total_w_change` 在 Settings adapter 直接呼叫。
- GUI `fold_designer_composition_settings.py` 只展示真實資料與控制項，沒有增加 CUTTING、BEND、DXF 或任何新的製造認證。驗收測試 `tests/test_issue2517_box_structure_settings_projection_engine_api.py` 覆蓋兩種 Family／四種結構、Save→Reload、矛盾尺寸 fail closed 和舊資料鎖定值。

## [CURRENT] #2517 BoxBody 製造請求的 Head/Tail 下折段來源 Engine API（2026-11-02）

`phase6_manufacturing_adapter.build_scene_payload_for_app` 原本在 GUI 相容層以 `phase6_key="ybottom1"` 掃描封頭／封尾 Y Fold profile，並將 `engine_segment_length_to_ui` 的物理長度回讀寫到 `head_ybottom1`／`tail_ybottom1`，形成製造 request 的實體折段身份決策。現改由 `manufacturing_api.project_manufacturing_endcap_bottom_fold_inputs(endcap_profiles)`（`ae_engine.endcap_xy_readback`）唯一辨識 Head/Tail 來源並用既有 `fold_material_segment_outside_length`（含相鄰 BEND 的 `ui_len_add`）回讀；GUI 僅將已儲存 profile map 作為輸入，未辨識來源時不覆寫任何數值；已辨識但無法解析／非有限的原始折段長度則明確拒絕，不能將舊 `_num` 展示 fallback 的 0 mm 當成製造來源。這是現行製造 API 的物理輸入接線，不新增 EndCap 截角、Joint、料長補償、CUTTING 製造公式，也不解鎖未認證的 Receiving 外部 export。#2517 OPEN。




## [CURRENT] #2517 受電箱內門 NFB 作業區高度與層高檢查 Engine API（2026-11-02）

`fold_designer_composition_receiving.inner_edit` 過去在 Tk 的「讀取層高」及「草稿預覽」兩處各自呼叫 `derive_door_layout_cells`、推算第一列 Door 工作區高度，並自行比較操作層高是否超出工作區。現將兩處收斂到 `manufacturing_api.project_receiving_nfb_work_area_height_mm(snapshot)` 與 `manufacturing_api.validate_receiving_nfb_layer_heights_for_work_area(snapshot, heights, *, layer_count)`，唯一實作在 `ae_engine.receiving_operator_projection`，沿用 `receiving_shared_settings.validate_setting` 對兩槽數值與一／二層的合法性判斷。單一上排 Door cell 取該實體 cell 的高度；沒有唯一上排 cell 的既存相容模式仍回退原 snapshot `h`，但無效、非有限或非正尺寸拒絕投影。GUI 僅讀 Tk 欄位、呼叫 API、顯示錯誤／唯讀預覽；不改既有一層 550、兩層 330／830、舊版 290／790（未寫入 operator heights 時）等不同權威來源，**不開放切孔、名義 Y 認證、成品出圖或外部製造授權**。#2517 OPEN。


## [CURRENT] #2517 受電箱兩片門原始來源身份與 Bay 拓樸 Engine API（2026-11-02）

`gui_modules/application/fold_designer_composition_receiving` 的 Set/Bay 原始門預覽原先在 GUI 呼叫私有 `project_receiving_bay_legacy_aliases`、`derive_door_layout_cells`，並自行判斷「只有一欄、兩片實體 Door」；初始來源又由 GUI 字串比對 Family 與 `door_c1_r1/r2` 製造身份。兩段現改從 `manufacturing_api.project_receiving_operator_door_cell_sources(snapshot, *, set_index, bay_index)` 與 `manufacturing_api.project_receiving_initial_door_source_scenes(snapshot, resolved)` 取得 Engine 已確認的 Bay snapshot/typed DoorLayoutCell 及已解析 Assembly 的真實原圖場景順序。GUI 只向既有 baseline scene provider 要求圖元並透過 `project_receiving_original_door_marks` 顯示；來源缺失、未啟用雙門、多欄／三列等不符目前兩面 sketch 的拓樸均維持不投影，無隱含單門 fallback。Engine 保持對既存 Save→Reload／Bay stable ID、原 scene 與 Source Type 的唯一識別；這是唯讀 SOURCE 顯示映射，**不構成生成新孔、CUTTING、成品 3D 或 DXF 製造認證**。#2517 仍 OPEN。




## [CURRENT] #2517 封頭／封尾 FW、WRAP reserve、Joint 交易單一公開 Engine API（2026-11-02）

原 `phase6_settings_transitions` 在 GUI 側合成 EndCap FW follow／override、Head/Tail WRAP reserve 和 Assembly Joint 交易，雖然最終呼叫 Engine 低層 helper，GUI 仍決定快照組合、source fallback 與物理 state 提交。現在 `manufacturing_api.operator_endcap_fw_follow`、`operator_endcap_fw_override`、`operator_endcap_bottom_wrap`、`operator_endcap_edge_relation` 統一擷取不可變 copy-on-write 輸入並呼叫既有 `endcap_factory_fold`、`endcap_bottom_wrap_state`、`assembly_joint` Canonical owner。WRAP 傳回 Engine `OperatorBottomWrapTransition(state,resolved)`；GUI 舊名稱 `BottomWrapTransition` 僅為型別別名。沿用金庫型／受電箱現有 FW 四態、Head/Tail linked→leader→independent、Joint Graph 優先、保存狀態及拒絕未支援板件，不變更工廠補償、Registry、DXF 認證或原始製造入口。#2517 仍 OPEN。



## [CURRENT] #2517 封頭／封尾 FW、WRAP reserve、Joint 交易單一公開 Engine API（2026-11-02）

原 `phase6_settings_transitions` 在 GUI 側合成 EndCap FW follow／override、Head/Tail WRAP reserve 和 Assembly Joint 交易，雖然最終呼叫 Engine 低層 helper，GUI 仍決定快照組合、source fallback 與物理 state 提交。現在 `manufacturing_api.operator_endcap_fw_follow`、`operator_endcap_fw_override`、`operator_endcap_bottom_wrap`、`operator_endcap_edge_relation` 統一擷取不可變 copy-on-write 輸入並呼叫既有 `endcap_factory_fold`、`endcap_bottom_wrap_state`、`assembly_joint` Canonical owner。WRAP 傳回 Engine `OperatorBottomWrapTransition(state,resolved)`；GUI 舊名稱 `BottomWrapTransition` 僅為型別別名。沿用金庫型／受電箱現有 FW 四態、Head/Tail linked→leader→independent、Joint Graph 優先、保存狀態及拒絕未支援板件，不變更工廠補償、Registry、DXF 認證或原始製造入口。#2517 仍 OPEN。


## [CURRENT] #2517 受電箱原始門板把手／銘牌孔位來源辨識 Engine API（2026-11-02）

原 GUI `gui_modules/application/receiving_multi_settings_window.extract_original_door_marks(scene)` 會自己從 `DrawingScene` 的 `CUTTING` 外框、帶 `source_type="nameplate_mount"` 身分的圓孔與唯一內輪廓判定門板把手與銘牌孔位，形成第二份來源辨識邏輯。現保留既有函式作兼容 GUI 單向轉接，將原算法原樣移至 `ae_engine.receiving_operator_projection.project_receiving_original_door_marks(scene)`，對外公開 `manufacturing_api.project_receiving_original_door_marks(scene)`。回傳既有正規化預覽 `{"nameplate": ..., "handle": ...}`；缺外框／多個內框時拒絕猜測，保留來源 Layer 與身分條件，GUI 只按比例繪圖，不再認定物理孔位。這是原圖來源的唯讀預覽映射，**不是補充新孔位、CUTTING 修改、成品尺寸定義或 DXF 製造認證**。#2517 仍 OPEN。


## [CURRENT] #2517 Fold Designer 截角選單／Joint snapshot 與 NFB 來源預覽公開 API（2026-11-02）

`gui_modules/application/fold_designer_snapshot_projection.py` 原本在 GUI 直接引用 `ae_engine.corner_type_ui` 的自訂型號判斷、`sheetmetal_geometry` 的截角選單常數及 `assembly_joint.migrate_legacy_snapshot_joints`。現由 `manufacturing_api.project_operator_corner_selection_catalog(model, baseline_models)` 提供凍結的選單資料，並由 `manufacturing_api.project_operator_assembly_joint_snapshot(prior_state, *, existing_parts, assembly_type)` 將操作者的現有實體清單與已選組合型態交給原 Engine Joint v2 migration。GUI 僅存回 Engine 回傳的 schema/joints，保留原本金庫型、受電箱、舊版自訂 alias、既存使用者 Joint 與 Save→Reload 行為，不另造 Joint 物理規則。另將舊 NFB DXF 真實來源的唯讀 `NfbDxfPreviewCache`／`Nfb2DViewport` 經 `manufacturing_api` 公開供 GUI 顯示，維持原 CSV 身分／來源 revision 防混用；這只是 SOURCE preview，**不開啟 CUTTING、MFG-2、整箱製造、外部 CLI export 或新 Factory 認證**。#2517 仍 OPEN。



## [CURRENT] #2517 受電箱固定片來源 2D 實體輪廓唯一 Engine API（2026-11-02）

`manufacturing_api.project_receiving_fixing_plate_source_2d(preview)` 接收 Engine 的 `BaseFixingPlatePreview`，嚴格檢查來源輪廓、孔位、T2、原 DXF 折線與孔組，從 `ae_engine.receiving_base_fixing_plate_geometry` 唯一已登錄來源 `_outline/_slot` 產生不可變 `FixingPlateSourcePreview2D` 顯示 DTO；孔組距離由原始位置推導，不在 GUI 硬編。GUI `phase6_navigation_view_adapter.show_receiving_base_fixing_plate_preview` 僅做 Tk 像素繪製，移除另一套圓弧／長圓孔物理計算及錯誤 T3、無 BEND 文案。實際原始來源為 T2 256×105，含既有 BEND 線；此 Preview **不提供折向／焊接 Z／成形或整箱製造認證**，不解鎖 DXF 或外部 source-only export。#2517 仍 OPEN。


## [CURRENT] #2517 實體 2D 板件孔位與受電箱內門板快取資格 Engine API（2026-11-02）

`gui_modules/application/fold_designer_manufacturing_projection._query_fold_designer_render_data` 不再從 GUI 直接 import `ae_engine.physical_sheet_features.with_physical_sheet_features` 做展開板件孔位幾何，也不在 GUI 判斷 Receiving Family/Set-Bay 或呼叫 `phase6_manufacturing_contracts.manufacturing_fingerprint` 取得內門板素材快取鍵。前者由既有實體孔位函式直接經公開 `manufacturing_api.with_physical_sheet_features` 傳入同源實體 Render/Features；後者由 `manufacturing_api.project_operator_inner_door_panel_preview_cache_signature(snapshot, panel, features)` 在 `ae_engine.receiving_raw_source_cache` 統一校驗實體 `InnerDoorPanelPart`、Family、當前實體 Bay 與 typed Feature 指紋，並與既有 panel ticket 共用算法。GUI 只保留對不可變素材的 LRU、操作者輸入與畫面呈現；簽章只證明 raw preview 輸入相同，不能當作製造、CUTTING、外部 export 或 Save→Reload 認證。#2517 OPEN。

## [CURRENT] #2517 原 DXF 出圖路由與未配置底板的重試資格移回 Engine API（2026-11-02）

原 `gui_modules/project/export_actions.py::_export_selected_resolved_parts` 自行認定金庫型合併模式、Receiving EAR/NFB 已提交 CSV 與舊式出圖前置拒絕的條件；`export_selected_dxf` 用製造錯誤字串判斷是否允許排除尚未配置底板。現在改用現有 Engine `manufacturing_selected_export` 擴充公開 `manufacturing_api.plan_selected_resolved_export_route` 取得 frozen 出圖路由計畫，及 `plan_unconfigured_receiving_base_export_retry` 僅對既有明確未配置底板錯誤產生排除底板之候選操作意圖。GUI 不得自行解釋來源證明、ERROR 或認定缺底板可製造；GUI 仍保有使用者明確同意的對話框，拒絕時不動既有檔，接受後必須以原 Engine 實體來源與嚴格製造 API 重跑。沿用既有 Vault/Receiving API、CURRENT NFB CSV、EAR 側板、PAD、保存來源漂移、DXF 逐片重開及原子輸出，**沒有新增任何製造認證或外部 source-only export**。#2517 OPEN。

## [CURRENT] #2517 Fold Designer 單件／多片箱身板料渲染路由 Engine API（2026-11-02）

`gui_modules/application/fold_designer_manufacturing_projection._authoritative_render_data` 原本在 GUI 比較 `BoxBodyPartSpec`、`BoxBodyStructureType.INTEGRAL` 與 `normalize_box_body_structure_state`，自行選 `build_part_render_data` 或 `build_box_body_structure_render_data`。現統一呼叫公開 `manufacturing_api.build_operator_part_render_data(spec, context)`；Engine 從同一份 canonical typed `PartSpec` 與結構 state 決定實體板件的單片或多片 FinalScene，GUI 只管理前輪由 Engine 來源證明的 LRU 與結果呈現。沿用原有 Factory Render、完成面規則與舊未知結構相容路由；不另建板件拓撲公式、Family 補償或外部製造通道，正式 DXF/Save→Reload/Registry/Collision 驗證仍不變。#2517 OPEN。

## [CURRENT] #2517 Receiving 原始板料重用資格與來源證明改走 Engine（2026-11-02）

`gui_modules/application/fold_designer_manufacturing_projection._authoritative_render_data` 曾在 GUI 自行判斷是否為受電箱 Set/Bay、哪些未解聯立 relief 的 Head/Tail 或 BoxBody 才能跨 W/H/D 暫存原始 `PartRenderData`，並在 GUI 選三片式實體後讀基準 DXF witness。現以 `manufacturing_api.plan_operator_raw_material_reuse(spec, snapshot, context=...)` 由 `ae_engine.manufacturing_cache_source_plan` 回傳 `OperatorRawMaterialReusePlan(eligible, source_stamp)`；必須維持原本 3 張基準檔、三片式實體專用 DXF、Head/Tail `封頭尾.dxf` 存在與新鮮來源條件。GUI 只負責 LRU capacity、快取命中與來源變動清除，不持有 Family／實體板件／來源資格製造規則。此快取只供 exact-typed raw 板料性能重用，正式 FinalScene 的 Joint／碰撞／組合／DXF CUTTING 與 Save→Reload 必須照常每次執行，不能以 source_stamp 或快取代表認證，亦不增加外部製造權限。#2517 OPEN。

## [CURRENT] #2517 Fold Designer 製造前來源驗證單一 Engine API（2026-11-02）

`gui_modules/application/fold_designer_manufacturing_projection.py::_require_verified_baseline_sources_for_manufacturing` 不再直接呼叫低層 `ae.baseline_part_path`／`ae.load_baseline_dxf_source_with_status` 或自訂箱身、封頭尾、門的 DXF 驗證策略；GUI 僅提供使用者當下選定的 model，交由正式 `manufacturing_api.require_verified_operator_baseline_sources(model_name)`。真正來源選取與新鮮 `VERIFIED` 解析由既有 `ae_engine.manufacturing_baseline_policy` 單一 Engine owner 執行，維持原本未指定型號及不存在之 optional baseline 不在此預檢自行造來源、存在但無法驗證者拒絕正式 export；不把舊預覽的 last-known-good 當可製造證據。正式 PartSpec／FinalScene／Factory Policy／Registry／DXF Save→Reload 的原有出口與驗證仍必須執行，這項 source preflight 本身不增加金庫型或受電箱的製造認證，也不開放 source-only 外部 export。#2517 OPEN。

## [CURRENT] #2517 Receiving 封頭／封尾 Hole Editor 完成面及共享孔位 Engine API（2026-11-02）

原 `fold_designer_composition_receiving.receiving_settings_ports.holes` 在 GUI 直接計算當下 Bay 的 W/D/T、EndCap 完成面 `resolve_endcap_finished_face_guide`、`feature_surface_from_rect`、原點參考 `RectGuide`，並自行調用 `receiving_shared_settings.setting_value` 讀取連動的 Head/Tail 孔。現改由無 GUI／Phase6 反向依賴的 `ae_engine.operator_receiving_endcap_hole_context` 提供 `manufacturing_api.project_receiving_endcap_hole_editor_context(snapshot, layout, set_index, bay_index, role)`；以同一份已驗證 Receiving Family 與當前實體 Set/Bay 的 canonical Width/Depth、CURRENT 07 完成面折彎語意、既有 Head/Tail Shared Settings 回傳同源 `surface`、`reference_guide`、`features`、W/D。GUI 只開既有 Unified Hole Editor，保持原 Session 交易、勾選多連分享／取消、Save→Reload 與來源 Hole Features 回存路徑；不得將快取或 CADCraft CHECK 當製造來源。非 Receiving、虛假角色、bool Set/Bay、跨連借材、無效實體都拒絕，不新增任何 NFB／PAD／EAR／外部製造放行。#2517 OPEN。


## [CURRENT] #2517 GUI 實體板件選取與匯出核取來源統一 Engine API（2026-11-02）

受電箱雙層實體底板、內門板，以及金庫型單門／多門原先由 `gui_modules/parts/panels/common.py::logical_part_present` 判斷物理 ID，主選擇 DXF 的 `gui_modules/project/export_actions.py::_selected_export_flags` 也自辨識 Receiving/NFB 真實板件並推算匯出核取旗標。現統一由公開 `manufacturing_api.logical_part_present`、`selected_project_export_flags` 依已存在之實體 ID 和已提交 NFB 來源決定；GUI 只收集當下勾選值、主畫面舊清單、workspace 已存在之身分。未提交、非 Receiving 或只有固定耳的假底板不得認定為已存在；雙層底板、內門、金庫型舊門格相容。此為選擇入口權責遷移，不授權製造；原 Engine FinalScene／CSV／PAD／EAR／NFB、Save→Reload、DXF 回讀與原子交易皆不變。#2517 OPEN。


## [CURRENT] #2517 Receiving 多 Bay 匯出來源決策與獨立 NFB 預覽 Engine API（2026-11-02）

`gui_modules/project/export_actions.py::_export_selected_resolved_parts` 不再自行決定受電箱實體 Bay 數、分組單 Bay 合格性及 Head/Tail/外門獨立出圖時的 NFB 提交狀態遮蔽。統一呼叫 `manufacturing_api.plan_receiving_multibay_export_source(snapshot, flags, group_mode)` 取得 detached `ReceivingMultiBayExportPlan`，使用 `preview_layout_for_bay(si, bi)` 產生不變動保存來源的局部預覽。任何包含底板、箱身等 NFB 依賴板件都不遮蔽真實 NFB，且舊未分組單 Bay 繼續走既有出圖。GUI 僅取得真實 Bay FinalScene 並傳入原正式 Engine 匯出入口，既有 CSV、EAR/PAD、幾何、DXF 重開、來源漂移、原子提交及不完整來源拒絕全部保持，沒有新增製造資格或外部能力。#2517 OPEN。

## [CURRENT] #2517 PAD＋底板版本／Set-Bay 出圖來源移至 Engine API（2026-11-02）

GUI `export_receiving_pad_base_part_only_dxf` 不再解析 QuantityModel 的 selected version、Set/Bay 單連 fallback 或自行組裝物理輸出身份；它只取操作者材質／製程／Q，並呼叫 `manufacturing_api.resolve_receiving_pad_base_export_source(snapshot)` 取得與當下已提交來源一致的獨立快照及 `version_id`，再交原有 `export_verified_pad_base_part_only` 執行實體 PAD+Base CHECK/Q。Engine 沿用既有 QuantityModel、project_common_box 與 Set/Bay authority，不重建 Family 或出口；錯誤版本、缺少／不一致 NFB、模糊多 Bay 都拒絕。GUI 的有命名 DXF 覆寫提示也改用既有 `resolve_live_cabinet_family`，支援 Receiving 正規別名；不得藉來源解析授權整箱、EAR 焊接、PAD MFG-2 或任意 export。#2517 繼續 OPEN。



## [CURRENT] #2517 Receiving 原始門板／框／隔板製造素材快取來源 Engine API（2026-11-02）

受電箱 `fold_designer_composition_receiving.py` 的 `_receiving_cached_bay_inner_door_panel`、`_receiving_cached_bay_inner_door_frame`、`_receiving_cached_bay_box_body_divider` 原在 GUI 判斷 Family／Bay、製造物理 Spec、來源 DXF 解析器代次與完整 SHA256、原成品 features，並自行核對實體素材 metadata 可否沿用。現統一移至 `ae_engine.receiving_raw_source_cache` 及公開 `manufacturing_api.receiving_raw_source_cache_kind`、`project_receiving_raw_source_cache_ticket`、`receiving_raw_source_cache_entry_valid`；GUI 只持有各 8 筆 LRU 及委託既有 PartSpec API／Factory。Frame A/B/D 需完整 `框.dxf` path／parser generation／bytes SHA 與回傳 metadata 匹配；Divider 需 `中隔.dxf` 與 `封頭尾.dxf` 兩份來源及 Ø6.4 mother rule metadata 完整匹配；Panel 只接受已存在於 canonical Family 內門板的純實體規格與孔位組合。Family 別名使用 Registry，而不是 GUI 的兩組敏感字串。未受支援的任何模式、缺來源、不完整 DTO、來源更新、Factory metadata 不一致均回落既有 Engine 正式工廠，不得快取假權威。整體 FinalScene、碰撞、材料 2D/3D／製造 DXF 必須仍做 canonical resolve；來源快取只是 GUI 效能，不能當出圖資格。#2517 OPEN。


## [CURRENT] #2517 Receiving 2D 實體底板／PAD／固定片來源單一 Engine API（2026-11-02）

`fold_designer_manufacturing_projection.py::_query_fold_designer_render_data` 不再自行認定 NFB 單層原底板、雙層 `base_plate:nfb_layer:[01]`、source-backed PAD 或原固定片的 2D 實體材料、Bay 來源漂移與 MFG status。新增 `ae_engine.operator_receiving_physical_2d`，由既有正式 `manufacturing_api` 公開 `resolve_operator_receiving_base_2d_source`、`resolve_operator_receiving_pad_2d_source`、`resolve_operator_receiving_fixing_2d_source`，直接委派已存在的 committed NFB/BasePlate/PAD/EAR source owners 和 canonical ResolvedManufacturingGeometry；GUI 只傳當前來源、供應既有 geometry resolver 與將 RenderData 套上特徵。選定 Bay 必須匹配同一真實 Set/Bay 的 W/H/D、Door/NFB 身分，禁止跨 Bay 借材；缺來源／偽造 PartKey／PAD 冒充可製造均維持拒絕。此輸出只代表原實體 2D RenderData；正式 DXF、MFG-2、EAR／PAD 工法尚未獲放行，必須照 Certified Registry gate。#2517 OPEN。


## [CURRENT] #2517 Receiving EAR 側板顯示與 CHECK 來源別名統一（2026-11-02）

`receiving_ear_side_display_context`、`receiving_ear_side_preview` 與舊有 CHECK-only DXF 來源驗證統一經 `cabinet_types.policy.canonical_family_name` 識別已註冊的 Receiving Family aliases，不再在 Engine／GUI 各維護一份僅匹配「受電箱」「RECEIVING」的判斷。2D 的 GUI 只傳 FoldDesigner 來源，必要時把 primary mirror 交 Engine 判斷來源漂移；CHECK 動作先呼叫 `manufacturing_api.receiving_ear_side_check_operator_inputs` 做無副作用的提交／模式／尺寸預檢，再走原 `export_receiving_ear_side_check_only_dxf`。來源側真實物理板材、UV／折彎／CUTTING 衝突、正反側 MARKING、DXF 原子儲存重開及失敗拒絕不變。CHECK 永遠是非製造驗證，不能授權 EAR 焊接、NFB/PAD MFG-2、整箱或 source-only 外部 export；金庫型仍拒絕。#2517 OPEN。


## [CURRENT] #2517 Receiving Bay 2D／3D 預覽快取資格回歸 Engine API（2026-11-02）

`fold_designer_composition_receiving.py` 原自行決定何種 Set/Bay／Joint／NFB／自訂板件改動可重用實體預覽、忽略哪些來源 Joint lock feature、何時允許平移快取 3D 實體。現將這些物理來源依賴判斷遷至無 GUI／Phase6 依賴的 `ae_engine.receiving_bay_preview_source`，公開 `manufacturing_api.project_receiving_bay_preview_fingerprint_snapshot`、`project_receiving_bay_preview_face_features_key`、`receiving_default_local_joints_only`、`plan_receiving_bay_preview_offset_rebase`；GUI 保留相容代理與 immutable FinalScene View 容器包裝、快取 LRU/Session UI。未知 cross-Bay Joint、source/Feature/metadata 及碰撞/干涉狀態不准重用；所有實體正式製造／DXF 必須仍走 canonical resolve，預覽快取與座標平移不能當製造證明。沿用 #1817 大量真實 Set/Bay／joint、2D/3D、保存回讀及來源 SHA 測試。#2517 OPEN。


## [CURRENT] #2517 Receiving Set/Bay 共用設定／NFB 交易公開 Engine API（2026-11-02）

`ReceivingSetBayAdapter` 原直接呼叫 `ae_engine.receiving_layout`、`receiving_shared_settings`、`receiving_nfb_transactions` 與製造 Readiness 內部模組，現改為只經 `manufacturing_api` 公開入口操作 Set/Bay／Joint 追加、刪除、更新、來源 stable_id、每連設定分享／解除分享、NFB 原子 Submit／Copy／Restore／Undo、開關品牌及 Readiness。真正的交易、來源資格與資料驗證仍由既有 Engine owner 實作；GUI 不複製公式，只保留 Session 選取、刪除確認、Undo 收據與 dirty flags。原 `receiving_layout_stable_ids` 名稱在 GUI 留相容代理，實作搬回 `ae_engine.receiving_layout`。金庫型、原 Factory/Registry、2D/3D/DXF、Save→Reload、source-only gate 不變；NFB 來源證據與 explicit Confirm／optimistic Undo 保持原拒絕語意，不新增製造放行。#2517 OPEN。


## [CURRENT] #2517 Receiving BasePlate／EAR／PAD 正式 Family aliases 單一來源（2026-11-02）

`receiving_base_plate_config.receiving_base_plate_values`、`receiving_base_fixing_plate.receiving_base_fixing_plate_previews`、`receiving_nfb_pad_operator_parts.committed_nfb_pad_draft_parts` 不再在 Engine 內用僅匹配「受電箱」「RECEIVING」大小寫敏感的第二份族別字串決策，改委派 `cabinet_types.policy.canonical_family_name`／既有 Registry aliases；以同一實體提交的 numeric V5 CSV、Set/Bay 與來源折型條件決定是否能投影。金庫型及非 Receiving Family 仍不得冒名取得底板／EAR／PAD，舊保存資料與 Factory 機械公式不變。此修復只消除 Family alias 路徑分岐；正式 BasePlate DXF 繼續沿用唯一 `generate_part` 與原來源 Gate；PAD、EAR、NFB MFG-2 未獲新增製造資格，source-only `EXTERNAL_EXPORT_NOT_CERTIFIED` 保持拒絕。#2517 OPEN。


## [CURRENT] #2517 派生板件選單 Receiving BasePlate／NFB Tier／PAD／EAR Engine API（2026-11-02）

`manufacturing_api.project_operator_base_navigation_identity`、`project_operator_multidoor_base_plate_dimensions`、`project_operator_receiving_auxiliary_navigation` 將 Fold Designer `sync_authoritative_derived_parts` 中原 GUI 直接認定實體根底板／雙 NFB Tier／門格底板收縮、補出已提交來源、固定片與 PAD 的實體資格及 2D Fold Profiles，統一搬入無 Tk 的 `ae_engine.operator_derived_navigation`；由原 `receiving_base_plate_values`、`receiving_nfb_layer_centers`、`receiving_base_plate_3d_profiles`、`committed_nfb_pad_draft_parts`／Fixing Plate source owner 判定來源。GUI 只擷取 Workspace 即時孔位／已保存快照、透過公開 API 接收 Profiles 並呼叫現有 `Phase6WorkspaceNavigationController.sync_derived_parts`，保持當前選取、已儲存／候選 PAD 來源優先與兩層隱藏根底板規則。這些選單 Fold 行與固定片圖樣僅供顯示，絕不新增 NFB MFG-2、PAD/EAR 焊接製造放行、外部 source-only Export 資格；2D/3D/DXF 正式製造仍由唯一 FinalScene／Registry owner 決定。#2517 OPEN。


## [CURRENT] #2517 CADCraft 已確認來源孔位入 Session 前置驗證 Engine API（2026-11-02）

`manufacturing_api.verify_cadcraft_verified_candidate_stage(output, whd_candidates, existing_features, surface, width, height)` 接收 WHD 既有 finished-face Features／實體 Surface 與 CADCraft 隔離交換 DXF，於 Engine 內驗證候選數量／CUTTING、實際物理面積、舊孔碰撞、外部圖元幾何及公制、交換檔容量和 SHA256，僅回傳已驗證來源 fingerprint。GUI `cadcraft_command_session_bridge.stage_verified_cadcraft_drawing` 只檢查原 Session 有效狀態、呼叫公開 API、核對 Session 未改變後執行原本 `preview_all`；Confirm／Cancel／Undo 的原子回滾與 hash 再驗均保留。原 `_MAX_EXCHANGE_BYTES` 由 Engine 常數單一來源提供，不增加另一套 Factory／CSV／DXF 或任何 CADCraft 製造認證。#2517 OPEN。


## [CURRENT] #2517 CADCraft 手動孔位回傳統一 Engine API（2026-11-02）

既有 `tools.issue1959_whd_cadcraft_command_draw` 的交換檔 R2010／mm／封閉形狀／圖元順序驗證遷至 `ae_engine.cadcraft_exchange_proof`；GUI 的 CADCraft 新孔形解析、原孔位平移、真實裁切面內驗證／孔位碰撞、零孔原始空檔驗證則遷至 `ae_engine.cadcraft_manual_return`。唯一公開呼叫為 `manufacturing_api.verify_cadcraft_manual_ticket_seed`、`project_cadcraft_manual_return_changes`、`cadcraft_new_hole_from_entity`、`cadcraft_feature_footprint_polygon` 等。GUI 只保存短效 Session ticket、完整來源 hash、回傳驗證結果 preview／cancel／confirm；歷史 GUI／CLI 名稱為薄相容轉接，不保留第二份製造公式。CADCraft 僅輸入經 WHD 核對的候選新孔，不是製造權威；CUTTING 只能經原 WHD Session 明確確認後由既有 Engine 再生，NFB 認證、Factory、source-only 出圖限制完全不變。#2517 OPEN。


## [CURRENT] #2517 Quantity 多版本製造請求／PAD BOM 完整 Engine API（2026-11-02）

`manufacturing_api.build_operator_quantity_manufacturing_requests(base_request, workspace_snapshot)` 與 `resolve_operator_quantity_manufacturing_batch(base_request, workspace_snapshot, resolve_request=...)` 將原 `phase6_quantity_manufacturing` 的版本專屬 Head/Tail PartSpec／來源 Features、Receiving singleton Bay／NFB alias 投影、fingerprint 及已解析 PAD 物理數量 BOM 一次遷回 Engine；GUI 舊函式只保留呼叫相同公開 API 的薄相容層。現有 `phase6_manufacturing_service.resolve` 可作同程序既有解析回呼，不是新的 GUI 製造演算法或外部 Worker。受電箱任意大小寫 `RECEIVING` alias 經 `cabinet_types.policy.canonical_family_name` 同一 Family owner 判斷，不再由 GUI 寫兩字串特例；`manufacturing_cache_signature` 同樣正規化來源 Family 的 W/H/D live override。原數量／版本語意、現有切板 DXF Gate、來源與 Save→Reload 契約不擴權；未驗證 PAD 或 NFB 不因此放行。#2517 OPEN。


## [CURRENT] #2517 Receiving 操作預設／後板模式 GUI→Engine 公開 API（2026-11-02）

`manufacturing_api.receiving_default_box_dimensions` 由受電箱現有 Family `BOX_BODY_DEFAULTS` 提供獨立 W/H/D 拷貝；`receiving_default_preview_dimensions` 由已保存 quantity／Set-Bay snapshot 決定唯讀尺寸。後板模式顯示與切換的 Family alias 條件交由 `receiving_family_supports_back_panel_mode`，三片式側背分離拓樸適用條件由 `receiving_back_panel_mode_control_applicable` 決定。GUI `receiving_multi_settings_window` 與 `fold_designer_composition_receiving` 只顯示、傳送 snapshot 與控制指令；舊模式暫存、保存結構、獨立尺寸、舊金庫型製造 API 及受電箱 DXF 出口均不變。本批不宣稱 NFB／內門／外部 source-only 製造認證；#2517 OPEN。


## [CURRENT] #2517 共用單板製造拒絕已註冊但未實作 Family（2026-11-02）

`manufacturing_api.generate_part(PartSpec, output_path, context)` 在建立目錄或暫存 DXF 前，呼叫既有 Family Registry owner 的 `cabinet_types.policy.require_implemented_manufacturing_family(spec.model_name)`；若 `RO/落地盤` 之類已註冊 Family 仍為 `implemented=False`，須回 `CABINET_FAMILY_NOT_IMPLEMENTED` 且不執行 exporter、不得建立 DXF。金庫型、受電箱（含 alias）沿既有正式單板 API 及各 Part 專屬來源 gate 繼續；`model_name=None` 與尚未建檔的歷史工廠字串為相容目的暫保留既有行為，不能把此相容視作製造認證。此 gate 只是「已知但未實作 Family 不得偷用舊公式」的必要條件，**不**聲稱所有 Family×Part×Operation 已經通過正式 Registry／DXF 核可。source-only `dispatch_manufacturing_integration(export)` 的拒絕維持原樣，#2517 OPEN。

## [CURRENT] #2517 受電箱 BasePlate 正式製造 Family Gate（2026-11-02）

既有 `manufacturing_api.generate_part(BasePlatePartSpec, ..., ManufacturingContext)` 仍是金庫型與受電箱共同單板出口，不增設 Receiving 專用 exporter。受電箱「必須提供已確認 `receiving_bend_pattern`，並走 guarded FinalScene 出圖」的判斷由 `cabinet_types.receiving.base_plate_requires_explicit_bend_pattern` 提供，經既有 `cabinet_types.policy.base_plate_requires_explicit_bend_pattern` canonical Family/alias hook 呼叫；不再由 `_base_plate_export` 字串硬判 `{"受電箱","RECEIVING"}`。因此 `受電箱`／`RECEIVING`／大小寫 alias 都不能因原字串不相等而落入通用底板出口。未給明確折型依舊拒絕 `RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING`，不產生 DXF；金庫型／未指定 Family 的舊通用 BasePlate exporter、CornerPolicy、目的檔交易語意不變。此項修正只封住 Family alias 的既有製造分派缺口，絕非新的 NFB/PAD/EAR/整箱製造認證，不改 source-only `dispatch_manufacturing_integration(export)` 閘門；#2517 OPEN。


> 本文件的 CURRENT 區只描述 **現行 ae_engine 製造架構、公開 API 與 authority boundary**。實際 Corner/Relief 製造公式仍由 Certified Registry 與其 canonical references 擁有；本文件不得複製一套第二公式來源。

## [CURRENT] #2517 Canonical Resolver 的已保存 Family 與 live override 同源（2026-11-02）

`manufacturing_resolver._cabinet_family(ManufacturingResolveRequest)` 現直接沿用既有 `resolve_live_cabinet_family(input_snapshot, live_model=request.cabinet_model)`，而非只用 `cabinet_model` 一欄；當同程序 Python caller 沒有重複填寫 live model，已保存 snapshot 的 `model/cabinet_type` 仍是正式 Family 權威，含受電箱大小寫 alias。明確提供的 live selector 照既有 precedence 優先於舊 snapshot；全空時保留金庫型既有相容 default，未註冊歷史型號也不因本次改動全域停用。這個 Family 結果同時供既有 EndCap relief 及 Receiving Joint MARKING/PAIRING 的 canonical 分派，不讓 Receiving snapshot 默默落成 Vault；不是新製造 executor、不變更 Fold/Corner/Registry、也不因選到 Receiving 自動發出 DXF 放行。GUI 不新增任何 Family 推導；#2517 OPEN。

## [CURRENT] #2517 Receiving Family alias 三片實體基準源／FinalScene 防繞過（2026-11-02）

`manufacturing_scene_orchestration.build_box_body_structure_render_data(BoxBodyPartSpec)` 仍使用原三片實體板件求解與專用 `receiving_panel_baselines` 的 `左側板.dxf`／`右側板.dxf`／`後面板.dxf`；只把原硬比對 `{"受電箱","RECEIVING"}` 改成既有 `cabinet_types.policy.canonical_family_name`，所以 Registered `受電箱`／`RECEIVING`／任意大小寫 alias 不得略過 Dedicated Baseline／來源 SHA／固定孔／後板契約，不得落回一般箱體三片無來源的通用產線。缺任一必要受信任基準檔仍明確拒絕、不產出 DXF。 `build_part_render_data`、`build_box_body_structure_render_data` 與 `manufacturing_resolver.resolve(ManufacturingResolveRequest)` 繼續支援 RO 等箱型的唯讀幾何／數量 BOM（這不是正式製造許可）；只有真正寫實體 DXF 的 `generate_box_body_structure_parts` 重用現有 `require_implemented_manufacturing_family`，已註冊 `RO／落地盤 implemented=False` 必須在建立輸出目錄之前拒絕，不得從唯讀板件繞過 `generate_part` 的製造限制。Resolver 對 Receiving snapshot 的 NFB source-selector rehydrate 同樣按 Family alias 正規化，不再只認大寫 `RECEIVING`。金庫型既有幾何、折型、直接 API 及未知舊 model 相容行為不變；本修復只守住已存在來源與 Family 判準，不新增平行 exporter、工廠公式、NFB/PAD/EAR/整箱 MFG-2 認證或 source-only 外部出口。#2517 仍 OPEN。

## [CURRENT] #2517 受電箱三片式箱身沿用既有 Engine 實體製造入口（2026-11-02）

原 `ManufacturingResolvedBayInput.confirmed_parts` 擴充同一個 `("box_body", BoxBodyPartSpec)` 實體選項，必須有已確認 `fold_profile`、`back_panel_contract` 與 `three_piece_side_back_split` 結構。Engine 仍用原 `build_box_body_structure_render_data(spec, context)`（直接讀既有受電箱三張實體基準來源），產出 `left_side`／`back`／`right_side` 真實實體 `pieces`；既有 `save_verified_resolved_manufacturing_geometry_batch_dxf` 分拆每片、staged Save→Reload、雙 guard 與原子提交。沒有新箱身 exporter；不得用 exploded preview、來源 P 盤標籤或一張箱身複合圖當三片 DXF。缺真實三片、來源基準檔、Fold 或後面板契約則拒絕，NFB/PAD/EAR 仍維持原獨立認證，source-only CLI 不開放。#2517 OPEN。

## [CURRENT] #2517 CADSplit confirmed PartSpec → 同一正式 Engine FinalScene／DXF API（2026-11-02）

`export_verified_resolved_integration_bays` 原有已解析 `ResolvedManufacturingGeometry` 契約不變；`ManufacturingResolvedBayInput` 現可選擇 **互斥** 的 `confirmed_parts=((part_key, PartSpec), ...)`，再由同一個 `manufacturing_api.build_part_render_data` 解析成真實 FinalScene，透過原 `save_verified_resolved_manufacturing_geometry_batch_dxf` staged Save→Reload、來源 pre/post guard 及原子提交。當次先限定受電箱已確認外門 `DoorPartSpec(feature_space="finished_face")`（含明確 gap/fold）及明確兩軸 Fold／Corner 的 Head/Tail `EndCapPartSpec`；BoxBody 三片/NFB PAD/EAR/內門格和全箱 MFG-2 不可從原圖或預覽自行補造，必須先用現有 Engine 實體解算取得已解析結果。Family、實體角色、重複、雙來源、未確認必要欄位都 fail-closed；source-only `dispatch_manufacturing_integration(export)` 繼續 `EXTERNAL_EXPORT_NOT_CERTIFIED`，不是同程序正式 API 的全域禁令。保留既有 Python 公開入口，不新增平行 exporter、CLI/Worker 權限或 Registry 放行。#2517 OPEN。

## [CURRENT] #2517 Hole Editor Canvas 已解析孔位公開 API（2026-11-02）

`manufacturing_api.resolve_hole_editor_canvas_features(surface, features, width, height)` 直接委派既有 `sheetmetal_features.resolve_surface_features`，回傳 immutable tuple 的世界座標解析孔位；超出物理 Feature Surface 的非法孔仍明確 `ValueError`。 `manufacturing_api.hole_editor_canvas_reference_point(feature, width, height)` 使用既有 saved reference-anchor authority；`manufacturing_api.hit_test_hole_editor_canvas_features(point, resolved_features, tolerance=...)` 沿用 Engine 有限／非 bool 的點選容差檢查。公開顯示 DTO `CanvasTransform`、`ResolvedCircle`、`ResolvedRect`、`Vec2` 沿用單一 Engine 類型。GUI `phase6_hole_editor_canvas_view.py` 只做 Canvas pixel placement、繪製、操作與結果呈現，不再直接 import 私有 `ae_engine.sheetmetal_features`。金庫型與受電箱共用相同 Feature Surface 合約；本次不變更 Feature 的實體製造／DXF、保存內容、2D／3D 真實板件與 Registry，不可把只讀孔位預覽當成製造放行，#2517 仍 OPEN。

## [CURRENT] #2517 BoxBody 對稱折彎 Family capability 公開 API（2026-11-02）

`manufacturing_api.box_body_symmetry_allowed(source)`／根包同名入口只是既有 `cabinet_types.policy.box_body_symmetry_allowed` 的正式公開重匯出，無第二套 Family 判準。 `phase6_bending_ui._phase6_box_symmetry_allowed` 仍由 GUI 選擇 live 型號／snapshot，實際受電箱不允許箱身對稱與金庫型支援對稱完全取 Engine public capability，GUI 不再私自 import Family policy；原 UI toggle/state、Save→Reload、BEND／2D／3D／DXF／Registry 不變，不新增製造授權；#2517 OPEN。

## [CURRENT] #2517 Fold Editor 唯讀包外列顯示 Engine API（2026-11-02）

`manufacturing_api.project_operator_fold_editor_display_rows(material_segments, thickness)` 在原有 `ae_engine.operator_fold_editor` 中使用同一 `apply_outside_dimension_compensation`／`fold_material_segment_outside_length`，從已保存真正料長與當下 BEND 拓樸產生獨立唯讀的操作者包外長度、正負操作方向與角度顯示列；不信任過時 `ui_len_add`，不修改 canonical source。舊 `Phase6BendingUI.render` 僅在呼叫原始 Tk renderer 的期間傳入顯示副本，`refresh_active_profile` 也只消費同一 Engine 結果；移除 GUI 展示時直接修改／還原實體 Fold 列的做法。原 GUI `save/add/remove/mirror` 的 Engine source、金庫型／受電箱、Save→Reload 和真正 2D／3D／DXF／Certified Registry 全數不變；僅顯示 API，不取得額外 CUTTING/DXF 放行，#2517 OPEN。

## [CURRENT] #2517 GUI 全入口掃描後的實體回讀與 CADCraft CHECK Engine API（2026-11-02）

全庫從 `localX@b82e34f498efe7d2fb9cfab769b900704de744a6` 掃過 159 個 GUI／Phase6／Fold Designer Python 入口及 23 個 `integration_cli` 入口；此為**靜態候選掃描**，不是每條功能已通過製造驗收。第一批實作讓 `fold_designer_bridge._phase6_box_body_piece_dimension_projections` 直接消費既有 `project_box_body_assembly_panel_piece_rows`；讓受電箱 Settings `physical_drawings` 消費新 `project_receiving_settings_physical_drawings`，只保留 GUI 角色顯示；CADCraft 唯讀的 finished-face 特徵解析與 CHECK DXF 由 `project_cadcraft_check_scene`、`save_cadcraft_check_scene_dxf` 在 `ae_engine.operator_cadcraft_preview` 執行，GUI 僅開啟外部檢查工具。CHECK 預覽不具 CUTTING/BEND/DXF 正式製造資格，不接收 CADCraft 產物回寫作為 canonical 幾何，不更動已認證 Registry／Factory。其他手動 CADCraft 回傳與剩餘 GUI 製造私有 import 尚屬 #2517 待遷範圍，不能宣稱全部完成。

## [CURRENT] #2517 Fold Editor Add／Remove Engine API（2026-11-02）

`manufacturing_api.operator_fold_editor_add_segment` 和 `operator_fold_editor_remove_segment` 將原 `Phase6BendingUI.add/remove` 實體折段追加、核心段刪除限制、對稱真實 `phase6_key` 配對與刪除後相鄰 BEND 補償搬回 `ae_engine.operator_fold_editor`；完全沿用原 `can_remove_box_body_fold_segment` 及 `apply_outside_dimension_compensation`。GUI 只送輸入並保留既有 Profiles Vault list 身分；未合法刪除回 `None` 且 Engine 不更動輸入。金庫型／受電箱用同一 API，原 Family policy 控制箱身對稱允許，不因新入口鎖舊版本；已認證 Factory/Registry／實體 2D／3D／DXF／Save→Reload 不改，不新增工廠製造放行，#2517 OPEN。

## [CURRENT] #2689–#2694 盤名與合併 DXF Engine API（2026-11-01）

**資料身分與保存：** `ae_engine.receiving_layout` 的每個 physical Set/Bay 都有獨立 `panel_name`，按全工程單調 `next_panel_number` 自動取 P1、P2…；刪連不回收、改名不重編、跨套不得重名，Save→Reload 保存這兩項 operator-owned canonical input。 `manufacturing_api.rename_receiving_panel(layout, set_index, bay_index, panel_name)` 是唯一改名入口；盤名只是顯示／DXF 分組名稱，絕不替代板件的 `stable_id`、物理身分、Certified Registry 或 2D/3D 幾何。金庫型單箱 `panel_name` 預設空白，`manufacturing_api.set_cabinet_panel_name(snapshot, name)` 驗證並保存。

**製造／儲存 API：** `manufacturing_api.save_composed_panel_dxf(panels, output_path, pre_commit_guard=..., overwrite=False)` 接受已解析 `ResolvedManufacturingGeometry` 多片真實 flat `DrawingScene`，以不重疊 offset 排版，獨立 Save→Reload 原片及合併檔的 CUTTING、BEND、MARKING、BLIND_HOLE 等圖元、CHECK 來源與 material；保存每片實體 ID，拒絕未認證 NFB/PAD/EAR、來源漂移和目的檔碰撞。它**不**用 3D 裝配 world 座標反推加工 UV，也不因合併格式擴大 MFG-2／NC 合法範圍。箱身物理片沿 Engine 原有 topology/owner 次序排列，其他實體片列於旁側；不能把 row order 當成新的鈑金尺寸或焊接世界定位權威。

**受電箱分組：** `manufacturing_api.plan_receiving_grouped_dxf(layout, mode)` 只讀 canonical Set/Bay 次序，可選 `PER_SET`（第1套.dxf、第2套.dxf…）、`ALL`（全部.dxf）、`END_VS_MIDDLE`（頭尾盤.dxf＋非空才有中間盤.dxf）。頭尾盤是**每套首末 Bay** 而非 `head/tail` 板件，一連只歸一次。 `manufacturing_api.export_grouped_receiving_multibay_dxf(saved_snapshot, physical_bay_geometry_provider=..., flags=..., output_dir=..., group_mode=..., pre_commit_guard=...)` 先由現行 CSV/Source/Registry/實體-owner gate 驗證並重新讀回每片，再做多檔 stage→單批 atomic publish；不可因某片缺來源而默默減片或發布完整製造。先前 `export_current_receiving_multibay_dxf` 每片檔相容 API 保留。

**GUI 接線：** `gui_modules/layout/left_panel.py` 只呈現模式與 Engine filename preview，`gui_modules/project/export_actions.py` 經公開 `manufacturing_api` 發出選取、來源狀態及匯出。金庫型匯出單檔，`manufacturing_api.vault_panel_dxf_filename(panel_name, at=...)` 在空名時依 `Asia/Taipei` 輸出 `金庫型_YYYYMMDD_HHMMSS.dxf`，有名時輸出 `<盤名>.dxf`；碰撞需操作者明確同意，不默默覆蓋。

**放行界線：** 成功生成分組 DXF ≠ Receiving 完整整箱 MFG-2/NC 已核准；#2344 仍獨立掌握工廠放行。以上擴充僅是增開公開 API／操作能力，不鎖舊 Family、不設第二製造入口、不變更 Certified Registry 的公式。

## [CURRENT] ae_engine Manufacturing / Certified Registry Contract

<!-- WHD_AUTHORITY_ROLE: CURRENT -->

> **WHD × CADSplit API／製造必讀 REFERENCE（`CADSPLIT_WHD_API_REFERENCE_READ_GATE_V1`）**：凡 WHD API、Engine、Family（金庫型／受電箱）、Bridge、CADSplit 自動拆圖／來源 Set/Bay 與 canonical 製造身份、跨版本或製造／DXF 驗收，施工前先讀本 04 CURRENT，再讀 [`docs/integrations/WHD_CADSplit_API_架構與權威整合_REFERENCE_v5.1.md`](../../docs/integrations/WHD_CADSplit_API_架構與權威整合_REFERENCE_v5.1.md) **全文**。依 `AGENTS.md::SOURCE_READ_EVIDENCE` 附 repo/ref/完整 SHA、路徑、相關章節及權威判斷；未讀不得宣稱核對完成。v5.1 僅 REFERENCE，不得覆蓋使用者已確認的產品規範、本 CURRENT、Certified Registry 或 07；CADSplit 現行缺陷與測試不能反向決定產品規範。

### 1. Current scope 與 Source of Truth 邊界

現行 repository-relative engine path 是：

`ae_engine/`

本文件不再用任何本機磁碟路徑當 current architecture locator。正式 source 一律以 repository path、current production code、Certified Registry 與 canonical AI Library / Registry references 為準。

現行 authority 分工：

1. 使用者已核准的產品／機械需求：最高 requirement authority。
2. `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`：尺寸語意、STANDARD 與 assembly semantic delta 的 CURRENT domain authority。
3. `基準檔/截角資料庫/certified_relief_rules.json` + `README_母規則說明.md`：已認證 Corner/Relief runtime formula、revision、precondition、dimension-space 與 certification metadata authority。
4. `ae_engine/`：把 Cabinet Family、Topology、canonical parameters、Registry result 與 final manufacturing geometry 串成 production data flow。
5. tests / fixture / probe / collision shadow / rendered result：只做 validation，不建立新的製造 Source of Truth。

因此 04 的責任是回答「engine 現在怎麼分層、公開哪些 API、各 authority 怎麼接起來」，不是把 Registry JSON 內容重新抄一份。

### #2517 Fold 編輯器包外→料長提交與箱身鏡射目標 Engine API（2026-11-02）

`manufacturing_api.commit_operator_fold_editor_rows(old_segments, operator_rows, thickness)` 由無 Tk 的 `ae_engine.operator_fold_editor` 將操作員輸入的包外長度與角度依**新拓樸**相鄰真實 BEND 數 × T 交既有 `box_body_fold_profile.apply_outside_dimension_compensation` 與 `box_body_editor_readback.box_body_ui_segment_length_to_material` 決定物理料長，保留原 `phase6_key`／`core`／負方向欄位；輸出新 detached material Fold rows，GUI 只採用回傳值寫入 Workspace。 `plan_operator_fold_mirror_target(segments, source_index, field, *, is_box_body)` 回傳 immutable `OperatorFoldMirrorPlan`，由 Engine 依真實結構鍵決定左／右同源折邊或明確禁止 legacy positional fallback；受電箱原不允許箱身對稱，仍由現有 Family `box_body_symmetry_allowed` gate 阻擋。保留金庫型原 UI、舊序列正反算、Save→Reload、2D/3D/DXF 共用 material source，不新增折彎公式或製造放行。#2517 保持 OPEN。

### #2517 組合面板 BoxBody 子板件實體尺寸與截角來源 Engine API（2026-11-02）

`manufacturing_api.project_box_body_assembly_panel_piece_rows(render_data)` 從**已解算的真實** `BoxBodyPartRenderData.pieces` 生成唯讀 `BoxBodyAssemblyPanelPiece`：現行 `box_body:<role>`／歷史明確 `piece.key`、成形包外 W/H、展開料 W/H 以及與該片同源的 `source_render_data`。這是現有 Engine BoxBody source readback 的操作展示投影，不自算幾何、折彎、截角或另建板件。 `phase6_assembly_presentation.project_box_body_piece_rows` 只附顯示 label；`phase6_assembly_panel.refresh_box_body_piece_info` 直接使用同一份 source 作既有 corner 文字，不再從 UI role 字串反查物理板件。無角色的歷史板件只有顯示鍵和尺寸，不得冒稱實體截角來源（`source_render_data=None`，原面板顯示 `截角尺寸：無`）。已核准的 Save→Reload、實體 2D/3D／CUTTING／DXF 與 Registry 權威不變；不得由此 API 宣稱加工放行。#2517 OPEN。

### #2517 受電箱內門 Confirm All Quantity 來源預檢 Engine 公開 API（2026-11-02）

`manufacturing_api.preview_quantity_inner_door_confirm(snapshot, quantity_model, part_key, features, staged_config, *, include_missing_heights=False)` 是原有 Single 設定與 3D 直接內門開孔編輯器共用的無 Tk、detached Engine 預檢。Family `validate_door_config`、共同箱體 `update_common_box`、真實 CSV 孔 `committed_csv_nfb_config` 與 Quantity 版本 `preview_quantity_nfb_submission` 仍由原 Engine owner 唯一驗證；返回 `(projected_snapshot, typed_nfb_config_or_none)`。兩個 GUI 僅在整體預檢成功後寫入 live version、project snapshot、workspace 與重畫；沒有 CSV NFB 只保存設定與 native Features，不能冒稱提交 NFB。為保留既有 Save→Reload，直接 3D 入口明確以 `include_missing_heights=True` 清除缺省層高，Single 設定入口保留舊高度。錯誤不得污染已提交來源；本操作不修改金庫型、物理 CUTTING、DXF 或取得製造放行，#2517 仍 OPEN。

### #2517 Door 主畫面展開摘要 Engine 公開 API（2026-11-01）

`manufacturing_api.project_operator_door_blank_dimensions` 將 `calculation_controller.update_calculations` 原單門 Baseline → 既有 AE 舊版顯示 fallback 與多門格實體 start W/H／frame_edges 展開尺寸委派給 Engine；GUI 僅選目前操作者看的門格及格式化尺寸。正式 `DoorPartSpec`／FinalScene／feature／DXF 來源未改，舊 fallback **僅限顯示**且不得升格為已驗證製造權威。保留沒有門板時「-」、基準存在／缺失的舊摘要語意，以及原 Save→Reload／2D／3D／DXF 契約，不新增任何 CUTTING/DXF 認證；#2517 OPEN。

### #2517 Door Layout 單格 2D 預覽 Engine 公開 API（2026-11-01）

`manufacturing_api.project_operator_door_cell_result`、`project_operator_door_cell_features`、`project_operator_door_cell_baseline` 將 `door_render_host_adapter` 原有單格結構件、已保存開孔＋Indicator／IndicatorBox 孔投影、Family 共用基準 DXF 來源／nameplate datum 與 fingerprint cache key 全數委派 Engine。GUI 只選格、保存操作狀態、轉交原輸入並畫圖；不再直接呼叫 `ae.calculate_door_finished_size`、`ae.get_stretched_door_data` 或引入私有 `sheetmetal` 製造推導。保留既有 UI preview 的輸入不完整容錯、共用基準、來源標籤及 cache 效能，正式 PartSpec／FinalScene／DXF／Save→Reload 製造權威不變；這些 read-only API 不新增 CUTTING／DXF 認證。#2517 OPEN。

### #2517 Hole Editor 四種操作板件預覽 Engine 公開 API（2026-11-01）

`manufacturing_api.project_operator_hole_editor_door`／`project_operator_hole_editor_base_plate` 將 `hole_editor.py` 原 Door、BasePlate 結構件、成品尺寸、guide、Door baseline preview 委派 Engine；原 `resolve_indicator_editor_components` 保留原有雙板契約，同時拆出 `resolve_indicator_box_editor_geometry`／`resolve_indicator_door_editor_geometry` 獨立呼叫，避免只編輯一板卻要求另一基準 DXF 可用。GUI 僅收操作者值、回傳 UI state 和編輯／保存回呼；舊 Factory／Registry／2D／3D／DXF 製造路徑不改，不新增認證能力；#2517 OPEN。

### #2517 獨立板件真實 3D 網格及 Door 實體顯示身分 Engine API（2026-11-01）

`manufacturing_api.project_independent_part_view_mesh` 把 `phase6_final_scene_renderer` 中原有受電箱獨立固定片來源已驗證 T2 MID-skin y=22（原 DXF BEND23 不變）、受電箱左側板 zl1 成形包外補正，以及標準 Fold Mesh 的建立路徑統一放回 Engine；只回傳實際網格、採用的資料 Fold Profiles／Guides 與固定片 3D hinge，GUI 只消費並繪製。 `door_display_part_role` 對 canonical Door／多門格／實體內門 Panel 做顯示身分分類，GUI 不再用文字 contains 判門板 opacity／真孔邊。維持 Family／Registry／實體來源、保存、2D CUTTING／DXF 不變，preview 不增加製造認證；#2517 OPEN。

### #2517 Project DXF 出圖 GUI API 單向化（2026-11-01）

`gui_modules/project/export_actions.py` 中 Door 輸出檔名、Receiving 數值 CSV 數量批次、多 Set/Bay、EAR side MARKING、SIDE CHECK-only、PAD+Base PART_ONLY 輸出一律走 `manufacturing_api` 公開入口，既有 Engine 物理來源／Factory／檢核／原子提交／DXF 回讀皆保持原有判準，未新增整箱製造放行。舊版已有的 Python API 不鎖版本，新功能僅有新 Engine 提供。 `receiving_csv_quantity_manufacturing` 不再反向引入 `gui_modules.project.export_actions` 判斷物理板件選取，統一調用同引擎 `manufacturing_export_selection.resolved_export_intention_key`；GUI 保留操作狀態、輸出位置、UI 訊息，不再進入內部 Engine 模組。#2517 OPEN。

### #2517 全 `ae_engine` 反向 Phase6 靜態依賴移除（2026-11-01）

已逐檔查核 `ae_engine` 264 個 Python 檔案的 `from/import phase6_*` 與 `gui_modules` 直接依賴；本次移除最後一批 8 個 Engine 實作模組對舊 `phase6_quantity_model`、`phase6_box_body_structure`、`phase6_manufacturing_geometry` 相容 facade 的直接匯入。實際權威仍為既有 `ae_engine.receiving_quantity_versions` 的 `QuantityModel`／normalize／inherited NFB brand 檢核，`ae_engine.box_body_structure_state` 的背板模式，及 `ae_engine.assembly_geometry.build_joint_world_geometry`。EAR SIDE CHECK-only／Joint MARKING 世界幾何仍是相同的 Engine 函式，保留原呼叫接縫別名及已提交身份、DXF reopening、atomic failure gate，不產生來源計算或公式副本。附加單一 pytest AST 全庫靜態契約：若 `ae_engine/**/*.py` 再直接匯入 Phase6、GUI、Bridge 或 Tk 即 RED；此檢查不涵蓋動態字串式載入或其它非 import 層面的架構責任，#2517 仍 OPEN。AI 04／07 與 Certified Registry 製造權威未改，舊版 Phase6 只是不具新能力的操作相容入口，禁止版本鎖定。

### #2517 Engine BoxBody／Receiving／Registry 反向 Phase6 import 清理（2026-11-01）

`ae_engine.box_body_piece_features`、`ae_engine.cabinet_types.receiving`、`ae_engine.certified_relief_registry` 與 `ae_engine.receiving_nfb_v5_part_only_manufacturing` 不再透過 `phase6_box_body_structure`、`phase6_fold_profiles`、`phase6_quantity_model` 反向取得製造設定與計算。其原相容匯入本就由 `manufacturing_api` 重匯出相同的 Engine owner；改為直接引用 `ae_engine.box_body_structure_state` 的 StructureType／BackPanelMode／side rear bend material length、`ae_engine.box_body_editor_readback.formed_box_body_fw_widths` 與 `ae_engine.receiving_quantity_versions.quantity_inherited_nfb_brand_conflicts`。不建立新的箱體策略、公式、Family/BEND 補償或門檻；Receiving 背板模式、Registered Relief、CSV NFB 單層來源驗證及所有舊版 Phase6 Python import identity 保持不變，沒有多出一份 Registry。#2517 仍 OPEN，其他 import 依賴須另依實際掃描判定。

### #2517 Phase6 FinalScene 製造解算主服務 Engine owner（2026-11-01）

`ae_engine.manufacturing_resolver.resolve` 是正式無 Tk 的製造主解算，透過 `ae_engine.manufacturing_api.resolve_manufacturing_request(request)`、根包同名入口公開，使用前一批唯一 `ManufacturingResolveRequest`／`ManufacturingResolveResult` DTO。實體 `AssemblyScenePart` 只在 `ae_engine.assembly_scene_part` 定義一次，由原 `phase6_final_scene_contracts` 相容路徑重新匯出；其他 FinalScene 顯示 DTO、操作適配器與 Tk 仍留於 Phase6。原 `phase6_manufacturing_service.resolve(request)` 僅做同型別請求／結果轉接，不再自算 Joint／Family／3D／Material。Engine 解算器直接調用既有 Engine 的 placement、材料 Fold mesh profiles、Joint world UV、Family Divider Relief 與 USER_ADDED Joint Relief，無逆向 `phase6_*` imports；其已核准的算式、受電箱 Set/Bay identity、BEND/CUTTING/MARKING、provisional relief 拒絕、狀態 mutation、mesh scope／cache receipt 及 solver fallback semantics 保持原樣。GUI request adaptation、Save→Reload、真實 2D/3D 和 DXF 僅沿用既有行為，不由這次搬遷取得額外製造放行。 舊 #1819、mesh reuse、#1502、GUI 效能驗收原本檢查 `phase6_manufacturing_service.resolve` 的內部呼叫與 decorator `__wrapped__`，現已改對真實 Engine resolver 進行同等嚴格的來源順序、DXF parity、快取前後幾何／效能與 EndCap replay 觀測，沒有停用驗收或將舊 wrapper 冒充 Engine。後續仍須沿 GUI adapters／其他 Phase6 geometry legacy wrappers 繼續瘦身，#2517 不因本批關閉。

### #2517 Main GUI BoxBody 2D 現行實體來源及子板件身分 Engine API（2026-11-01）

`manufacturing_api.project_receiving_box_body_2d_source` 對真實 `ResolvedManufacturingGeometry` 選取唯一 `box_body` 實體 render source，Receiving 沒有 real `pieces` 即拒絕，不使用 Main GUI 的泛用箱身複製品；`manufacturing_api.project_box_body_2d_piece_inventory` 從實際 Engine `BoxBodyPartRenderData.pieces` 生成 canonical `box_body:<role>` 物理身份列表，按操作員選擇只查既有實體，沒有就保留舊 aggregate fallback。原 `gui_modules/application/render_snapshots.py::box_body_render_snapshot` 現僅負責 tab 選擇、接收 Engine response、把選取的 Receiving SIDE 交既有 UI display-only EAR MARKING layer 投影和畫面格式化；所有 canonical 來源、實體 role、piece identity 都由 Engine 返回。原 #1503 Side EAR 真實 2D source/Save→Reload/UV/MARKING 測試與 immutable DXF material 都不得放寬；不新增 MFG release。#2517 OPEN。

### #2517 Main GUI 多門格隔板／內門框、單門指示燈標註 Engine 2D API（2026-11-01）

`manufacturing_api.project_operator_door_divider_frame_preview` 實際集中原 GUI 的多門格 divider `derive_box_body_dividers`、內門框 `derive_inner_door_frame_sets`、二者 `resolve_assembly_placement` 世界偏移與原容錯；GUI 只組原始專案輸入、欄位／active UI 與繪圖顯示。`manufacturing_api.project_operator_door_indicator_guides` 集中單門的 `DoorIndicatorContext`／Lamp 版位／enclosure reference distances／X/Y 尺寸線推導，GUI 不再直接計算物理孔位／折邊 reference。兩項皆沿用原有 Engine Family/Topology 與源 geometry，不新增另一公式；legacy 不足以繪製時保留舊 preview-only fallback，不改 CUTTING／DXF release。金庫型及受電箱依既有 source 法則執行，#2517 繼續 OPEN。

### #2517 Main GUI BasePlate 2D 真實實體來源與世界座標 Engine API（2026-11-01）

`ae_engine.operator_base_plate_2d.project_receiving_base_plate_2d_snapshot` 及 `project_legacy_base_plate_2d_bounds` 經 `manufacturing_api` 與根包公開。原 `gui_modules/application/render_snapshots.py::base_plate_render_snapshot` 不再自行判定 Receiving NFB 已提交單／雙 Tier 底板身分、挑選實際 source part、核對最新 CSV Bend pattern／實體 topology W/H 或計算舊式底板世界座標。GUI 僅傳操作者目前 committed snapshot、實際已解析 `ResolvedManufacturingGeometry`、目前選片／2D 輸入，顯示 Engine 的 material 及 view bounds。Engine 保留原有 1 Tier root、2 Tier `base_plate:nfb_layer:*`、未提交來源、CSV stale source fail-closed、無實體不退回 generic 的精確拒絕行為；不以預覽開啟任何製造出圖 release。現有 #1502/#1503 真實 2D/CSV source 測試及新的 headless 公開 API 等價測試須保留。#2517 仍 OPEN，正式 X／Windows UAT 不因本切片完成。

### #2517 不可變製造 Request/Result 與 canonical 指紋 Engine owner（2026-11-01）

`ae_engine.manufacturing_contracts` 正式持有原 `phase6_manufacturing_contracts.py` 全部唯一製造契約實作：`ManufacturingPartInput`／`ManufacturingResolveRequest`／`ManufacturingResolveResult`、診斷／mutation／effect／cache receipt、`FrozenMapping`／`FrozenObjectMapping`、canonical JSON／freeze／thaw／fingerprint。透過 `ae_engine.manufacturing_api` 與根包公開同一組 class/function；原 `phase6_manufacturing_contracts` 僅由公開 API 重新匯出完全相同物件，沒有第二份 hash 或資料驗證算法。保留 runtime part order 及 fingerprint 的 order-stable canonical input、Receiving Set/Bay 整數身份、Tk/callable 拒絕與結果 immutable 強制驗證，正式機械/Certified Registry、DXF 解算與儲存語意均未修改。舊版 Python 路徑依舊可用，不以版本鎖定阻擋新功能。本批**未**把複雜 `phase6_manufacturing_service.py` 解算器宣告搬遷完成；其跨 `phase6_manufacturing_geometry`／final scene 的邊界仍列 #2517 待做。

### #2517 數量製造分組與 NFB CHECK/Q Engine 公開 API（2026-11-01）

`ae_engine.quantity_manufacturing_groups` 是 `QuantityManufacturingBatch`、`quantity_manufacturing_groups` 與 `quantity_nfb_checked_manufacturing_groups` 的正式 Engine owner；原 `phase6_quantity_manufacturing.py` 保留量產 request→resolved FinalScene 的 Phase6 相容調用及同名 alias，但不再保存第二份實體分組／CHECK 判準。GUI 專案出圖的舊分組相容別名與 `manufacturing_api` 指向同一份 Engine 函式，保留舊 Python 呼叫能力，不產生第二製造實作；#1503 真實 Tk 驗收的 CHECK/Q 收據 spy 改攔截真正被 CSV exporter 匯入的 `ae_engine.quantity_manufacturing_groups` Engine owner，原本實際 DXF/Q/physical identity 斷言及嚴格 gate 一項不刪。Receiving CSV 數量制造正式模組不再逆向 import `phase6_manufacturing_contracts`、`phase6_quantity_manufacturing`、`phase6_quantity_model`：改採 Engine 已存在 `manufacturing_value_thaw`、`receiving_quantity_versions.QuantityModel` 及新 Engine group owner。每版 NFB source identity、已提交 CSV、physical manifests、Q conservation、PART_ONLY gate、CUTTING/BEND/DXF 原有測試與拒絕條件不變；本批不宣告整箱製造放行。舊 Phase6 API 向後相容，新版僅新增公開 Engine 入口，未鎖舊版。#2517 OPEN。

### #2517 EndCap 摘要／金庫型基準 Fold 預設 Engine 公開 API（2026-11-01）

`manufacturing_api.project_operator_endcap_blank_dimensions` 將主畫面 EndCap 無已提交 Fold Profile 時的 baseline-first 總料寬／深回讀與舊 AE 公式回退統一移入 Engine；已有 committed Profile 時仍由同一 FinalScene material bounds 作準。 `manufacturing_api.read_operator_baseline_fold_defaults` 將金庫型型號切換時的 EndCap／Door 基準 Fold 預設及舊 Door DXF 解析失敗的四數值 UI 相容回退搬入 Engine；GUI 僅將回傳數值填入操作欄。兩者只供操作顯示／預設，不是正式製造或 DXF 認證，保留自訂／受電箱既有路徑與原 Save→Reload／2D／3D 來源；#2517 OPEN。

### #2517 BasePlate 展開摘要唯一 Engine 計算公開 API（2026-11-01）

`manufacturing_api.base_plate_blank_dimensions` 以既有 `sheetmetal_part_adapters` 的 BasePlate 料寬／料高計算為唯一擁有者，正式 `build_base_plate_result`／自訂角 `build_unknown_base_plate_result` 與 GUI `calculation_controller.update_calculations` 共用同一函式。GUI 只傳操作者 W/H／縮邊／折邊並顯示返回尺寸，不再另算公式。保留沒有底板時「-」、獨立板件契約及原 2D/3D/DXF/Save→Reload 行為；此函式**不取代**受電箱 NFB/多層實體底板的專用來源，亦不代表已取得 CUTTING／DXF 製造認證。#2517 OPEN。

### #2517 Receiving candidate quantity draft public API (2026-11-01)

`manufacturing_api.AllocationDraft` / `validate_quantity_allocation` are the public Engine boundary for Receiving candidate Head/Tail draft selections. `AllocationDraft.replace_version`, `select_version`, and `set_step` own per-role candidate identity replacement, row order/quantity preservation, assignment invalidation, and two-step readiness. `receiving_quantity_allocation_ui` only presents the controls and forwards operator actions. Draft-only changes never commit Set/Bay physical features; the original validated `apply_receiving_endcap_quantity_configuration` remains the sole project mutation. Existing multi-Set/Bay Save→Reload and Tk confirmation requirements remain; no new CUTTING/DXF certification. #2517 OPEN.

### #2517 Phase6 操作快照 CornerPolicy 製造組裝 Engine API（2026-11-01）

`manufacturing_api.resolve_operator_snapshot_corner_policy` 公開接收已保存四角 raw CornerType、操作快照、設定覆蓋與 EndCap FW 四態，不啟動 Tk 即由既有 Engine `endcap_corner_selection_from_raw`、`resolve_endcap_fw`、`corner_type_ui.policy_from_corner_state` 及 Cabinet Family `effective_endcap_bottom_fw` 建立唯一正式 Policy。原 `phase6_manufacturing_adapter._corner_policy_for_app` 僅轉送輸入，再由 `operator_finished_dimensions_for_app` 傳遞 Engine Policy DTO；缺四角維持 `None`，金庫型原語意、受電箱既有 Bottom FW、舊 Family 可選投影 fallback 與保存後結果保持原樣。此切片不新增截角公式、Registry、CUTTING／DXF 出圖認證或外部 Worker 能力，#2517 仍 OPEN。

### #2517 Phase6 Head/Tail EndCapPartSpec 操作製造 Request Engine API（2026-11-01）

`manufacturing_api.build_endcap_operator_part_spec` 與 `ae_engine.endcap_operator_part_spec` 現為 EndCap Head/Tail 不依賴 Tk 的唯一操作製造 PartSpec 建構 owner。GUI `gui_modules/application/manufacturing_adapter.py::_end_cap_part_spec_from_values` 只蒐集 W/H/D/T/FW、操作者 Fold、洞資料、已保存 CornerPolicy、BoxBody structure、AssemblyJoint 與 Bottom WRAP state，再呼叫 Engine；不再自行決定 Family D 補償、Head/Tail X/Y Fold DTO、Bottom WRAP 製造退讓或裁切實體資料。既有 Vault 3T／Receiving 2T Family Policy、完整既存 AssemblyJoint schema／圖狀態與 reserve_u/v 投影、手動 depth_comp_t 優先、過去無效可選 WRAP 投影的相容容錯及已驗證 relief CUT 僅作 request 轉送，全部依現有 Engine 來源；未新增公式、Factory Registry、CUTTING／DXF 出圖認證，#2517 仍 OPEN。

### #2517 BasePlate／IndicatorBox 操作製造 PartSpec Engine API（2026-11-01）

`ae_engine.operator_auxiliary_part_specs` 正式擁有 `manufacturing_api.build_base_plate_operator_part_spec`／`build_indicator_box_operator_part_spec`，原 `gui_modules/application/manufacturing_adapter.py` 的 `_base_plate_part_spec_from_values`、`_indicator_box_part_spec_from_values`、`_indicator_box_part_spec` 僅轉送既有輸入。BasePlate 操作 W/H/T、四側縮邊、BEND、BoxBody 既存 Structure/Fold、操作者 Corner/Feature，以及 Receiving 既有 NFB source bend pattern／已提交深淺 pair 和物理 ID 均由 Engine 建構同一 `BasePlatePartSpec`；原有 `受電箱`／`RECEIVING` saved key 判準不變，金庫型不得意外承接 Receiving 專用來源。IndicatorBox 所有入口共用唯一 `IndicatorBoxPartSpec` 轉換，無第二組 GUI int／T 解釋。只移動原製造 Request 組裝責任，仍使用既有物理與 Certified Registry／DXF 原始來源，不新增 NFB、CUTTING、DXF 認證、鎖版或正式 X；#2517 OPEN。

### #2517 Assembly Relief 保存來源指紋／原子 Head Tail／已提交 CUT replay Engine API（2026-11-01）

`ae_engine.assembly_relief_state` 現唯一擁有舊 `phase6_assembly_relief_state.py` 完整保存／回放判準：`RELIEF_CONTRACT_VERSION`、`relief_profile_fingerprint`、`structure_fingerprint`、`build_current_source_signature`、`source_matches_current`、`committed_relief_cuts`、`build_persisted_relief_state`。全數經 `manufacturing_api`／根包公開，同一 Python 物件由 Phase6 舊路徑相容重匯出；GUI `manufacturing_adapter`、Fold Designer composition 與 Bridge 直接消費公開 API，不再以 Phase6 佔有 Registry 版本／驗證原子保存決策。這批只搬移既有狀態演算法，保留已保存 JSON schema、Head/Tail 一起提交、已認證 rule_id/revision 與舊高階 assembly_type mirror 不作實體身份、Box Body／EndCap material Fold 指紋與 world formed FW 用於拒絕 stale replay。實際 Joint geometry／Registry／3D solver 仍為既有 Engine owner；無新增 CUTTING／DXF 認證或正式 X 發布，#2517 OPEN。

### #2517 GUI 已保存 Assembly Relief CUT 來源回放 request → Engine API（2026-11-01）

`manufacturing_api.resolve_operator_committed_relief_cuts(part_key, values, *, relief_state, joint_state, structure_state, cabinet_family, box_body_profile, part_profiles)` 將原 `gui_modules/application/manufacturing_adapter.py::_resolved_committed_assembly_relief_cuts` 的製造 scalar keys／`ae.*_def`、Joint Graph 機械指紋、Box Body 實體成形 FW 與保存來源比對移回 `ae_engine.operator_relief_replay`。GUI 現只蒐集操作者資料／目前工作區狀態後委派同一 Engine owner；未啟用 Relief 仍不讀取未初始化 BoxBody Profile。引擎沿用 `assembly_joint.resolved_joint_graph_fingerprint`／`box_body_editor_readback.formed_box_body_fw_widths` 與前批唯一 `assembly_relief_state` 保存契約；舊資料 invalid graph 時仍不回放 CUT，source 的 W／Family／Joint／Fold 變更皆不得復活舊已提交裁切。僅轉移公開 API 權責，不更改 Registry、Verified CUT、DXF／3D、Save→Reload schema 或正式 X，#2517 OPEN。

### #2517 Fold Designer Door／BasePlate 門格實體來源 Engine API（2026-11-01）

`manufacturing_api.resolve_fold_designer_payload_topology(part_key, payload)` 是 Fold Designer 顯示／出圖 request 前的 `door_cN_rN`、`base_plate_cN_rN` 物理來源選擇權威，唯一實作在 `ae_engine.fold_designer_payload_topology`。它沿用既有 `sheetmetal_part_adapters.derive_door_layout_cells` 的每欄寬／由上而下列高／四邊 FrameEdges，及原生 `door_layout_export_filename` stable ID；BasePlate-cell 必須指向對應真正 Door-cell 而非猜測 W/H。原 GUI `fold_designer_manufacturing_projection._payload_topology_context` 只呼叫公開 Engine API，不再自行遍歷物理門格；缺欄、失效 stable_id 仍 fail-closed，`未知類型` 舊資料正規化與 W/H 缺省保留。這批不更動 Certified Registry、Door／Base Plate 料長、2D／3D／DXF 解算、Save→Reload schema 或製造認證，#2517 OPEN。

### #2517 Fold Designer Receiving BasePlate 真實 NFB 來源選擇 Engine API（2026-11-01）

`manufacturing_api.resolve_fold_designer_base_plate_source` 與 `ae_engine.operator_auxiliary_part_specs` 現負責 Fold Designer 所有 BasePlate 操作欄位、單／多門格實體 stable ID、Receiving 實體來源優先序及 CornerPolicy 覆寫判斷。它僅沿用現有 `receiving_base_plate_config.receiving_base_plate_values` 的已提交來源 NFB V5／CSV／LEFT／CENTER／PAD／Tier 及舊檔相容規則：有真實已選 contour 就使用原來實體 H／縮邊／折型並沿用其 own Corner；無來源仍是舊預覽 fallback，**不可**冒充已認證加工；Receiving 的 `base_plate_c*` 一律拒絕。GUI `fold_designer_manufacturing_projection._fold_designer_part_spec_from_payload` 只將原始操作／來源資料傳送公開 API，回傳後走既有 `_base_plate_part_spec_from_values` → `manufacturing_api.build_base_plate_operator_part_spec` 的單向 Engine request。保留金庫型／自訂、舊 Save→Reload、2D／3D／DXF／Certified Registry 的既有判準；無新的製造能力或正式 X 認證，#2517 OPEN。

### #2517 FinalScene BEND／CUTTING Fold 實體來源投影 Engine API（2026-11-01）

`ae_engine.final_scene_fold_source` 新公開 `manufacturing_api.scene_fold_boundaries`、`profile_to_scene_boundaries`、`fold_ownership_exemptions`，將原 Phase6 FinalScene 由真正製造 `DrawingScene` BEND 線／材料 CUTTING shape 推得的材料段邊界、折向 Profile 與角落雙折所有權全部原樣移入無 Tk Engine。GUI `phase6_final_scene_projection._phase6_scene_fold_boundaries` 等三個相容函式只傳入 scene／material／operator profile，不能另行推定成品 W/H、BEND、折彎補償或局部截角。原始 1e-6 線位 dedupe、材邊條件、公差與既有 `ae_engine.assembly_geometry_folded_mesh` 的 `fold_exemptions` 消費保持不變，完全不增加 Factory／DXF/製造 cert，#2517 OPEN。

### #2517 EndCap 真實 CUTTING 內孔的 3D 世界投影 Engine API（2026-11-01）

`manufacturing_api.project_endcap_cutting_hole_rim_segments`（`ae_engine.endcap_cutting_hole_rims`）將原 `phase6_final_scene_render_helpers._draw_endcap_cutting_hole_rims` 內對 Head/Tail 已解算 local／world 裝配表面首點和真實 material inner rings 的物理座標投影搬到 Engine，單一現有 Fold Profile mapper 負責 X/Y 回投，不使用展示三角形 T-junction 當 CUTTING，亦不猜成品中心。GUI 僅轉交原資料、顏色和 line style 進行 3D 顯示；空網格／無孔／非 EndCap 回傳空線段，沒有新 Registry HIT、孔位／折邊、DXF 或正式 X 授權。原始 Head/Tail 正負號、world origin 及幾何公差維持同值，#2517 OPEN。

### #2517 FinalScene 箱身 BEND 製造來源世界線段 Engine API（2026-11-01）

`ae_engine.final_scene_box_body_bend_lines` 唯一持有 `manufacturing_api.project_assembly_box_body_bend_segments` 與 `project_box_body_structure_bend_segments`；前者接受正式 Box Body 製造 Scene BEND／Fold Guide／裝配 local reference，後者用正式 Box Body physical `pieces`（含已保存 FoldSegment）轉真正多片 3D 世界 BEND。兩個 port 重用已存在的 `assembly_geometry_primitives.place_assembly_points`、`assembly_geometry_folded_mesh.place_box_body_structure_points` 和正式 Fold mapper；不複製 Factory／Registry／料長公式。原 GUI FinalScene Render Helpers 只呼叫公開 Engine、畫線；原單片／多片可見過濾、背板隱藏 BEND 顯示、樣式不變。 `contract_fold_profile_rows` 也搬回同一 Engine，Phase6 舊名保留薄相容入口。Save→Reload 及製造／2D／3D／DXF 原資料不變，沒有新加工認證或正式 X 發布，#2517 OPEN。

### #2517 FinalScene 非接觸 MARKING 世界投影與 Joint 去重 Engine API（2026-11-01）

`manufacturing_api.project_assembly_scene_marking_segments` 使用原正式 `DrawingScene` MARKING／Fold Profile／已解析 assembly local reference 經唯一 Engine `place_assembly_points` 投影世界線段；`marking_line_signature` 與 `joint_marking_flat_signatures` 依原有 9 位小數無向端點及既有 `JOINT_PLACEMENT_MARKING` metadata 去重，真正 Joint 物理接觸線保持使用已保存 world 線段，不由 GUI 自行回推。Head/Tail flat fallback 不開放；原 GUI `_draw_assembly_scene_markings` 只畫線並保留既有視覺樣式。Engine 內 `final_scene_box_body_bend_lines` 沿用既有 Fold／world 核心，未改任何 Registry／DXF MARKING 或 Save→Reload 來源。#2517 OPEN，正式 X 未發布。

### #2517 FinalScene 獨立板件 BEND／MARKING／BLIND_HOLE 3D Engine API（2026-11-01）

`manufacturing_api.project_independent_scene_bend_segments`／`project_independent_scene_annotation_paths`（`ae_engine.final_scene_independent_annotations`）接管 FinalScene GUI 原 `_draw_scene_bends`、`_draw_scene_markings` 的實體 `DrawingScene` BEND、MARKING、BLIND_HOLE Fold→3D 線段投影；唯一座標根據為正式 material Fold Mapper，不另造 Factory、料長、孔位或 3D 衝突公式。現有 64 等分圓／閉合折線／MARKING 與 BLIND_HOLE 樣式都保持，GUI 只取 API 回傳線段並繪製，不以 UI 網格取代 CUTTING。舊製造／3D／DXF／Save→Reload／檔案格式不更動，#2517 OPEN、未發布正式 X。

### #2517 FinalScene Door CUTTING 真孔及固定片 3D hinge 無 Tk API（2026-11-01）

`ae_engine.final_scene_independent_annotations` 經公開 `manufacturing_api.project_independent_cutting_hole_rim_segments` 將真正製造 material CUTTING Polygon／MultiPolygon 內孔透過既有 Fold／assembly 世界位置投影；缺真孔或空 assembly datum 就不畫。`project_independent_fixed_plate_hinge_segment` 僅消費已驗證 `IndependentPartViewMesh.fixed_plate_hinge_y`、`source_flat_dimensions`，保持 Receiving 固定片的 3D MID-skin y=22／真實製造 DXF BEND y=23 不混用。原 GUI `_draw_cutting_hole_rims` 與獨立板件 renderer 只負責 3D 畫線、保留原色彩公差，不再判定物理座標；無新孔加工／Certified Registry／Save→Reload 改動或正式 X 發布，#2517 OPEN。

### #2517 BoxBody 組合干涉來源實體網格單一 Engine API（2026-11-01）

`manufacturing_api.project_box_body_collision_source_mesh`（`ae_engine.box_body_collision_source_mesh`）將 FinalScene Renderer 原 BoxBody 結構／整片干涉網格加厚及實體來源選擇移入 Engine。多片已由 Engine 驗證的 `physical_piece_world` 是 **已含真實 T 的 skin**，禁止再加厚一次；舊版中面 fallback 和整片 BoxBody 只以現有 `thicken_triangle_surface` 各處理一次。GUI 僅轉交已解析 part／mesh／thickness，原 `detect_world_mesh_surface_interference`、顯示／CUTTING／Relief 與 tolerance 均不動，無新的製造認證，#2517 OPEN。

### #2517 Receiving EAR 3D SIDE 定位線 Engine 公開 API（2026-11-01）

`manufacturing_api.project_receiving_ear_side_marking_segments(formed_ear_skins, visible_side_piece_keys=None)` 是受電箱固定片（EAR）在組合 3D SIDE 視圖的唯一實體來源選擇／驗證入口。Engine `receiving_fixed_plate_side_contact` 先驗證 2／4 片完整物理 owner、唯一 `part_id`、真實 T2/BEND23 formed skin，再依實體側板 `box_body:left_side`／`box_body:right_side` 顯示範圍輸出世界座標線段；空來源返回空 tuple，不以隱藏側板掩蓋錯誤來源。GUI `phase6_final_scene_render_helpers._draw_receiving_ear_side_markings` 僅接收並描繪 Engine 回傳的三條上定位／短提示線，不再自行選擇接觸面或實體 owner。此線為 **DISPLAY ONLY**，不代表 side UV MARKING、焊接認證或 DXF 出圖授權；已核准的固定片折彎、NFB、2D／3D／製造來源與 Save→Reload 契約不變。#2517 持續 OPEN。

### #2517 EndCap pre-solve 固定截角 delta 世界干涉診斷 Engine API（2026-11-01）

`ae_engine.endcap_relief_interference_preview.project_assembled_endcap_relief_interference` 經 `manufacturing_api`／根包公開；從已提交 pre-solve probe 取得 `restored_endcap_relief_delta`，或沿用舊 `ignore_fixed_corner_relief` 操作 fallback 的 delta，使用既有 Engine `folded_mesh_from_polygon`／`resolve_assembled_endcap_world_skins`／`detect_world_mesh_surface_interference`。GUI `phase6_final_scene_renderer` 只轉交原始 Engine 來源並顯示診斷，不再自行用已切角後的展示材料猜碰撞。未得到有效 delta 或世界網格則不顯示；不得將整片 EndCap 原料放進干涉判斷製造假陽性。現有 Registry、Relief CUTTING、DXF、Save→Reload 全不改，#2517 OPEN。

### #2517 Joint 接觸標註世界座標來源 Engine 公開 API（2026-11-01）

`manufacturing_api.project_joint_marking_world_segments(render_data)` 以既有 Engine-resolved FinalScene `metadata["joint_markings"]` 為唯一來源，篩選 `JOINT_PLACEMENT_MARKING` 且已有正確三維 `world_p1/world_p2` 的實體接觸標註，回傳不可變的 3D 世界線段；不從 flat `p1/p2` 推測 3D、也不補算 Fold／Joint placement。原 `phase6_final_scene_render_helpers._draw_joint_marking_world_rows` 僅呼叫 Engine 公開 API 並畫線，不再解讀來源身分或 world 座標。原 `joint_marking_flat_signatures` 去重與 `project_assembly_scene_marking_segments` 非接觸 MARKING 投影路徑完全保留，金庫型／受電箱共用同一來源。此為 DISPLAY-only 既有 Joint 資料呈現，不授予新增接觸認證、CUTTING／DXF 或其他製造 release；#2517 繼續 OPEN。

### #2517 FinalScene 單板 3D 成品尺寸標註線 Engine API（2026-11-01）

`manufacturing_api.project_operator_dimension_guides(x_profile, y_profile, triangles=(), thickness=None)` 與不可變 `OperatorDimensionGuidePlan` 由 `ae_engine.display_dimensions` 以**既有 canonical Fold 物理核心段**及**真正已成形 3D world mesh 外包絡**計算尺寸線端點、刻度與 W/H 文字座標；有真實網格時與 `resolve_operator_finished_dimensions` 使用完全相同的 `folded_outside_envelope`，沒有網格時保留原 Fold core 座標。原 `phase6_final_scene_render_helpers._draw_operator_dimensions` 只取 Engine 的 6 條線與 2 個文字定位點、顯示已解析的 W/H／原文字，不再自行計算 Fold 起迄、mesh 外包絡或尺寸線偏移。原 5.5% offset／1.2% tick 僅為顯示樣式，不參與任何料尺寸、折彎補償、孔位或 DXF 製造。保留金庫型／受電箱、原 Save→Reload、2D／3D、失效物理網格 fail-closed 與所有 Certified Registry 權限；#2517 仍 OPEN。

### #2517 專案 Save→Reload Door／Receiving 身分狀態 Engine API（2026-11-01）

`manufacturing_api.normalize_authoritative_door_state`／`normalize_project_snapshot_authority` 將 `phase6_project_file` 原本自算的已保存 Door Layout、Handle edge、內門共享 Divider stable ID 重綁、derived frame／finished size 清除、Receiving 各 Set/Bay Door source 與 Quantity state 正規化移回 Engine。原 Phase6 只保留 .p6fold JSON／Feature codec、schema 驗證、檔案路徑與 GUI 操作。Save 與 Reload 呼叫同一公開 API，拒絕不合法的實體來源；多 Bay legacy aliases 只作記憶體相容投影，FinalScene 仍由正式來源重解算而不進專案保存。這是 source authority 責任移轉，不更改已確認的 Factory、Topology、Registry、CUTTING／BEND／DXF 或額外授權任何製造能力；#2517 OPEN。

### #2517 受電箱 EAR 單／雙層組合 3D 真實板材來源 Engine API（2026-11-01）

`manufacturing_api.resolve_receiving_ear_assembly_display_skins` 將原 `phase6_final_scene_view._formed_ear_assembly_preview` 的 EAR 完整物理 owner（每層左／右，共 2／4 片）、canonical BasePlate parent ID、來源 T2／BEND23 是否真正驗證、任何 weld／MFG-ready 旗標拒絕統一交還 Engine；由原 `resolve_receiving_tier_ear_mating_xy` 與 `build_receiving_formed_fixing_plate_skins` 唯一製造來源解算。另由 `receiving_ear_assembly_display_source_key` 提供既有來源+DXF SHA 快取指紋，GUI 僅維持顯示快取、固定片開關與錯誤提示，不再自行決定物理來源真假。此為 `DISPLAY_ONLY`，不是側板 UV MARKING、焊接接觸、成套 MFG-2 或 DXF 製造放行；未改現存 source DXF、CUTTING／BEND、Save→Reload 或現有 T2／BEND23 幾何，#2517 持續 OPEN。

### #2517 Receiving 組合 3D EAR／PAD 真實世界網格 Engine API（2026-11-01）

`manufacturing_api.project_receiving_assembly_trial_world_skin_meshes(formed_fixing_plate_skins=(), formed_nfb_pad_skins=(), show_fixing_plate_mesh=True)` 於 `ae_engine.receiving_assembly_trial_display_skins` 讀取**既有真正 T2/BEND23 formed EAR skins** 與 NFB PAD 已解析 world meshes。Engine 統一驗證 EAR 的 source BEND、signed forming、未核准 manufacturing/weld，以及 PAD 的 flat+BEND、實體 Base 四定位方孔、未認證接觸與 manufacturing flag，回傳不可變 `ReceivingAssemblyTrialSkinMesh(role, part_id, world_triangles)` 序列，無來源即空。原 FinalScene Renderer 不再自行審核實體旗標或由 face.world 重建三角網格；僅按角色著色並畫 Engine 已驗證網格，保留 EAR 顯示開關獨立於 PAD／SIDE MARKING 的現有語意與原錯誤拒絕碼。這些仍為 DISPLAY-ONLY TRIAL，沒有 PAD/EAR 焊接、MFG-2、CUTTING、DXF 或製造權限；現有 2D／3D／Save→Reload 來源不變，#2517 OPEN。

### #2517 FinalScene Receiving Base Plate 實體來源顯示診斷 Engine API（2026-11-01）

`manufacturing_api.inspect_receiving_base_plate_display_source(snapshot, cabinet_family)` 將原 `phase6_final_scene_view.receiving_base_source_display_warnings` 自行判斷的 Receiving 底板實體來源是否可解析／失敗／未設定移至 `ae_engine.receiving_base_display_source`。Engine 僅委派現行 `receiving_base_plate_config.receiving_base_plate_values` 唯一實體來源判準，回傳 immutable `ReceivingBasePlateDisplaySource`（`RESOLVED_DISPLAY_ONLY`／`UNAVAILABLE`／`INVALID`／`NOT_APPLICABLE`）；GUI 僅呈現原繁中警告。保留 NFB 已提交 CSV／Set/Bay 自動來源與舊版沒有手動底板設定的判準，不增加新的箱型入口、Fold／CUTTING／BEND／DXF 或 EAR 焊接製造認證，#2517 持續 OPEN。


### #2517 FinalScene Shared Material Fold Mesh and World Placement Public API（2026-11-01）

manufacturing_api.folded_material_mid_mesh、project_box_body_structure_world_points、physical_mesh_world_bounds、project_assembly_world_triangles 直接公開既有 ae_engine.assembly_geometry／assembly_geometry_folded_mesh／assembly_geometry_primitives 的真實 material Fold 網格、箱身多片 world point、world mesh bounds 及裝配三角網格位置算法。phase6_final_scene_projection 四個舊 helper 僅保留相容 display adapter，改由公開 Engine API 消費，不再 import 低階 assembly_geometry。2D CUTTING 實體孔、3D 孔洞、T／BEND／世界座標保持原始 canonical 演算法；這是單向 API 接線，沒有新製造認證、DXF 放行或 Save→Reload 資料變更，#2517 OPEN。

### #2517 Receiving PAD 已提交真實 3D 來源／快取／不放行閘門公開 Engine API（2026-11-01）

`manufacturing_api.receiving_pad_assembly_display_active`、`receiving_pad_assembly_display_source_key`、`resolve_receiving_pad_assembly_display_skins` 將原 `phase6_final_scene_view._formed_pad_assembly_preview` 的 Receiving/NFB 提交狀態、CSV/共用加工規則與 BasePlate 真實 CUTTING 四方孔來源快取檢驗、已形成 PAD 製造或裝配貼合旗標拒絕統一由 Engine 公開 API 持有。沿用既有 `receiving_nfb_pad_preview_cache.pad_preview_source_fingerprint`、`receiving_nfb_pad_assembly_preview.build_committed_pad_assembly_display` 真正的孔位/折型/世界面 solver，並保留原錯誤碼；GUI 僅做顯示快取、顯示/隱藏、繁中警告。單層/雙層、Set/Bay 與 CSV 身份必須走原 Engine source，而非由 UI 推定；此為 DISPLAY ONLY，並不核准新 PAD CUTTING／BEND／DXF／焊接／整箱 MFG-2，#2517 OPEN。

### #2517 多門格 2D 既有真實 Door 同源預覽 Engine API（2026-11-01）

`manufacturing_api.project_operator_door_layout_peer_cells(cells, render_data_by_part_key)` 由無 Tk 的 `ae_engine.operator_door_layout_peer_2d` 按現行 `door_c<column>_r<row>` 物理實體身分，讀取**已解析的 canonical Door FinalScene** 的 `scene`／`material.bounds`，回傳不可變 `DoorLayoutPeerCell`。這個入口僅支援已存在的實體來源，缺少 Scene 或空實體輸出 `present=False`，不得用相鄰格、Legacy 預覽或輸入 W/H 代填真實來源；重複／錯誤格位及非法實體界限 fail-closed。原 `gui_modules/application/render_snapshots.door_layout_overview_snapshot` 的 peer 模式只接收 Engine 已驗證的格位、場景及尺寸，保留未提交時的 local 操作模式；不再自行決定實體 key／來源界限。原 `max(size,1e-9)` 是顯示防零除下限，不是料尺寸或製造放行。金庫型與受電箱共用，並維持 Save→Reload、2D／3D／DXF 既有母源；不新增 CUTTING、MFG2 或 DXF 權限，#2517 仍 OPEN。

### #2517 FinalScene 全實體板件干涉來源及厚板公共 API（2026-11-01）

`manufacturing_api.project_assembly_collision_display_audit` 接管原 FinalScene GUI 的實體 BoxBody piece／內門框／Head Tail 組合 world mesh 來源、visible keys 選取及 `audit_all_physical_part_pairs` 呼叫。原 Certified Registry Relief 與 `ASSEMBLY_COLLISION_MISSING_VISIBLE_PARTS` 等 fail-closed 規則保持既有 Engine 唯一判準；GUI 只快取和描繪未證實交叉。另由 `manufacturing_api` 公開既存 `restore_unrelieved_endcap_material`、`restored_endcap_relief_delta`、`thicken_triangle_surface`、`MeshInterferenceDiagnostic`、`collision_part_display_name`，Phase6 renderer 不再直接 import 底層幾何／碰撞分類。此為 3D 顯示診斷 API，不修改全箱 2D／3D／Save→Reload／正式 DXF、亦不新增製造認證；#2517 OPEN。

### #2517 Manufacturing Request RAW 實體板件來源及 Set/Bay 擁有權 Engine API（2026-11-01）

`manufacturing_api.canonical_manufacturing_request_part_keys(snapshot, available_parts)` 將原 `phase6_manufacturing_adapter._canonical_part_keys` 中 Receiving 已提交 NFB 底板來源的缺件補齊、雙層四片固定耳唯一 owner 身份重建、衍生 BoxBody／tier BasePlate／PAD 非 RAW ID 過濾移回 Engine；沿用 `receiving_base_plate_values`、`receiving_base_fixing_plate_previews` 與 `physical_part_identity` 的原有判準及錯誤處理。GUI 不再直接讀取低階來源模組，也不自推板件身份。Engine 回傳同順序 immutable RAW PartSpec key tuple，非新的 CUTTING/BEND/DXF/焊接製造認證；#2517 OPEN。

### #2517 數量模式即時版本特徵合法性製造 API（2026-11-01）

`manufacturing_api.validate_operator_manufacturing_quantity_context(input_snapshot, live_workspace_snapshot)` 將原 `phase6_manufacturing_adapter` 組 RAW request 與 cache lookup 前兩處直接 `require_valid_quantity_features`、合併目前 Workspace `quantity` 和 `receiving_quantity_box` 的規則統一收回 Engine。沿用既有 `receiving_quantity_box.require_valid_quantity_features` 對各版本 Head/Tail finished-face 特徵合法性與原 `不能輸出 DXF` 錯誤的單一判準；非數量模式 N/A。GUI 只取得 Workspace source 及呈現 Engine 拒絕，不新增補償或假製造權限；#2517 OPEN。

### #2517 FinalScene Joint 接觸／穿透／保留／退讓 3D 診斷世界來源 Engine API（2026-11-01）

`manufacturing_api.project_joint_diagnostic_display_sources(render_data)` 由無 Tk 的 `ae_engine.joint_diagnostic_display` 讀取**已由 Joint Solver 建立**的 `ResolvedJointDiagnostic`，以 `selected_joint_id` 選取現行 source；僅保留 contact／penetration／preserve／relief 的合法三維世界線段與已解析方向向量，輸出不可變 `JointDiagnosticOverlaySource`。原 `phase6_final_scene_render_helpers._draw_joint_diagnostic_overlays` 只按 Engineer-result role 選 Matplotlib 畫筆、畫線與方向箭頭，不再自己過濾 Joint 來源、判斷世界座標或計算方向差分。非有限／不完整世界線段不會被呈現為診斷來源。這只是 solver 診斷的 read-only 3D 顯示，不變更 Registry 認證、Joint 接觸解算、世界碰撞報告、CUTTING／BEND／DXF 或 Save→Reload；金庫型與受電箱共用，#2517 仍 OPEN。

### #2517 Phase6 Manufacturing Scene Set/Bay／Joint／BOTTOM Reserve 唯一來源 Engine API（2026-11-02）

`manufacturing_api.project_manufacturing_scene_settings_overlay`、`project_manufacturing_scene_joint_source`、`project_manufacturing_bottom_relief_structure` 將原 `phase6_manufacturing_adapter.build_scene_payload_for_app` 的 Receiving 當前 Set/Bay Door/NFB 保留規則、舊 Joint 快照 migration、Family EndCap BOTTOM 實體避讓 reserve 投影移入無 Tk Engine。權威仍為既有 `ae_engine.receiving_layout.RECEIVING_DOOR_STATE_KEYS`、`assembly_joint.migrate_legacy_snapshot_joints`、`cabinet_types.policy`／`endcap_bottom_wrap_state`；不允許全域舊 settings 覆蓋當前 Bay 來源、不變更切割折彎公式或製造認證。GUI 只做場景來源收集、API 調用及顯示；#2517 OPEN。

### #2517 Receiving BoxBody 真實 DXF 來源快取失效決策 Engine API（2026-11-02）

`manufacturing_api.plan_manufacturing_cache_source(snapshot, workspace_structure)` 將原 `phase6_manufacturing_adapter._cache_service_for_app` 中 Receiving Set/Bay cache 容量、有效 BoxBody 結構白名單、三片式專用左右／後板來源包含判定交給 Engine。唯一來源仍為 `box_body_structure_state.BoxBodyStructureType` 及 `manufacturing_baseline_policy.receiving_baseline_source_stamp`（真實 DXF fingerprint／reload generation）；未知結構不復用原製造結果，GUI 只接實際資源 Context 與管理 bounded cache。非 Receiving 模式維持單份快取，正式製造／DXF 閘門不變，#2517 OPEN。

### #2517 真實板件 BoxBody／Receiving 分層固定耳父子身份 Engine API（2026-11-02）

`manufacturing_api.project_physical_part_navigation_rows(available_parts)` 將原 `phase6_part_navigation.project_hierarchy` 中 BoxBody 實體子板、受電箱 BasePlate 單／雙層與四片固定耳的 owner 解析收回無 Tk Engine，沿用 `physical_part_identity.is_box_body_physical_piece_key` 與現行 NFB tier identity。只消費 Workspace 已存在的板件，不創造父板，不更動操作者清單順序；GUI 僅轉 `NavigationRow` 顯示及管理 selection。此為身份只讀投影，非製造放行，#2517 OPEN。

### 1.1 GUI → Engine API 單向製造權責 `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1`

**[CONFIRMED PRODUCT RULE｜2026-11-02] 全箱型共用既有 Engine 製造架構，不為受電箱另開一條製造路線。** 這是對 #2517 與 CADSplit #15 的原則性澄清，優先於舊的「另開外部 export」施工建議：

- **唯一製造 owner、按能力重用既有入口。** WHD GUI 與 CADSplit 的可信 operator/source adapter 都交由 `ae_engine.contracts`／`ae_engine.manufacturing_api` 的同一套公開 Engine 能力執行；單一板件沿用 `generate_part(PartSpec, ..., ManufacturingContext)`，組合、數量、Set/Bay、NFB、已解析實體板件／FinalScene、批次 DXF 則選用當版**已存在且適用**的製造／解算／驗證 API。共用的是 Family／Topology／Policy／geometry／Registry／輸出權威，**不等於強迫所有操作呼叫同一函式**。
- **新箱型只擴充差異。** 在 `ae_engine/cabinet_types/registry.py` 登記 identity／alias，受電箱特有 Factory/Topology/Policy 在 `cabinet_types/receiving.py`、`policy.py` 與既有 canonical owner 擴充；不得複製金庫型 Door／BoxBody／EndCap exporter、另造 Receiving 專用製造 pipeline／API／GUI／Bridge，或以來源盤名、Set/Bay、W/H/D/T 猜出 `physical_part_id`、Fold、Corner 或 Factory Policy。既有 API 不能表達的**真新操作**才可向後相容加入口，不能因新增 Family 而加入口。
- **source-only ≠ 正式製造。** `ae_engine.integration_api.dispatch_manufacturing_integration(ManufacturingIntegrationRequest(operation="export", ...))` 只有 source identity、Family 等資訊；目前所有已實作 Family 一旦進入該分支，固定回 `EXTERNAL_EXPORT_NOT_CERTIFIED`／`WHD_INTEGRATION_MANUFACTURING_NOT_CERTIFIED`，不會出 DXF。2026-11-02 CADSplit #15 以兩張真 DXF 呼叫已確認此事；**這不是受電箱被禁止用共用 Engine，也不是缺 CSV 欄位的問題**。禁止單純刪掉拒絕分支、把 source-only `export` 改造成第二個製造 executor，或誤導 CADSplit 把它當唯一正式製造入口。舊安裝版 Worker/EXE 仍退役。
- **應補的是同一條來源接線。** CADSplit 從原始 DXF／finalized info_data 保留來源證據；可信 Project／Factory authority 補足 PartSpec／實體拓樸／Set/Bay 對應所需的已確認輸入；WHD Engine 做製造身分、Family/Part/Operation 適用性、幾何與 Registry 判定；既有 verified DXF Save→Reload 檢核及來源漂移 guard 才能宣稱當次輸出通過。缺任一必要權威只拒絕受影響的 Part／Operation，舊版金庫型合法能力不因受電箱未完成而停用。
- **現況不得冒稱完成。** `cabinet_types.registry` 目前主要是 identity；`manufacturing_api._export_to_temp()` 仍主要按 `PartSpec` 類別分派，尚未全入口落實 Family×Part×Operation 製造資格。CADSplit 既有金庫型 Door／EndCap Bridge 能組出 `PartSpec` 並呼叫 `generate_part`，不代表其所有 DXF 都已認證；Receiving 有條件式 Engine resolved/verified batch 路徑，但原圖正常流程尚未證實能完整組出可信請求。後續施工在 #2517 補 **既有** API／Family seam、正反例與金庫型不退化驗收，不得用文件、`prepare` 或「可匯入」代替實際 DXF 回讀驗證。



**#2517 EndCap 實體裝配世界面／T 厚皮公開 API（2026-11-01）**：`manufacturing_api.resolve_assembled_endcap_world_skins` 經已存在的 Engine `place_endcap_against_box_body`＋`thicken_triangle_surface` 統一回傳 immutable `AssembledEndcapWorldSkins`（折後表面、實體板厚世界三角網格）。Receiving 設定 2D、FinalScene 3D 主視圖及 fixed-relief 碰撞 probe 同源委派，沿用原 Head/Tail、T/2 實體內面接合、`preserve_core_origin` 與正常／診斷顯示來源；GUI 不再直接補償 EndCap 配置／厚度。未更動原版材、已認證 Relief、CUTTING／BEND／DXF／Save→Reload 或新增製造核准；#2517 OPEN。

**#2517 箱身多片真實板厚世界座標 Engine API（2026-11-01）**：`manufacturing_api.resolve_box_body_true_world_piece_meshes(part, dimensions, thickness)` 將 3D FinalScene `_phase6_box_body_true_world_piece_meshes` 原來自行重複的物理 Box Body 源寬資格、唯一實體 ID、W/H/D、真實 T 厚網格與世界位置驗證，統一委派既有 `ae_engine.receiving_settings_assembly_mesh` 求解器及 canonical `build_joint_world_geometry`；Receiving 2D 組合視圖也共用同一公開 API。只傳已解析實體 DTO，不改來源／形狀／順序；無片、預覽占位返回空，非法來源 fail-closed。不新增製造演算法、CUTTING/BEND/DXF 認證，#2517 持續 OPEN。

**#2517 箱身多片折後中面網格公開 Engine API（2026-11-01）**：`manufacturing_api.resolve_box_body_structure_mid_meshes(render_data, thickness=...)` 沿用已存在的 Engine `_structure_meshes` 唯一實體折後 source owner，回傳按原始 physical piece 順序的組合位置中面網格；只有預覽 stub 回空，非法外側 W 來源沿原驗證拒絕。3D FinalScene `_phase6_box_body_structure_meshes` 不再自行折料、複算 Box Body 世界定位，只將公開 Engine 回傳轉為舊 list，相同 API 也供受電箱 2D 設定頁重用；真實 T 厚板、成形物理身份、製造 BEND/CUTTING、碰撞與 DXF 權威沒有改變。#2517 維持 OPEN。

**#2517 3D 組合物理尺寸證據 Engine API（2026-11-01）**：`manufacturing_api.project_assembly_physical_dimension_evidence` 由已解析實體 Box Body 左／右側板 Fold profile 按既有 Engine 相鄰 BEND／T 算法讀取折後包外各段（保留正式 `formed_length`），對中隔則讀真實 material span、原 `physical_geometry_contract` 的 FW/core 包外。`phase6_final_scene_projection._phase6_assembly_physical_dimension_lines` 只負責 UI 繁體中文與數值格式，不再直接重算補償／讀物理 bbox。結果 immutable、唯讀，未變更 CUTTING、BEND、DXF、Save→Reload 或製造放行；#2517 持續 OPEN。

**#2517 受電箱設定 2D 實體組合世界座標 Engine API（2026-11-01）**：`manufacturing_api.resolve_receiving_settings_assembly_world_meshes` 接受已解析 Assembly part DTO、成品尺寸、板厚與原 EndCap Core 原點設定，統一由 Engine 依現有多片 Box Body 真正實體 world skins／FW／Z、各板件折後網格與封頭封尾裝配接合解出世界 XYZ；GUI `receiving_settings_preview_2d._assembly_world_meshes` 只送 request 及轉換顯示 role，再交既有公開 XY 輪廓 API。沿用原 source ID、順序、未核准實體拒絕與 GUI 視覺選擇；本 API 唯讀，不新增 CUTTING／BEND／DXF 認證，#2517 維持 OPEN。

**#2517 Receiving committed NFB 實體板件組合公開 API（2026-11-01）**：`manufacturing_api.resolve_receiving_nfb_assembly_parts(snapshot, parts)` 統一 Engine 原有兩段程序：先以既有 `expand_receiving_nfb_layer_parts` 展開獨立兩層 Base Plate 實體；僅 Receiving 且 `nfb_config_submitted is True` 再以既有 `apply_committed_csv_v5_to_canonical_parts` 套用已提交 CSV 螺絲孔／來源 FinalScene。Engine 層板件生成改以 `dataclasses.replace(root, ...)` 重建相同 frozen dataclass 型別，移除 `phase6_final_scene_contracts` 反向 import。保留未提交候選、單層、來源身份漂移、缺正式 Z／CSV 的既有 fail-closed；不另發明 NFB 孔位、EAR、CUTTING／DXF 或認證。#2517 保持 OPEN。

**#2517 受電箱設定頁實體組合 2D XY 邊線 Engine API（2026-11-01）**：`manufacturing_api.project_solid_mesh_xy_outline` 從已解析的實體 3D mesh 經既有 `physical_solid_mesh_feature_segments` 生成唯讀世界 X/Y 邊線，保留原五位小數、零長線剔除及無向去重。GUI `receiving_settings_preview_2d._projected_outline` 只負責公開 API 委派；Canvas 色彩、角色顯示及互動仍在 GUI。此視圖不能作為 CUTTING、BEND、DXF、NFB、PAD、EAR 製造權威；其餘組合網格的 GUI 既有路徑仍待後續獨立遷移，#2517 OPEN。

**#2517 受電箱 EAR 固定片側板 2D／單板 3D 來源預覽 Engine API（2026-11-01）**：`manufacturing_api.resolve_receiving_ear_side_display_context`／immutable `ReceivingEarSideDisplayContext` 統一 GUI 兩個入口重複的 FoldDesigner 已提交 NFB 來源判定、主視窗鏡像來源漂移拒絕、原始 Box Body 實體板件 baseline SHA／真實圖元快取指紋及 W/H/D/T 包外來源輸入。GUI `receiving_ear_side_2d` 只讀取/選擇視窗快照、呼叫 Engine `project_receiving_ear_side_piece_2d_preview` 並保留 Canvas／隔離單板顯示快取；實際 EAR UV／MARKING 的唯一來源仍是原 Engine。保留 #1503 受電箱左右側板標記、真實 2D/3D、主視窗過期拒絕與 Save→Reload CHECK DXF 正反案例；**此 read-only 顯示不是 EAR 焊接、PAD、CUTTING、DXF 或整箱 MFG-2 製造核准**，#2517 OPEN。



**#2517 受電箱 NFB CSV V5 真實單／雙層底板來源預覽 Engine API（2026-11-01）**：`manufacturing_api.preview_receiving_nfb_v5_real_base_sources` 接管原 GUI `receiving_nfb_v5_scene_preview` 自行做的實體底板原始 PartSpec 身份、包外尺寸／T、縮邊與實際折型、Set/Bay 提交來源、NFB 層別及兩片獨立實體 BasePlate 來源核對；沿用原 Engine `source_receiving_nfb_tier_base_specs` 與真實 V5 source preview，不複製製造公式。`require_receiving_nfb_v5_inner_door_trial_preview`／`require_receiving_nfb_v5_base_trial_preview` 將 GUI 畫出未核准 FinalScene 前的試作狀態／製造旗標拒絕也移到 Engine；GUI 只拿驗過的 render data 在 Canvas 畫圖。現有 #1901 真實底板 Set/Bay/source stale 與 #1502 單雙層案例保持原判準，**此預覽絕非 DXF、EAR、PAD、整箱 MFG-2 製造放行**，#2517 OPEN。



**#2517 受電箱 NFB 製造清單 read-only Engine Validation API（2026-11-01）**：`manufacturing_api.validate_receiving_nfb_manifest_view` 與 `validate_receiving_nfb_highlighted_manifest` 接管 GUI 原本的物理片數／READY 狀態一致性、CSV V5 尚未製造診斷、Set/Bay/version 身份與多 Bay 選片驗證。GUI `receiving_nfb_manifest_view` 僅將已驗證的來源證據呈現繁體中文，不得自行證明可加工或製造合格。此 API 僅是**防止顯示假綠燈的 read-only report 檢核**；實際放行仍須當次來源重驗與 typed `NfbPartialExportManifest.require_export`／正式 Engine DXF writer。原 #1501 UI 文字與正反回歸保留，絕不藉 UI status 宣稱 PAD／EAR／整箱 MFG-2 已認證；#2517 OPEN。



**#2517 受電箱 NFB 成對實體 DXF Engine API（2026-11-01）**：`manufacturing_api.export_verified_receiving_nfb_door_base_pair`、`export_current_csv_nfb_door_base_pair`（單層兩片／雙層三片）及 immutable `NfbCsvPairedPartOnlyDxf`／`NfbCsvTwoTierPartOnlyDxf` 接管原 GUI 內門＋底板來源重驗、實體板件選取、NFB CSV/X/Y/旋轉、層別深度/XYZ、真實 FinalScene 同源比對、CHECK/Q、暫存 DXF 重開及無覆寫原子發布。GUI `receiving_nfb_pair_partial_export_action` 只保留 Engine 公開 API／原型別相容 re-export；維持既有 `NfbPairedPartOnlyDxf` 真實來源回執與所有既有 1502 單層／雙層正反案例，不新增第二套製造數值或允許 PAD／EAR／整箱 MFG-2 出圖，#2517 OPEN。



**#2517 受電箱 NFB 實體內門 PART_ONLY 出圖 Engine API（2026-11-01）**：`manufacturing_api.export_verified_receiving_nfb_inner_door` 將原 GUI `receiving_nfb_partial_export_action` 中已提交 Set/Bay/version、Switch 品牌、唯一實體內門穩定 ID、原始 DXF SHA＋上層 handle/revision、保存孔位／世界 X 與旋轉、無覆寫 PART_ONLY DXF writer 驗證全部搬到 Engine；GUI 檔只保留公開 API 相容匯入與操作參數。原 1501 正反測試的 mock 點移到同一 Engine 函式，不更改其失敗判定、來源數值或真正 writer。內門單件未核准 BasePlate／PAD／EAR／整箱 MFG-2／額外 CUTTING 或 DXF，#2517 OPEN。



**#2517 受電箱 NFB 實體底板 PART_ONLY 放行 Engine API（2026-11-01）**：`manufacturing_api.nfb_verification_geometry_changed`、`prepare_verified_receiving_nfb_base_plate`、`export_verified_receiving_nfb_base_plate` 將原 GUI BasePlate 的實際 Set/Bay/version 提交證據、現行 NFB 原 DXF SHA、上／下來源 handle、BasePlatePartSpec／Family 物理身分、已確認孔位、真正 DXF PART_ONLY 保存與拒絕全部遷入 Engine。GUI 原 `receiving_nfb_base_partial_export_action` 只保留相容 API 匯入，`receiving_nfb_partial_export_action` 也共用 Engine 來源幾何指紋；沿用既有 verified geometry composer 和原子 DXF writer。三個 Receiving BasePlate 原始折型、舊資料、斷來源／錯板件拒絕保持原契約。**個別底板**不能冒充 PAD／EAR 焊接／整箱 MFG-2 放行，未新增 CUTTING 或 DXF 製造認證；#2517 OPEN。



**#2517 受電箱 NFB 內門＋底板成對 DXF CHECK/Q 公開 API（2026-11-01）**：`manufacturing_api.NfbPairedPartOnlyDxf` 與 `NfbPairedQuantityInput`／`NfbPairedQuantityCheck`、`group_reopened_nfb_pair_check_q`、`save_checked_reopened_nfb_pair_q_dxf` 將原 GUI 成對 DXF 重開比對、原始來源 SHA、Set/Bay/version＋兩張實體 ID、一筆 Q 數量守恆及 PART_ONLY 寫入決策搬入 Engine。GUI 輸出 action 與原 CHECK/Q 匯入路徑只 re-export 公開 Engine typed DTO／operation。原 `NfbQuantityPartGate`、`manufacturing_equivalence`、`verify_saved_part_render_data_dxf` 保留唯一製造判準，絕不將兩張 PART_ONLY 的來源證據擴張為整箱 MFG-2／EAR／PAD 核准；未新增 CUTTING／DXF 認證，#2517 OPEN。



**#2517 受電箱 NFB 多 Bay 內門部分出圖公開 API（2026-11-01）**：`manufacturing_api.require_highlighted_nfb_inner_doors`、`manufacturing_api.export_highlighted_nfb_inner_doors` 接管原 GUI `receiving_nfb_partial_batch_dispatcher` 的已提交來源、真實 Set/Bay/version 與實體內門 ID 查核、批次 DXF 隔離暫存、無覆寫原子發布及失敗回滾。原 GUI module 僅作公開 API 相容 re-export；`manifest`／`partial_export` 仍是來源必須即時重驗的原正式 port，過期／跨 Bay／偽造 typed receipt 必拒絕。明確選擇 allow_held 時僅放行 READY 內門並產生未出圖 Bay 報告，不把底板／PAD／EAR 誤計為已出板片；不新增孔位／CUTTING／DXF 認證或整箱製造權，#2517 持續 OPEN。


**#2517 Receiving NFB CSV 已出圖範圍來源證明 Engine API（2026-11-01）**：`manufacturing_api.resolve_verified_csv_v5_export_scope` 由既有 `receiving_nfb_model_identity.selected_numeric_spec`、`receiving_nfb_y_projection.project_nfb_inner_door_nominal_y` 確認精確 Set/Bay、W、實體孔身分與 X/Y/rotation；`capture_verified_csv_v5_pair_display_proof` / `verified_csv_v5_operator_label` 由 Engine 唯一校驗已提交 snapshot、原品牌 CSV 真實 bytes、已實際存檔並重新開啟的兩／三片 PART_ONLY DXF 真實 bytes 與目前來源是否完全相等。GUI exporter 只採原本的 typed 成功 receipt，`receiving_nfb_verified_scope_display` 只傳輸來源與回傳顯示標籤，不再持有 SHA、來源型號／物理身份及是否可以標示過去已出圖的決策。Proof 為 immutable 的暫存歷史輸出展示憑據，不寫入專案；來源或輸出檔任何漂移立即失效、不推定全箱／EAR／PAD／下一次正式製造權限。原出圖、Save→Reload、Fail closed 不改；#2517 保持 OPEN。


**#2517 Receiving NFB V5 CSV 來源預覽公開 API（2026-11-01）**：`manufacturing_api.ReceivingNfbV5SourcePreviewCache.load(brand, model_ref)` 與 immutable `ReceivingNfbV5SourcePreview` 將原 GUI 的 V5 廠牌／型號身份比對、`brand_csv_path` 檔案版本簽章、當次 CSV 解析與最多 8 筆的 per-editor source cache 改由 Engine 擁有。既有 `receiving_nfb_model_identity.selected_numeric_spec` 和 `receiving_nfb_numeric_catalog` 仍是唯一型號／孔位數值來源；原 CSV 在解析期間改變版本則拒絕緩存，未知／跨品牌身份 fail-closed。GUI `receiving_nfb_source_preview.NfbDxfSourcePreviewPanel` 僅依 Engine 回傳的來源實體和數值畫 source-only 示意、處理縮放及 verified-output 標籤，不再直接解析 NFB 身份或讀 CSV 檔案來源時間。舊 DXF 預覽、同來源快取、缺數值禁止製造、Set/Bay 提交／出圖／DXF 認證均保留原界線；此 API 不構成 CUTTING／DXF 製造核准，#2517 維持 OPEN。


**#2517 EAR 實體側板 read-only 2D MARKING 公開 API（2026-11-01）**：`manufacturing_api.project_receiving_ear_side_piece_2d_preview(snapshot, source_piece, piece_key, geometry, dimensions, sheet_thickness, world_geometry=None, display_only_marking_overlap=False)` 由 Engine 一次核對已提交 Receiving、真實左／右側板、成品材料與 baseline source SHA，透過既有 `build_joint_world_geometry`、`resolve_receiving_ear_side_uv_receipts`、`build_receiving_ear_side_marking_previews` 將物理 inside-skin world→UV 證據投影成獨立 `render_data` scene 複本，並保留 `ear_side_mark_preview_only`／`manufacturing_ready=False` 的原安全界線。GUI `receiving_ear_side_2d` 現只負責原有快取、顯示/失敗提示與公開 API 呼叫，不直接驗製造側板身分／材料／UV，也不引用低階 solver。原 SIDE MARKING、真正 2D／單件 3D 預覽、CHECK-only DXF 與未核准焊接／正式製造的 fail-closed 完全沿用；#2517 持續 OPEN。


**#2517 Receiving 內門縮圖 NFB 型號／層數公開 API（2026-11-01）**：`manufacturing_api.resolve_receiving_inner_door_preview_inventory(config)` 回傳 immutable `ReceivingInnerDoorInventoryLayer`，以既有 `receiving_shared_settings.switch_filenames_in_layer`、`receiving_nfb_model_identity.display_model_ref` 投影真正儲存的每層開關身份、重複數量與顯示標籤，支援 legacy `.dxf` 與 V5 `nfbv5:廠牌:型號`。數量先依完整身份分組，不能因跨品牌同名合併；舊 0/1/2 顆存檔相容與原本可見層數契約不變。GUI `receiving_inner_door_thumbnail` 只畫縮圖文字及數量 glyph，不再直接 import 低階 Engine 型號驗證或解析身份；這不是孔位、3D、CUTTING、DXF 來源／製造認證。#2517 持續 OPEN。


**#2517 正式板件 ResolvedManufacturingPart 組裝 API（2026-11-01）**：`manufacturing_api.materialize_resolved_manufacturing_parts(parts)` 使用既有 Engine frozen DTO，按原始順序組裝已解析實體板件 Render、Fold X/Y 的各段 mapping 複本、placement、offset；Phase6 只轉送已解析資料，不建立第二份 canonical 製造板件。仍由 `ResolvedManufacturingGeometry` 拒絕重複 part key，保留實體資料／保存／2D／3D／DXF 權威，不新增任何 Fold／CUTTING 公式；#2517 OPEN。

**#2517 USER_ADDED Explicit Joint relief 求解公開 API（2026-11-01）**：`manufacturing_api.resolve_manufacturing_explicit_joint_reliefs` 由 `ae_engine.explicit_joint_pipeline` 唯一持有原 Phase7 A6 七階段實體製造／碰撞／裁切、World/UV 驗證、saved-cut replay、provisional 診斷；callbacks 只來自 Engine 既有 `assembly_joint`、`assembly_collision`、`assembly_geometry`，不反向 import Phase6/Tk/FinalScene；`phase6_manufacturing_geometry` 只委派 Engine，舊 `phase6_explicit_joint_pipeline` 只作 import shim。臨時驗證材料由原 resolved part immutable dataclass replace 或等價 headless DTO 建立，不改已認證 cut／Save→Reload／Registry，未新增 CUTTING／DXF 能力；#2517 OPEN。

**#2517 Relief rule trace／Joint diagnostic 公開 API（2026-11-01）**：`manufacturing_api.resolve_manufacturing_relief_evidence(resolved_parts, solutions, joints)` 統一由 Engine 將既有 solver EndCap corner、3D shadow、Receiving bottom-WRAP metadata 與 Registry Joint ownership 投影成 `ResolvedReliefRuleTrace`、`ResolvedJointDiagnostic`。保留既有 trace 順序、`USER_ADDED` 獨立 relief pipeline、legal contact／穿透診斷及 deep-copy evidence；Phase6 只組合 Engine 結果供顯示。沒有新增 Certified Registry 來源、CUTTING／DXF 授權；#2517 仍 OPEN。

**#2517 Fold Designer 實體中隔／內門框／內門板選片 API（2026-11-01）**：`manufacturing_api.resolve_fold_designer_divider_part`、`resolve_fold_designer_frame_part`、`resolve_fold_designer_panel_part` 依既有 canonical Door grid、Cabinet Family 與 Frame/Panel Part topology 選擇真正 physical stable ID；不存在的選片 fail-closed。GUI 僅正規化操作員中隔欄位、提交 payload，拿回 Engine Part 再呈現既有 FinalScene。Family 補償、Frame/Panel 尺寸與製造 2D/3D/DXF 公式沒有新版本，也不增加任何認證；#2517 仍 OPEN。

**#2517 AssemblyJoint 製造拓樸公開 API（2026-11-01）**：`manufacturing_api.resolve_manufacturing_joint_graph(input_snapshot, available_part_keys)` 使用既有 Engine `migrate_legacy_snapshot_joints` 與 `ResolvedAssemblyGraph` 一次處理保存 schema migration、真實可用板件 Joint 篩選、自訂板件未確認 placement 的 fail-closed，以及 Joint ID／region 驗證。Phase6 僅傳 snapshot 與可用實體板件清單，不再決定製造拓樸；原始保存值、Assembly Intent／Certified Registry／CUTTING／DXF 權威不變；#2517 保持 OPEN。

**#2517 EndCap Assembly relief 求解／診斷公開 API（2026-11-01）**：`manufacturing_api.solve_endcap_assembly_relief(body_part, endcap_part, ...)` 使用既有 Engine World-backprojected solver，處理實體 Box Body／Head/Tail Render、Fold profile、放置位置／Family 與已確認裝配語意；`manufacturing_api.endcap_relief_solution_diagnostic(solution)` 根據既有 Engine certified/verified policy 分類 3D Shadow 與未驗證穿透，保留原錯誤訊息。`phase6_manufacturing_service` 僅提交來源與呈現結果，不再直接呼叫 private collision 求解器或重寫認證診斷。不新增截角公式、CUTTING／DXF 認證；#2517 仍 OPEN。

**#2517 EndCap Head/Tail 原子提交 API（2026-11-01）**：`manufacturing_api.endcap_relief_transaction_committable(required_parts, solutions)` 依 Engine 既有 `endcap_relief_solution_committable` 認證判準，對實體 Head/Tail 同批採全有或全無決策；任一必要解不存在、不可提交或空集合時拒絕。`phase6_manufacturing_service` 僅提交所需實體身份與已解析結果，不再自組 `all()` 決定製造發布。保留既有已認證 ENGINE_CONFLICT 與 3D 影子診斷分離；不新增 CUTTING 或 DXF 認證，#2517 保持 OPEN。

**#2517 verified EndCap relief canonical replay（2026-11-01）**：公開 `manufacturing_api.replay_resolved_endcap_render(part_input, solution)` 是已認證 EndCap Joint/relief 2D CUT 的唯一 PartSpec replay owner，直接依既有 Engine `serialize_joint_relief_polygons` 與 `build_part_render_data` 重建正式 FinalScene；`phase6_manufacturing_service._replay_endcap_render` 僅委派。保留無 PartSpec 輕量 headless 已解析 Render 相容路徑；正式 canonical material 存在性與 2D/3D solver symmetric-difference 面積閘門（既有 1e-5 閾值）也統一移到 Engine，Phase6 不再自行計算製造幾何差異，不能把 solver preview 當正式製造或新增 DXF 認證；#2517 保持 OPEN。


**#2517 Live Cabinet Family identity API（2026-11-01）**：公開 `manufacturing_api.resolve_live_cabinet_family(input_snapshot, live_model=None)` 統一 GUI 即時選擇型號優先序、Cabinet Registry 正規 Family 與舊版未知／空值 fallback。Phase6 GUI 只讀 snapshot 與 selector，`phase6_manufacturing_service` 也使用同一 API，避免 3D Joint／Receiving Marking 再有第二份型號判定。未註冊自訂來源保留原始名稱供既有 Family=ANY Joint 使用，空值維持既有金庫型相容預設；不新增 CUTTING／DXF 認證或幾何公式，#2517 仍 OPEN。

### #2517 Physical sheet Hole Editor context public API (2026-11-01)

- `manufacturing_api.resolve_physical_sheet_editor_context(part_key, render_data, custom_spec=None)` and immutable `PhysicalSheetEditorContext` (also exported by `ae_engine`) resolve exactly one real Box Body child sheet from an already-authoritative BoxBody structure, or reuse the canonical individual sheet Render and `physical_sheet_feature_context`; CustomFold uses the existing validated `CustomFoldPartSpec` / `custom_fold_feature_context` owner, rejecting identity mismatch. GUI `physical_part_hole_editor.open_workspace_sheet_editor` only collects source render/spec and opens the existing Hole Editor; it no longer selects physical child Render by role nor imports low-level physical-sheet/custom-fold geometry helpers. Existing feature editing, Save→Reload, 2D/3D/DXF and unverified EAR export fail-closed behavior remain authoritative and unchanged. No new manufacturing or DXF certification; #2517 remains OPEN.

### #2517 Canonical corner-dimension readback public API (2026-11-01)

- `manufacturing_api.project_render_corner_relief_measurements(render_data)` returns immutable `RenderCornerDimensionGroup` rows from the existing Engine `assembly_collision_corner.measure_material_corner_reliefs` authority, using actual manufacturing material for a single part or each physical BoxBody piece in stable render order. Main GUI / Fold Designer `phase6_corner_dimension_display` now only formats Engine-owned measurements into Chinese UI labels; it never chooses physical material carriers or invokes the lower-level collision solver. Zero genuine material cuts return no rows; the old 2D, single-3D and assembly-3D texts remain identical. This is display-only readback, not new Corner/Relief formula, CUTTING/DXF certification or an external Worker capability; #2517 remains OPEN.

### #2517 Receiving EndCap saved-feature thumbnail public API (2026-11-01)

- `manufacturing_api.receiving_endcap_feature_preview_shapes(features, width, depth)` (also exported by `ae_engine`) is the headless owner of saved EndCap feature anchors, legacy-hole conversion, rotation and per-layer contour projection used by the Receiving Head/Tail operator thumbnail. Unknown/invalid features are reported, never fabricated as CUTTING. GUI keeps only rendering style, scaling and UI fallback labels; the old GUI `endcap_preview_geometry` symbol is a compatibility delegator with no feature geometry calculation. This read-only feature thumbnail **is not** canonical FinalScene or new DXF/CUTTING certification, and #2517 remains OPEN.

### #2517 Receiving inner-door Hole Editor context API (2026-11-01)

- Public `manufacturing_api.resolve_inner_door_hole_editor_context(input_snapshot, part_key)` and immutable `InnerDoorHoleEditorContext` (also exported by `ae_engine`) own physical panel identity, existing Vault-door structural/feature surface, finished and Receiving work-area measurement guides, and the canonical CUTTING/BEND render for one active inner-door editor. GUI only submits a snapshot/physical part key and draws the returned result. The large reference guide is **display-only**: never use it as manufacturing CUTTING or FeatureSurface containment; no new NFB/DXF certification granted. #2517 remains OPEN.

### #2517 Assembly physical mesh profile API (2026-11-01)

- Public `manufacturing_api.resolve_material_mesh_profiles(part_input, material)` now owns the historical Phase6 assembly request-time Fold X/Y normalization for the canonical whole Box Body and one-axis divider/inner-door frames. Material bounds are consulted lazily only when an actual physical single-material part needs a derived flat span, with the unchanged strict invalid/nonfinite bounds rejection. The GUI/Phase6 compatibility entry only forwards already-resolved manufacturing inputs. No new manufacturing formula, Certified Registry policy, CUTTING or DXF capability is created; #2517 remains OPEN.

**#2517 Receiving NFB 候選套用／實體孔身份 API（2026-11-01）**：候選的 `NFB_CSV_SOURCE` 實體內門來源驗證、混合 CUTTING 拒絕、已提交 NFB 與非 CSV 覆寫衝突，以及真實 Bay 專屬 physical hole ID 一律由 Engine 公開 `candidate_committed_csv_nfb_config`／`validate_candidate_nfb_replacement`／`replace_candidate_bay_nfb` 處理。GUI 只選擇版本、Set/Bay 及提交 Engine 回傳的 layout；同一份 CSV/Project/物理 provenance 權威不變，保存/候選套用不自動核准 NFB X 或新增 DXF 製造能力。

**#2517 Receiving NFB 品牌變更實體 X 證據 API（2026-11-01）**：公開 `manufacturing_api.rebase_receiving_set_parent_nfb_brand(set_row, proposed_brand)` 由既有 `ae_engine.receiving_nfb_brand_transition` 統一決定 Set 品牌變更與已提交 NFB 實體孔 X 的 `RECONFIRM_REQUIRED`。回傳 (detached Set row, changed)，不改輸入；原繼承來源不再可當作已確認 X，明確品牌 override、保存的來源／數值與不受影響 Bay 均維持。GUI Set/Bay adapter 僅決定目前選定的 Set 和提交結果，不能判斷或寫入孔位製造驗證狀態。這是來源狀態移轉，不是新增 NFB CUTTING／DXF 認證。

**2026-10-31 核准的全域決策**：WHD 專案的 GUI 只是使用者操作、輸入、表單格式檢查、選取、呼叫與結果顯示。所有與製造相關的規則、正確性、箱型策略、板件拓樸與身份、孔／折／截角／避讓、加工資料、DXF、2D/3D canonical geometry 的唯一實作與權威都在 `ae_engine`，並經公開 API 提供。GUI 可把明確輸入轉成 DTO/PartSpec，但**DTO 組裝絕不能夾帶機械演算**。

```text
GUI（operator input / action / presentation）
  → Engine request + public API
  → Family + Topology + ManufacturingPolicy + Certified Registry
  → authoritative FinalScene + physical parts + 2D/3D/DXF + Save→Reload
  → Engine response → GUI presentation
```

全箱型、全實體板件、所有孔型、數量／套／連／Bay、3D 預覽、製造匯出、編輯與儲存都適用；**這不代表所有相關 API 已完成或已驗證製造**。GUI 禁止複製折彎／展開／CUTTING／BLIND_HOLE／MARKING／offset 計算、決定製造板件、低層 `ae.export_*` 與直接 DXF 序列化。Engine 禁止反向 import GUI/Tk 或依賴 GUI widget／renderer 才能產生正確幾何。

Python 公開 seam 以 `ae_engine.contracts`、`ae_engine.manufacturing_api` 和 `ae_engine.__init__` 的正式 export 為準；**外部 CADSplit 目前沒有可用的已驗證製造 API seam**。`integration_cli/cadsplit_worker.py` 的 `capabilities/prepare/export` 與 versioned schema **僅保留 source-only JSON/CLI 通訊相容介面**：`capabilities` 的製造能力全部 false，公開 `prepare/export` 驗證協定後仍回 `WHD_OPERATION_NOT_IMPLEMENTED`、`manufacturing_verified=false`，不產生 DXF；不可把 wire 命令存在誤稱為已授權製造接線。CADSplit 內的 `ae_engine` 是 WHD Engine 程式副本，不具有獨立製造權威，也不代表已連上 WHD 的外部 API。未來外部 consumer 必須消費 WHD Engine 正式公開 API，並以真實 capability、schema、來源與端到端製造驗收確認；若重新採用安裝版 Worker／EXE，另須遵守第 10 節的明確使用者決策。功能缺席時**先補 Engine API、schema、capability 宣告與契約測試**，否則回傳 unsupported；GUI 與 CADSplit 均不得以 fallback／Preview／自製公式假裝支援。能力表只反映實際驗證、信任與授權，不由 UI 清單代替。

驗收同時驗 request → Engine API → result → GUI／Save→Reload／2D／3D／DXF，且每類箱型、板件、操作都必須以真實來源及 fail-closed 能力宣告證實。CI `tools/gui_engine_api_boundary_gate.py` 與 `.github/workflows/whd-gui-engine-api-boundary.yml` 阻擋可偵測的 PR **新增**越界程式碼；歷史技術債並非已經消失，須逐步搬回 Engine。靜態檢查不足以代替 domain 測試與 required branch check。


### 2. Current manufacturing data flow

```text
operator / project canonical state
        ↓
Cabinet Family + physical-part Topology
        ↓
canonical parameters / Fold / Assembly Intent
        ↓
ManufacturingPolicy + ManufacturingContext / PartSpec
        ↓
Certified Registry lookup / family policy resolution
        ↓
resolved canonical manufacturing answer
        ↓
Final Material + BEND + features + stable physical-part output
        ↓
2D / single-part 3D / assembly 3D / DXF / Save→Reload
```

硬規則：

- 2D、3D、DXF、Save→Reload 不得各自重算第二份製造幾何。
- Cabinet Family 決定 family-specific policy；Topology 決定實體板件與折法。兩者不能互相冒充。
- physical-part identity、Fold、feature、relief 與 persistence 必須沿 authoritative manufacturing state 傳遞，不能由 UI label / renderer / test expected 反推。
- `canonical parameters` 必須有獨立來源，例如 project state、Family/Topology policy、Certified Registry、authoritative T、approved DXF datum/feature；不得來自單次驗收差值。

### 3. `ae_engine.__init__` current public surface

Current public surface 以 `ae_engine/__init__.py` 實際 export 為準。04 至少必須跟上以下 Registry / manufacturing contract API：

- `ManufacturingPolicy`
- `ManufacturingContext`
- `PartSpec`
- `DoorPartSpec`
- `BoxBodyPartSpec`
- `EndCapPartSpec`
- `BasePlatePartSpec`
- `IndicatorBoxPartSpec`
- `PartExportResult`
- `generate_part`
- `resolve_policy`
- `expected_baseline_path_for`
- `receiving_baseline_source_stamp` — Engine-owned Receiving baseline source witness；GUI 只傳 model/context/多片選擇，DXF 專用片缺來源時不得沿用舊製造快取（此 witness 不等於已驗證 DXF 實體或外部 prepare token）。
- `expected_shared_indicator_baselines` — Engine-only selection of the paired IndicatorBox/SmallDoor source paths；external prepare attests both exact paths/content, no Worker private-Engine source selection; path existence alone never certifies manufacturing.
- `map_door_features_to_unfolded_material` — canonical Engine map of finished-face Door features to unfolded material；Worker Export calls it only for independently attested source-feature vs FinalScene verification, no private compatibility helper or second coordinate formula.
- `door_material_frame_width` / `door_finished_face_size` — authoritative public Engine Family material FW and finished Door face size for the exact typed `DoorPartSpec`. GUI multi-Door hole editor now uses the same canonical spec and API as indicator fit/export instead of calling low-level AE finished-size arithmetic. This is not a new feature geometry or DXF grant (#2517).
- `indicator_small_door_operator_spec` — Engine-only composition of the operator Small Door Factory Policy snapshot, canonical `indicator_small_door_spec`, and immutable `DoorPartSpec`/`ManufacturingContext`. GUI only forwards groups/T/FW/door gaps/optional fold and existing feature list; former GUI policy `replace()` and spec derivation are forbidden. The global IndicatorBox baseline, existing CUTTING/DXF algorithm and manual feature-space semantics remain unchanged (#2517).
- `fold_designer_secondary_scene_rows` — Headless Engine-only projection of existing CUTTING/BLIND_HOLE baseline source primitives to legacy read-only numeric hole rows; GUI supplies no hole formula and skips only structural outline as previously specified.
- `query_fold_designer_baseline_rows` — Engine-owned Vault/Receiving Door/EndCap baseline source query and family material FW; only optional editor reference data, **not** certified DXF manufacturing readiness or an External Worker capability.
- `apply_cabinet_family_endcap_policy` — Engine-owned family-specific EndCap bottom material FW resolution from operator state and authoritative topology. GUI cannot derive physical bottom FW or apply Receiving material offsets. No new manufacturing formula: reuse canonical `ae_engine.cabinet_types.policy.effective_endcap_bottom_fw`.
- `select_quantity_nfb_partial` / `quantity_partial_live_manifests` / `verify_quantity_nfb_inner_door` / `QuantityNfbPartialSelection` — Engine owns per-version NFB source recheck and actual physical Q/partial CHECK; GUI is only an input/selection/display adapter. `receiving_quantity_versions.QuantityModel` is the one version-state owner; `phase6_quantity_model` retains only public-API compatibility.
- `build_box_body_fold_profile` / `box_body_profile_to_fold_segments` — Engine-only BoxBody D-W-D Fold, Family topology, real adjacent-bend outside→material compensation and immutable Fold DTO. Legacy Phase6 Fold Designer and trusted Receiving Worker consume the one Engine implementation; no reverse phase6 import. Custom Fold / EndCap/Joint remaining seams are separate #2517 work.
- `merge_box_body_fold_profile` — Engine owns user-custom BoxBody Fold reconciliation: preserve operator segment topology, refresh authoritative D-W-D/FW material sizes, apply Family-specific outer segment transforms (including Receiving no `zr1`), recompute actual adjacent-BEND outside metadata, reject missing D-W-D core. Phase6 `merge_box_body_profile` is only a thin public API compatibility call; do not regenerate removed custom outer folds.
- `formed_box_body_fw_widths` / `box_body_ui_segment_length_to_material` / `read_box_body_outside_dimensions` / `can_remove_box_body_fold_segment` — Engine owns BoxBody material/outside Fold readback, FW formed witness, actual D-W-D symmetrical core checks and structural removal capability. Phase6 only displays or forwards operator input. Formed FW is an assembly/collision witness, never the physical CUTTING oracle.
- `build_endcap_editor_simple_profile` / `read_endcap_editor_simple_profile` — Engine owns the legacy three-row EndCap top/depth/bottom Fold and scalar readback, reusing the existing canonical adjacent-BEND compensation. Phase6 only forwards. Does not certify separate full Head/Tail X/Y FinalScene.
- `resolve_endcap_xy_outside_dimensions` / `fold_material_segment_outside_length` — authoritative headless Engine readback of EndCap X/Y material Fold into formed outside W/D/FW, preserving the existing Family D-core 2T/3T and actual BEND metadata. Phase6 may show the numbers but must not recalculate manufacturing dimensions. Physical EndCap X/Y source profile *building* and full FinalScene remain separately tracked.
- `endcap_corner_selection_to_raw` / `apply_endcap_box_assembly_type_to_raw_state` — canonical Engine serializes the persisted EndCap CornerType and applies shared box Assembly Intent to Head/Tail typed corners, preserving existing bottom manual selections except explicit reset. Phase6 only forwards JSON input/readback; use existing `ae_engine.corner_type_ui.apply_box_assembly_type` instead of a second GUI manufacturing mutation.
- `corner_policy_from_payload` — Engine owns Fold Designer raw/manual CornerType → canonical FourCornerTypePolicy and Registry-backed known-family fallback. Complete operator corners win, missing custom corners remain unsupported; GUI cannot invent or silently borrow Vault geometry. No new Relief/CUTTING formula.
- `resolve_live_corner_policy` — Engine owns current GUI manual CornerType selection, typed legacy C02 preservation, explicit known-family Registry fallback and custom CROSS defaults; `gui.py::_manual_corner_policy` is only input/adapter and invokes the already Engine-owned EndCap family bottom-FW adjustment for explicit edits. Does not modify any CUTTING formula.
- `ensure_corner_part` / `commit_corner_pair` / `commit_corner_type` / `commit_corner_mode` / `commit_corner_parameters` / `apply_corner_preset` — original manual CornerType state mutations have moved intact to `ae_engine.corner_state_transactions` and return public `CornerStateTransition`; Phase6 Settings functions are only public-API compatibility adapters. No geometry or relief policy duplication (#2517).
- `resolve_family_divider_reliefs` — existing `ae_engine.divider_manufacturing` is the unique Engine owner of Receiving Family Divider ↔ BoxBody Joint construction, physical side-sheet collision source lookup, Registry-certified CROSS relief final material, world/refold verification, certification diagnostics and fail-closed missing side pieces. Uses Engine `build_joint_world_geometry`; Phase6 only public API request adapter (#2517).
- `apply_verified_joint_cut_to_part` / `apply_verified_joint_cut_to_owner` — existing `ae_engine.assembly_collision` owns real Verified Joint CUTTING material difference, canonical FinalScene CUTTING/BEND rebuild, source physical child BoxBody role and exploded preview. Engine uses `dataclasses.replace` for caller-owned AssemblyScenePart DTO without importing GUI, preserving placement/Fold metadata. Phase6 adapters only call public API; bounded solver/Registry must verify the cut before application (#2517).
- `serialize_joint_relief_polygons` / `restore_joint_relief_cut_geometry` — canonical `ae_engine.assembly_collision` owns Explicit Joint verified relief CUTTING exterior-polygons Save→Reload codec. Existing provisional source-proof and real material/UV authority are required before pipeline replay. Phase6 polygon helpers are thin Engine public API adapters, not an independent cut geometry codec (#2517).
- `build_joint_world_geometry` — Engine `ae_engine.assembly_geometry` now owns Joint Solver v2 physical 3D world skins, canonical folded flat UV mapping and multipart physical aggregate. For split BoxBody only real piece keys have `flat_material_by_part`; the assembly-only whole `box_body` contains world triangles, never forged flat UV. Phase6 `build_joint_world_geometry` is a thin public API forwarder; collision/backprojection/Divider use the same Engine assembly geometry and no GUI-owned source (#2517).
- `joint_registry_diagnostic_info` — canonical `ae_engine.assembly_joint` owns BOTTOM WRAP Certified evidence, STANDARD non-delta and other-edge rule/revision/trust/collision diagnostic interpretation. Existing Registry and solver proof are the only source; `phase6_manufacturing_geometry` forwards the public API to GUI/status presentation, no second HIT/MISS manufacturing rule (#2517).
- `resolve_box_body_piece_solver_key` / `side_wrap_target_corners` / `joint_relief_state_item_matches` — canonical Engine `assembly_joint` owns physical multi-piece relief UV mapping, Head/Tail WRAP target identity and persisted provisional source-proof; Phase6 bounded callbacks only forward Engine public API (#2517).
- `expand_box_body_fw_world_mid` / `shift_multistage_terminal_fold_world_mid` / `fit_receiving_left_zl1_world_mid` — Engine `ae_engine.assembly_geometry_folded_mesh` owns side-sheet D-core physical outer-skin offsets, terminal multistage formed-tangent projection and Receiving left zl1 formed outside 3D skin, consumed by canonical world-space collision/UV mapping. GUI Phase6 is compatibility forwarder, never second skin/formula oracle; material CUTTING remains unchanged (#2517).
- `resolve_scene_assembly_placement` / `resolve_legacy_door_cell_scene_placement` — Engine owns physical assembly placement dispatch for Vault legacy Door grid, Receiving topology-derived Door/BasePlate/Divider/InnerDoor and saved legacy divider offsets. GUI `phase6_manufacturing_geometry` only forwards; canonical `ae_engine.assembly_placement.resolve_assembly_placement` remains the single Receiving manufactured coordinate owner. The actual `base_plate:fixing_plate:` weld Z is unsupported and remains standalone instead of fabricated (#2517).
- `box_body_piece_editor_profiles` / `reverse_box_body_fold_traversal` — Engine-owned manufacturing Fold editor readback for real BoxBody physical children: right-side reverse bend ownership, legacy Receiving left-side source inverse and sign metadata. `fold_designer_bridge` only forwards; no GUI manufactured dimension inverse. Existing `BoxBodyStructureRenderData` remains the physical authority, no second geometry (#2517).
- `apply_box_body_structure_numeric` — existing `ae_engine.box_body_structure_state` exclusively owns operator BoxBody 2/3-piece W numeric allocations, join seam, side/back OUTSIDE or MATERIAL rear bend, back width compensation and nonnegative relief. Phase6 Settings numerical edit is only a public API forwarder. Existing certified geometry remains unchanged (#2517).
- `plan_cabinet_family_model_transition` / `FamilyModelPlan` / `FamilyModelTransition` — Engine owns entire Family-model transition of manufacturing state (fresh Vault/Receiving defaults, Receiving first Set/Bay current CSV NFB source, inner-door/door-cell topology resets, canonical Assembly Intent/Joints, EndCap BottomWrap and BoxBody structure preservation). Same-family aliases retain edited state. Phase6 Settings is a compatibility API adapter and the Settings Controller only commits returned state/presentation. Reuse existing Cabinet Family Policy/Receiving CSV/Registry owners; no second formulas (#2517).
- `commit_assembly_intent_state` / `normalize_assembly_type` / `AssemblyIntentTransition` — canonical Engine assembly-intent transaction in `ae_engine.assembly_intent_transactions` combines Registry intent validation, Engine-owned joint graph state/temporary part context, legacy EndCap CornerType projection and persisted Save→Reload mirror. Phase6 Settings `assembly_intent` and `normalize_assembly_type` are compatibility adapters only; no GUI business rule. `WRAP_OVERLAY` bottom remains an actual Joint WRAP, never a mirrored top CornerType (#2517).
- `legacy_endcap_corner_projection_for_intent` — Engine-validated `WRAP_OVERLAY` → `OVERLAY` applies only to legacy Head/Tail CornerType mirror; canonical BOTTOM WRAP remains Assembly Joint Graph. Reuse Engine owner for raw CornerType serialization/assembly-state mutation (#2545); GUI/Phase6 only forwards.
- `commit_box_fw` / `commit_endcap_fw` / `set_endcap_fw_follow` / `set_endcap_fw_override` — Head/Tail canonical FW write side joins Engine-owned `normalize_endcap_fw_state` / `resolve_endcap_fw` read side. Engine owns FOLLOW_BODY→FOLLOW_HEAD/TAIL→INDEPENDENT and explicit box FW reset, including legacy saved states. Phase6 only sends operator edits and displays the public Engine result; the manufacturing fold builder remains the sole material owner.
- `normalize_endcap_bottom_wrap_state` / `resolve_endcap_bottom_wrap` / `commit_endcap_bottom_wrap` / `commit_endcap_bottom_wrap_joint` — Engine owns saved Head/Tail lower WRAP link/leader/split state, Receiving Family defaults, explicit adjustable reserves and canonical BOTTOM AssemblyJoint graph priority. GUI Phase6 only forwards operator edits/readback; do not treat legacy enabled mirrors as production Joint authority or export capability.
- `endcap_editor_fold_tabs` / `normalize_endcap_profile_order` — Engine owns legacy Head/Tail Fold editor supported axes and tail-native canonical Y BEND/order rehydration on Save→Reload; GUI/Phase6 only delegates and preserves custom profiles, original material lengths and unrelated metadata. This does not grant new DXF capabilities.
- `build_endcap_xy_fold_profiles` / `resolve_endcap_fw` / `normalize_endcap_fw_state` / `resolve_endcap_assembly_type` — Engine owns all Head/Tail X/Y Fold source roles, Family 2T/3T, FW material/outside and FOLLOW_BODY/FOLLOW_HEAD/FOLLOW_TAIL/INDEPENDENT plus persisted/legacy Assembly Intent. Existing Phase6 Fold and EndCap state helpers only delegate via public APIs; no GUI formula. Actual source DXF FinalScene and certified corner/relief remain canonical in their existing Engine owners.
- `endcap_profiles_for_assembly` — Engine owns GUI-to-Head/Tail request-time assembly Fold reconciliation. OVERLAY must use the Engine-built flat physical X (no left/right BEND), restoring INSERT from formerly-flat X rebuilds canonical Family X while preserving the operator Y; missing stored profiles retain legacy `None` except OVERLAY. GUI is only a public API adapter; Registry and CUTTING formulas unchanged (#2517).
- `build_linked_endcap_xy_fold_profiles` / `is_canonical_box_body_mating_profile` / `box_body_front_mating_fold_chain` — Engine owns arbitrary BoxBody to Head/Tail linked Fold. Canonical D-W-D validation, original operator angles, FW budget, and tail-native reverse Y are preserved for five/twenty or other segment counts. GUI/Phase6 only passes the source data and consumes public API. No second DXF/relief authority.
- `resolve_box_body_back_panel_contract` — 公開 Engine Family API 專責受電箱三片結構背板寬度補償、角落相依高度及 FULL/BACK_OPENING 製造 contract；Worker 僅傳原始外尺寸、來源 Fold 輸入與已驗證 mode/state，禁止在 Worker 重算。既有 Fold profile adapter 仍須後續從 phase6 遷入純 Engine，不可反向 import phase6 假裝完成。
- `box_body_structure_state` / `set_side_back_back_panel_mode` / `back_panel_mode` — canonical Engine-owned BoxBody structure state and Receive rear FULL/HALF/BACK_OPENING persistence. `phase6_box_body_structure` is a re-export compatibility shim, never a second structure policy. Worker back panel resolves its signed mode via public Engine API; `ae_engine.box_body_structure`/`box_body_structure_core` no longer reverse-import Phase6 and use Engine BEND compensation.
- `resolve_receiving_box_body_structure_state` — public Engine Family API for Receiving's immutable side/back state (fresh OUTSIDE rear bend, legacy MATERIAL compatibility, back W−2.5T and default FULL). Worker left/right side consumes this canonical state instead of private Cabinet Family imports. `ae_engine.cabinet_types.receiving` no longer imports Phase6.
- `expected_endcap_feature_baseline` — Family-aware EndCap 固定孔基準檔路徑選擇；受電箱透過 Engine policy 指向金庫型共用固定孔基準，不改受電箱 D−2T 或 Head/Tail FinalScene。Worker 僅負責來源檔案位元組／Frame／交易驗證，Expected Path 本身不是製造認證。
- `CabinetTypeRegistration`
- `registered_cabinet_types`
- `resolve_cabinet_type`
- `CertifiedReliefStatus`
- `CertifiedReliefRule`
- `CertifiedReliefResult`
- `CertifiedCornerPolicyRule`
- `CertifiedReliefRegistryError`
- `CertifiedReliefRegistryAmbiguityError`
- `registered_certified_relief_rules`
- `registered_certified_corner_policy_rules`
- `lookup_certified_endcap_relief`
- `lookup_certified_corner_state`
- `certified_corner_policy_for_part`
- `certified_rule_revision_exists`
- `build_relief_promotion_candidate`

若 public export 改變，應同步更新本 CURRENT contract 與永久 guard；不得讓文件繼續描述不存在的舊 API。

### 4. Certified Registry 是已知 Relief 的 production authority

#### 4.1 Registry HIT

**Registry HIT = canonical manufacturing answer。**

當 `CertifiedReliefRule` / `CertifiedCornerPolicyRule` 命中，production 使用該 rule 的 formula、preconditions、`rule_id`、`revision`、`trust_level`、`standard_ref`、`dimension_space`、target semantics 與 canonical parameters 產生製造結果。

對 Registry HIT：

- 3D collision / backprojection 只能做 **3D shadow validation**；
- shadow result 可以指出 conflict，但**不得覆蓋**已認證答案；
- current code 不得另寫第二套相同 Corner/Relief 公式；
- fallback 開關不得跳過 Certified lookup。

#### 4.2 Registry MISS

只有 **Registry MISS** 才可進未知 geometry 的 3D `discovery` / candidate flow。

MISS 不代表「任意量 collision bbox 就直接製造」。candidate 必須保持可追溯來源，並經正式 promotion / regression / human-approved authority 後才能成為 Certified rule。

`PROVISIONAL_3D` 不是 Certified production truth；只有符合 registry promotion contract 的結果才可能進 `CERTIFIED_FROM_3D` 或其他正式 Certified 狀態。

#### 4.3 Ambiguity / conflict

多條同等優先規則競爭時必須回報 `REGISTRY_AMBIGUOUS` / `CertifiedReliefRegistryAmbiguityError` 並 **fail closed**；禁止靠 list order、第一筆 match、UI 順序或舊 cache 猜答案。

Registry / engine conflict 同樣只能阻擋或診斷，不能偷偷採用 validation output 當新的 production formula。

### 5. Registry record / canonical parameter contract

Current Certified record 至少要保持可解釋的製造 provenance，包括：

- `rule_id`
- `revision`
- `trust_level`
- Cabinet Family scope / part role / joint face / Assembly Intent 或 Corner domain
- Topology / preconditions
- formula / canonical parameters
- `standard_ref`
- `dimension_space`
- target semantics / adjustment type
- certification evidence
- geometry inputs

Fixture 的固定輸出可以出現在 certification evidence；它不能取代 formula / parameter provenance。

Receiving Divider 的 current 例子是既有 `CornerType=CROSS + 參數`；Registry HIT 後 3D 只做 shadow/penetration verification。不得因 schema 不方便另造 Divider CornerType 或偷換成 INSERT_OVERLAY。

### 6. Validation is one-way

**Validation is one-way：validation 可以判定 production 對不對，但不得回灌 production。**

下列全部只屬 validation evidence：

- pytest `expected value`
- fixture output / golden result
- collision / solver `probe`
- screenshot / rendered number
- bbox / measured delta
- assertion `tolerance` / epsilon / boolean fringe
- PASS / FAIL log

硬規則：

- expected value、fixture、probe、tolerance **不得回灌 production** formula、offset、compensation、branch selection 或 placement。
- 若 actual=A、expected=B，禁止把 `B-A` 寫成 magic compensation；必須回查 requirement → Family/Topology → canonical parameters → Registry / manufacturing derivation。
- tests、fixtures、QA artifact 不得被 production import/read 來決定製造答案。
- 只有具獨立 authoritative provenance 並正式進 canonical spec/state/Registry 的數值，production 才能使用。

### 7. 3D / collision 的 current role

3D 仍然重要，但角色必須依 HIT/MISS 分流：

- Registry HIT：3D = shadow validation / penetration check / conflict evidence。
- Registry MISS：3D 可以參與 discovery，產生 candidate，但 candidate 不是 Certified truth。
- promotion 後：runtime 回到 Registry formula；不得每次重新用 3D 發明已知答案。
- visibility / renderer 只影響顯示，不得改 mechanical authority 或 collision datum source。

因此「先碰撞、再決定所有正式 CUTTING」不是現行全域通則；它只可能是未知 geometry discovery 的一段流程。

### 8. Current references

修改 ae_engine / Registry / Corner / Relief 前，至少交叉讀：

- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`

Preflight / test evidence 只能證明這些 authority 被遵守，不能反過來成為製造公式來源。

### 9. Joint Placement MARKING ownership contract

Joint Placement MARKING 的 production authority 必須沿 physical mating-region/contact ownership 傳遞，不得由 renderer、UI、fixture 或量測差值反推。Inner Door Frame 的接合端由 authoritative `LOWER_TERMINAL_FACE` 提供 mating-region；Receiving 的 shared horizontal Divider 以 `CORE_PHYSICAL_SEGMENT` physical skin 作接觸面。合法接觸使用 contact-local boundary frame 與 locator-only backprojection；工程 coplanar tolerance 屬幾何判定 authority，不得為了 fixture 通過而放寬。

Joint marking policy/diagnostics 由 engine registry/orchestration 擁有；production activation 的 accepted disposition 是 `ALLOW_EXPORT_WITH_DIAGNOSTIC`。Gate A 可保留 dormant foundation，但 Receiving Gate B 只有在 product disposition 已解決後才能啟用。2D、3D、DXF 與 Save→Reload 必須消費同一份 enriched manufacturing geometry/result，不得各自建立第二套 marking 幾何或 placement 規則。

Validation 維持單向：contact probe、collision、fixture expected、pytest tolerance、rendered result 與 QA artifact 只能驗證上述 authority，不得成為 production formula、offset、placement 或 marking policy 的來源。


### 10. CADSplit × WHD source-only Worker boundary（installed Worker/EXE retired）

2026-11-01 使用者決策：**安裝版 WHD Worker／WHD-Engine.exe 接線退役**。這項退役不改變 WHD Engine 對製造、實體板件、幾何、2D/3D/DXF 與 Save→Reload 的唯一權威，也不降低 GUI → Engine API 硬閘門。

- `integration_cli/cadsplit_worker.py` 與 `integration_cli/schemas/` 只保留 source-only wire boundary；公開命令仍只有 `capabilities/prepare/export`，沒有 `verify`。
- source-only `capabilities` 的製造能力全部 false；公開 `prepare/export` 必須回 `WHD_OPERATION_NOT_IMPLEMENTED`、`manufacturing_verified=false`，不得寫 DXF。
- **不存在安裝版 admission**：不得由 `installation_id`、DPAPI/HMAC、installer source/output custody、packaged manifest 或 frozen EXE 啟用製造；`--installation-id` 與 `_private_installed` 均不是合法 CLI。
- **不存在安裝版 public certification owner**：舊 `private_worker_installation.py`、`public_installed_adapter.py`、`worker_key_custody.py`、`packaged_identity.py` 與 private Windows Engine EXE workflow 已退役，不得從 Git history 默默恢復。
- W-03/W-04/W-06 的純 Python helper／transaction／source-verification 基礎可作內部測試或未來 Engine API consumer 的實作材料，但它們不由 `cadsplit_worker.main()` 對外接線，也不能宣稱 Gate A／外部製造已放行。
- 若未來重新需要 CADSplit 外部 executable/installer，必須有新的明確使用者決策與 CURRENT owner，且只能消費同一 WHD Engine 公開 API；不得復活第二套 Worker 製造 authority。


---

## [HISTORICAL/SUPERSEDED] Legacy ae_engine notes

> **以下內容只保留歷史 provenance，不可作 CURRENT routing / runtime oracle。** 2026-09-13 起，若本區與上方 CURRENT contract、AI 07 或 Certified Registry 衝突，一律以上方 CURRENT authority chain 為準。

### Historical local workspace locator

早期文件曾以本機路徑定位程式：

- `Z:\Ollama-整合whd\ae_engine\`
- `Z:\whd-corner-new-engine-implemented\`

這些只代表當時開發機 workspace，已 **SUPERSEDED**；current locator 是 repo-relative `ae_engine/`。

### Historical Layer A / B / C 架構描述

早期曾把系統簡化成：

```text
Layer A = 純 2D Geometry
Layer B = 舊 ae / DXF 轉接
Layer C = GUI / 拆圖
```

並以 `sheetmetal_geometry.py → ae.py → gui.py` 類型的三層鏈作主要 current architecture。這段在 Family、physical topology、Manufacturing API、Certified Registry、AssemblyJoint、shared 2D/3D manufacturing state 成形前有歷史價值，但已不足以描述現行系統，故不得繼續作 current architecture authority。

### Historical collision-first relief direction

早期 04 曾把 BoxBody / EndCap assembly relief 固化成：

> **先形成名義板件與折後實體，再由實際干涉反推 2D CUTTING**。

當時流程大意是：nominal part → collision region → ownership → 3D/2.5D backprojection → relief candidate → CUTTING → replay。

這段對「未知 geometry discovery」仍有歷史背景價值，但作為**全域 production rule 已 SUPERSEDED**：

- Registry HIT 時 Certified formula 已是 canonical manufacturing answer；3D 只能 shadow validate，不得覆寫。
- Registry MISS 才允許 discovery/candidate。
- candidate / measured collision result 不會因驗證通過自動升格成 Certified formula。

### Historical fixed-model / CornerType sediment

舊 04 曾逐次追加 C01/C02/C03/C04、INSERT/OVERLAY/INSERT_OVERLAY、WRAP、UI lock/unlock、assembly scene、placement、collision 等大量階段性規則。這些段落的單次數值或當時 UI 結構都只應視為歷史演進證據。

Current 製造語意應回到：

- AI 07 的尺寸語意 / STANDARD / semantic delta；
- current Cabinet Family + Topology；
- Certified Registry 的 active rule / revision / canonical parameters；
- current production API；
- validation one-way boundary。

不得因舊文件曾記錄某個 fixture、probe 或碰撞量測，就把該數字重新寫回 current production。

<!-- WHD_PHASE7_OWNERSHIP_WRITEBACK_V1 -->
## Phase 7 — manufacturing owner consolidation

Phase 7 對大型 manufacturing modules 做 owner deepening；CURRENT 規則是「public/compatibility facade 薄化，solver / serialization / request / render / export 各回唯一 deep owner」，不改變本文件既有 Registry / Family / Topology / validation-one-way authority。

### P7-C — `ae_engine/ae.py`

- `ae_engine/ae.py`：legacy/public compatibility facade。
- DXF serialization：`ae_engine/dxf_serialization.py`。
- baseline source/cache/resource：`ae_engine/baseline_source.py` + `ae_engine/baseline_resources.py`。
- baseline-to-scene adapter：`ae_engine/baseline_scene_adapters.py`。

### P7-D — `manufacturing_api.py`

- `ae_engine/manufacturing_api.py`：thin public facade。
- verification owner：`ae_engine/manufacturing_verification.py`。
- export / naming / physical-part sink owner：`ae_engine/manufacturing_export.py`。
- resolved request / precedence owner：`ae_engine/manufacturing_requests.py`。
- render-data orchestration owner：`ae_engine/manufacturing_render.py`。

Public facade 可以 re-export / delegate，但不得重新持有第二份 verification、request precedence、export naming 或 render orchestration implementation。

### P7-E — collision / relief solvers

- `ae_engine/assembly_collision.py`：thin shared collision/backprojection compatibility facade。
- generic collision/backprojection owner：`ae_engine/collision_backprojection.py`。
- Divider relief solver owner：`ae_engine/divider_relief_solver.py`。
- EndCap world-relief solver owner：`ae_engine/endcap_world_relief_solver.py`。

上述 solver separation 不改變 Registry HIT/MISS 規則：Certified Registry HIT 仍是 production answer；collision/backprojection 對 HIT 仍只是 shadow validation，不得回灌 formula。

### P7-F — explicit-joint pipeline

- `phase6_manufacturing_geometry.py::_phase6_resolve_explicit_joint_reliefs`：thin compatibility/manufacturing facade。
- bounded explicit-joint orchestration owner：`phase6_explicit_joint_pipeline.py`。
- canonical collision/backprojection solver truth：`ae_engine.assembly_collision` 及其 Phase 7 deep owners。
- canonical world/cut geometry helpers 仍由 `phase6_manufacturing_geometry.py` 擁有，透過 bounded `ExplicitJointPipelineOps` 注入；pipeline 不得複製 geometry formula。

永久 invariant：facade forwarding 不建立第二份 production path；reverse import、duplicate owner、第二 composition root、validation→production backflow 都必須保持 0。

Accepted provenance：Phase 7 #618/#620/#621/#623 與 Combined Acceptance #626；combined regression run `36277114074` GREEN @ `77429fa487166e0598c2f00e4d5ff1fa2d837219`。

### Receiving V1.6 — accepted Set/Bay/Joint / pairing-mark contract (#1116)

以下為 Receiving multi-set/multi-bay V1.6 在 #1111～#1116 完成後的 CURRENT manufacturing invariants；它們屬本文件既有 manufacturing-architecture authority 的 Receiving 子契約，不建立第二份 authority：

- **Set/Bay/Joint identity**：Receiving v2 只持久化 authoritative Set/Bay/Joint state 與 stable IDs；legacy v1 aliases 僅供 migration / transient compatibility，不得重新成為 v2 persisted authority。
- **Joint scope**：Joint 僅存在於同一 Set 的相鄰 Bay；2×2 等 multi-Set layout 不得產生 cross-set Joint。
- **Direction contract（R-029，owner-approved）**：FRONT=`+Z`、REAR=`-Z`、LEFT=`-X`、RIGHT=`+X`；Joint local `u` 固定 FRONT→REAR，`v` 固定 BOTTOM→TOP。程式／測試若與此衝突，視為 implementation/test bug，不得自行改寫方向語意。
- **Joint alignment**：FRONT/REAR × BOTTOM/TOP 四種 alignment 都必須讓 mating lock holes 在 world space 重合；不同 Bay D/H 只影響合法 alignment offset，不得產生第二套 lock-coordinate generator。
- **Pairing MARKING ownership**：每個 Bay pairing mark 只落在該 Bay 的 `box_body:left_side`，○ 表示右側有 Joint lock，X 表示右側無 Joint lock；每個 Set 重新計算自己的 ○/X，不跨 Set 串接。
- **Pairing placement**：標記位置先由 formed left-side authoritative main-face geometry 決定，再經同一份 formed/world→flat backprojection 寫入 DXF；export 不得額外 mirror / rotate，也不得把 renderer/UI 座標升格成 manufacturing datum。
- **OPEN-02（owner-approved）**：`PAIRING_SYMBOL_INSET = 5.0 mm` 為正式 release 值。它是 authoritative 50×50 pairing-symbol region 的內縮量，因此 ○/X 的 `symbol_size = 40.0 mm`；**不是** DXF 板外框／零件外緣 5 mm offset。
- **Back-panel variants**：FULL 使用固定 50×100 frame；HALF 只使用 TOP 50×50；BACK_OPENING 使用固定 50×100 frame，並在 BOTTOM 50×50 區域置中固定 30×20 horizontal glyph。不得因空間不足自動縮放或裁切。
- **Bounds / conflict**：pairing geometry 必須同時落在 formed authoritative face 與 Final Material 內；與同件 CUTTING / BLIND_HOLE / MARKING 的 zero-clearance touching / endpoint contact 都視為 conflict，fail closed。
- **Manufacturing readiness / export**：Receiving requested Set / project batch export 以 canonical resolved manufacturing geometry 為唯一來源；blocked Bay/Joint 的 invalidity 依 R-028 做 bounded propagation，不得意外 chain 到不相干 Bay/Set。multi-instance physical DXF 檔名必須帶 stable Set/Bay namespace，禁止 collision / overwrite；batch 驗收以重新開啟 DXF 後 CUTTING / BLIND_HOLE / MARKING inventory 與 canonical PartRenderData 一致為準。
- **Validation one-way**：1×1、1×2、1×4、2×2、mixed W/H/D、mixed FULL/HALF/BACK_OPENING、Save→Reload、DXF reopen 與 regression 都是 acceptance evidence；它們驗證上述 authority，但不得反向創造新產品規格或 offset。

Durable signoff provenance：#1116 owner signoff 記錄 R-029 與 OPEN-02；OPEN-02 implementation finalization 由 PR #1167 merge 至 `cleanup/2d-3d-sync`。後續若要改方向、5 mm inset、pairing ownership 或 Joint scope，必須以新的 product-owner decision 更新本 CURRENT authority，不能只改 code/test。


### #2383 Vault standalone BasePlate Worker route (2026-10-31)

Installed `integration_cli` v1.1 now routes `金庫型/base_plate` through the existing
`BasePlatePartSpec → build_part_render_data → FinalScene → save_verified_final_scene_batch_dxf`
with HMAC-bound exact-job preparation and original-source empty-modelspace verification.
Source `part_formed_outer` dimensions and all four shrink values plus bend are explicit;
no default assembly relationship is fabricated. There is no dedicated BasePlate baseline;
its verified code, Registry, policy and canonical material are the source. The signed
Frame denotes only the unfolded Final Material envelope and prohibits external Features.
This scope does **not** enable Receiving pattern, Joint, cross relief, original-source
hole mapping, box-body assembly or any other blocked W-08 feature.

### #2383 Vault/Receiving standalone custom Fold Worker route (2026-10-31)

Independent `金庫型/custom_fold` and `受電箱/custom_fold` manufacturing must
consume the explicit source physical `custom:<positive integer>` ID, one X/Y
fold axis, transverse material span and every material Fold Profile segment
(length, angle and optional formed outside length) through WHD's
`CustomFoldPartSpec` and `ae_engine/custom_fold_manufacturing.py`. That owner
alone resolves real CUTTING/BEND and Final Material, then the already guarded
Worker W-03/04/06 Save→Reload path exports independently verified DXF.

A size-only signed Frame attests unfolded material bounds, never an assembly
placement, original CADSplit source-to-DXF feature mapping or a second fold
formula. Original CADSplit DXF must be empty for the feature-disabled export.
No implicit preset, material conversion, 3D joint, corner relief or original
feature transfer may be guessed. Other family roles stay closed until their
own exact Gate C manufacturing authority exists.

### #2383 Vault integral BoxBody W-08 source-controlled API (2026-10-31)

`金庫型/box_body` accepts one integrated physical sheet only. Its independent
W/H/D/T, FW, zl1/zl2/zr1/zr2/z_comp inputs are all signed at W-03; the WHD
Phase6 canonical D-W-D source performs Fold outside/material conversion.
Existing Vault `箱身.dxf`, certified Registry and AE `BoxBodyPartSpec`
are the sole geometry authority, with canonical CUTTING/BEND FinalScene,
trusted HMAC, original empty-source check and DXF Save→Reload. The advertised
Frame is a size-only unfolded blank; source-feature mapping, independent
multi-piece bodies, Receiving family assembly, collision/Joint and manual
external Fold profiles remain blocked pending their own physical Gate C.

### #2383 Receiving physical inner-door panel signed Worker API (2026-10-31)

The `受電箱/inner_door` external Worker manufacturing entry applies only to
one source-confirmed physical `inner_door:<id>:panel`, with stable source
`inner_door_id`, `inner_door_cell_key` and formed W/H/T. The existing
`ae_engine.inner_door_panels.derive_inner_door_panel` and
`ae_engine.manufacturing_scene_orchestration.build_inner_door_panel_render_data`
are the *only* owner of material Fold, factory 19-mm flanges, corner CUTTING,
BEND and stable physical identity. This signed size-only Frame supports an
empty original CADSplit DXF only; it makes no claim for NFB holes, side or
upper frames, Divider, joinery, mounting screws or full installation assembly.
Original external entities, unverified coordinates or alternate Fold params
fail closed; exact W-03/04 HMAC recheck, registry identity and verified DXF
Save→Reload remain mandatory. The owner of the inner-door frame set is unchanged.

### #2383 Receiving physical Side Panel signed manufacturing route (2026-10-31)

`受電箱/side_panel` chooses only one physical side source ID
`box_body:left_side` / `box_body:right_side`. The existing Receiving
`build_box_body_profile` eight-segment Receiving outside→material owner, fixed three-piece
`resolve_box_body_structure_state`, `resolve_back_panel_contract` and
`build_box_body_structure_render_data` alone own geometry/stock/bends and
baseline CUTTING/BLIND_HOLE/MARKING. All three dedicated source files
`左側板.dxf`, `右側板.dxf`, `後面板.dxf` are WHD-signed resources for this
single-part route; Vault integral BoxBody cannot act as a reference substitute.
No CADSplit external Feature transform, untrusted original DXF entities,
assembly/world Joint or unrelated multipart output is certified; preserve
original source SHA and W-03/04/06 exact-job verification and DXF Save→Reload.


### W-08 Receiving rear sheet installed Worker scope

`受電箱/back_panel` only admits `box_body:back`, source-confirmed FULL or
BACK_OPENING and exact source factory dimensions. The authoritative
`receiving.resolve_back_panel_contract` plus `receiving_piece_baseline_features`
against verified `後面板.dxf` produce the actual flat CUTTING with four
keyslots and optional source-derived 650x200 rear opening. The signed source
snapshot attests all three Receiving side/back DXFs; no virtual assembly,
manual hole transfer or spurious BEND is allowed. HALF cannot be released
until its persisted two-section Door topology is independently bound.


### W-08 Receiving independent head/tail Worker authority

`受電箱/end_cap_head` and `受電箱/end_cap_tail` expose two separately
signed physical-sheet routes. Source W/H/D/T/FW, yl1/yr1/ytop1/ybottom1 and
rear Fold value are explicit. `build_endcap_xy_profiles` determines real
head/tail orientation and flat Fold material; Receiving `D-2T` and family
`endcap_corner_policy` determine physical corner CUTTING. The canonical
Receiving policy maps *only baseline fixed Ø6.4 holes* to existing
`基準檔/金庫型/封頭尾.dxf`; it does not import Vault D-3T. HMAC-signed
W-03/04/06, source-empty verification, exact reference bytes and actual
CUTTING/BEND Save→Reload remain mandatory. No assembled WRAP/Joint, external
CADSplit Feature transform or other uncertified physical roles are released.


### #2383 Receiving physical inner-door A/B/D frame Worker extension (2026-10-31)

For an independently source-confirmed inner-door ID and exact frame side
LEFT/RIGHT/TOP plus span/T, `inner_door_frames.derive_inner_door_frames`
owns the signed physical Fold Chain. `receiving_frame_baseline` owns the true
A/B/D source CUTTING and D's two holes in `基準檔/受電箱/框.dxf`;
`build_inner_door_frame_render_data` consumes **the installed resource-root
baseline** for W-03/W-04, not an unsealed repository fallback. W-03 HMAC
binds exact material, frame side and baseline digest; W-04 verifies the
same FinalScene and DXF Save→Reload. The existing single panel remains
supported. Source DXF Feature transforms, C-divider, unsourced bottom frame,
NFB, physical assembly and joint marking are *not* authorized by this
frame-only route.


### #2517 EndCap live Fold dimension synchronization (2026-11-01)

- `endcap_derived_core_lengths` and `reconcile_endcap_live_outside_dimensions` are Engine public API owners of the existing EndCap 4T W / Family 2T–3T D material/outside live editor reconciliation.
- The Tk bridge only forwards operator top W/D, prior W/D and material Fold rows and applies returned dimensions. These methods do not grant new manufactured DXF capability, nor close #2517.


### #2517 Finished-face feature preview projection (2026-11-01)

- `project_finished_features_to_legacy_renderer_holes` is the Engine public owner of Circle/Rect finished-face hole positioning and integer legacy Fold Renderer display rows, consuming the existing `feature_finished_point` authority.
- The former GUI `project_features_to_original_holes` now forwards request→Engine→result only. Profile/custom features remain independent; a preview DTO never authorizes cutting/DXF and does not close #2517.


### #2517 Settings finished part dimensions to Engine (2026-11-01)

- `project_part_dimensions`, `door_part_projections` and `DoorPartProjection` now belong to public `ae_engine.manufacturing_api`; Family Door FW, Door-cell finished sizes, Receiving BasePlate physical blank and persisted dimension reconciliation are computed from existing canonical Engine sources.
- `phase6_settings_profile_projection` retains the existing Settings freeze/plan/presentation contract but re-exports the Engine API only; it does not implement second Door/BasePlate size formulas. This is one #2517 slice, not a declaration of complete manufacturing/DXF capability.


### #2517 Standard Door/BasePlate/Indicator Fold profiles (2026-11-01)

- Engine public `build_standard_part_fold_profiles` now owns existing Door, BasePlate, IndicatorBox/IndicatorDoor and standard fallback X/Y material segment construction, including topology-based `ui_len_add`, Family receiving physical BasePlate precedence and finished-size consumption.
- Settings/GUI `build_standard_part_profiles` forwards standard part identities only; existing `custom:` keys retain the separate Phase6 custom extension until its own Engine API migration. Standard API rejects custom IDs, never silently substitutes generic material.


### #2517 Keyed Fold reconciliation Engine API (2026-11-01)

- `merge_keyed_fold_profiles` publicly owns Settings' reconciliation of newly computed Engine material `len`, bend `ui_len_add` and core metadata with operator-added Fold rows, per X/Y axis. The GUI Settings planner only delegates and presents the resulting detached profiles. Missing canonical keys fail closed to the complete Engine default axis, never guessed material lengths.
- This migration does not change Family material geometry, Certified Registry, Custom Fold ownership, independent manufacturing DXF gates, or the open #2517 acceptance status.


### #2517 Derived physical part ID classification (2026-11-01)

- Engine public `is_box_body_physical_piece_key` and `is_derived_physical_part_key` now own the existing physical-child identity distinctions. Phase6 navigation and Settings are display/planning adapters, not independent manufacturing physical-ID authorities.
- This does not allocate IDs or certify Save→Reload, 2D/3D/DXF manufacturing support.


### #2517 EndCap relief production commit policy (2026-11-01)

- `endcap_relief_solution_committable` is the public Engine authority for existing verified/certified Head/Tail relief commit acceptability. Phase6 manufacturing service consumes the API result; GUI/Phase6 must not decide certified/trust precedence itself.
- The certified-formula versus 3D shadow conflict distinction is preserved. This is not a new rule registration, uncertified DXF grant, or full #2517 completion.


### #2517 Door-layout Indicator Box/Small Door editor ownership (2026-11-01)

- `gui.py::open_door_indicator_component_editor` now delegates physical box/small-door editor surfaces, CUTTING/DATUM/BEND source scene, finished-face guides and widths/heights to existing public `manufacturing_api.resolve_indicator_editor_components(groups, thickness, door_spec)`, using the same `_indicator_door_part_spec` already consumed by Phase6. GUI retains operator mode/group selection, feature-store identity, baseline-status display and commit callbacks.
- The global IndicatorBox source `基準檔/指示燈/盒子.dxf` remains authoritative; the historic `model_name` argument to `baseline_scene_adapters.get_stretched_indicator_box_data` is explicitly ignored. No new CUTTING formula, worker routing or DXF manufacturing capability is claimed. #2575 cache fingerprint is a separate independently developed slice; #2517 remains OPEN.

### #2517 Manufacturing cache semantic signature Engine API (2026-11-01)

- `manufacturing_state_fingerprint` and `canonical_manufacturing_signature_value` are public Engine owners of pre-scan manufacturing cache dependency policy, replacing Phase6 decisions about Receiving live W/H/D versus Settings seed values, persistence mirrors, UI-only typography, normalized nested Fold state, physical intent, and finite numeric validity.
- Phase6 only extracts operator/workspace data and invokes Engine. Cache equality does **not** certify CUTTING/DXF nor bypass complete geometry/Save→Reload verification; #2517 remains OPEN.

### #2517 Standard Fold Settings readback Engine API (2026-11-01)

- `read_standard_part_fold_profiles` is the public Engine owner of the approved reverse material Fold → operator setting mapping for Door, BasePlate, IndicatorBox/IndicatorDoor, including the four-edge equality rejection and Receiving root BasePlate real physical Fold precedence. Phase6 manufacturing adapter is only a GUI request/response delegate.
- Physical Fold/FinalScene and Certified Registry remain authoritative. A reverse Settings DTO is neither a DXF/CUTTING grant nor permission to fabricate Custom Fold or overwrite Receiving source geometry; #2517 stays OPEN.


### #2517 Live operator finished dimensions source precedence (2026-11-01)

- Public `resolve_live_operator_finished_dimensions` now owns the legacy GUI's sparse snapshot W/H/D fill and Receiving live Bay/Quantity working dimensions-over-seed precedence, while consuming existing canonical `resolve_operator_finished_dimensions` (mesh, Head/Tail Corner policy) without a second manufacturing formula.
- The Phase6 adapter only collects operator input and passes Corner policy DTOs to Engine. No persisted values are rewritten and no unverified DXF capability is granted; #2517 remains OPEN.

### #2517 Custom physical identity and X/Y Fold Engine ownership (2026-11-01)

- Public Engine `CustomPartCatalog`, `is_custom_part`, `custom_part_only_change` own stable nonrecycled custom physical IDs, snapshot comparison and metadata validation. `descriptor_from_snapshot`, `build_custom_part_profiles`, `custom_part_spec` own both X/Y single-axis operator outside 17/100 → material Fold and physical `CustomFoldPartSpec` construction, with original 1T-per-actual-adjacent-BEND contract and transverse flat axis.
- Former `phase6_custom_parts.py` and `phase6_custom_fold_profiles.py` are public Engine API compatibility facades only; neither may independently validate physical metadata or derive manufacturing Fold.
- Preserve fail-closed invalid thickness, missing descriptors, nonmatching transverse span and unverified external Feature handling. This change does not certify 2D/3D/DXF Save→Reload or complete #2517.

### #2517 Receiving Inner Door quantity Apply Engine API (2026-11-01)

- `apply_receiving_inner_door_quantity_configuration(layout, library, quantities, assigned, *, expected_counts=None)` 是跨所有 Receiving Set/Bay 內門版本配置的唯一製造狀態交易入口。Engine `receiving_inner_door_pairing` 先完整檢查 topology／各版本數量／對應、每個候選正式 NFB CSV／CUTTING 單一來源及已提交實體 NFB 覆寫衝突，再原子回傳 detached layout 與受影響 physical Bay stable IDs；未通過不得部分寫入。
- GUI `ReceivingSetBayAdapter.apply_inner_door_quantity_configuration` 現僅轉發操作者配置與更新 UI dirty IDs；不再自己決定已套用版本、物理孔身份、正式 NFB 持久化及多連共享設定交易。既有 `receiving_shared_settings`／`receiving_layout`／`receiving_nfb_csv_committed_config` 是原有 source owner。此 API 沒有新增 CUTTING／DXF 認證，未授權 X 發布；#2517 繼續 OPEN。

### #2517 Receiving Head/Tail quantity Apply Engine API (2026-11-01)

- `apply_receiving_endcap_quantity_configuration(layout, role, library, quantities, assigned, *, expected_counts=None)` 是跨 Receiving Set/Bay 的封頭／封尾候選數量配置公開交易入口。Engine `receiving_quantity_allocation` 先驗證完整拓樸、版本數量、套／連對應與正式版本 ID，再透過現有 `receiving_shared_settings` 對每個真實 Bay 原子寫入 Head/Tail Hole Editor Feature 與已套用版本，回傳 detached layout 及 stable IDs，不修改原輸入或不同角色的候選與加工來源。
- GUI `ReceivingSetBayAdapter.apply_quantity_configuration` 只提交操作者選擇、更新界面 dirty IDs；不得複製候選數量、實體 Bay 設定或 Feature 的製造交易。這不新增 Head/Tail 孔公式、CUTTING／DXF 認證；#2517 仍需其他功能繼續遷移。

### #2517 Receiving Head/Tail highlighted Apply Engine API (2026-11-01)

- `apply_receiving_endcap_candidate_to_bays(layout, role, set_index, bay_indices, features, *, version_id=None)` 是操作者高亮封頭／封尾候選套用的唯一 Engine 實體狀態交易入口。Engine 以正式 `receiving_shared_settings` 對原始 Feature 型別、角色／版本與真實 Set/Bay index 完整檢核，對選中的 Bay 解開共享 refs 並原子更新，回傳 detached layout、排序後 selected index、physical Bay stable IDs；不得更動未選擇的 Bay/Set 或另一種端板角色。
- GUI `ReceivingSetBayAdapter.apply_candidate_to_bays` 僅傳遞使用者高亮選取、提交 Engine 結果及 dirty UI IDs，不能自行套用製造孔位 Feature 或共享來源。這是對已認證製造資料來源的交易移轉，不新增孔位計算／CUTTING／DXF 認證；#2517 保持 OPEN。

### #2517 Receiving Live version provenance Engine API (2026-11-01)

- `mark_receiving_bays_live_version(layout, role, set_index, bay_indices)` 是所有 Receiving Head／Tail／Inner Door 操作者「即時 Apply」版本來源狀態的 Engine 交易入口。按真實 Set/Bay 穩定身分處理高亮的版本欄位，把被選取的共享 ref 單獨 unlink 並保存 `""`（明確即時），不影響其他 Bay 的 `None`（未套用）／已套用版本、其他角色或實際 Hole Editor／NFB 物理來源。非法 role／Set／Bay（bool、越界、unhashable）必須整筆拒絕。
- GUI `ReceivingSetBayAdapter.mark_live_version_for_bays` 現僅轉送操作、呈現與記錄 dirty IDs；其餘製造狀態持久化由 Engine 公開 API 管理。不宣告新的 CUTTING、DXF 或 Registry capability。#2517 繼續 OPEN。

### #2517 Receiving 單一內門候選多 Bay Engine API（2026-11-01）

`manufacturing_api.apply_receiving_inner_door_candidate_to_bays(layout, config, set_index, bay_indices, *, version_id=None)` 是單一候選版套用已高亮 Bay 的公開製造狀態交易，與整批數量配置 API 不同。Engine 用既有 `validate_door_config`、`receiving_shared_settings`、`receiving_nfb_csv_committed_config` 檢驗實體 Bay 選取、CSV NFB source／CUTTING 擁有者，統一提交 detached Layout 並回傳排序 Bay indices 與 stable IDs；GUI 只更新 UI dirty 狀態。非法輸入、source 衝突不部分寫入；X 保持 `UNVERIFIED_BASIS`、既有 Save→Reload 保持、無新 DXF 製造放行。#2517 仍 OPEN。

### #2517 Receiving Bay 批次尺寸／NFB X 證據交易 Engine API（2026-11-01）

公開 `manufacturing_api.apply_receiving_bay_dimensions(layout, set_index, bay_indices, *, width, height, depth, expected_count)` 由 `ae_engine.receiving_layout` 擁有全部多連 W/H/D 正整數／完整選取驗證、門格 `complete_partition` 保留先前操作尺寸、NFB 已確認 X 在 W 改變後 `RECONFIRM_REQUIRED` 的 canonical 證據移轉，整批僅做一次 `normalize_receiving_layout`。輸入資料不被修改；回傳 (detached layout, changed physical Bay IDs)，同尺寸 no-op 回傳原 layout 與空 IDs 不執行 normalize。GUI 僅轉送輸入、接收結果和 UI dirty IDs，不再自行決定任何尺寸／孔位／成品製造語意。本移轉維持原 Save→Reload、Door Partition、NFB source 和 #1817 batch 效能測試，沒有新增 CUTTING/DXF 製造認證；#2517 仍 OPEN。

### #2517 Receiving 新增實體 Bay Family 預設尺寸 Engine API（2026-11-01）

`manufacturing_api.resize_receiving_bays_with_family_defaults(layout, *, set_index, bay_count)` 是 GUI 增減 Receiving 實體 Bay 的公開 Engine 入口；擴增時呼叫 canonical `receiving_layout.resize_receiving_bays` 建立實體拓樸、Joint、共享來源，再由 Engine `cabinet_types.receiving.BOX_BODY_DEFAULTS` 決定**僅新 Bay**的實際 W/H/D，委派既有 `apply_receiving_bay_dimensions` 同步 Door partition／NFB X 確認依據。既有 Bay 的操作者尺寸及來源均保留，不再由 GUI 計算或由上一 Bay 自訂 W/H/D 取代 Family 預設。減少 Bay 的使用者確認／選取／dirty bookkeeping 仍由 GUI 擁有；低層 `resize_receiving_bays` 的純 copy-by-value 契約未更動，Save→Reload 和已提交 NFB 驗證不放寬。無新 CUTTING、DXF 製造認證；#2517 保持 OPEN。

### #2517 Door Layout 刪除列／欄時的實體內門身分與孔位來源（2026-11-01）

公開 `manufacturing_api.receiving_inner_door_stable_id_for_cell(cell_key)` 保留 `0:0→upper`、`0:1→lower`、其他 `cNrN` 實體內門 ID；`manufacturing_api.remap_receiving_door_layout_after_delete(operation, column_index, row_index, inner_doors, cell_sources, physical_sources)` 是**純 Engine、原來源不可變**的物理身分與全部來源重映射交易。刪除 Door 欄／列後，依實際 cell 索引重新鍵入內門 stable IDs、原有 `inner_door:<stable_id>:*` 孔位來源、`door_cN_rN` 2D Door cell 孔位，以及主 Workspace／Fold Designer 的物理來源及面特徵；來源衝突在 GUI 寫入前 fail-closed。GUI `door_layout_host_adapter` 只提交刪除動作、收集 UI/Workspace snapshots 並套用 Engine 的單次完整結果，`gui.py` 不再自行製造 stable ID。保持現行 Save→Reload source 資料、上／下內門實體身分、DXF source guard、門格合法分割與獨立實體孔位語意；不新增任何 CUTTING／DXF 認證。本批與 Receiving live version #2592、Head/Tail relief #2598 分開，#2517 保持 OPEN。

### #2517 Door Layout W/H 門格數量補足／編輯閘門 Engine API（2026-11-01）

`ae_engine.door_layout_numeric_transitions` 是原 Phase7 A2 門格定向驗證演算法的唯一 Engine 數值 owner。公開 `manufacturing_api.recompute_door_layout(columns, *, total_width, total_height, selected_key)` 用現行 `complete_partition`、相同 0.01 容差與 operator-owned fixed／auto 語意，回傳型別化剩餘欄寬、逐欄層高、合法選取；`door_layout_cells` 仍委派原 canonical `validate_door_layout_dimensions`；`validate_door_layout_width_commit`／`validate_door_layout_height_commit` 在 Engine 執行門格編輯上限、餘數自動欄／列判定及非有限／布林／索引拒絕。GUI `door_layout_controller.py` 只保留舊簽名委派與門格 UI key remap，不再保存第二套尺寸／容差算法，`door_layout_host_adapter` 既有 Tk 與畫面生命周期不變。型別化 DTO 也由 `ae_engine.__init__` 匯出；不更動 Saved Door source、2D/3D/DXF manufactured geometry 或其認證範圍，#2517 保持 OPEN。

### #2517 Receiving Base Plate 實體來源與焊耳孔預檢 Engine API（2026-11-01）

`manufacturing_api.validate_receiving_base_plate_settings(input_snapshot=..., settings_values=..., config=...)` 為受電箱既有 Base Plate 物理選型提交的公開 Headless Engine 預檢：先以 CURRENT `receiving_base_plate_blank_dimensions` 裁決實際板材展開，再透過 `build_receiving_base_plate_result` 與 `ae._receiving_base_weld_ear_mount_slots` 驗證目前 LEFT／RIGHT／CENTER source 的焊耳安裝孔距及拓樸，任何來源不吻合均 fail-closed，回傳 detached 設定（取消選型回傳 None）。GUI `receiving_base_plate_settings_transaction` 只轉交輸入、提交 Engine 驗證結果及控制 submit callback 失敗時回復原專案，不再直接 import 製造板材建構、私有 EAR 孔演算法或 DrawingScene。保留既有 Receiving Base Plate #1502 操作、儲存與重新讀回／2D／3D 不變，預覽／手動設定不自動取得 DXF/CUTTING 製造批准；#2517 保持 OPEN。

### #2517 Receiving Switch 層數／連數／品牌操作的公開 Engine 交易（2026-11-01）

`manufacturing_api.normalize_receiving_switch_operator_layout` 與 `apply_receiving_switch_operator_action(layout, *, operation, brand=None, layer_index=None, delta=None)` 是原 `receiving_switch_layout` CURRENT 來源的 Headless 公開入口。Engine 擁有真實 Switch 層 stable ID、尾端層數增減、至少一層／一連、每層連數增減下界、品牌合法性與物理層索引的 fail-closed 選取；每次回傳 detached normalized layout 和 changed flag，沒有直接產生 CUTTING 或預設 NFB 型號的權利。GUI `ReceivingSwitchLayoutAdapter` 只把操作員整數輸入（含既有整數文字）送往 Engine 並提交回傳值，不再 import 內部 `ae_engine.receiving_switch_layout` 或自行決定物理連數增減。既有 Save→Reload、Receiving switch brands 與 source-only 預覽規則不變；#2517 保持 OPEN。



### #2517 Fold Designer 原始快照板件尺寸公開 API（2026-11-01）

`manufacturing_api.project_fold_designer_snapshot_dimensions(snapshot, indicator_layer_groups)`
與 `FoldDesignerSnapshotDimensions` 由 Engine 投影原始 Fold Designer
root 快照的箱身／封頭／封尾／單門／底板／指示燈盒／小門實體尺寸；GUI
`_snapshot_part_dimensions` 僅讀取操作員 layer/group 與顯示設定，
並保存 Engine 回傳的尺寸。Door Family FW、既有 formed Door 計算、
Receiving physical Base Plate blank、Indicator shared unfolded factory 與
原單組顯示 fallback 保持既有來源與結果，不建立第二套公式。
多門格各 cell 的真正 physical IDs 與尺寸仍由
`project_part_dimensions` 統一投影，此 root 快照 API 不製造 cell。
不新增 CUTTING／DXF 認證，#2517 仍 OPEN。



### #2517 Fold Designer 多門格 Feature 實體來源公開 API（2026-11-01）

`manufacturing_api.project_fold_designer_snapshot_part_features(snapshot, surface_features, door_layout_features)`
由 Engine 承接 Fold Designer 的 Door-cell 操作 Feature store 與正式
`door_cN_rN` 實體板件身分對應。唯一 canonical 格位與 ID 來源仍是
`sheetmetal_part_adapters.door_layout_feature_map_to_part_features`；
Engine 按既有規則保留未操作格位的舊 Feature、允許已操作格位空值清空
舊 Feature、接受 legacy tuple 格位標記作為空值提交證據，並回傳與輸入
隔離的 `part_features`。GUI 不再解析 `door_cN_rN` 或決定物理 Feature
合併；既有 Save→Reload schema、2D/3D/CUTTING/DXF 工廠不更改。
不新增機械規則與 DXF 製造授權，#2517 維持 OPEN。


### #2517 FinalScene Fold Profile 3D 座標／BEND span 公開 Engine API（2026-11-01）

`manufacturing_api.fold_profile_base_index`、`fold_profile_geometry`、
`fold_profile_bend_mask`、`fold_profile_map_with_guides`、
`fold_profile_map`、`fold_profile_flat_map` 統一經既有
`ae_engine.assembly_geometry_folded_mesh` 執行材長展開累計、語意 W
基準段、折後 3D 座標與有限 BEND span 的每點 fold mask。
`phase6_final_scene_projection` 六個舊入口只相容委派；
不再在 GUI 保留一套 angle／sin／cos／Fold 長度演算。
`prepare_fold_profile_mapper` 依來源 profile／BEND guide 準備 Engine 既有的 per-mask Fold chain，供 GUI 繪圖時重用，變更來源必須失效；禁止每個 3D vertex 重算 Fold。既有 Receiving source-owned `formed_length` 僅影響相對應折後 leg，
展開 CUTTING／BEND 保持物理料長；未有 BEND guide 的舊 profile
仍依原有 fallback 判斷。完整 FinalScene／3D 組合採同一 Engine
權威，不新增機械公式或 CUTTING／DXF 認證；#2517 保持 OPEN。

### #2517 厚板 3D 網格特徵邊 Engine 公開 API（2026-11-01）

`manufacturing_api.physical_solid_mesh_feature_segments(triangles, *, tolerance=1e-6)`
由 `ae_engine.solid_mesh_feature_edges` 接手已成形實體 3D 網格的
法向量比較、可見外周／孔緣／折邊／板厚邊與共平面三角剖分對角線剔除。
`phase6_final_scene_projection._phase6_mesh_feature_segments` 僅相容委派，
GUI 的 Matplotlib 不再決定實體特徵邊。FinalScene 製造材料來源不變，
此線段資料純顯示，不新增 CUTTING、DXF／碰撞認證；#2517 持續 OPEN。



### #2517 單門／多門 DoorPartSpec 公開建構 API（2026-11-01）

`manufacturing_api.build_door_operator_part_spec(values, *, model_name,
features, indicator_hole, door_indicator, door_indicator_offset,
use_box_distance, corner_policy, frame_edges, indicator_window_groups,
nameplate_center_datum_top)` 接收 GUI 的當次操作資料後，由 Engine
產生 immutable `DoorPartSpec`。GUI
`_door_part_spec_from_values` 僅取得／傳遞操作輸入，不能再次
自行決定 `feature_space`、Fold 欄位、FrameEdges、
指示燈與名牌孔的製造 request 語意。既有 `legacy_unfolded`
feature 座標空間、單門及 door-cell physical 尺寸、後續
Door finished-face、2D/3D/DXF、Save→Reload 與 Certified Registry
權責原樣保留，無新增製造核准；#2517 維持 OPEN。

### #2517 Receiving singleton Bay Door snapshot API（2026-11-01）

**#2517 Receiving 單一 Bay 內門操作 Save→Reload Engine API（2026-11-01）**：`manufacturing_api.project_receiving_single_bay_door_controls(snapshot)` 將原 `fold_designer_snapshot_projection._snapshot_workspace_state` 的 Receiving 唯一 Set／唯一 Bay 操作內門 `door_state` 寫回權責搬入 Engine，由 `receiving_layout.RECEIVING_DOOR_STATE_KEYS` 和 `update_receiving_bay` 的唯一已存 schema 驗證／交易。只有已存在的 singleton Bay、Set/Bay 模式、非空 `inner_doors` 才從 GUI 根層當次輸入複製門狀態；多 Set／多 Bay／Quantity／非 Receiving 一律不投影、不覆蓋其他已提交 Bay。輸入 layout 與原始 GUI snapshot 不被修改，GUI 僅把 Engine 回傳的 detached persisted layout 放進待保存 snapshot。保留原 70/105 mm 內門位移 Save→Reload 相容及 2D/3D/正式 DXF 權威不變；不增加新的 CUTTING／製造授權，#2517 仍 OPEN。

### #2517 衍生實體板件 namespace／選片修復 Engine 公開 API（2026-11-01）

`ae_engine.derived_part_projection` 與
`manufacturing_api.build_derived_part_projection_request`、
`build_derived_part_sync_plan` 是 Door-cell／BasePlate-cell／Divider／
InnerDoor 實體 namespace、既有 Feature/Profile stash 與
active/selected physical ID repair 的唯一 Engine 權威。
由原 `phase6_derived_part_projection` 純函式機械式搬移，GUI
舊模組僅相容 import；Composition 蒐集 Domain Engine
既有 Derivation 結果送 Engine，Navigation Owner 只套用
immutable Plan。Receiving 原單一 Base Plate 的保留／two-tier
存量相容判斷不改動，未引入第二份 NFB、孔、Fold、2D／3D／DXF
或 Save→Reload 物理規則。本 API 只處理已衍生實體選片，
不是加工輸出認證；#2517 保持 OPEN。



### #2517 BoxBodyPartSpec 操作輸入 → Engine 製造 request（2026-11-01）

`manufacturing_api.build_box_body_operator_part_spec` 與
`ae_engine.box_body_operator_part_spec` 是金庫型／受電箱
BoxBodyPartSpec 製造 request 組合權威。GUI
`_box_body_part_spec_from_values` 僅蒐集 workspace 當前輸入、
Head/Tail Y Fold、結構 state、Features 和 override；不得再決定
箱身實體 piece Features、EndCap `ybottom1` 物理 readback、
Family BoxBody Structure／Back Panel contract 或材料 Fold DTO。
既有 source profile `ui_len_add` 由 Engine canonical
`fold_material_segment_outside_length` 處理，手動 override
優先次序與原 `ae.ybottom1_def` fallback 不變。
本變更不更動 #2621 outside-W datum、NFB 製造、尺寸
補償公式、2D／3D／DXF 認證或 Save→Reload schema；
#2517 持續 OPEN。

### #2517 多片 Box Body 實體外側 W 定位 Engine API（2026-11-01）

`manufacturing_api.resolve_box_body_formed_width_datum(pieces)` 是
箱身多片 3D world mesh 的實體 W datum 判準。原 GUI 的
`_phase6_box_body_formed_width_datum` 已改為單純 Engine API 委派。
既有 `formed_w_end` 正值表示已確認的成形定位；全部空值是
preview-only 不得偽裝成實體；任一非有限、布林或部分缺失的
定位資料皆 fail-closed。受電箱側背分離的合法左側板 W=0
必須同時有 `formed_w_start=0` 與正數有限 `formed_outer_width`
原來源才能接受。沿用既有物理 Part provenance 與 world mesh，
不創新製造尺寸、CUTTING／DXF 規則或認證；#2517 OPEN。

## [CURRENT] #2517 Receiving 多門格 confirmed PartSpec → 正式 Engine DXF（2026-11-02）

`ManufacturingResolvedBayInput.door_layout_columns` 是使用者已確認的多門格位輸入，只能與完整 `confirmed_parts` 共用。現有 `export_verified_resolved_integration_bays` 會透過唯一 Engine `manufacturing_api.door_part_projections` 驗證全部 `door_cN_rN` 實體身分、W/H、T/FW/gap、左右上下 FrameEdges 與已提供的 BoxBody W/H；缺格／漂移先拒絕，不能從來源 P 盤名猜物理格位。合法格位繼續走既有 `build_part_render_data`／verified batch DXF writer 的 staged Save→Reload 和來源雙 guard。原單門、三片箱身、source-only `EXTERNAL_EXPORT_NOT_CERTIFIED`、Factory/Registry 安全邊界全保留；非整箱 MFG-2 或外部 CLI 認證。

## [CURRENT] #2517 Receiving BasePlate Family alias 真實製造與 confirmed Bay 對接（2026-11-02）

既有 `cabinet_types.policy.base_plate_requires_explicit_bend_pattern` 是受電箱 BasePlate 的唯一 Family capability。正式 `generate_part`、`build_part_scene` 與 `build_part_render_data` 現一致使用 canonical Family／aliases；`受電箱`、`RECEIVING`、大小寫與前後空白 alias 的已確認 LEFT／RIGHT 折型都經原 FinalScene DXF 出圖及 Save→Reload，缺折型仍阻擋。原 `ManufacturingResolvedBayInput.confirmed_parts` 可選 `("base_plate", BasePlatePartSpec)`，僅接受原本已有正規製造來源的 LEFT_FLAT_SIDE／RIGHT_FLAT_SIDE、普通 `base_plate` 實體；原 `build_part_render_data`／verified batch DXF／source pre-post guard 仍是單一權威，拒絕未確認 CENTER、NFB depth pair/tier、PAD/EAR 或其他冒名角色。此批不給 NFB MFG-2、全箱或外部 CLI 新放行；source-only `EXTERNAL_EXPORT_NOT_CERTIFIED` 保留，#2517 OPEN。

## [CURRENT] #2517 Registry 候選截角 3D 驗證由 Engine 公開 API 擁有（2026-11-02）

Fold Designer 只收集原有 box_body/head/tail 實體 RenderData、X/Y Fold、結構、T、組合意圖；公開 manufacturing_api.validate_operator_relief_registry_candidate_3d 經 Engine operator_relief_candidate_3d 唯一執行現存候選公式驗證、evaluate_editable_endcap_rule_record 與 solve_world_backprojected_endcap_relief，回傳與舊 GUI 一致的 candidate-specific 3D 證據。候選 Shadow 不改 Registry，不授權製造；缺實體、錯誤身份、意圖不符或公式不適用皆 fail closed。現存金庫型／受電箱機械權威不變，#2517 OPEN。

## [CURRENT] #2517 Phase6 專案 Schema／NFB Save→Reload 唯一 Engine API（2026-11-02）

原 phase6_project_file.py 直接依 Family、受電箱提交 NFB、Set/Bay／Quantity 來源判斷 v1/v2/v3、保存時剝除 legacy aliases、載入時重建 UI aliases，現統一交由 ae_engine.operator_project_persistence 和公開 manufacturing_api.validate_operator_project_payload、project_operator_project_for_write、project_operator_project_for_read；GUI 保留檔案選擇、UTF-8 JSON／Features 編解碼和對話操作。Engine 沿用 normalize_project_snapshot_authority、normalize_quantity_snapshot、receiving_layout 與 committed NFB source owner，防止 v3 提交來源被降為舊版後悄悄丟失，保存不得保留 derived final_geometry。保留金庫型 v1、Receiving v2/v3 的歷史檔可讀相容性與原有拒絕錯誤。此 API 僅確認專案狀態權威，不新增 DXF 製造資格，#2517 OPEN。

## [CURRENT] #2517 Divider／InnerDoor Frame／Panel 物理導覽來源統一 Engine API（2026-11-02）

\`manufacturing_api.project_operator_derived_divider_inner_profiles(snapshot)\` 在既有 \`ae_engine.operator_derived_navigation\` 透過 Family policy、\`derive_box_body_dividers\`、\`derive_all_inner_door_frames\`、\`derive_inner_door_panels\` 與各自 \`part_profiles\` 實體權威，產出同一批 Divider、內門框／內門板 stable IDs 及 Fold Profiles；\`fold_designer_composition_shell_settings.sync_authoritative_derived_parts\` 僅收取公開 API 的只讀映射並執行選單同步。原 Receiving 的 top／left／right 實體框、共享 Divider 底端與 Panel 獨立成品尺寸／折料不改；原 Vault/Custom 儲存的 legacy frame_spans 仍保留（不能以 GUI 猜新尺寸）。原保存、FinalScene、DXF 不得重建另一組實體身分，本 API 只投影資料，不增任何製造放行。#2517 持續 OPEN。

## [CURRENT] #2517 Receiving BasePlate 設定／縮量鎖定／重載資格單一 Engine API（2026-11-02）

原 GUI \`fold_designer_composition_settings\` 使用字串比對 Receiving Family 並直接呼叫 \`receiving_base_plate_values\` 組合板件縮量與折型來源；\`fold_designer_composition_registry_edges\` 在四邊縮量 commit/render 各有一份 Receiving 字串判定；\`gui_modules.project_actions.load_phase6_project\` 在重載時再次私下解析已提交 NFB 的底板實體資格。統一移至既有 \`ae_engine.receiving_operator_projection\`，由 \`manufacturing_api.project_operator_receiving_base_plate_settings\`、\`operator_base_plate_edge_shrink_editable\`、\`project_operator_receiving_base_plate_reload\` 做 Family alias、來源解析、來源錯誤與唯讀導覽資格判斷。GUI 只呈現／保留原儲存 source、同步 2D 選單；錯誤／缺來源不推測替代物理板件。原金庫型可編輯四邊縮量、Receiving 不可修改來源尺寸；原 v1/v2/v3 Save→Reload、防止舊 NFB 製造放行與來源認證閘門不變。此批不新增 DXF 或 MFG-2 放行，#2517 OPEN。

## [CURRENT] #2517 內門原生 Hole Editor NFB 主孔驗證與 Session 暫存計畫 Engine API（2026-11-02）

原 \`gui_modules/editors/hole_editor_composition._bind_editor_actions\` 的「來源已驗證 NFB 帶入」及「CSV 候選主孔重選」分別在 GUI 直接檢查 \`ProfileFeature\`、\`NFB_VERIFIED_SOURCE/NFB_CSV_SOURCE\`、實體內門 \`part_id\`、重複來源及 \`feature_is_strictly_within_surface\`，混入第二份孔位物理准入判斷。現由 \`ae_engine.receiving_nfb_hole_stage\` 經 \`manufacturing_api.plan_operator_inner_door_nfb_hole_stage(..., mode="verified_append"|"csv_replace")\` 以原有 finished-face FeatureSurface、當前內門 stable_id、尺寸及 Editor Features 一次做唯讀驗證，回傳候選主孔的 detached tuple；GUI 僅將回傳資料送進既有 \`HoleEditorAction.preview_all\`、重畫、Undo／Confirm／Cancel。既有原始 source 驗證者（\`verified_nfb_openings_to_editor_features\`／\`csv_openings_to_editor_features\`）及實體／碰撞／CSV SHA 校驗仍在原 Engine owner，來源 type 字串或本 stage API **不構成任何 NFB 製造批准**；真正 CUTTING／DXF 必須由原正式製造 API 再認證。非法板件、錯誤來源、跨內門主孔、重複、超界拒絕且 Session 未改；空 CSV 選單只移除先前 CSV 草稿，使用者其他孔與已驗證實體主孔不受影響。金庫型與受電箱原 PartSpec、2D／3D、Save→Reload、DXF 與 source-only external gate 不變。#2517 OPEN。

## [CURRENT] #2517 活動 3D Mesh Profile 與左右側板實體 Fold 單一 Engine API（2026-11-02）

原 fold_designer_bridge._phase6_mesh_profiles_for_part 在 GUI 直接呼叫 box_body_structure.project_side_back_3d_input_fold_to_physical、cabinet_types.policy.box_body_profile_uses_outside_dimensions，並依 material.bounds 補完 Divider／內門框缺軸長度。現統一改由 manufacturing_api.project_operator_3d_mesh_profiles 進入 ae_engine.assembly_mesh_profiles，從相同 Family 和既有物理 Fold source 單向投影，不把 Mesh 當 operator 輸入。GUI 只供應當前／儲存／箱身 Fold Profiles、active part、來源快照與 Render material。沿用原 Receiving LEFT outside 補償與 RIGHT 反序 angle 移轉，並復用 resolve_material_mesh_profiles 只對需要 material bounds 的 BoxBody／Divider／Frame 進行有限正尺寸校驗，完整兩軸 Fold 不受無關材質錯誤影響。原 Registry candidate 3D 會透過原 GUI adapter 消費此 API；不新增製造公式、DXF 或外部 source-only 授權。#2517 OPEN。


## [CURRENT] #2517 指示燈盒線槽 MARKING 與操作欄位共用 Engine 來源（2026-11-02）

`manufacturing_api.project_indicator_box_marking_layout(layer_groups)` 將既有指示燈盒實體 MARKING 線槽打標孔的組數、X 起點、水平間距與第一層 Y 位置集中於 `ae_engine.indicator_box_marking_layout`。原 `ae_engine.ae_door_indicator.get_indicator_box_data` 產生的 `MARKING` 圓孔與一字線直接使用同一份投影，主 GUI `cabinet_controller._refresh_indicator_box_result_values` 僅把此公開 API 回傳值帶入可編輯欄位，不再維護第二份 171/90/191/50/150/178.5 物理規則。仍沿用既有 `sheetmetal_features.indicator_box_outer_size` 與 `_normalize_indicator_groups` 來源驗證；原多層群組及金庫型／受電箱同一指示燈盒圖面維持，未擴充 CUTTING／DXF／外部 export 認證。實際 MARKING 圓心可直接與 API positions 對照；#2517 OPEN。


## [CURRENT] #2517 圓孔排列實體預覽由 Engine API 決策（2026-11-02）

`gui_modules/editors/hole_editor_round_settings._RoundHoleSettingsDialog` 原本自行以實體孔心距選最近鄰孔、決定對齊後孔位、實際填滿／重新填滿、選出須取代原孔的實體結果。現由 `manufacturing_api.nearest_operator_round_hole_neighbor_index` 與 `manufacturing_api.plan_operator_round_hole_preview` 接管，實作放在 `ae_engine.operator_round_hole_projection`，沿用 `sheetmetal_feature_reference` 已存在的 `align_circle_to_neighbor`、`generate_round_fill/refill` 與 `feature_is_within_surface`；GUI 只收操作者方向、間距、對齊、是否重新填滿，並把 Engine 的 detached `OperatorRoundHolePreview` 交既有 `HoleEditorAction.preview_all`。完整確定／取消／Undo 仍由 `Phase6HoleEditorSession` 執行。非法孔身份、鄰孔選擇或無法在板面生成的孔位 fail-closed 且不修改來源，不新增 Family 或第二份孔位／DXF 製造公式，不放行外部未認證 export；#2517 保持 OPEN。


## [CURRENT] #2517 Hole Editor 指示燈盒開口實體 2D 預覽由 Engine API 決策（2026-11-02）

原 `gui_modules/editors/hole_editor_render.HoleEditorCanvasRenderer.draw_extra` 在 `indicator_box` 模式用 Door 的 left/bottom fold、finished face W/H 和 operator offset 私下計算 CUTTING `ResolvedRect` 的中心。現經公開 `manufacturing_api.project_operator_hole_editor_indicator_box_opening`，由既有 `ae_engine.operator_door_2d_preview` 使用原 `manufacturing_door_indicator.indicator_box_opening_size` 生成同一 `ResolvedRect`，GUI 僅傳入已有 `DoorIndicatorContext`、群組、T 和偏移並顯示；輸入 NaN/Inf/布林或非法尺寸 fail-closed。孔心位置與舊顯示相容，來源使用現行金庫型／受電箱 Door physical API，2D/3D/CUTTING/DXF/Save→Reload 仍由各自原本正式 Engine 工廠與測試驗證；這是預覽統一，不授權任何原本未認證的製造或外部 export。#2517 OPEN。

## [CURRENT] #2517 Receiving 已確認 EndCap 原始孔位 → 正式 Engine DXF（2026-11-02）

既有 manufacturing_api.build_receiving_factory_confirmed_parts 和 ManufacturingResolvedBayInput 擴充可選 confirmed_endcap_features，只接收由可信來源／操作者確認並已按 Engine canonical 實體 role 對應的 head/tail 成品面 1:1 mm CUTTING CircleFeature／RectFeature／ProfileFeature。禁止用 CADSplit P 盤視圖名猜 Head/Tail、未解析 DXF 圖元冒孔位；非法 role、型別、成品面錨點、非有限座標及非正尺寸 fail closed。Engine 沿原建構 EndCapPartSpec(holes=...)、Family／Corner／FinalScene 和 verified physical DXF Save→Reload 接續，無第二製造算法或輸出系統。未提供孔位維持舊行為；其他板件孔位、全套 Set/Bay、NFB 或 source-only 外部 export 未因此獲得認證，#2517 OPEN。
已確認 Head/Tail 的 typed Feature 雖然宣告了 `Vec2`／Profile 頂點型別，直接公開 API 呼叫仍可能傳入 `offset=None`、非 Vec2、損壞的 `points` 或溢位整數。`ae_engine.receiving_factory_requests._confirmed_endcap_source_features` 現與原 Door 一樣將 `AttributeError`／`TypeError`／`OverflowError`／來源 `ValueError` 全部收斂為 `RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID`；壞來源在建立 PartSpec／DXF staging 前拒絕，不能改以 Python 非正式例外流出。合法 Head/Tail CUTTING 仍使用相同 Engine `EndCapPartSpec`、verified physical DXF Save→Reload，不更改製造幾何、層級或 source-only 認證。

## [CURRENT] #2517 受電箱底板 Part Session 啟用／儲存 Fold 來源單一 Engine API（2026-11-02）

原 GUI gui_modules.application.fold_designer_part_session 的活化來源判斷以 model 字串限定受電箱，另在 save_current_part 直接呼叫 ae_engine.receiving_base_plate_3d_profiles，造成既有 Family alias 在切換後可能使用錯誤的 generic 編輯器快取。現把兩條路徑統一交 ae_engine.operator_part_session_profiles，公開 manufacturing_api.project_operator_part_activation_profiles 與 project_operator_receiving_base_plate_save_profiles。Engine 透過同一 cabinet_types.policy.canonical_family_name 辨識 Receiving alias；來源已具 receiving_ 實體 Fold 識別時，啟用只採用當前 canonical defaults，不讓舊 Profile 反寫；實際儲存只對已配置且可物理解析的受電箱底板呼叫原 receiving_base_plate_3d_profiles，失敗不降級為假 Fold，無配置與金庫型仍保留歷史 editable profile。GUI 只 stash 回 Engine 投影並維持原 Session/Save→Reload。此入口不授權 NFB CUTTING、DXF 或 source-only 製造；原實體 33／35 mm Fold、CURRENT 07 和正式 Registry gate 不變。#2517 OPEN。

## [CURRENT] #2517 Fold Designer 來源固定片 DXF／工作區實體 Placement API 邊界（2026-11-02）

原 GUI `gui_modules/application/fold_designer_composition_state.export_selected_dxf_from_3d` 從 `ae_engine.receiving_base_fixing_plate_geometry` 直接 import `save_independent_source_flat_dxf`，繞過既有公開 Engine facade；`collect_workspace_state` 直接注入 `ae_engine.assembly_placement.resolve_assembly_placement` 作為實體版件 Save→Reload 的位置解析器。現於既有 `ae_engine.manufacturing_api` **原 callable 同一身份重匯出** `save_operator_fixing_plate_source_flat_dxf` 與 `resolve_operator_assembly_placement`；GUI 只控制操作者選擇／確認／路徑／錯誤顯示，並將 workspace snapshot 與 Part IDs 交給公開 API。原 `save_independent_source_flat_dxf` 的真實 SOURCE T2 CUTTING／BEND23、atomic write、反讀幾何查核、不可覆寫、非法 Part ID／缺 NFB tier source 拒絕完全不改；**source-flat specimen 不是正式成形／焊接／整箱製造 DXF 認證**，不能取得外部 source-only export 之外的製造授權。Assembly Placement 原 engine owner 唯一，保留 Vault／Receiving 實體 3D 和存檔重載身分與座標，沒有 GUI 自行推算物理偏移。#2517 持續 OPEN。

## [CURRENT] #2517 Receiving Set/Bay Part Session 無變更導航儲存判斷由 Engine 擁有（2026-11-02）

GUI Fold Designer 的 `activate_part` 不得以 model 字串／Fold list／W-H-D 差值自行決定是否略過可能寫回製造來源的 Part Session save。由公開 `manufacturing_api.can_skip_operator_receiving_part_save` 依 canonical Family、Set/Bay mode、上一個實體 part、顯示模式、前後實際 Fold 與 live/committed W-H-D 判定；只有 Receiving 非單板 Assembly 離開隱藏 BoxBody，或來源可證明完全未編輯的 Head/Tail，才能視為 display-only。缺少值、讀取錯誤、折型異動或 W/H/D 異動都必須走既有儲存，不得無聲跳過。GUI 僅收集 Tk 欄位、處理換頁與呼叫 Engine；不新增幾何算法、出圖分流、製造認證或外部 source-only 放行。#2517 持續 OPEN。

## [CURRENT] #2517 Part Session Settings Flush 的 Receiving 已提交 W/H/D 來源由 Engine API 投影（2026-11-02）

Fold Designer `save_current_part` 不應根據 GUI 內的 `model` 字面值或自行擷取 W/H/D 決定把 Settings flush 的舊視窗尺寸覆蓋 live Bay。公開 `manufacturing_api.project_operator_receiving_settings_live_dimensions` 由 Engine 依 canonical Family、是否正在套用 Settings 與已提交來源完整性判斷；有可信 W/H/D 時以既有 Engine `normalize_operator_source_dimension` 檢查正數有限值，保留來源數字原型回傳供 UI 同步和後續 BoxBody 投影使用，無值時維持原流程，非法物理值明確拒絕。Vault、未在套用 Settings、其他部件與 2D／3D／DXF 原製造路徑不改；GUI 僅作 Tk 同步與 Session 交易協調。#2517 仍 OPEN。

## [CURRENT] #2517 Part Session 包外 W/H/D 與 Receiving Quantity 共用尺寸來源由 Engine API 統一（2026-11-02）

`gui_modules.application.fold_designer_part_session.save_current_part` 原在每次 Part save 先以 GUI `get_int` 把畫面 W/H/D 截成整數，再於 BoxBody 和 Head/Tail 兩處直接用 `float(receiving_quantity_box[axis])` 覆寫，且封頭尾依欄位是否存在決定整數／浮點寫回，可能丟失合法小數、讓過時 UI Set/Bay 尺寸污染已提交的 Quantity 共用箱體，或使無效來源靜默走兼容 coercion。現由公開 `manufacturing_api.project_operator_part_session_source_dimensions` 與 `project_operator_quantity_box_dimensions` 共同使用 Engine Family registry 與 `receiving_quantity_box.normalize_common_box` 的正式共用箱體來源；非 Quantity 保留操作欄位並走 `normalize_operator_source_dimension` 正數有限非 bool 驗證，不做取整。明確配置的受電箱 Quantity W/H/D 無論 GUI 標頭是否落後，都採用同一 canonical 共用箱體；未配置的 legacy 專案仍依原操作輸入（非補猜模式來源）；配置不合法則拒絕而不得 fallback。Head/Tail 由既有 Engine Fold 解算取得的 W/D 在更新 GUI 交易前走相同公共尺寸驗證，不再依是否存在 `receiving_quantity_box` 決定整數化。GUI 只收操作值、呼叫公開 API、執行原 Session UI 導航；無第二製造幾何算法或新出口認證。#2517 保持 OPEN。

## [CURRENT] #2517 CustomFold Part Session 儲存與開孔編輯走同一公開 Engine API（2026-11-02）

原 GUI `gui_modules/application/fold_designer_part_session.py` 在自訂板件 Save 中自行讀取 FoldAxis／T、挑選實體折彎軸、呼叫兼容補償函式把 `ui_len_add` 原地寫入 GUI Profile；開孔時又直接從 Engine 內部模組 import `custom_fold_feature_context`。現在由正式 `manufacturing_api.project_operator_custom_fold_save_profiles(snapshot, part_id, profiles)` 呼叫既有 `ae_engine.custom_fold_api`：共用 `CustomPartCatalog` descriptor、現行 `build_custom_part_profiles` 的厚度合法性、`custom_part_spec` 的單軸／另一軸 span 驗證與 `box_body_fold_profile.apply_outside_dimension_compensation` 的唯一相鄰 BEND × T owner，輸出 detached X/Y Profiles，不改輸入。GUI 只傳入操作 snapshot／part ID／編輯 rows 並保存；Hole Editor 使用公開 `manufacturing_api.custom_part_spec` 與原同一 callable `manufacturing_api.custom_fold_feature_context`，不得另算實體孔位平面。既有 X/Y CustomFold `PartSpec → FinalScene → DXF Save/Reload` 的測試仍為製造真值；金庫型／受電箱皆不得由 GUI 決定折法，非法板厚／Flat span 拒絕。這不新增箱體製造公式、Set/Bay 或外部 CLI 認證；#2517 OPEN。

## [CURRENT] #2517 主 GUI 受電箱 BasePlate／BoxBody 2D 實體來源路由歸 Engine Family Registry（2026-11-03）

- 主 GUI `gui_modules/application/render_snapshots.py` 先前用 `snapshot["model"] in ("受電箱", "RECEIVING")` 自行判定是否選用已提交 Receiving NFB BasePlate／BoxBody 的實體 2D FinalScene。正式 Family Registry 還支援 `receiving`、大小寫別名，因此同一受電箱可被錯導到 GUI 舊通用板件預覽，與已核准的實體 3D／DXF 來源分裂。
- 現在兩個 2D 入口只將原 Project snapshot 傳給公開 `manufacturing_api.uses_operator_receiving_committed_2d_source(snapshot)`；實作位於 `ae_engine/operator_box_body_2d.py`，使用唯一 `cabinet_types.policy.canonical_family_name`。True 時仍必須呼叫原本正式 `project_receiving_base_plate_2d_snapshot` 或 `project_receiving_box_body_2d_source`，缺少已提交 resolver／physical FinalScene 依原 fail-closed 拒絕，**不得回退通用圖**；非 Receiving 保留原單板件合法流程。這只是來源路由，不新增製造幾何公式、Set/Bay、外部 CLI 認證或 DXF 放行。
- 定向回歸同時覆蓋 Registry 別名、真實兩層 NFB BasePlate material identity、真實 BoxBody SIDE mother scene／EAR 表示層及未配置來源的拒絕；所選 2D 實體仍是製造／3D 的同一 Engine resolved scene，真正 DXF Save→Reload 和其他板件製造放行仍由各自既有正式流程驗證。#2517 仍 OPEN。

## [CURRENT] #2517 Fold Designer 專案儲存不能忽略當前板件提交失敗（2026-11-03）

- 原 `gui_modules/application/fold_designer_composition_state.py::build_project_snapshot` 在建立 Save/Save As payload 前呼叫 `_save_current_part(notify=False)`，但 `except Exception: pass` 會把任何當前板件 Fold、孔位或來源提交失敗吞掉，再從較舊的 Workspace 製作專案快照，破壞來源與 Save→Reload 同源承諾。
- 現在直接將真實 Part Session commit 失敗往上傳遞；原 `save_project_file` 既有錯誤提示與 write boundary 會拒絕後續寫檔，保留舊有檔案位元組，正向成功路徑不變。這是 GUI 應負責的交易錯誤呈現／取消保存，不發明任何 Engine 幾何、Board 身份、Fold/Feature 公式或第二儲存權威。測試覆蓋 ValueError／RuntimeError 原因回傳、未觸發 write、既有專案位元組未變及 source method 不再吞錯；已有正向 `tests/test_issue2517_project_save_reload_engine_authority.py` 與實體 GUI Save→Reload 繼續驗證。#2517 仍 OPEN。

## [CURRENT] #2517 Manufacturing Request T 實體來源禁止隱性 2mm 預設（2026-11-03）

`phase6_manufacturing_adapter.build_manufacturing_request` 原本在製造輸入不足或 Settings 板厚字串錯誤時，使用相容 `_num(...,2.0)` 默默將 T 改成 2mm。此來源 fallback 已不符合 #2517 的公開 Engine 契約及 CURRENT 07 操作員包外來源。GUI Request adapter 現只依序取得已確認 Snapshot `t`、否則 Settings `t`，交由既有公開 `manufacturing_api.normalize_operator_source_dimension(raw, field="t")` 驗證正值、有限數字、非 bool；缺少或格式錯誤時阻止建構製造 Request，不可帶假 T 進入 Fold／2D／3D／DXF。合法小數厚度保留，舊式 Fold Editor 展示精度不改。沒有新增任何製造幾何、Family 公式、CADSplit 專用 API 或 source-only CLI 認證。

## [CURRENT] #2517 主門／多門 2D 預覽實體 W/H/T/FW 讀取共用 Engine 驗證（2026-11-03）

`gui_modules/application/render_snapshots.py` 的單門 2D 原用 GUI `float()` 取得操作員 W/H/T/FW，多門概覽也直接 `float()` 取得 W/H，導致 NaN／Infinity 等非有限來源可能進入 PartSpec 或預覽尺寸。現兩條路只讀取 GUI 控制項，直接交由已存在的公開 `manufacturing_api.normalize_operator_source_dimension(raw, field=...)` 驗證正數、有限值、非布林與合法小數；單門來源無效時不得呼叫 PartSpec／FinalScene，概覽維持既有 `error` 呈現。門縫與折邊等可能合法為零的其它操作參數不變，沒有 GUI 自製尺寸公式、第二套 Door 製造入口，也不開放任何未驗證的 DXF 認證。

## [CURRENT] #2517 Fold Designer 多門格 Indicator 製造來源拒絕暗中補值；CustomFold Payload 只走公開 Engine API（2026-11-03）

原 `gui_modules/application/fold_designer_manufacturing_projection.py::_door_part_spec_from_payload_context` 先用 GUI 相容狀態正規化、再做 `max(1,min(6,int(layers)))` 和 `int(groups)`，會把非法小數、布林或缺失實體孔位資料修成可出圖數值。現在製造 payload 直接傳每一格已儲存的原始狀態給公開 `manufacturing_api.project_operator_door_cell_indicator_manufacturing_source`：Engine 只接受明確有效的啟用來源，使用既有 `normalize_operator_hole_editor_indicator_state` 的層數、組數、偏移、互斥模式驗證；缺少 physical groups、非法數字與不可能的層數 fail closed。不啟用時仍是無孔門板；歷史 `enabled/box_enabled` flags 只用來還原模式，不得補失去的實體組數。單門 saved payload 的啟用指示燈群組也使用既有 Engine `normalize_fold_designer_indicator_groups`，不再在 GUI `int()` 轉型。

同一製造 payload 中的 CustomFold 不再透過 `phase6_custom_fold_profiles` 相容模組，而直接以 `manufacturing_api.is_custom_part` 與 `manufacturing_api.custom_part_spec` 取得正式 PartSpec，沿用既有 Family／PartSpec／FinalScene／DXF 來源。定向測試覆蓋兩種模式、真實 X/Y 金庫型及受電箱 DXF Save→Reload、非法孔數／偏移、明確未知模式拒絕及不改來源；多門格真實 Door PartSpec／DXF 回讀，不表示外部 CLI 或未確認完整 Set/Bay 獲得認證。#2517 仍 OPEN。

## [CURRENT] #2517 受電箱 Family 別名之實體底板配置在快照、設定與 Project Save→Reload 必須同源（2026-11-03）

原始 Fold Designer 主 GUI `_snapshot_base_state` 只用 `{"受電箱","RECEIVING"}` 判斷是否把已提交的 `receiving_base_plate` 複製到專案快照；Engine 物理底板 Settings preflight 亦僅允許同樣兩個字面值。Family Registry 接受 `receiving`／混合大小寫，因此同一受電箱從編輯、快照到 `.p6fold` Save→Reload 可能丟失明確實體型式或拒絕本來合法的底板設定。

現改由既有 `ae_engine.receiving_operator_projection.receiving_family_supports_back_panel_mode`（共用 Registry）決定：公開 `manufacturing_api.project_operator_receiving_base_plate_snapshot_source(snapshot, persisted)` 僅 deep-copy 已提交、明確存在的 `receiving_base_plate`，沒有資料就不補、明確 None 保持 reset；非法配置型別 fail closed、其他 Family 一律不攜帶受電箱來源。原 `validate_receiving_base_plate_settings` 改走同一 `cabinet_types.policy.canonical_family_name`，其真實 EAR 孔／板件輪廓檢查完全保留，**沒有放寬實體製造認證、沒有新增 Fold／DXF 公式**。實際主 GUI snapshot、合法金庫型拒絕、來源不變性與 `.p6fold` 保存重開驗證；#2517 仍 OPEN。

## [CURRENT] #2517 多門格指示燈 GUI 專案快照不准把非法實體孔數修成預設值（2026-11-03）

`gui_modules/application/fold_designer_snapshot_projection.py::_snapshot_base_state` 原先直接使用 GUI `normalize_door_indicator_state` 來保存每一格指示燈，該顯示相容函式會把非法層數、布林孔數、非有限偏移變成 1／2／0，造成儲存來源與 Engine 實體製造判準分裂。正式存檔現在交由公開 `manufacturing_api.project_operator_door_layout_indicator_snapshot_states` 對每格呼叫現有 `project_operator_door_cell_indicator_manufacturing_source`，使用 Hole Editor 同一份 Engine 驗證規則，輸出 detached、具有舊版 `enabled/box_enabled` 閱讀相容欄位的合法物理來源。啟用但來源不完整／非法時失敗且不提交快照；停用時未使用的欄位不會產生孔；歷史 flags 僅決定 mode。GUI 原本的顯示相容函式可繼續處理畫面，不得成為實體 Save／製造資料權威。金庫型／受電箱的 GUI Snapshot→Project Save→Reload 對應真實來源與非法拒絕測試；製造門檻與 DXF 寫入器未改，#2517 仍 OPEN。

## [CURRENT] #2517 門格 Door PartSpec 與獨立指示燈盒／小門 DXF 必須使用未經 GUI 修補的 Engine 實體來源（2026-11-03）

主 GUI `manufacturing_adapter._door_layout_part_spec` 與 `export_actions.export_multi_door_indicator_box_parts` 原本均對層數執行 `max(1,min(6,int(...)))`，再用 `int(groups)` 自行決定實際孔數；而 GUI `_door_layout_indicator_state_for_key` 可能已做畫面相容修補。兩條製造入口現在優先讀取已提交的原始 `door_layout_indicator_states[physical_cell_key]`（只有無此來源容器的舊 client 才從既有展示適配器取輸入），經同一公開 `manufacturing_api.project_operator_door_cell_indicator_manufacturing_source` 驗證才建 Door PartSpec 或指示燈盒／小門 PartSpec；沒有原始實體來源，不得因展示值而增加孔位；非法層數、孔數、偏移與模式不得出圖。DXF 真正寫入仍沿用既有 `_export_authoritative_part` → Engine FinalScene sink，沒有新公式、沒有新放行權。定向測試覆蓋 Door、兩獨立板件、無效來源無呼叫／無輸出、禁用 GUI 數值修補回長；#2517 仍 OPEN。


### #2517 門格原始來源必須在 GUI 顯示 accessor 原地修補之前驗證（2026-11-03）

`door_render_host_adapter._door_layout_indicator_state_for_key` 原為顯示相容入口，曾對 `door_layout_indicator_states[key]` 原地 `clear()/update()` 修補；現改為只回傳 detached 顯示資料，**不創建缺少的 cell、也不覆寫已保存的 physical source**。2D 預覽讀 Features 使用 `.get` 而非 `setdefault`，開啟 Door/Indicator Box/SmallDoor Hole Editor 的 Feature 清單為獨立工作副本，僅既有 `sync_callback` 才寫回真正 Project/Workspace Feature。即使 Door PartSpec 或指示燈盒／小門獨立 DXF 隨後呼叫嚴格的 `project_operator_door_cell_indicator_manufacturing_source`，若**先呼叫顯示 accessor**，Engine 看到的已非原始物理來源，非法 bool／零／過量群組、層數或 NaN 偏移可能變成合法預設。正式路徑 `manufacturing_adapter._door_layout_part_spec`、`export_actions.export_multi_door_indicator_box_parts` 與 `_validate_selected_indicator_exports` 現必須先讀既有來源容器中的原始 row，交同一 Engine API 驗證；只有根本沒有來源容器的舊相容 client 才使用顯示 accessor。原容器存在但特定 cell 缺少時由 Engine 判為未啟用，**不得創造實體孔位、不得就地修改來源**。定向測試模擬真實會修改原 dict 的 GUI accessor，要求非法來源在預檢、Door PartSpec 與獨立 DXF 出口全部拒絕、不產生檔案且保留原資料；不修改 Family／Factory／FinalScene／DXF 製造算法或認證。#2517 維持 OPEN。

**門格 Door Hole Editor 物理基準歸 Engine（2026-11-03）：** 主 GUI `open_door_layout_cell_editor` 先前直接用低層 `feature_surface_from_structural_result`、`build_finished_reference_guide` 取得物理表面及成品尺寸 guide，並自行從 GUI Fold 值組 `DoorIndicatorContext`。現在委派公開 `manufacturing_api.project_operator_hole_editor_door_cell(result, door_spec, baseline_scene=..., baseline_status=...)`：既有 Engine `OperatorHoleEditorGeometry` 統一返回真實 selected-cell surface、材質 W/H、成品 guide、Fold datum／frame edges；`result` 與 `door_spec` 分別來自 GUI 原本已使用的 Engine 公開結構及同一 DXF DoorPartSpec。不使用預覽 bbox／另一份 Family 公式；GUI 僅傳遞來源和顯示結果。舊 2D/3D、DXF／Save→Reload、source-only export 保護不變，#2517 未結案。

**開孔編輯器同源補齊（2026-11-03）：** `gui.py::open_door_indicator_component_editor` 原先先呼叫會原地修補 `door_layout_indicator_states` 的展示 accessor，再以 GUI `int()`／層數裁切建 IndicatorBox／SmallDoor 編輯用 PartSpec；`manufacturing_adapter._indicator_component_editor_contexts` 亦重做同一套 GUI 孔數轉型。兩條入口現在改為直接消費原始已保存 Door-cell 操作資料與同一公開 `manufacturing_api.project_operator_door_cell_indicator_manufacturing_source`，只用 Engine 回傳的合法 layers/groups 對接原 `resolve_indicator_editor_components`。沒有原始 cell 不增孔，非法來源在建 Spec／開 editor 前拒絕且不修改原資料；歷史無來源容器的客戶端只保留既有 accessor 作來源讀取，仍須通過 Engine 驗證。UI 顯示、Feature store、Confirm callback、正式 FinalScene／DXF、Factory 不變。驗收 `tests/test_issue2517_door_indicator_component_editor_engine_api.py` 與 `tests/test_engine_indicator_editor_boundary.py`；#2517 仍 OPEN。

## [CURRENT] #2517 Fold Designer 指示燈 X/Y 偏移的唯一 Engine 來源驗證（2026-11-03）

- 原 `gui_modules/application/fold_designer_snapshot_projection._snapshot_part_dimensions` 以 Python `float(self.door_indicator_offset_x/y)` 將即時使用者數值寫入 `door_indicator_offset` 保存快照，能把 `True` 變成 1 mm 或將 NaN/Inf 直接寫進 Project；同一指示燈 Hole Editor／正式 Feature 製造路徑的 `ae_engine.fold_designer_snapshot_dimensions.normalize_operator_hole_editor_indicator_state` 已嚴格拒絕非有限偏移，GUI/Headless 來源不同權威。
- 現在上述原 Engine owner 抽出 `normalize_fold_designer_indicator_offsets(x, y)` 並經**既有** `manufacturing_api` 公開，Hole Editor 與原 Fold Designer Project Save 共用同一個有限非布林檢查。合法帶正負號位置、零與小數精度原樣保留；X、Y 任一無效則在 GUI 改變任一 Snapshot 欄位之前拒絕，無 1 mm/0 mm 杜撰 fallback。不改 `door_indicator_offset` 的 tuple/JSON list wire、門格的正式儲存 DTO、Hole Editor 模式、CUTTING 孔位公式或 DXF/外部 CLI 資格。
- 驗收 `tests/test_issue2517_fold_designer_indicator_offset_engine_api.py` 與 `test_issue2517_fold_designer_snapshot_dimensions_engine_api.py`，包括 Vault/Receiving、正負偏移、Headless 與 GUI 共用 API、JSON Save→Reload、禁布林/NaN/Inf、未修改快照及現有產品／GUI API Gate 回歸；#2517 OPEN。


## [CURRENT] #2517 NFB CSV 直接建立可稽核的原生 Bay 候選（2026-11-06）

- 原生 NFB 的尺寸、開口與螺絲規格唯一來源是當前 WHD 各廠牌 `NFB數值規格.csv`，不要求已有 NFB DXF 或另一份已提交的 `NFB_CSV_SOURCE`。原始 CADSplit DXF 只供盤位／設備型式與物理身份證據，不是 V5 製造幾何規格。
- 公開 `manufacturing_api.candidate_receiving_nfb_csv_for_fresh_bay` 以確認的原生 Set 廠牌、合法 V5 型號、真 Bay W/H/D/T、已確認 Door source Partition，沿既有 Engine `fresh_receiving_mode`／Bay projection／`editor_nfb_features_from_csv` 產生 CSV SHA、原生內門 part_id、實體 slot 及可核對 CUTTING 矩形之**未確認草稿**；不在 CADSplit 複製幾何算法。已有提交的 Bay 不可覆寫。
- 只為編輯位置提供 Engine 一層 550mm 或兩層 330/830mm 既有預設；未證實的 X 必為 `UNVERIFIED_BASIS` 與 `manual_x_mm=None`。原生 Apply 只提交來源，不能自動變成 FinalScene MFG 或全箱 DXF 放行。缺型號數值、缺廠牌、非預設分割卻缺內門身份都拒絕，不允許從另個 Bay 偷借來源或虛構物理 X。


## [CURRENT] #2517 原生 CSV 首次候選孔的世界 X 製造阻擋（2026-11-06）

- 自動新建 Bay 的 candidate_receiving_nfb_csv_for_fresh_bay 會依 WHD 數值 CSV 建立 NFB_CSV_SOURCE，保留 source_params.placement=native_editor_initial，並額外標記 source_params.fresh_bay_auto_unconfirmed=True。CSV SHA、矩形尺寸、Bay 及 slot 身份成立，只證明來源正確與編輯器初始顯示位置；預設 X 即使是 0 也未經操作者確認。
- WHD 的 _source_world_x_from_committed_editor_feature 只對 fresh_bay_auto_unconfirmed=True 的自動候選拒絕回推出 world X；manual_x_mm=None／UNVERIFIED_BASIS 保持未確認，export_current_csv_nfb_pair_from_request 對這種唯一來源必須拒絕且不輸出 DXF。**不能**一律阻擋 native_editor_initial：既有 WHD GUI 原 Hole Editor「確定全部」是獨立、由操作者實際確認的來源路徑，原 Feature 即使保留 native_editor_initial 也不得因此被誤封鎖；仍須通過原 CSV 型號、輪廓、Y、實體身份等 Engine 驗證。已明確確認且受持續 datum 保護的 CONFIRMED X 也保留原生 FinalScene、PAD／底板及 2D／3D／DXF 功能。
- 不建立新 X 規格、不填補 CSV 缺數據、不覆蓋 R5 現場 NFB數值規格.csv，不放寬多 Bay PAD／EAR 或整箱 DXF 認證。

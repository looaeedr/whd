---
whd_doc_role: CURRENT
whd_contract: manufacturing-architecture
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 🔩 04. WHD 鈑金展開幾何引擎規範（ae_engine）

## [CURRENT] #2517 共用單板製造拒絕已註冊但未實作 Family（2026-11-02）

`manufacturing_api.generate_part(PartSpec, output_path, context)` 在建立目錄或暫存 DXF 前，呼叫既有 Family Registry owner 的 `cabinet_types.policy.require_implemented_manufacturing_family(spec.model_name)`；若 `RO/落地盤` 之類已註冊 Family 仍為 `implemented=False`，須回 `CABINET_FAMILY_NOT_IMPLEMENTED` 且不執行 exporter、不得建立 DXF。金庫型、受電箱（含 alias）沿既有正式單板 API 及各 Part 專屬來源 gate 繼續；`model_name=None` 與尚未建檔的歷史工廠字串為相容目的暫保留既有行為，不能把此相容視作製造認證。此 gate 只是「已知但未實作 Family 不得偷用舊公式」的必要條件，**不**聲稱所有 Family×Part×Operation 已經通過正式 Registry／DXF 核可。source-only `dispatch_manufacturing_integration(export)` 的拒絕維持原樣，#2517 OPEN。

## [CURRENT] #2517 受電箱 BasePlate 正式製造 Family Gate（2026-11-02）

既有 `manufacturing_api.generate_part(BasePlatePartSpec, ..., ManufacturingContext)` 仍是金庫型與受電箱共同單板出口，不增設 Receiving 專用 exporter。受電箱「必須提供已確認 `receiving_bend_pattern`，並走 guarded FinalScene 出圖」的判斷由 `cabinet_types.receiving.base_plate_requires_explicit_bend_pattern` 提供，經既有 `cabinet_types.policy.base_plate_requires_explicit_bend_pattern` canonical Family/alias hook 呼叫；不再由 `_base_plate_export` 字串硬判 `{"受電箱","RECEIVING"}`。因此 `受電箱`／`RECEIVING`／大小寫 alias 都不能因原字串不相等而落入通用底板出口。未給明確折型依舊拒絕 `RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING`，不產生 DXF；金庫型／未指定 Family 的舊通用 BasePlate exporter、CornerPolicy、目的檔交易語意不變。此項修正只封住 Family alias 的既有製造分派缺口，絕非新的 NFB/PAD/EAR/整箱製造認證，不改 source-only `dispatch_manufacturing_integration(export)` 閘門；#2517 OPEN。


> 本文件的 CURRENT 區只描述 **現行 ae_engine 製造架構、公開 API 與 authority boundary**。實際 Corner/Relief 製造公式仍由 Certified Registry 與其 canonical references 擁有；本文件不得複製一套第二公式來源。

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

---
whd_doc_role: CURRENT
whd_contract: manufacturing-architecture
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 🔩 04. WHD 鈑金展開幾何引擎規範（ae_engine）

> 本文件的 CURRENT 區只描述 **現行 ae_engine 製造架構、公開 API 與 authority boundary**。實際 Corner/Relief 製造公式仍由 Certified Registry 與其 canonical references 擁有；本文件不得複製一套第二公式來源。

## [CURRENT] ae_engine Manufacturing / Certified Registry Contract

<!-- WHD_AUTHORITY_ROLE: CURRENT -->

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

### 1.1 GUI → Engine API 單向製造權責 `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1`

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

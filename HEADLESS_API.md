---
whd_doc_role: REFERENCE
whd_contract: project-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Headless Manufacturing API（Phase 6：AE Engine Clean Break）

目的：讓 GUI、自動拆圖、CLI 或其他 Python 程式都使用同一個 AE 出圖入口，不必建立 Tkinter GUI，也不必直接呼叫 `ae.export_xxx_dxf()`。

## Box Body formed mid-surface assembly API (#2517)

`manufacturing_api.resolve_box_body_structure_mid_meshes(render_data, *, thickness)` exposes the existing canonical Engine's physical Box Body piece-local fold and world placement to both 3D FinalScene and Receiving settings 2D inspection. For already-resolved real multipart Box Body material it returns ordered immutable `(source_piece, placed_mid_surface_triangles)` pairs; placeholder-only sources return empty and invalid outside-W provenance fails closed via the existing `resolve_box_body_formed_width_datum`. The 3D compatibility method `phase6_final_scene_projection._phase6_box_body_structure_meshes` now only converts the Engine tuple to its historic list shape; it no longer builds Fold meshes or transforms physical points. The Engine 2D inspector shares the same public seam rather than a second private copy. Real-T physical skins, collision, CUTTING, BEND, DXF, saved material and certified source remain unchanged.

## Shared cabinet model selector API (#2517)

`manufacturing_api.list_cabinet_model_choices(available_baselines=None)` is the
headless, read-only model catalog shared by the main WHD GUI and Fold Designer.
Its baseline sources are read from AE when not supplied explicitly. Resource-backed
金庫型 is listed only when its real baseline exists; the implemented formula-backed
受電箱 is listed without a DXF baseline; unsupported registered families remain
hidden unless a physical baseline model already exists. Custom/自訂 stays last.
The GUI only presents these Engine-returned choices. This is an operator entry
catalog, **not** a new manufacturing, DXF, CADSplit or certification capability.
CURRENT architecture authority stays with AI library 04.


## Assembly physical dimension evidence API (#2517)

`manufacturing_api.project_assembly_physical_dimension_evidence(part, *, thickness)` consumes one already-resolved physical Assembly part and returns immutable `AssemblyPhysicalDimensionEvidence` rows. For real Receiving Box Body left/right SIDE fold profiles, Engine reuses the canonical `apply_outside_dimension_compensation` adjacent-BEND rule (while preserving explicit `formed_length` source). For physical Dividers, it reports the original material extent and saved `fw_physical_face` / `core_physical_segment` outside metadata. `phase6_final_scene_projection._phase6_assembly_physical_dimension_lines` only formats operator-facing Chinese labels and numbers; no physical/BEND arithmetic remains there. Unrelated, missing or empty parts return no rows. This is read-only UI evidence, not manufacturing permission, dimensional overwrite, new CUTTING/BEND/DXF certification or a substitute for approved Registry evidence.

## Receiving settings assembled world mesh API (#2517)

`manufacturing_api.resolve_receiving_settings_assembly_world_meshes(assembly_parts, *, finished_dimensions, thickness, preserve_endcap_core_origin=False)` consumes already-resolved canonical Assembly part DTOs and returns physical source roles, part IDs and actual world XYZ triangles for the 2D inspection path. The Engine alone computes Box Body piece-local folding/placement, the same true-T world skins from `build_joint_world_geometry`, physical EndCap mating and thickness projection. `receiving_settings_preview_2d._assembly_world_meshes` forwards only source input and maps raw roles to UI labels; its existing XY projection still calls `project_solid_mesh_xy_outline`. This is read-only visualization evidence, not permission to manufacture, CUTTING, BEND or DXF certification. Legacy incompatible/incomplete geometry remains fail-closed; family/Set/Bay source, saved Features, and official manufacturing data are unchanged.

## Receiving committed NFB physical assembly API (#2517)

`manufacturing_api.resolve_receiving_nfb_assembly_parts(snapshot, parts)`
owns the existing two-stage canonical FinalScene route: first expand actual
two-tier Base Plate blanks with their manufacturing-blocked metadata, then
apply the committed CSV V5 NFB holes to the same physical scene **only** for
a Receiving snapshot with `nfb_config_submitted is True`. Draft, single-tier,
identity-drift and incomplete manufacturing sources retain all existing
fail-closed behavior. The Engine tier builder now uses immutable
`dataclasses.replace(root, ...)` rather than importing a Phase6 GUI part
class; concrete part type and output shape remain identical. No new NFB
pitch, hole position, EAR, CUTTING/DXF or certification rule is invented.

## Receiving highlighted Live applied-version provenance API (#2517)

`manufacturing_api.mark_receiving_bays_live_version(layout, role,
set_index, bay_indices)` is the headless Engine state transaction for explicit
operator 即時 Apply. It validates Head, Tail or Inner Door role and exact
physical Set/Bay selection, then unlinks shared applied-version references for
the selected Bays only and commits the canonical empty-string Live marker.
Returns the detached layout, sorted highlighted indices and physical Bay IDs.

This does **not** clear or replace actual saved Hole Editor Features, NFB
source, accepted X evidence, topology or 2D/3D/DXF manufacturing geometry.
The GUI only forwards operator action and marks presentation dirty IDs;
Save→Reload retains the distinct None (never applied) and "" (explicit Live)
version states.

## GUI／引擎權責（2026-10-31）

全域硬閘門 `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1` 的唯一 CURRENT owner 是 AI 庫 `第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`；此檔是 REFERENCE。GUI 全功能只處理操作與輸入，所有製造資料、公式、實體板件、孔位／折展開及 2D/3D/DXF 的 canonical 結果由引擎公開 API 處理。既有舊 GUI adapters 的存在**不代表每個箱型與功能均已完成改造**。遇 API 不支援，回引擎開發／測試或明確拒絕，不許 GUI 私做 fallback。對外 CADSplit Worker `capabilities/prepare/export` 僅宣告實際已驗證與授權的能力。靜態 CI gate：`tools/gui_engine_api_boundary_gate.py`，但它不代替行為契約測試或平台 required status check。


## Canonical resolved physical part materialization API (#2517)

`manufacturing_api.materialize_resolved_manufacturing_parts(parts)` returns
the ordered tuple of existing immutable `ResolvedManufacturingPart` DTOs:
physical part keys, authoritative RenderData, X/Y Fold-profile segment copies,
assembly placement and offset. Phase6 passes already-solved parts, then
receives the canonical Engine result for `ResolvedManufacturingGeometry`,
Relief diagnostics, 2D/3D and DXF consumers. The per-segment mapping copies,
original render references and ordering remain unchanged, and duplicate part
identity still fails at the canonical geometry contract. No second Fold
calculator, changed geometry or new CUTTING/DXF authority is introduced.

## Explicit USER_ADDED Joint physical relief Engine API (#2517)

`manufacturing_api.resolve_manufacturing_explicit_joint_reliefs(parts, joints,
*, finished_dimensions, sheet_thickness, clearance=0, committed_state=None)`
runs the existing seven-stage physical/UV Joint collision, owner selection,
verified-cut application and saved-cut replay in `ae_engine.explicit_joint_pipeline`.
It constructs the physical callback table exclusively from canonical Engine
Joint/Collision/Geometry functions. `phase6_manufacturing_geometry` delegates
and `phase6_explicit_joint_pipeline` is a backwards import-only compatibility
module, not a second solver. Temporary replay uses the incoming frozen
resolved-part dataclass where possible, otherwise an equivalent headless DTO;
Engine never imports Phase6 FinalScene/Tk. Existing USER_ADDED provisional 3D
status, failed/partial rejection, diagnostics and Save→Reload ownership are
preserved. This move does not grant new CUTTING/DXF certification.

## Manufacturing Relief rule traces and Joint diagnostics API (#2517)

`manufacturing_api.resolve_manufacturing_relief_evidence(resolved_parts, solutions, joints)`
returns the existing canonical `ResolvedReliefRuleTrace` and
`ResolvedJointDiagnostic` DTOs, owned by Engine instead of Phase6. It
preserves solved EndCap corner order and shadow geometry evidence, Receiving
bottom-WRAP rule metadata, and normal Joint registry ownership/trust/contact
diagnostics. `USER_ADDED` diagnostics remain owned by the separate explicit
Joint relief pipeline; Phase6 only composes that pipeline's returned records
and Family divider records with these Engine DTOs for GUI display. No new
physical geometry, certification or 2D/3D/DXF manufacturing authority.

## Fold Designer physical Divider / inner-door selection API (#2517)

`manufacturing_api.resolve_fold_designer_divider_part(part_key, divider_input)`,
`resolve_fold_designer_frame_part(part_key, payload, *, default_thickness)`,
and `resolve_fold_designer_panel_part(part_key, payload)` select existing
authoritative Box Body Divider, inner-door frame or panel by physical stable ID.
The Engine performs complete Family/Topology derivation and rejects stale or
unavailable part IDs; the GUI only normalizes operator Divider fields, forwards
current snapshots, then displays the Engine-produced render. The existing
Family dimensions, Fold and baseline/3D/DXF rules are unchanged. These APIs
do not certify a previously unsupported part or complete #2517.

## Canonical AssemblyJoint manufacturing graph API (#2517)

`manufacturing_api.resolve_manufacturing_joint_graph(input_snapshot,
available_part_keys)` owns existing schema migration, physical membership
filtering, unplaced custom-joint fail-closed policy and canonical
`ResolvedAssemblyGraph` validation used by assembly 3D and EndCap relief.
Phase6 passes saved input and available physical part identity without
duplicating Joint selection, migration, provenance or topology. Approved
Assembly Intent, explicit historical Joint edges and Registry remain the only
authorities. No new Joint geometry or CUTTING/DXF grant is introduced.

## Headless EndCap assembly relief solve and diagnostic API (#2517)

`manufacturing_api.solve_endcap_assembly_relief(body_part, endcap_part, *,
finished_dimensions, sheet_thickness, clearance, assembly_intent,
assembly_graph, cabinet_family, allow_3d_fallback)` owns the existing
World-backprojected EndCap physical relief call. The Engine consumes actual
Box Body and Head/Tail render data, Fold X/Y, placement and approved inputs.
`manufacturing_api.endcap_relief_solution_diagnostic(solution)` owns verified,
certified-with-shadow-conflict and unverified physical error classification;
existing Chinese diagnostics are unchanged. Phase6 supplies already-resolved
operator inputs and displays these results; the Engine's atomic Head/Tail
commit and canonical PartSpec replay remain the production authority.
No additional CUTTING/DXF approval is implied.

## Atomic EndCap Head/Tail relief commit API (#2517)

`manufacturing_api.endcap_relief_transaction_committable(required_parts, solutions)`
owns the all-or-nothing production decision for the existing Head/Tail
physical relief transaction. It composes the existing certified/verified
single-part Engine policy; a missing required result or empty transaction
fails closed. Phase6 passes immutable required identities and solver results,
then displays the Engine decision without reproducing physical trust rules.
This does not certify new CUTTING, DXF or unverified 3D geometry.

## Verified EndCap relief canonical replay API (#2517)

`manufacturing_api.replay_resolved_endcap_render(part_input, verified_solution)`
replays certified, verified physical relief via the same immutable PartSpec +
ManufacturingContext → canonical `build_part_render_data` used for 2D and DXF.
Only Engine serializes the solver's physical relief polygons and writes them
into a detached `resolved_assembly_relief_cuts` PartSpec. The Phase6 assembly
service only passes the already-resolved inputs: Engine also validates that
canonical material is present and agrees with the solver's physical material
to the original 1e-5 area tolerance before returning it. A preexisting lightweight
headless fallback accepts `solved_render_data` only without a real PartSpec,
and missing fallback rejects explicitly. No new Registry/CUTTING/DXF approval
or independent geometry is introduced.

## Live Cabinet Family identity for assembly manufacturing (#2517)

`manufacturing_api.resolve_live_cabinet_family(input_snapshot, live_model=None)`
is the public Engine owner of operator live-model precedence, registered
Cabinet Family canonicalization and historical unknown/empty-model fallback.
The GUI reads the live selector and saved snapshot without Family decisions;
Phase6 manufacturing service uses the same headless API from its immutable
request. Unknown/custom source names remain unchanged for Family=ANY Joint
compatibility; an empty source retains the existing Vault fallback. This is
identity routing only, not a new manufacturing capability or source geometry.

## Assembly physical material mesh Fold profiles (#2517)

`manufacturing_api.resolve_material_mesh_profiles(part_input, material)` is
now the public Engine owner for request-time 3D assembly mesh X/Y Fold
profile normalization. It retains explicit saved Fold profiles and only uses
already-resolved physical material bounds for the whole Box Body Y span or
missing single axis of divider/inner-door frame material. Invalid bounds are
rejected only if the physical fallback is required. The Phase6 helper is a
compatibility delegation; this API does not certify new 2D/CUTTING/DXF output.

## Receiving NFB candidate source and Bay physical identity API（#2517）

`manufacturing_api.candidate_committed_csv_nfb_config(source)` validates a
single certified CSV-backed inner-door physical source and rejects mixed
untrusted CUTTING. Without CSV source it returns None, never invented holes.

`manufacturing_api.validate_candidate_nfb_replacement(layout, bay_keys, source,
csv_config, *, rejection_message=None)` rejects a non-CSV candidate's
unrelated features when a physical Bay already has submitted NFB.
`manufacturing_api.replace_candidate_bay_nfb(layout, set_index, bay_index,
csv_config)` deep-copies the verified source and scopes stable hole IDs to the
selected Bay. Native GUI single-Bay and quantity allocation share these Engine
ports. Saved source, independent other Bays, and unverified X are preserved;
no new CUTTING, DXF or NFB shop release is implied.

## Receiving NFB Set brand / inherited physical X confirmation API（#2517）

`manufacturing_api.rebase_receiving_set_parent_nfb_brand(set_row, proposed_brand)`
returns a new detached Set row and a changed flag, with no Tk or caller-state
mutation. The existing Engine brand-source check revokes only still-CONFIRMED
inherited physical NFB X evidence when the parent Set brand changes;
explicit override slots, saved model identities and X coordinates remain
unchanged. The Set/Bay GUI adapter selects the Set and commits the returned
row; it no longer inspects physical hole proof state. Invalid brands fail
closed. Existing Save→Reload and physical NFB tests remain the acceptance
oracle; this does not authorize new CUTTING or DXF.

## Live manual CornerType policy（#2517）

`manufacturing_api.resolve_live_corner_policy(state_map, part_key, fw, *, model_name=None, cabinet_family=None)` 將原本 `gui.py::_manual_corner_policy` 的即時手動狀態與已知 Family／自訂預設交給 Engine。明確編輯維持既有 typed CornerType（包含尚未遷移的 C02 rotation）並使用 Engine `policy_from_corner_state`；缺少手動狀態時，已知箱型由 Certified Registry 載入預設，自訂由 Engine `new_manual_corner_state` 設定原有 CROSS 標準預設。GUI 只傳狀態與 Family；此步不改 Registry、CUTTING、FinalScene 或 DXF 認證。與先前保存 payload 的轉換函式是**不同入口**，避免把手動 C02 強制套用另一種正規化規則。

## CornerType payload → 製造 Policy（#2517，非標準 Fold PR）

`manufacturing_api.corner_policy_from_payload(corner_state, part_key, fw, *, known_family=None)` 在無 Tk 的 Engine 內解析已保存的四角 `CornerTypeSelection`／raw row，並交給現有 `policy_from_corner_state` 建立正式 `FourCornerTypePolicy`。舊 C01–C04 typed input 沿用 Engine `normalize_corner_selection`；完整操作者選擇優先。缺角且由已知箱型提供 `known_family` 時，回到既有 Certified Registry 的已知 CornerType；未知／自訂不允許拿金庫型的 fallback。無來源時回傳 `None`，無效型別拋錯而非虛構加工資料。

GUI 的 `_fold_designer_corner_policy_from_payload` 僅為相容代理，`_payload_policy` 的已知 Family fallback 同樣透過公開 Engine API。本改動僅搬責任，**沒有變更任何截角公式、Registry、FinalScene 或 DXF 認證**；標準板件 X/Y Fold 由另一條工作路徑處理。

## Fold Designer 基準孔位（#2517 第一個 GUI API 遷移切片）

`ae_engine.manufacturing_api.query_fold_designer_baseline_rows(part_key, model_name, values)` 接收 Fold Designer 明確的操作者 `w/h/d/t/fw` 與 Door gap/fold 可選欄位；Engine 自行解析 Door/EndCap 正式基準來源、Cabinet Family 物理 FW 與現有 `CUTTING/BLIND_HOLE` 孔中心／尺寸。GUI 只傳 request 與呈現數值，不能從 DrawingScene 重新推導加工孔位。

`ae_engine.manufacturing_api.fold_designer_secondary_scene_rows(scene)` 提供在同一引擎內重用的相容投影；原 GUI 方法僅是直通 alias。無基準、未知盤型或不支援的板件返回空的可選讀取結果；輸入無效或實體來源錯誤的 Engine exception 由原 GUI 讀取入口以空白可選面板呈現，**不得**被視為加工成功、可用的實體出圖或自動 fallback。這項改造只涵蓋 Fold Designer 基準孔位讀取，不代表整個 WHD GUI / 全功能 API 完成。

## 封頭／封尾 Family Bottom FW（#2517 Engine API 移轉）

`ae_engine.manufacturing_api.apply_cabinet_family_endcap_policy(policy, part_key, *, family_source, structure_state, thickness)` 專責對既有 EndCap CornerPolicy 套入可追溯的 Family／Topology 成形下折邊 `bottom_fw`。現有 Receiving 規則沿用 `ae_engine.cabinet_types.policy.effective_endcap_bottom_fw`，不額外創造補償公式；金庫型與其他無此 family capability 的規則不變，操作者 CornerType 選擇保留。

WHD GUI Fold Designer 僅蒐集既有操作者 family、structure、T 輸入並委派 Engine API；此函式沒有啟用新的 DXF 製造 capability，不代表全 GUI API 化或外部 CADSplit 可加工放行。

## Legacy EndCap Fold 重讀／可用頁籤（#2517）

`ae_engine.manufacturing_api.normalize_endcap_profile_order(profiles, snapshot, part_key)` 只在舊 `tail` 四段 canonical Y Profile 重新載入時，依 Engine 已有 `build_endcap_xy_fold_profiles` 恢復原生 Y 順序及 BEND/core/UI metadata；保留原始料長、operator metadata 和所有非標準自訂 Fold。`endcap_editor_fold_tabs(snapshot, part_key)` 由 Engine 依 Assembly Intent 決定 OVERLAY EndCap 沒有 X 折彎頁籤。`phase6_fold_profiles` 保留原介面，只轉呼叫，不再自行整理製造拓樸。兩者不改 DXF/Registry/外部 Gate C 的授權。

## EndCap BOTTOM WRAP Assembly Joint／保存狀態（#2517）

`ae_engine.manufacturing_api.normalize_endcap_bottom_wrap_state(snapshot)`、`resolve_endcap_bottom_wrap(snapshot, part_key, *, state=None)` 與 `commit_endcap_bottom_wrap(state, part_key, *, enabled=None, reserve_u=None, reserve_v=None)` 將原 GUI lower-WRAP 聯動／分離、可調 reserve 狀態改由引擎擁有；`commit_endcap_bottom_wrap_joint(snapshot, part_key, enabled)` 僅透過 Engine AssemblyJoint 規範提交有效 BOTTOM relation。明確 Joint Graph 優先於舊 UI enabled mirror，既有 Family／Registry、違法 relation fail-closed、Save→Reload 不變。Phase6 保留相容名稱作薄轉接，不獨立判斷製造；此 API 不等於對外 Gate C 認證。

## EndCap FW 四態寫入 API（#2517）

`ae_engine.manufacturing_api.commit_box_fw(state, value)`、`commit_endcap_fw(state, part_key, value, *, box_fw=None)`、`set_endcap_fw_follow(state, part_key, follow_box, *, box_fw)`、`set_endcap_fw_override(state, part_key, value)` 由 Engine 按原有 Head/Tail FOLLOW_BODY/FOLLOW_HEAD/FOLLOW_TAIL/INDEPENDENT 與舊檔相容狀態機處理操作者 FW 修改。讀取仍用既有 `normalize_endcap_fw_state` / `resolve_endcap_fw`，實體折邊只由 `build_endcap_xy_fold_profiles` 生成；Phase6 同名入口只轉接，不另作狀態推導或出圖認證。

## EndCap Assembly Intent／CornerType 原始狀態 API（#2517）

`ae_engine.manufacturing_api.endcap_corner_selection_to_raw(selection)` 是現行 CornerType 保存格式的 Engine 投影；`apply_endcap_box_assembly_type_to_raw_state(corner_state, pair_same, type_id, *, reset_bottom_defaults=False)` 使用相同的 Engine Assembly Intent／CornerType policy 修改 Head/Tail 上角，保持手動底角設定，僅在操作者要求 reset 時重設原有 Family bottom defaults。原 `phase6_endcap_semantics.selection_to_raw` 與 `apply_box_assembly_type_to_raw_state` 保持 GUI 相容轉呼叫。這不創造新的角落 CUTTING/Relief Registry 公式。


## 手動 CornerType 編輯交易（#2517）

`ae_engine.manufacturing_api.ensure_corner_part`、`commit_corner_pair`、`commit_corner_type`、`commit_corner_mode`、`commit_corner_parameters`、`apply_corner_preset` 的公開輸入為 JSON-safe `corner_state`、`corner_pair_same`，輸出為 `CornerStateTransition`。既有 Phase6 Settings 寫入語意（成對／拆對、重入、型別切換、參數、固定 Family preset）已原樣搬至 `ae_engine.corner_state_transactions`，原 Phase6 同名函式只相容轉呼叫。這個狀態 API 不決定正式 CornerType CUTTING／Relief；幾何權威維持原 Certified Registry 及 Engine 原有求解器。

## Receiving Family Divider physical Join relief API（#2517）

`ae_engine.manufacturing_api.resolve_family_divider_reliefs(parts, *, finished_dimensions, sheet_thickness, clearance=0.0)` 現由既有 `ae_engine.divider_manufacturing` 負責實際 Receiving Divider ↔ BoxBody 家族 Join Graph、左右實體 side-sheet 世界碰撞皮面來源、每片中隔的 canonical `resolve_divider_final_geometry` Registry CROSS 實體切割解算與 refold shadow validation、已認證/暫定證據及不合法穿透報告。世界／UV 由已遷入 Engine 的 `build_joint_world_geometry` 統一生成；缺少實體側板幾何不得假稱合格。Phase6 `_phase6_resolve_family_divider_reliefs` 只 forward 公開 API；正式 DXF 與 CUTTING 仍以同一 verified physical result 決定，不建立第二份 Divider relief 公式。

## Explicit Joint 已驗證 CUTTING material 套用 API（#2517）

`ae_engine.manufacturing_api.apply_verified_joint_cut_to_part(part, cut_polygon)` 與 `apply_verified_joint_cut_to_owner(part, owner_key, cut_polygon)` 在既有 Engine `assembly_collision` 擁有已驗證 Joint relief CUTTING 的實際 `material.difference`、canonical FinalScene CUTTING／BEND 重建、`PartRenderData` 及 BoxBody 分片角色精確更新／exploded preview。此 API 只能接收經 `Certified Registry` 或有驗證／來源證據的 bounded Joint pipeline 傳入之 cut，不能將 renderer／probe 變成 cut 權威。Engine 以 dataclass `replace` 保留原呼叫端已解析的 part metadata、placement、尺寸與 Fold profile，無需也禁止 import GUI 的 `AssemblyScenePart`。Phase6 同名函式僅 forward Engine，原合法 material、錯誤及保存行為不變。

## Explicit Joint verified cut Save→Reload geometry API（#2517）

`ae_engine.manufacturing_api.serialize_joint_relief_polygons(geometry)` 與 `restore_joint_relief_cut_geometry(item)` 現由 `ae_engine.assembly_collision` 擁有，供 bounded Explicit Joint pipeline 輸出已驗證 CUTTING 多邊形外框、JSON/P6FOLD 保存及依先前 source-proof 檢查後重讀重播；不可把 UI preview 當正式 CUTTING。遵守舊格式 exterior ring 去重端點、每片 polygon 至少 3 頂點、空／非 Polygon 忽略、無效多邊形既有 `buffer(0)` 修復及 `unary_union`，不新增 manufacturing relief、材料補償或新的 cache permissiveness。Phase6 原兩個函式僅是公開 Engine API 相容 adapter，`joint_relief_state_item_matches` 繼續拒絕舊來源漂移、bool、NaN/Inf。

## Joint Solver 3D world mesh／flat UV single authority（#2517）

`ae_engine.manufacturing_api.build_joint_world_geometry(parts, finished_dimensions, sheet_thickness)` 接收 Engine 已解析的實體板件／真實 Fold profiles／material／3D assembly placement，從 canonical `ae_engine.assembly_geometry` 產生供 Joint Solver、collision/backprojection 使用的 `flat_material_by_part`、`mapped_skin_triangles_by_part`、`world_triangles_by_part`。多片 BoxBody 只有各單獨 side/back 實體料的平面 UV；整體 `box_body` 只聚合世界座標碰撞皮面，**不得**創造跨板共用的假平面料圖。Side FW formed outside、末端多段折邊及 Receiving 左側 zl1 使用 Engine `assembly_geometry_folded_mesh` 已有的公開實體幾何運算，不從 GUI 反算。原 `phase6_manufacturing_geometry._phase6_build_joint_world_geometry` 僅向 Engine API 轉發，保留既有 bounded Explicit Joint pipeline 和 Family Divider 接線及 2D/DXF 正式來源。

## Assembly Joint Certified Registry diagnostics API（#2517）

`ae_engine.manufacturing_api.joint_registry_diagnostic_info(joint, render_by_part, solution_by_part)` 由 canonical `ae_engine.assembly_joint` 判定 BOTTOM WRAP Certified rule evidence、BOTTOM 無特殊 delta 的 STANDARD、其他 edge 的 solution trust/rule/revision/probe diagnostic 與 UNKNOWN。若證據缺失不能把 MISS 當成 HIT；影響切割權威的 `rule_id`／`revision`、pre/post pair counts 及 shadow evidence 維持原 Engine Registry 來源。Phase6 原函式只轉公共 API，GUI 僅顯示解讀結果，不另發明 manufactured status。

## Explicit Joint Relief physical UV owner / source proof API（#2517）

`ae_engine.manufacturing_api.resolve_box_body_piece_solver_key(body_part, region, *, require_flat_uv)` 將 BoxBody 的 Joint region 連接至真正 side/back 物理板件，無單一 UV 所有權時拒絕 relief 回投。`side_wrap_target_corners` 由 Engine 判定 Head/Tail 的物理 WRAP 邊角；`joint_relief_state_item_matches` 比對真實 source material bounds／area 和 joint_id／relation／verified，拒絕 NaN／Inf／布林及失效保存切割。Phase6 的三個原函式是公開 API 轉接，不再重算製造規則。

## BoxBody 側板 formed skin 與末端折邊世界座標 API（#2517）

`ae_engine.manufacturing_api.expand_box_body_fw_world_mid`、`shift_multistage_terminal_fold_world_mid`、`fit_receiving_left_zl1_world_mid` 由原 Phase6 Joint/world collision 映射實作原樣搬回 `ae_engine.assembly_geometry_folded_mesh`，以現有同一物理 piece Fold profile、D-core 世界中面、已展開平面 UV、T 及 formed_length 決定 **collision / 3D physical skin**，不以 preview 或固定 Z 座標製造另套結果。GUI `phase6_manufacturing_geometry` 三個函式僅轉呼叫 Engine；原 Joint Solver v2 的 mapped skin/UV 輸出、2D/DXF CUTTING 來源與覆寫限制保持不變。

## Assembly Scene placement API（#2517）

`ae_engine.manufacturing_api.resolve_scene_assembly_placement(snapshot, part_key)` 是原 Phase6 製造裝配位置分派、現有 Vault 門格 legacy 規格、受電箱 topology-derived 門格／內門／隔板／底板及舊專案已保存 divider offset 的唯一公開 Engine 入口。真正 Receiving/Bay placement 仍由既有 `ae_engine.assembly_placement.resolve_assembly_placement` 原生 resolver 產生，無第二份座標公式。`resolve_legacy_door_cell_scene_placement` 保存舊 Vault 門格的正式 (W/H) 原始座標語意，拒絕 bool、非有限外框及不存在門格；從 GUI `phase6_manufacturing_geometry` 移走計算與 fallback 分派，原 Phase6 函式保留同名相容轉呼叫。舊式 assembly workspace offset 仍按原格式檢查，實體固定板未有核准焊接 Z 時保持 standalone，不偽稱已取得製造裝配授權。

## BoxBody 實體分件 Fold 編輯投影 API（#2517）

`ae_engine.manufacturing_api.box_body_piece_editor_profiles(render_data, snapshot=None)` 以 Engine 已解析的 `BoxBodyStructureRenderData.pieces`（含實體物理角色、正式 Fold segment、材寬與 formed dimensions）產生各子板 `X/Y` 編輯／Save→Reload 投影，原右側板反向 traversal 的實際 BEND ownership 與舊 Receiving 左側板 source-order inverse 在同一 `ae_engine.box_body_editor_readback` owner，`reverse_box_body_fold_traversal` 同時供編輯寫回使用。舊 `fold_designer_bridge` 同名函式均只轉呼叫 Engine 公開 API。GUI 不得重算實體長度、反推出其他幾何或以 2D preview 取代正式製造資料。

## 箱身分片數值寫入 API（#2517）

`ae_engine.manufacturing_api.apply_box_body_structure_numeric(state, type_id, field, value, *, total_w, outside_family=False)` 是 BoxBody 二片／三片分配、接合折邊、側背後折邊、後板補償與避讓參數的唯一 Engine 製造狀態寫入。既有 `ae_engine.box_body_structure_state` 持有尺寸守衛、W 互補、OUTSIDE/MATERIAL、負避讓拒絕及 canonical Save→Reload 結構；`phase6_settings_transitions.apply_box_structure_numeric` 僅轉呼叫公開 API，GUI Controller 只套用結果，不重新實作規則。

## Family／型號切換製造狀態 API（#2517）

`ae_engine.manufacturing_api.plan_cabinet_family_model_transition(new_model, old_model, *, ...)` 接收使用者選擇的 Family、既有 snapshot/Corner/BottomWrap/Structure、可用板件及 Settings 值，回傳 `FamilyModelPlan`、`FamilyModelTransition`。唯一 Engine owner `ae_engine.cabinet_family_model_transition` 保留原 Family 切換全鏈：Registry Family 預設、金庫／受電箱固定角落、受電箱 fresh Set1/Bay1 及 CURRENT CSV NFB 特徵來源、Door-cell/Inner Door topology、EndCap Assembly Joint/BottomWrap 與 BoxBody 結構狀態。相同 Family 別名切換不得誤清操作者既有資料；跨 Family 正式切換才重置受控狀態。Phase6 `family_model_transition` 只負責 API request forward，原 Settings Controller 負責將回傳 plan 套用到 workspace／UI。

## Assembly Intent 寫入交易 API（#2517）

`ae_engine.manufacturing_api.commit_assembly_intent_state(input_snapshot, corner_state, corner_pair_same, type_id, *, available_parts=(), project_legacy_corner=False, reset_bottom_defaults=False)` 是 GUI 與 headless 共用的唯一寫入入口，傳回 `AssemblyIntentTransition`（包含 canonical `assembly_type`、`assembly_joints`／schema、JSON-safe 舊 CornerType mirror）。`normalize_assembly_type` 使用正式 Registry 驗證，但仍保留舊 GUI 三種 enum／包覆貼外字串回傳。`available_parts` 是當次 Joint Graph 投影上下文，不能寫入原專案 existing_parts；正式下方 WRAP 仍只由 Engine Assembly Joint Graph 決定。Phase6 `assembly_intent` 和 `normalize_assembly_type` 只轉接 API，原 Settings controller 操作入口不變。

## EndCap 舊 Assembly Intent CornerType 投影（#2517）

`ae_engine.manufacturing_api.legacy_endcap_corner_projection_for_intent(value)` 先以正式 Assembly Intent Registry 驗證，再把 `WRAP_OVERLAY` 的舊 Head/Tail CornerType mirror 投影為 `OVERLAY`。正式 BOTTOM WRAP 仍由 Assembly Joint Graph 決定，沿用現有 `apply_endcap_box_assembly_type_to_raw_state` 公開 API；Phase6 只轉接，不建立第二個 serializer 或物理公式。

## 公開入口

```python
from ae_engine.contracts import ManufacturingContext, DoorPartSpec
from ae_engine.manufacturing_api import generate_part

spec = DoorPartSpec(
    width=500,
    height=600,
    thickness=2.0,
    frame_width=25.0,
    model_name="金庫型",
    features=(),  # finished-face 1:1 mm Feature / legacy feature dict
)

result = generate_part(
    spec,
    r"D:\輸出\加工圖\門-展開.dxf",
    ManufacturingContext(
        resource_root=r"D:\拆圖專案",  # 這裡底下有 基準檔\
        overwrite=True,
        draw_stock=False,
    ),
)
```

## PartSpec

目前支援：

- `DoorPartSpec`
- `BoxBodyPartSpec`
- `EndCapPartSpec(is_tail=False)`：封頭
- `EndCapPartSpec(is_tail=True)`：封尾
- `BasePlatePartSpec`
- `IndicatorBoxPartSpec`

指示燈小門沿用 `DoorPartSpec(model_name="指示燈")`，由 API 自動選 `基準檔/指示燈/小門.dxf`。

Feature 座標契約不變：**finished-face 上的 1:1 mm 實體座標**。API 不接受 Canvas pixel、normalized coordinate 或展開料座標作為來源加工座標。

## GUI Adapter（第二階段已完成）

GUI 的 DXF 出圖現在固定走：

```text
Tkinter state
→ GUI adapter helper
→ immutable PartSpec
→ manufacturing_api.generate_part()
→ existing AE exporter / resolver
→ DXF
```

`gui.py` 的出圖方法不再直接呼叫任何 `ae.export_*`。`ae` 仍可被 GUI 預覽與基準讀取邏輯使用，但**製造輸出入口只有 manufacturing_api**。

目前 GUI adapters 包含：

- Box Body（含 left/back/right face feature ownership）
- Head / Tail（完整保留 H、Y 折邊與 Z-side fold 參數）
- Single Door
- Multi-Door per-cell Door
- Base Plate
- Single / Multi Indicator Box
- Single / Multi Indicator Door

## Baseline 規則

- Door：存在 `基準檔/<model>/門.dxf` 時自動使用 stretched exporter；不存在才 formula fallback。
- `model_name="指示燈"` 的 Door 使用 `小門.dxf`。
- End Cap：存在 `封頭尾.dxf` 時使用 stretched exporter；不存在才公式 fallback。
- Box Body：主 CUTTING/BEND 永遠由 StripFoldChain 公式生成；如果存在 `箱身.dxf`，由既有 Box Body exporter 載入固定孔 / MARKING 等基準特徵。
- Base Plate / Indicator Box：目前沒有 model baseline dispatch，直接走既有 authoritative exporter。

## Resource Root

`ManufacturingContext.resource_root` 告訴 Adapter：

```text
<resource_root>/基準檔/
```

在哪裡。這讓 AE 程式放在 `modules/` 時，不需要再複製第二份 `modules/基準檔`。

GUI standalone 目前使用 `resource_root=None`，因此沿用 AE 既有 standalone / PyInstaller 資源搜尋；拆圖端未來會明確傳入拆圖專案根目錄。

## Factory Policy（第四階段）

`ManufacturingContext` 現在可攜帶 `ManufacturingPolicy`。Automatic bridge 不再 import `ae` 讀取 FW/T/gap/fold；它只透過：

```python
policy = manufacturing_api.resolve_policy(context)
```

取得同一次出圖要使用的 policy snapshot，並把 snapshot 放回 Context。Policy 目前正式包含：

- default thickness
- frame width (FW)
- Door gap W/H
- Door fold L/R/T/B
- Indicator Box fold
- Indicator small-door fold

若 caller 未注入 policy，`manufacturing_api` 才在 API 邊界從 wrapped AE Core 讀取現行 Factory Policy。外部 Adapter 不得直接讀 `ae.T` / `ae.FW` / `ae.*_def`。

製造公式也集中在 API helper：

- `door_finished_face_size()`
- `door_indicator_offset_for_finished_center()`
- `indicator_box_opening_feature()`
- `indicator_small_door_spec()`
- `indicator_small_door_operator_spec(groups, *, thickness, frame_width, door_gap_w, door_gap_h, indicator_door_fold=None, features=())`: returns `(DoorPartSpec, ManufacturingContext)` using the same Factory Policy and canonical small-door source; GUI cannot compose a manufacturing policy or infer small-door size. Defaults use existing Engine `indicator_small_door_fold_def`. Does not certify any new DXF manufacturing capability.

因此 automatic bridge 只保留來源 ownership、finished-face extraction、replacement semantics 與 Feature validation。

## Atomic Overwrite

`generate_part()` 不直接覆蓋舊 DXF：

```text
export → 同目錄 temp DXF → exporter 成功 → os.replace() → 正式檔
```

若 exporter 中途失敗，舊加工圖保持不變。

## 拆圖端第三／四階段接法

拆圖端維持原責任：

```text
finalized info_data + finished-face Feature
                     ↓
              split-side Adapter
                     ↓
                  PartSpec
                     ↓
             generate_part()
                     ↓
                    DXF
```

拆圖端保留 source ownership、physical feature、selector、替換 CSV、LOG、snapshot、PermissionError 與 finalized `info_data` 等責任；不把這些搬進 AE Core。

## Phase 6：最終 Clean Break

目前正式結構只保留一份製造核心：

```text
ae_engine/
├─ ae.py
├─ contracts.py
├─ manufacturing_api.py
├─ sheetmetal_geometry.py
├─ sheetmetal_features.py
├─ sheetmetal_part_adapters.py
├─ sheetmetal_drawing.py
├─ hole_catalog.py
└─ cabinet_types/
```

不再提供任何根目錄或 `modules/` compatibility shim。`ae_engine` 內部也只允許 package-relative import。

拆圖專案自己的來源 catalog 已正式改名為：

```text
modules/automatic_hole_catalog.py
```

它持有 `開孔.csv` / `管孔尺寸清單.csv` / `自動開孔替換.csv`、source lookup、replacement parser 等拆圖責任，**不屬於 AE Core，也不得被 AE 更新覆蓋**。

未來 AE 更新唯一標準動作：

```text
AE 專案/ae_engine/
        ↓ 整個資料夾覆蓋
拆圖專案/ae_engine/
```

不再複製單一 `.py`，也不再合併 `modules/ae.py`。

`RO / 落地盤` 已保留 `ae_engine/cabinet_types/ro.py` 與 registry dispatch；目前 `implemented=False`，代表尚未加入未確認的 RO 製造幾何。


## 測試環境：Headless 與 Xvfb 不可互相替代

- `env -u DISPLAY pytest ...` 只驗證 **pure/headless contract**。需要 Tk 視窗的測試在沒有 `DISPLAY` 時必須被標記/辨識為 `SKIP`，不得把 `TclError: no display name` 計為 production failure。
- 正式 GUI release gate 必須在有效的 X display（建議 Xvfb）下執行；有 `DISPLAY` 時 `requires_tk_display` 不會 skip，Tk 測試必須真正建立 GUI 並跑完。
- 中央規則位於 `tests/conftest.py`：新 GUI 測試應使用 `@pytest.mark.requires_tk_display`；舊測試若漏 marker，只在 `DISPLAY` 未設定且錯誤明確是缺 display 的 Tk `TclError` 時相容轉為 skip。其他 Tcl/Tk 錯誤一律維持 failure。
- 因此：**headless PASS ≠ GUI PASS**；正式出包仍必跑 Xvfb GUI suite。

## EndCap live Fold W/D reconciliation (#2517)

`ae_engine.manufacturing_api.endcap_derived_core_lengths(snapshot, width, depth)` and
`reconcile_endcap_live_outside_dimensions(snapshot, *, top_width, top_depth,
previous_width, previous_depth, profiles)` own the canonical Family 4T W / 2T
Receiving or 3T Vault D conversion for live Head/Tail editor sync. Explicit
operator top-panel edits outrank stale Fold rows; unchanged top fields accept
changed material cores. Missing material cores never become invented sizes.
The GUI only reads Tk values, calls this public API, and applies returned
dimensions to existing editor state; this is a compatibility synchronization
contract, not a new DXF/Worker manufacturing capability.


## Fold Designer finished-face feature → legacy renderer（#2517）

`ae_engine.manufacturing_api.project_finished_features_to_legacy_renderer_holes(features, width, height)`
projects immutable Circle/Rect finished-face Features into the original integer
legacy Fold Renderer hole DTO. The Engine's `feature_finished_point` owns hole
coordinates, anchors and offsets; GUI forwards only feature inputs and face
dimensions and displays the result. Profile/custom features are preserved in
the source bundle without inventing circles/rectangles. This compatibility
display projection **is not** a manufacturing approval or a DXF capability.


## Finished part dimension projection / Door-cell topology (#2517)

`ae_engine.manufacturing_api.project_part_dimensions(snapshot)`,
`door_part_projections(snapshot)`, and the immutable `DoorPartProjection`
are the Engine's public headless projection of existing Settings state to
finished physical part sizes and multi-Door cell identities. The original
single-Door calculation, Family material FW, Receiving physical BasePlate
blank and per-cell source frame edges are not recreated by GUI. The existing
`phase6_settings_profile_projection` module re-exports these public Engine
owners as compatibility callables. No new manufacturing formulas, scene or
DXF capabilities are asserted by this refactor.


## Standard part Fold profiles (#2517)

`ae_engine.manufacturing_api.build_standard_part_fold_profiles(snapshot, part_key)`
is the Engine-owned approved X/Y material fold-profile builder for standard
Door (including derived cells), BasePlate, IndicatorBox, IndicatorDoor and
legacy fallback panel contracts. It shares `apply_outside_dimension_compensation`
with the existing Engine fold topology and, for Receiving BasePlate, the
canonical FinalScene-derived physical profile when available. `phase6_settings_profile_projection.build_standard_part_profiles`
is now only a compatibility router: standard IDs call the Engine API; custom
IDs remain dispatched to their separate persisted custom-fold implementation.
Calling the *standard* Engine API on a custom key explicitly fails closed.
This is an incremental ownership migration, not a claim that custom Fold or
DXF production readiness is complete.


## Keyed Fold profile reconciliation (#2517)

`ae_engine.manufacturing_api.merge_keyed_fold_profiles(existing_profiles, default_profiles)`
is the Engine public owner for applying freshly derived canonical material
`len`, `ui_len_add`, and `core` to keyed X/Y Fold rows without overwriting
operator-added (unkeyed or unrelated) Fold segments, their order or bend angles.
A missing canonical key on an axis replaces that axis with detached Engine
defaults; an empty axis also takes defaults. Neither input is mutated. The
Phase6 Settings plan uses only a compatibility delegate and must not rederive
the canonical material or outside compensation. This API by itself is not
DXF/CUTTING certification.


## Derived physical part identity classification (#2517)

`ae_engine.manufacturing_api.is_box_body_physical_piece_key(part_key)`
and `is_derived_physical_part_key(part_key)` are Engine-owned public, pure
classifiers for existing persisted BoxBody physical-piece, Door/BasePlate cell,
Receiving fixing/NFB/Divider, and inner-door panel/frame identities.
The Phase6 Settings planner and operator navigation delegate their identity
decisions to Engine. GUI still controls hierarchy, focus, and selection.
Recognizing an existing ID never authorizes unsupported DXF manufacture.


## EndCap relief manufacturing commit policy (#2517)

`ae_engine.manufacturing_api.endcap_relief_solution_committable(solution)`
owns the existing production-commit decision applied to actual Head/Tail
World-backprojected EndCap relief solutions. Verified solutions commit.
An otherwise unverified result requires both a nonempty certified `rule_id`
and a recognized certified trust status (`CERTIFIED`,
`CERTIFIED_FROM_3D`, or certified formula `ENGINE_CONFLICT`).
An unknown or unverified rule without proof is not committable.
A separate GUI diagnostic can continue to report shadow/3D conflicts;
this predicate does not bypass or perform CUTTING itself.


## Multi-Door hole-editor finished face via Engine (#2517)

The `gui.py::open_door_layout_cell_editor` operation now builds the same
`DoorPartSpec` as per-cell indicator fit/export through
`_door_layout_part_spec(cell, val)`, using the active Receiving Bay's dimensions
when available. Its reference guide and indicator editor consume
`ae_engine.manufacturing_api.door_finished_face_size(spec)`; the GUI must not
compute a second finished Door W/H from `ae.calculate_door_finished_size`.
The public `door_material_frame_width(model, frame_width, thickness)` entry
delegates unchanged to the existing canonical Cabinet Family policy for
legacy GUI spec adapters. Vault/Receiving compensation continues in Engine;
no manufacturing formula, physical part identity, CUTTING, or DXF capability
is created or re-certified by this ownership migration.


## Door-layout Indicator component editor uses Engine geometry (#2517)

The legacy `gui.py::open_door_indicator_component_editor(key, component)`
for `indicator_box` and `indicator_door` now consumes
`ae_engine.manufacturing_api.resolve_indicator_editor_components(
groups, thickness=t, door_spec=typed_small_door_spec)`.
This is the same Engine geometry provider used by Phase6's per-cell Indicator
editor contexts. The GUI only owns operator input, selected physical component,
stored feature lists, presentation labels/baseline status, and feature commit
callbacks. It cannot directly call `ae.get_stretched_indicator_box_data`,
`ae.get_stretched_door_data`, or build finished material/cut guides.

IndicatorBox canonical source is the shared `基準檔/指示燈/盒子.dxf`;
the historical model_name argument to its baseline adapter is ignored by
design. This is an API ownership migration, not a new manufacturing/Export grant.

## Canonical manufacturing pre-scan cache signature (#2517)

`ae_engine.manufacturing_api.manufacturing_state_fingerprint(*, input_snapshot,
settings_values, working_box, corner_state, endcap_fw_state,
endcap_bottom_wrap_state, available_parts, part_profiles, assembly_intent,
ignore_fixed_corner, relief_clearance)` is the Engine-owned public
headless cache-key policy for WHD's actual manufacturing state. This signature
excludes UI typography and persisted/derived mirrors, uses Receiving live
working W/H/D rather than old Settings defaults, and includes real physical
Fold/corner/assembly state. The normalization entry
`canonical_manufacturing_signature_value(value)` preserves legacy
representation equivalence (including numeric precision, unordered sets and
nonfinite fail-closed). GUI gathers operator input only and forwards to Engine;
a cache hit never substitutes for actual FinalScene/Save→Reload certification.

## Standard physical Fold readback into Settings (#2517)

`ae_engine.manufacturing_api.read_standard_part_fold_profiles(part_key, profiles,
original_snapshot)` is the Engine public reverse-projection owner for existing
standard Door, BasePlate, IndicatorBox and IndicatorDoor material Fold keys.
Its result contains only the corresponding persisted operator fold settings.
Four-edge BasePlate/Indicator folds must agree exactly to supply one shared
Settings value; mismatches raise instead of choosing an arbitrary side.
The real Receiving root BasePlate physical Fold takes precedence: if its
certified source-backed 3D profiles exist, no generic four-edge setting is
backfilled from its BEND. Unknown/custom keys return no standard settings.
The GUI `phase6_manufacturing_adapter` only forwards the same profiles and
snapshot; it does not perform a second material or identity interpretation.


## EndCap Head/Tail stored Fold reconciliation by Assembly Intent (#2517)

`manufacturing_api.endcap_profiles_for_assembly(values, stored_profiles, assembly_type, part_key)`
reuses Engine `build_endcap_xy_fold_profiles` and the canonical
`normalize_assembly_intent_id` to return physical X/Y Fold source rows. For
OVERLAY, Head/Tail X has no left/right bend even without stored profiles; for
INSERT after a stored flat X the current Family-generated X is restored.
Custom/stored Y and independent Head/Tail scene order remain preserved.
No stored INSERT profiles still return `None`, retaining legacy renderer
fallback semantics. GUI `_endcap_profiles_for_assembly` simply forwards
operator inputs. No Registry/CUTTING/DXF capability is created or granted.


## Live operator finished-dimension source precedence (#2517)

`ae_engine.manufacturing_api.resolve_live_operator_finished_dimensions(part_key,
*, input_snapshot, settings_values, working_box, triangles,
head_corner_policy, tail_corner_policy)` is the public headless
Engine entry for the previously Phase6-owned sparse snapshot and Receiving
live working W/H/D preference. Explicit snapshot fields are not overwritten
during sparse fill, while Receiving's live Bay/Quantity working W/H/D take
precedence over seed Settings values exactly as before. The function then
delegates to the existing Engine `resolve_operator_finished_dimensions`
for canonical Fold/Corners/finished physical 2D/3D dimensions; invalid world
mesh is still rejected. The GUI reads input state, forwards policy DTOs
and displays the result only. This is not a new CUTTING/DXF capability.

## Custom physical sheet Catalog and single-axis Fold manufacturing (#2517)

Engine `manufacturing_api.CustomPartCatalog` owns stable physical IDs,
nonrecycled `custom:N` allocation, fail-closed metadata, and defensive
snapshots. `is_custom_part` and `custom_part_only_change` are also
public Engine policy. For actual manufacturing, headless
`manufacturing_api.descriptor_from_snapshot(snapshot, part_key)`,
`build_custom_part_profiles(snapshot, part_key)`, and
`custom_part_spec(snapshot, part_key, *, features=(), profiles=None)`
own one-axis X/Y outside 17/100 → canonical material Fold with adjacent
bend-count × T compensation and the transverse flat span. GUI/Phase6
modules only re-export these public Engine functions as compatibility
entry points; no GUI-owned custom physical formula or allocator remains.
Existing verified CustomFold PartSpec → FinalScene → CUTTING/BEND → DXF
worker acceptance remains separate; this move never authorizes
unsupported features, mismatched physical metadata or new DXF capability.

## Receiving Inner Door cross-Set/Bay quantity allocation transaction (#2517)

`manufacturing_api.apply_receiving_inner_door_quantity_configuration(
layout, library, quantities, assigned, *, expected_counts=None)`
is the headless manufacturing-state Apply for all selected Receiving Bays.
It validates exact topology/counts/version assignment and each candidate's
physical CSV NFB source, mixed CUTTING and replacement permission **before**
any write. It commits the same canonical per-Bay shared setting values,
version IDs and Bay-qualified physical NFB source as the previous GUI path,
and returns `(detached_layout, changed_bay_stable_ids)`.

The GUI uses the result only to set its current layout and update dirty
presentation IDs. Failure leaves its layout and saved candidate library intact.
Saved NFB X remains unverified; no new CUTTING or DXF capability is granted.

## Receiving Head/Tail candidate quantity allocation Engine API (#2517)

`manufacturing_api.apply_receiving_endcap_quantity_configuration(
layout, role, library, quantities, assigned, *, expected_counts=None)`
is the headless manufacturing-state transaction for every Receiving Set/Bay.
The Engine validates Head/Tail candidate version identities, exact topology,
counts and explicit assignments before updating canonical shared feature
settings and the persisted applied version IDs. The return value is
`(detached_layout, changed_physical_bay_stable_ids)`, so invalid or stale
operator assignments cannot partially update a Bay.

The GUI only supplies operator selection and displays/marks the resulting
changes. Head and Tail are independent; no NFB source, DXF certification
or new Hole Editor CUTTING geometry is inferred by this API.

## Receiving Head/Tail highlighted candidate Apply Engine API (#2517)

`manufacturing_api.apply_receiving_endcap_candidate_to_bays(
layout, role, set_index, bay_indices, features, *, version_id=None)`
validates operator Head/Tail candidate Features, version ID and exact selected
physical Bay indices (bool, missing, out-of-range and unhashable selections
are rejected) before updating one detached canonical Receiving Layout. Engine
unlinks shared features/version refs for only the selected Bays and returns
`(detached_layout, sorted_selected_indices, physical_bay_stable_ids)`.
Other Bays/Sets and the other Head/Tail role stay unchanged, including existing
Hole Editor source geometry. GUI only forwards and records UI dirty IDs.
No new CUTTING, DXF or certified Registry manufacturing capability is granted.

## Receiving single inner-door candidate Apply to selected Bays (#2517)

`manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
layout, config, set_index, bay_indices, *, version_id=None)` applies one
source-backed candidate (distinct from cross-Set quantity allocation).
Engine validates all selected physical Bays, exact candidate settings, CSV NFB
provenance and existing submitted CUTTING ownership before committing
canonical shared settings, version and Bay-specific physical hole IDs. Returns
`(detached_layout, sorted_bay_indices, physical_bay_stable_ids)`.
GUI only forwards input and displays/records the returned state; invalid input
never partially commits. Saved manual NFB X remains unverified and the API
does not authorize new DXF/CUTTING manufacturing.

## Receiving W/H/D multi-Bay operator batch Engine transaction (#2517)

`manufacturing_api.apply_receiving_bay_dimensions(layout, set_index,
bay_indices, *, width, height, depth, expected_count)` returns a detached
canonical Receiving layout and exactly the physical Bay IDs whose W/H/D
changed. It rejects incomplete/invalid highlighted physical selections and
non-finite dimensions before staging, preserves authored leading Door
partitions using the canonical Engine `complete_partition`, and revokes
previously CONFIRMED NFB physical X evidence on width changes using
`reconfirm_copied_nfb_config`. One batch validates the entire layout exactly
once; no-op performs no normalization. GUI only commits the returned layout
and updates operator dirty UI state. No new CUTTING/DXF approval is granted.

## Receiving new Bay dimensions from Family Engine owner (#2517)

`manufacturing_api.resize_receiving_bays_with_family_defaults(layout, *,
set_index, bay_count)` is the public headless resize for the Receiving
operator client. Canonical `resize_receiving_bays` creates persistent Bay,
Joint and shared-setting identities. Newly appended Bays **only** receive the
current Receiving Family's W/H/D defaults through the existing Engine
`apply_receiving_bay_dimensions`, preserving any authored dimensions of
pre-existing Bays and the canonical partition/NFB-X invalidation contract.
Shrinking uses the same canonical tail-only resize; GUI alone handles
destructive confirmation, selection and dirty UI bookkeeping. Source-only
low-level `resize_receiving_bays` retains its old copy-by-value semantics.
No new manufacturing DXF/CUTTING authority is introduced.

## Door-layout deletion physical identity and feature-source remap (#2517)

`manufacturing_api.receiving_inner_door_stable_id_for_cell(cell_key)`
is the Engine-owned persisted physical inner-door ID resolver
(`0:0=upper`, `0:1=lower`, other cells `cNrN`).
`manufacturing_api.remap_receiving_door_layout_after_delete(
*, operation, column_index, row_index=None, inner_doors=None,
cell_sources=None, physical_sources=None)` is a pure headless transaction
for deletion of a Door grid row/column. It stages the new physical inner-door
identity list, keyed per-cell input stores, and detached physical feature
snapshots for the main 2D surface, Workspace and Fold Designer (including
per-face features) before exposing any result. It moves existing panel-hole
keys and rebuilds `door_cN_rN` feature owners; conflicting physical source
identities reject the entire transaction. GUI only forwards the operator
deletion and applies returned workspaces, never generates physical part IDs.
No source transformation certifies CUTTING/DXF manufacture.

## Door-grid numeric partition and edit validation Engine API (#2517)

`manufacturing_api.recompute_door_layout(columns, *, total_width,
total_height, selected_key)`, `door_layout_cells(columns, *, total_width,
total_height)`, `validate_door_layout_width_commit(columns, column_index,
total_width, current)`, and `validate_door_layout_height_commit(columns,
column_index, row_index, total_height, current)` are the public headless
Engine ports backed by `ae_engine.door_layout_numeric_transitions`.
The same authoritative 0.01 mm partition completion, preserved authored
fixed cells, auto-remainder retention, physical cell index checks, finite
positive W/H validation and canonical cell projection apply in GUI and
headless paths. The existing GUI DoorLayoutController signatures remain
compatibility forwarding adapters; Tk variables, operator selection and
presentation effects stay in GUI. No new DXF/CUTTING authorization.

## Receiving Base Plate operator physical preflight (#2517)

`manufacturing_api.validate_receiving_base_plate_settings(
*, input_snapshot, settings_values, config)` is the public headless Engine
entry for validating a real selected Receiving Base Plate before GUI commit.
It stages an immutable source probe, reuses
`receiving_base_plate_blank_dimensions`, canonical
`build_receiving_base_plate_result`, and the existing welded-EAR
physical slot/pitch guard. A mismatch of CENTER vs LEFT/RIGHT geometry
fails before project mutation. `None` is a deliberate settings reset,
not an inferred manufactured blank. The GUI only submits the detached
validated selection and rolls back its project state if the external
geometry update callback fails. No new DXF/CUTTING authorization follows.

## Receiving Switch operator topology public Engine transaction (#2517)

`manufacturing_api.normalize_receiving_switch_operator_layout(layout)`
and `manufacturing_api.apply_receiving_switch_operator_action(layout, *,
operation, brand=None, layer_index=None, delta=None)` publicly expose the
canonical `receiving_switch_layout` state transitions. Supported actions
are `set_brand`, `add_layer`, `remove_layer` and `resize_connections`.
The Engine owns stable layer IDs, tail-only resize, brand validation,
index/type safety, and the >=1 layer/connection lower bounds. Results are
`(detached_layout, changed_flag)`, never manufacturing approval. GUI
adapters only parse literal operator input and commit the Engine result.
No fabricated NFB opening, CUTTING, or DXF release is implied.



## Original Fold Designer snapshot part dimensions Engine API (#2517)

`manufacturing_api.project_fold_designer_snapshot_dimensions(snapshot,
indicator_layer_groups)` returns `FoldDesignerSnapshotDimensions` with the
seven legacy root part sizes and normalized Indicator groups. The GUI only
reads control values and submits the unchanged operator snapshot; canonical
Door finished-face size, physical Receiving Base Plate blank size, and shared
Indicator Box / Small Door unfolded sizes are Engine-owned. Existing invalid
Indicator controls retain the historical single-group display fallback, never
manufacturing/DXF authorization. Distinct multi-door cell identities remain
owned by `project_part_dimensions`, not this legacy root overview. This is a
move-only ownership change; existing geometry/Save→Reload policy is unchanged.



## Original Fold Designer Door-grid Feature ownership Engine API (#2517)

`manufacturing_api.project_fold_designer_snapshot_part_features(snapshot,
surface_features, door_layout_features)` is the pure headless ownership seam
for operator-authored Door cell Features and formal physical part identities.
It uses the existing canonical `door_layout_feature_map_to_part_features`
for `door_cN_rN` IDs and `col:row` content; the Engine preserves the exact
saved-part merge rule: edited empty cells clear stale features, unedited
cells retain saved content, and legacy tuple cell keys only signal authored
empty clears. GUI only submits source stores and copies returned Features
into the original Save/Reload schema. No hole coordinate transform,
manufacturing CUTTING/DXF authorization or new geometry is introduced.


## FinalScene canonical Fold profile 3D mapping Engine API (#2517)

`manufacturing_api.fold_profile_base_index`,
`fold_profile_geometry(profile, *, enabled_folds=None)`,
`fold_profile_bend_mask(profile, axis, cross_position, fold_guides, *, tol=1e-6)`,
`fold_profile_map_with_guides(position, cross_position, profile, *, axis, fold_guides)`,
`fold_profile_map(position, boundaries, folded)` and
`fold_profile_flat_map(position, boundaries, *, profile=None)` expose the
existing authoritative `ae_engine.assembly_geometry_folded_mesh` material-to-formed
cross-section mapping to the FinalScene GUI. Former Phase6 functions are
compatibility delegates, not a second physical Fold algorithm. The engine's
already-established source-owned formed_length exception is preserved while
unfolded BEND stations continue to use physical material length. Finite BEND
guide spans determine local bend activation; unlisted legacy folds retain the
existing enabled behavior. `prepare_fold_profile_mapper(profile, *, axis,
fold_guides=())` returns the canonical source-scoped prepared Engine callable,
using the existing per-mask chain cache rather than rebuilding a Fold for each
visible 3D vertex. A GUI display cache must invalidate when any Fold profile
or source BEND guide changes. No new Fold compensation, 2D CUTTING or DXF
certification follows. #2517 remains OPEN.

## Physical solid-mesh feature edge API (#2517)

`manufacturing_api.physical_solid_mesh_feature_segments(triangles, *,
tolerance=1e-6)` projects real exposed perimeter, hole rims, fold/miter
creases and thickness edges from an already-authoritative thickened 3D
physical mesh, excluding coplanar triangulation diagonals. The engine
implementation `ae_engine.solid_mesh_feature_edges` is the moved original
FinalScene algorithm. GUI `_phase6_mesh_feature_segments` only forwards and
Matplotlib paints returned segments. No redefinition of canonical material,
geometry, CUTTING, 2D/3D certification or DXF capability follows.



## Door operator input → physical DoorPartSpec Engine API (#2517)

`manufacturing_api.build_door_operator_part_spec(values, *, model_name,
features=(), indicator_hole=None, door_indicator=None,
door_indicator_offset=(0,0), use_box_distance=False, corner_policy=None,
frame_edges=None, indicator_window_groups=None,
nameplate_center_datum_top=None)` is the canonical headless source of the
single-door and already-selected door-cell PartSpec. The GUI gathers current
operator inputs only; Engine owns every material request field and the legacy
`feature_space="legacy_unfolded"` export coordinate contract. Existing
DoorPartSpec fields, the caller's physical per-cell edges/size, nameplate
datum, Fold/Corner inputs, and downstream 2D/3D/DXF/Save→Reload remain
unchanged. This API does not approve manufacturing, override Certified
Registry geometry, or create a second physical cell topology. #2517 OPEN.

## Receiving highlighted Set/Bay NFB inner-door partial DXF public Engine API (#2517)

`manufacturing_api.require_highlighted_nfb_inner_doors(ports, set_index,
bay_indices, *, allow_held=False)` and
`manufacturing_api.export_highlighted_nfb_inner_doors(ports, *,
set_index, bay_indices, output_directory, allow_held=False)` are the
headless, Engine-owned operation for current-source-verified Receiving
highlighted Set/Bay **inner-door only** partial export. Existing live
`manifest` and real `partial_export` ports are mandatory; a UI READY
indicator cannot grant authority. The Engine rechecks each physical
Set/Bay/version and inner-door stable ID before publishing, rejects
forged writer manifests or stale source, stages all actual DXFs, forbids
overwriting, and atomically links outputs with rollback on publish failure.
Explicit `allow_held=True` publishes READY sheets only and an honest
held-Bay JSON manifest; unrelated BasePlate/PAD/EAR pieces are never
counted as emitted. The historical GUI import module is only a
compatibility re-export of these public functions. No whole-cabinet
manufacturing, new hole/CUTTING formula, DXF certification, or external
installer capability follows from this move. #2517 remains OPEN.


## Receiving NFB physically reopened pair CHECK/Q public Engine API (#2517)

`manufacturing_api.NfbPairedPartOnlyDxf`, `NfbPairedQuantityInput`,
`NfbPairedQuantityCheck`, `group_reopened_nfb_pair_check_q(inputs)`
and `save_checked_reopened_nfb_pair_q_dxf(checked, output_directory)`
are the headless owners of real current-source inner-door plus BasePlate
**PART_ONLY** CHECK/Q. The Engine requires the typed exporter receipt,
real Set/Bay/version and physical owner IDs, original current source SHA,
matching saved NFB hole metadata, two unchanged DXF reopen comparisons,
positive integer piece counts and actual material/process parameters. It
uses the existing NFB physical gate and geometry-equivalence grouping;
only explicitly verified paired parts can be written with Q, without
overwriting. Neither filename nor cached readiness can grant whole MFG-2,
EAR, PAD or complete-cabinet manufacturing. The old GUI quantity module
and NFB pair output DTO remain compatible imports that alias Engine
objects; no second manufacture/quantity formula exists in GUI.


## Receiving source-current NFB BasePlate PART_ONLY public Engine API (#2517)

`manufacturing_api.nfb_verification_geometry_changed(current, verified)`,
`prepare_verified_receiving_nfb_base_plate(bundle, *, layout, current_snapshot,
base_spec, index_path, profile_path)`, and
`export_verified_receiving_nfb_base_plate(bundle, *, layout, current_snapshot,
base_spec, output_directory, index_path, profile_path)` now own the historical
Receiving NFB original physical BasePlate source checks and real PART_ONLY DXF
operation. The Engine revalidates a signed live submitted Set/Bay/version,
original indexed DXF SHA, exact saved NFBConfig, physical BasePlatePartSpec and
inner-door identity, original upper profile handle/revision, lower fixing
reference and real source-derived holes, before using the existing geometry
composer and atomic DXF writer. The previous GUI base action is a public
Engine API re-export, and the shared geometry-staleness check used by the
inner-door GUI export is also the same Engine function. Existing three Base
Plate bend patterns and positive/negative saved DXF tests stay unchanged.
An individual BasePlate remains **PART_ONLY**, not complete MFG-2,
manufacturing-ready EAR weld, PAD or whole-cabinet release. No new numeric
source, CUTTING formula or DXF certification is introduced.


## Receiving NFB real physical inner-door PART_ONLY export public Engine API (#2517)

`manufacturing_api.export_verified_receiving_nfb_inner_door(bundle, *,
layout, current_snapshot, output_path, index_path, profile_path)` now owns
the original source-current real inner-door **PART_ONLY** DXF export previously
implemented under the GUI operator action. It revalidates the actual
NfbVerifiedDraftSubmission, saved Set/Bay/version and parent switch brand,
source-only original DXF indexed profile SHA/handle/revision, unique physical
upper inner-door panel from current canonical Family, saved physical hole IDs,
confirmed WORLD-X and rotations, before calling the existing Engine
`export_current_nfb_inner_door_partial_dxf` with no overwrite. The single
geometry-staleness fingerprint is already Engine-owned and is shared with
BasePlate and the GUI operation's preview invalidation. The GUI legacy
module now only re-exports these Engine public functions. The prior UI
mock-injection test now patches the canonical Engine implementation without
loosening any negative tests. This grants no middle/base/PAD/EAR, quantity
Q or complete-cabinet manufacturing, nor new CUTTING/DXF certification.


## Receiving native + CSV-V5 paired real DXF public Engine API (#2517)

`manufacturing_api.export_verified_receiving_nfb_door_base_pair(bundle, *,
layout, current_snapshot, base_spec, output_directory, index_path,
profile_path)` is now the Engine-owned original-indexed-source real
inner-door + BasePlate PART_ONLY atomic export. It reuses the exact
live Set/Bay/version, actual base source validator, source-verified inner-door
holes and world X, immutable physical receipt, real FinalScene and existing
no-overwrite atomic DXF writer. `manufacturing_api.export_current_csv_nfb_door_base_pair(
snapshot, *, assembly_parts, base_spec, output_directory)` is the same
public operation for submitted numeric CSV V5; it selects 1-tier or 2-tier
physical BasePlate sources, re-derives and compares every installed scene
and signed stable ID, enforces actual tier depth/XYZ and existing CHECK/Q
material equivalence, reopens the staged 2 or 3 actual DXFs before publishing
all-or-none. The immutable `NfbCsvPairedPartOnlyDxf` and
`NfbCsvTwoTierPartOnlyDxf` types and original `NfbPairedPartOnlyDxf` remain
available from public Engine and legacy GUI imports as identical objects.
The old GUI paired-export module has no geometry, PartSpec or manufacturing
authority. Neither path authorizes PAD, welded EAR, whole MFG-2 or new
CUTTING/DXF certification, and no numeric/3D formula was changed.


## Receiving NFB read-only live manifest validation API (#2517)

`manufacturing_api.validate_receiving_nfb_manifest_view(view)` and
`validate_receiving_nfb_highlighted_manifest(ports, set_index, bay_indices)`
reject contradictory actual ready-piece counts, forged READY flags, CSV-V5
diagnostics masquerading as production parts, duplicate/invalid highlighted
Bay selections and missing physical Set/Bay/version IDs. The latter reads
each live manifest exactly once and returns validated detached display
snapshots. The GUI now only paints the same Traditional Chinese warning
and physical-part rows, never computes or validates manufacture eligibility.
These are **read-only display safety checks**, not manufacturing approval:
every DXF operation must separately revalidate sources through the existing
typed NFB Engine manifest/export gate. No new PAD/EAR/MFG-2 authorization,
CUTTING formula, or DXF capability is introduced.

## Derived physical part namespace/selection sync Engine API (#2517)

The pure immutable `DerivedPartRequestAssemblyInput`,
`DerivedPartProjectionRequest`, `DerivedPartSyncPlan` and
`manufacturing_api.build_derived_part_projection_request` /
`manufacturing_api.build_derived_part_sync_plan` are now owned in
`ae_engine.derived_part_projection`. This moves the existing source
reconciliation rules for `door_cN_rN`, `base_plate_cN_rN`,
`box_body:divider:` and `inner_door:` namespaces, stale part/Feature
stash, active/selected physical ID repair, and Receiving's existing single
Base Plate preservation into Engine unchanged. The original
`phase6_derived_part_projection` is an import-only compatibility mirror.
GUI composition only collects already-derived profiles/physical sources,
calls the Engine public API, and applies its immutable plan via the existing
workspace mutation owner. No second family formula, new NFB source, DXF
entitlement, or Save→Reload schema. #2517 OPEN.



## Physical BoxBody operator → Engine manufacturing PartSpec (#2517)

`manufacturing_api.build_box_body_operator_part_spec(values, *, model_name,
features=(), face_features=None, head_corner_policy=None,
tail_corner_policy=None, fold_profile=(), structure_state=None,
source_part_features=None, endcap_y_profiles=None, head_ybottom1=None,
tail_ybottom1=None, snapshot=None)` is the public headless BoxBodyPartSpec
owner for Vault and Receiving. GUI only collects live input, workspace
Fold/Features and override values. Engine chooses the existing canonical
Family structure state, rear-panel manufacturing contract, physical
BoxBody piece Features (excluding Divider namespace), Fold material
segments and the actual Head/Tail Y/ybottom1 outside Fold readback;
explicit Head/Tail overrides retain priority over profile and scalar
fallback. This is an ownership move, not a new compensation formula,
Certified Registry rule, Rear W datum, 2D/3D/DXF certification or a
Save→Reload format. #2517 remains OPEN.


## Receiving CSV-V5 unapproved inner-door/base real source trial API (#2517)

`manufacturing_api.preview_receiving_nfb_v5_real_base_sources(snapshot,
inner_door_id, *, door, configured_holes, root_base_spec)` is the
sole Engine owner for the GUI's existing one-/two-tier BasePlate preview
source validation. It verifies the real BasePlate PartSpec against current
Receiving sheet dimensions, bend pattern, physical ID and true submitted
Set/Bay source; the actual tier PartSpecs come from the same canonical
`source_receiving_nfb_tier_base_specs` as physical Assembly FinalScene.
The GUI now merely calls this API and paints its original trial data.

`require_receiving_nfb_v5_inner_door_trial_preview(trial)` and
`require_receiving_nfb_v5_base_trial_preview(trial)` reject a forged
manufacturing-ready/approved trial before the UI renders any FinalScene.
These return render data **for read-only visualization only**, not DXF
authorization; the current part-only/welded-EAR/PAD/MFG-2 gates remain
untouched. The existing #1901 real physical tier, SHA/Set/Bay drift and
single/two-layer proofs remain the acceptance sources.


## Receiving EAR side 2D/3D display source context (#2517)

`manufacturing_api.resolve_receiving_ear_side_display_context(snapshot,
piece_key, aggregate_render_data=None, *, main_mirror=None)` returns the
immutable `ReceivingEarSideDisplayContext`. It decides *read-only
visualization eligibility*, not manufacturing readiness: the true committed
FoldDesigner snapshot is preferred to the non-authoritative main-GUI mirror,
stale primary submitted-NFB claims fail closed, and the actual physical
Box Body child piece roles, baseline source SHA and scene primitives form the
same 2D/3D cache invalidation digest. The Engine returns the existing actual
outside-W/H/D and thickness for a downstream verified EAR SIDE MARKING
projection; GUI uses these values, renders, and stores display-only caches.

This does NOT grant EAR welding, PAD, DXF, CUTTING or whole MFG-2 production
permission. Actual UV/material and safety rejection remain in
`project_receiving_ear_side_piece_2d_preview`. The primary 2D / FoldDesigner
3D source and stale-primary cases and actual Save→Reload CHECK-only DXF
regression remain the acceptance evidence.

## Receiving settings physical world XY outline API (#2517)

`manufacturing_api.project_solid_mesh_xy_outline(triangles)` consumes an already-resolved solid 3D mesh, uses Engine's canonical physical feature-edge extractor and returns deterministic world XY line pairs (five decimal places, duplicate / zero-length edges omitted). This is a headless, read-only 2D inspection projection; the WHD GUI owns only canvas rendering and selection. It does not create, validate or certify CUTTING, BEND, DXF, NFB, EAR or PAD manufacturing data. Legacy GUI assembly mesh orchestration is a separate #2517 migration.

## Box Body physical multipart outside-width datum Engine API (#2517)

`manufacturing_api.resolve_box_body_formed_width_datum(pieces)` validates
the actual canonical `formed_w_end` source of Box Body multipart physical
skins before any FinalScene viewer uses or assembles a world mesh. Complete
placeholder-only previews return `None`; real positive outside-W pieces
are accepted; a zero-W-origin Receiving left SIDE is accepted only when
both authoritative `formed_w_start == 0` and `formed_outer_width > 0`
are present and finite. An incomplete or forged width/role source fails
closed with the original diagnostic errors. GUI only forwards resolved
Engine piece DTOs; no physical 3D mesh, manufacturing material, 2D CUTTING
or DXF is newly synthesized or certified.

---
whd_doc_role: REFERENCE
whd_contract: project-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Headless Manufacturing API（Phase 6：AE Engine Clean Break）

目的：讓 GUI、自動拆圖、CLI 或其他 Python 程式都使用同一個 AE 出圖入口，不必建立 Tkinter GUI，也不必直接呼叫 `ae.export_xxx_dxf()`。

## GUI／引擎權責（2026-10-31）

全域硬閘門 `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1` 的唯一 CURRENT owner 是 AI 庫 `第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`；此檔是 REFERENCE。GUI 全功能只處理操作與輸入，所有製造資料、公式、實體板件、孔位／折展開及 2D/3D/DXF 的 canonical 結果由引擎公開 API 處理。既有舊 GUI adapters 的存在**不代表每個箱型與功能均已完成改造**。遇 API 不支援，回引擎開發／測試或明確拒絕，不許 GUI 私做 fallback。對外 CADSplit Worker `capabilities/prepare/export` 僅宣告實際已驗證與授權的能力。靜態 CI gate：`tools/gui_engine_api_boundary_gate.py`，但它不代替行為契約測試或平台 required status check。


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

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

**2026-10-31 核准的全域決策**：WHD 專案的 GUI 只是使用者操作、輸入、表單格式檢查、選取、呼叫與結果顯示。所有與製造相關的規則、正確性、箱型策略、板件拓樸與身份、孔／折／截角／避讓、加工資料、DXF、2D/3D canonical geometry 的唯一實作與權威都在 `ae_engine`，並經公開 API 提供。GUI 可把明確輸入轉成 DTO/PartSpec，但**DTO 組裝絕不能夾帶機械演算**。

```text
GUI（operator input / action / presentation）
  → Engine request + public API
  → Family + Topology + ManufacturingPolicy + Certified Registry
  → authoritative FinalScene + physical parts + 2D/3D/DXF + Save→Reload
  → Engine response → GUI presentation
```

全箱型、全實體板件、所有孔型、數量／套／連／Bay、3D 預覽、製造匯出、編輯與儲存都適用；**這不代表所有相關 API 已完成或已驗證製造**。GUI 禁止複製折彎／展開／CUTTING／BLIND_HOLE／MARKING／offset 計算、決定製造板件、低層 `ae.export_*` 與直接 DXF 序列化。Engine 禁止反向 import GUI/Tk 或依賴 GUI widget／renderer 才能產生正確幾何。

Python 公開 seam 以 `ae_engine.contracts`、`ae_engine.manufacturing_api` 和 `ae_engine.__init__` 的正式 export 為準；外部 CADSplit 的 seam 是已授權 `integration_cli` 的 `capabilities/prepare/export`。功能缺席時**先補 Engine API、schema、capability 宣告與契約測試**，否則回傳 unsupported；GUI 不准以 fallback／Preview／自製公式假裝支援。能力表只反映實際驗證、信任與授權，不由 UI 清單代替。

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


### 10. CADSplit × WHD-Engine Worker authority / Gate A boundary (#2375 / #2382)

**公開 Gate A 維持獨立 fail-closed**：GUI／Engine API 的單向權責調整，不等於對外 CADSplit 製造能力已放行；私有安裝、簽章／HMAC 核准、局部 capability 或測試通過，都不可替代公開 Gate A 的實際全項驗證與授權。既有 Gate B/D/E 仍依原有證據判定。

此段是既有製造架構的**入口與權責對照**，不另建立製造公式、第二套 CURRENT owner 或對外可用性承諾。

- **公開 wire/CLI**：`integration_cli/cadsplit_worker.py` 與 `integration_cli/schemas/` 定義三個且只有三個公開命令 `capabilities`、`prepare`、`export`（沒有獨立 `verify`）；`docs/integrations/CADSplit_WHD_Contract.md` 是 REFERENCE wire contract。來源模式、未選擇安裝及原舊 protocol 1.0.0 的製造能力仍全 false／`WHD_OPERATION_NOT_IMPLEMENTED`。protocol 1.1.0 的**已封存 Windows 安裝、每份 exact-job HMAC 核准**請求可由公開 `prepare/export` 進入 `public_installed_adapter.execute_public_installed`，不是無條件開放任意 CADSplit 出圖；`capabilities --installation-id` 僅在安裝憑證實際可驗證時宣告條件式 P0 能力，且列明每 job 仍需獨立核准。
- **封裝與私有安裝信任**：`integration_cli/packaged_identity.py` 驗證 exact engine commit、EXE、Registry、baseline、policy 的實際內容；`integration_cli/worker_key_custody.py` 與 `private_worker_installation.py` 保管 Windows current-user DPAPI/HMAC、預先綁定來源 DXF／輸出／durable store，並對每次 `(client_installation_id, job_id, operation, request_digest)` 簽發獨立不可變授權。`cadsplit_worker._private_installed_main` 僅在已封裝 Windows EXE、已獲私有安裝及 exact-job 授權時進入；這不是公開 CADSplit API，也不是同帳號惡意程式的 OS 隔離保證。
- **私有製造資料流**：`cadsplit_worker._execute_request(trusted_context=...)` → `private_worker_dispatch.execute_private_worker` → `prepare_batch.prepare_trusted_door_batch`／`job_identity_ledger.DurableJobIdentityLedger`／`prepare_recheck.recheck_trusted_door_export` → `source_circle_verification.verify_trusted_original_dxf_features` → `verified_door_finalscene.save_trusted_door_circle_finalscene_batch` → WHD `manufacturing_api.build_part_render_data`、`save_verified_final_scene_batch_dxf` → W-06 journal/immutable DXF readback。原圖路徑、token、Frame、原始 SHA、來源加工層、Registry/資源以及輸出鎖由 WHD 受信任 owner 驗證，不由 CADSplit JSON 自行宣稱。
- **目前受限的實體類型**：私有 W-04 已以 WHD native FinalScene 支援 `door`、`indicator_small_door`、`indicator_box`、`end_cap_head`、`end_cap_tail` 的受信任 batch。Door／small-door 的來源 `CIRCLE`、封閉 LWPOLYLINE `RECT/PROFILE` 須對原始 modelspace handle、SHA、圖層 `CUTTING` 與幾何／變換逐項核實；Box／Vault EndCap 仍只有 **原 DXF modelspace 真正為空、沒有外部 Features** 的 WHD intrinsic、size-only 路徑，不得藉由 wire 宣稱直接授權來源開孔或自訂裝配。
- **W-08 全功能發現 API（#2383）**：已安裝 `capabilities` 可附帶 `feature_catalog`，逐筆列出「金庫型／受電箱」的全部已註冊 WHD 功能、唯一實作 owner、`public_operations`、`manufacturing_supported`、`production_scope`、`blocked_code`。此目錄只是外部 API 的完整**可發現／可拒絕**表面，不得把 `capabilities` 存在當成 `prepare/export` 製造已通過。只有同一簽章 Worker 的原有五種實體製造角色可以亮起 `manufacturing_supported=true`（盤型各自限定）；箱身分片、Base Plate、Custom Fold、Inner Door、Divider、Fixing Plate、Receiving NFB、Quantity/Multi-Bay、Fold/Joint/Relief 需沿著 CURRENT WHD geometry/physical-ID 和 CADSplit Source→Frame→Save→Reload Gate C 分別開通。目錄本身不能自行建立幾何、金鑰、job 或額外對外 CLI command。
- **P1 受電箱／金庫型 API 盤型矩陣（#2383）**：安裝後的 v1.1 `capabilities[*].cabinet_families` 是明確的 part-kind×Family 宣告；`door` 允許已驗證的「金庫型」及「受電箱」外門，Receiving Door 保留自身 WHD Family policy 與既有 Vault 共享的 baseline source，並以原始來源→W-03 Frame→W-04 FinalScene→DXF reopen 驗證。共用指示燈盒／小門對上述兩盤型維持 WHD 原生獨立物理件。封頭／封尾的目前 Worker 外部接口只對「金庫型」已認證；**受電箱封頭、箱身、Divider、Inner Door 和 multi-Bay 不可從此矩陣推導成已驗證**，W-03 必須先拒絕，後續需要獨立 Family/Topology/Certified Registry 證據。來源模式 v1.0 不得因 v1.1 family metadata 自動升級；CADSplit 必須真實協商安裝 ID、1.1 wire、source Frame/Features 與每-job installer 核准，否則仍不得出圖。
- **公開 Export 成功的責任界線**：私有 W-04 receipt 仍為 `manufacturing_verified=false`，不能直接翻轉。公開 `public_installed_adapter._public_export_receipt` 僅在 `prepare_recheck` 的 HMAC/來源/Frame/環境重驗、WHD FinalScene 的 DXF Save→Reload、W-06 `committed` journal、完整 physical-part inventory 與每件 SHA/mtime /輸出路徑重驗都一致時，建構符合 v1.1 schema 的 `manufacturing_verified=true`。實際 EXE／GUI exact SHA 測試能證明受信任安裝的條件式能力，不代表所有未安裝 CADSplit 均可製造、CADSplit Gate B/D／使用者 Gate E 或正式 X 已放行；完整 Gate A 仍依 #2382 真實全項證據判定。

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

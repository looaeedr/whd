
# WHD Fold Designer Phase 5 規格書
## Bridge Surface Decomposition / Capability Deep Modules & Presentation Boundaries

**狀態：Draft for review — 未 accepted 前禁止 implementation**  
**日期：2026-09-20**  
**Repository：looaeedr/whd**  
**Production branch：cleanup/2d-3d-sync**

---

# 0. Phase 5 固定起點

~~~text
PHASE5_ROOT_BASELINE =
396bfd96524a44a178c29bbefaf1b7c0437c119f
~~~

此 SHA 是 Phase 3、Phase 4 均已接受，且 spec-authority guardrail 已正式合併後的 production HEAD。

Phase 5 cumulative root 不得因後續 production 漂移而偷偷替換。若 accepted 後 production 有其他不相關工作先進入：

- T1～T7 仍依本規格的 predecessor / isolation 規則；
- T8 cumulative baseline 永遠固定為 PHASE5_ROOT_BASELINE；
- 不得拿較新的 production HEAD 取代固定 root；
- reconcile 只能走明確 non-force reconciliation + post-merge acceptance。

## 0.1 Specification authority

本文件目前狀態：

~~~text
SPECIFICATION_REQUIRED
→ DRAFT_FOR_REVIEW
~~~

只有使用者明確接受本規格後，才可切換：

~~~text
AUTHORIZED_IMPLEMENTATION_SCOPE
~~~

在 accepted 前只允許：

- fresh-read production；
- ownership / dependency / call-graph census；
- deep-module scan；
- deletion test；
- 規格修改與 review；
- non-mutating design analysis。

在 accepted 前禁止：

- 建立 Phase 5 implementation tickets；
- 建立 implementation branch/worktree；
- 寫 RED/GREEN implementation tests；
- 修改 product/runtime code；
- 修改 manufacturing / Registry / DXF；
- 建立 Phase 5 production QA workflow；
- merge 任何 Phase 5 implementation。

核心規則：

~~~text
continuity != authority expansion
~~~

「繼續 / GO / 輪」只能推進已 accepted scope，不會自動擴大成新 Phase、新 ownership 或新 task chain。

## 0.2 Pre-spec invalid evidence / inherited tooling

本規格前曾誤啟動：

- #413：原誤作 Phase 5 master，已改為 specification-required hub；
- #414：pre-spec census bootstrap；
- #416 / PR #417：pre-spec derived-topology exploratory extraction；
- PR #419：未依 Knowledge Preflight / 掃描深模組 Skill 產生的 invalid spec draft。

正式規則：

~~~text
PRE_SPEC_EXPLORATION != ACCEPTED_PHASE5_EVIDENCE
~~~

1. #416 / PR #417 已 invalidated / closed，不得當正式 T1 predecessor 或 acceptance。
2. #419 已 invalidated / closed，原 spec file 已刪除。
3. production 中已存在的 pre-spec census tooling 只算 inherited tooling。
4. inherited tooling只能在正式 T0 fresh-validate 後決定採用、修正或移除。
5. 在正式 T0 terminal GREEN 前，T0_ACCEPTED=0。
6. pre-spec run / GREEN 不得縮短正式 RED / GREEN / A/B / invariant。

---

# 1. Phase 5 目的

Phase 3 已完成第一層 owner extraction：

- Workspace / Navigation
- Settings Transaction
- Project / Persistence
- Registry / Diagnostics
- 2D Corner Data View
- 3D Final Scene View
- Lifecycle / Update Intent / Facade wiring

Phase 4 已完成兩個高風險 deep owner 的深化。

Settings：

~~~text
mutable controller
→ immutable contracts
→ pure transitions
→ explicit service/effects
→ compatibility facade
~~~

Final Scene：

~~~text
owner=self + dynamic service bag
→ typed dependencies
→ pure projection
→ renderer/runtime
→ explicit composition
~~~

Phase 5 不重做 Phase 3 / Phase 4。

Phase 5 的目標是：

> 對仍然承擔大量責任的 fold_designer_bridge.py 做 ownership deepening，把仍由 bridge 持有的 pure projection、derived-part sequencing、Registry / Settings / Assembly / Operator Workspace presentation 移到真實 capability seam 後方；bridge 最後只保留 application composition、top-level Tk event wiring、explicit adaptation 與 legacy compatibility。

Phase 5 不是：

~~~text
bridge 太大
→ 搬函式到其他檔案
~~~

Phase 5 要做到：

~~~text
distributed knowledge
→ capability owner

shallow wrapper
→ deep module

bridge-owned ordering knowledge
→ controller-owned invariant

domain semantic + presentation state
→ separated seams

compatibility alias
→ thin read-through / re-export
~~~

---

# 2. Source-first / Knowledge Preflight

本規格撰寫前已依 AGENTS.md 完成 WHD Knowledge Preflight。

Machine preflight：

~~~text
REQUIRED SKILLS
✓ 掃描深模組
✓ phase6-corner-3d-model-integrity
✓ executable-continuity-controller

REQUIRED REFERENCES
✓ 全域踩坑庫
✓ 深模組掃描規則
✓ 截角資料庫母規則
✓ certified relief rules
✓ assembly relief pitfalls
✓ executable continuity pitfalls

RC=0
~~~

Durable evidence：

~~~text
logs/preflight/20260920_issue413_phase5_spec_evidence.md
~~~

Supporting Skills 已讀：

- 程式碼庫設計
- 深度質詢
- 領域建模
- DEEPENING
- DESIGN-IT-TWICE
- 掃描深模組 HTML-REPORT

Source-first 已回讀：

- Phase 3 #363 / #372；
- Phase 4 #388 / #397；
- Phase 4 post-merge RUN 35479290249；
- DM1～DM5 Divider deep-module evidence；
- DM6 semantic identity evidence；
- CONTEXT.md；
- current bridge source；
- current Phase 2/3/4 owners。

本規格不新增產品／機械 domain definition，因此不建立新 domain glossary / ADR。

---

# 3. Deep-module scan baseline

PHASE5_ROOT_BASELINE fresh-read：

~~~text
fold_designer_bridge.py
blob SHA = 7ddbcec24693238772edb9209c271c57cdbe23f3
~~~

Spec-drafting observation：

~~~text
source split lines             ≈ 9460
top-level def/class            = 344
_phase6_* top-level def        = 286
literal self.* occurrences     = 1423
unique self attrs observed     = 332
direct class assignments       = 0
facade binding keys observed   = 69
~~~

這些數字只作 drafting evidence，不是正式 T0 canonical machine authority。

正式 T0 必須建立唯一 census algorithm，至少固定：

- LINE_COUNT
- TOP_LEVEL_DEF_CLASS_COUNT
- PHASE6_TOP_LEVEL_DEF_COUNT
- SELF_REF_COUNT
- UNIQUE_SELF_ATTR_COUNT
- FACADE_BINDING_COUNT
- DIRECT_CLASS_ASSIGNMENT_COUNT
- REVERSE_BRIDGE_IMPORT_COUNT
- APP_OWNER_DEREF_COUNT
- TK_REACHABLE_ROOTS
- COMPATIBILITY_WRAPPER_COUNT
- UNKNOWN_OWNER_COUNT

T0 要同時記錄：

- script SHA；
- root SHA；
- bridge blob SHA；
- metric definition；
- symbol start/end/span；
- dependency edges；
- callback / Tk reachability；
- owner bucket；
- deletion-test classification。

---

# 4. Deep-module scan findings

## 4.1 Pure derived topology / operator projection

bridge 仍有一批：

- 無 Tk；
- 無必要 app mutation；
- 可由 immutable / resolved input 得到 deterministic result；
- 但仍存在 composition surface；

的邏輯。

代表責任：

- door part projection；
- physical-piece identity predicates；
- operator selector keys；
- structure hierarchy rows；
- reverse fold traversal；
- box-body physical-piece profile / dimension projection；
- door / base-plate dynamic part predicates。

問題：

~~~text
semantic projection knowledge
still lives in composition surface
~~~

這是 Phase 5 最乾淨的 pure-owner candidate。

## 4.2 Derived-part synchronization / editor sequencing

代表責任：

- authoritative derived-part refresh；
- linked EndCap/profile rebuild；
- profile refresh after settings；
- editor value store；
- physical-piece commit；
- active-part / derived-profile reconciliation。

Pitfall hard gate：

~~~text
如果 bridge 仍知道 A → B → C 的正確順序
而新 module 只提供 do_a / do_b / do_c
則新 module 只是 Middle Man
~~~

Deletion test：

> 刪掉 bridge 內該 orchestration 後，正確 ordering / invariant 是否仍完整存在於新 owner？

只有 YES 才算 deepening。

## 4.3 Settings / Corner presentation

Phase 4 已完成 Settings core：

- contracts；
- transitions；
- service；
- transaction compatibility facade；
- presentation classification。

Phase 5 不重做 Settings core。

bridge 仍直接建立：

- box-structure settings UI；
- EndCap FW controls；
- assembly controls；
- symmetry controls；
- receiving bottom-wrap controls；
- Corner controls；
- drawing-edge controls；
- settings panel extension widgets。

Phase 5 只處理 presentation seam。

## 4.4 Registry presentation

phase6_registry_diagnostics_controller.py 已是 accepted semantic/action owner。

bridge 仍持有：

- raw/display translation；
- rule form collection；
- candidate form；
- 2D preview UI；
- 3D validate/preview UI；
- formula matrix controls；
- promote controls；
- rule tree；
- joint form；
- floating window lifecycle。

Registry presentation 不得重解 formula / rule semantics。

## 4.5 Assembly presentation

bridge 仍持有：

- assembly part list；
- nested group；
- details expand/collapse；
- box-body physical-piece details；
- visibility controls；
- mousewheel / scroll bind；
- diagnostics presentation；
- formed / blank / corner display。

硬 invariant：

~~~text
identity != navigation != visibility
~~~

hidden physical piece 不得：

- 退出 manufacturing；
- 改 assembly datum；
- 改 collision source；
- 改 physical identity。

aggregate box_body 不得被 remembered child 劫持。

## 4.6 Operator Workspace presentation

Phase 3 已有 navigation/domain owner。

bridge 仍持有：

- content switch；
- structure tree；
- physical-piece selector；
- part activation UI；
- corner-data navigation；
- corner-data canvas lifecycle；
- home / assembly / corner-data page switching。

Phase 5 必須清楚分開：

~~~text
navigation authority
≠
navigation presentation
~~~

## 4.7 Workspace shell / persistent controls

bridge 仍持有：

- project toolbar；
- transaction buttons；
- visual controls；
- fullscreen；
- global persistent controls；
- sticky structure controls；
- output controls；
- status bar；
- text-scale presentation；
- persistent top area。

這些是 application presentation/chrome，不是 Project / Output / Lifecycle semantic owner。

---

# 5. Design It Twice 結論

## 5.1 Rejected — 單一 giant BridgeSurface

拒絕原因：

- pure/domain/Tk/Registry/navigation 仍混在一起；
- locality 是假的；
- 只是把 giant bridge 換檔名；
- ownership classifier 仍無法證明責任清楚。

## 5.2 Rejected — 按函式 prefix 搬檔

例如 registry_* 全搬到 registry_helpers.py，但 bridge 繼續決定：

- 呼叫順序；
- mutable owner；
- rollback；
- refresh sequencing；
- semantic fallback。

這只是：

~~~text
move-only != deep module
~~~

## 5.3 Rejected — 所有 seam 先做 ports/adapters

只有一個 concrete adapter 時：

~~~text
one adapter = hypothetical seam
~~~

不得為 speculative variability 增加 abstraction。

## 5.4 Accepted direction — capability deep modules + existing composition root

~~~text
pure projection
→ pure owner

stateful sequencing
→ deep controller

Settings / Corner widgets
→ presentation owner

Registry form/window
→ presentation owner

Assembly panel
→ presentation owner

Operator Workspace
→ presentation owner

Workspace chrome
→ presentation owner

existing Phase4 composition root
→ connect owners

fold_designer_bridge
→ composition access / top-level Tk wiring / compatibility
~~~

Phase 5 不建立第二個 competing composition root。

existing authority：

~~~text
gui_modules/application/fold_designer_adapter.py
Phase6FoldDesignerComposition
FinalSceneCompositionPorts
~~~

---

# 6. Phase 5 不做的事

Phase 5 是 behavior-preserving architectural refactor。

禁止順手修改：

- CornerType 機械語意；
- EndCap FW 公式；
- Fold Profile 公式；
- Receiving / Vault family geometry；
- Divider CROSS；
- Certified Registry formula；
- manufacturing solver；
- physical collision/backprojection；
- true-thickness semantics；
- Door / Base Plate / Divider / Inner Door geometry；
- DXF schema / geometry；
- config.ini defaults / semantics；
- project schema / persistence semantics；
- AssemblyJoint semantics；
- part keys / stable physical IDs；
- visible UI wording；
- current UI layout；
- Issue163/164 layout authority；
- output stock/export semantics；
- keyboard command semantics；
- event ordering；
- Save/Reload authority；
- FinalScene projection / renderer semantics。

若 refactor 暴露既有功能 bug：

~~~text
classify
→ separate focused remediation
~~~

不得在 extraction 內順手改產品行為。

---

# 7. Protected owners / surfaces

## 7.1 Phase 2 manufacturing

~~~text
phase6_manufacturing_cache.py
phase6_manufacturing_contracts.py
phase6_manufacturing_geometry.py
phase6_manufacturing_service.py
phase6_manufacturing_adapter.py
~~~

Hard：

~~~text
MANUFACTURING_SEMANTIC_DELTA=0
VALIDATION_AS_PRODUCTION_AUTHORITY=0
~~~

## 7.2 Phase 3 accepted owners

~~~text
phase6_workspace_navigation_controller.py
phase6_project_controller.py
phase6_registry_diagnostics_controller.py
phase6_corner_data_view_adapter.py

gui_modules/application/command_router.py
gui_modules/application/lifecycle.py
gui_modules/application/state_sync.py
~~~

Presentation 可以 consume 這些 owner。

禁止：

~~~text
controller/service → new presentation
controller/service → fold_designer_bridge
~~~

## 7.3 Phase 4 Settings

~~~text
phase6_settings_contracts.py
phase6_settings_transitions.py
phase6_settings_service.py
phase6_settings_transaction_controller.py
phase6_settings_panel.py
~~~

phase6_settings_panel.py 是 presentation layer；可做最小 seam adaptation，但：

- 不重寫 layout；
- 不把 domain state 搬進 panel；
- core 不反向 import presentation；
- typed Settings contract 不退化。

## 7.4 Phase 4 Final Scene

~~~text
phase6_final_scene_contracts.py
phase6_final_scene_projection.py
phase6_final_scene_renderer.py
phase6_final_scene_view.py
gui_modules/application/fold_designer_adapter.py
~~~

禁止：

- 恢復 owner=self；
- 恢復 generic service bag；
- 把 projection / renderer 拉回 bridge；
- 在 presentation module 重解 Final Scene geometry。

## 7.5 Manufacturing / Registry canonical sources

Protected：

- certified_relief_rules.json；
- Registry rule id / revision / formula；
- RECEIVING_DIVIDER_CROSS_STANDARD_V1；
- DXF baseline / certified features；
- Cabinet Family policy；
- authoritative T；
- AssemblyJoint semantics；
- resolved final material。

Presentation 只能顯示 / 轉接，不能重建第二套 mechanical truth。

---

# 8. Dependency direction

合法：

~~~text
domain / manufacturing / pure projection
            ↓
controller / service
            ↓
presentation module
            ↓
application composition
            ↓
fold_designer_bridge compatibility / top-level event boundary
~~~

禁止：

~~~text
domain → presentation
domain → bridge
service → bridge
service → Tk
pure projection → Tk
pure projection → app self
presentation → manufacturing formula
presentation → Registry formula reconstruction
deep module → fold_designer_bridge
deep module → generic app owner
~~~

---

# 9. Target capability owners

此節定義 responsibility boundary，不把目前函式名字直接升格成 ownership oracle。

每個 T1～T7 的 exact symbol membership 必須由 T0 fresh ownership + deletion-test census 凍結。

## 9.1 Pure Derived Topology / Operator Projection

建議檔名：

~~~text
phase6_derived_topology.py
~~~

責任：

- stable part identity predicates；
- door/base-plate dynamic projection；
- box-body physical-piece hierarchy；
- operator selector projection；
- reverse traversal；
- immutable physical-piece profile/dimension projection；
- non-localized semantic identity projection。

Hard purity：

~~~text
SELF_REFS=0
TK_REFS=0
BRIDGE_IMPORTS=0
APP_OWNER_DEREF=0
WORKSPACE_MUTATION=0
MANUFACTURING_SOLVE=0
PRESENTATION_STRING_AS_IDENTITY=0
~~~

## 9.2 Derived Parts Controller

建議檔名：

~~~text
phase6_derived_parts_controller.py
~~~

責任：

- derived-part refresh sequencing；
- linked profile/endcap reconciliation；
- settings-driven profile refresh sequencing；
- physical-piece editor commit sequencing；
- authoritative part refresh ordering；
- explicit mutation/effect planning。

Hard：

~~~text
TK_WIDGET_CONSTRUCTION=0
MANUFACTURING_FORMULA_DUPLICATION=0
REGISTRY_FORMULA_DUPLICATION=0
FINAL_SCENE_GEOMETRY_DUPLICATION=0
~~~

Deletion test：

~~~text
delete bridge sequencing
→ controller interface still preserves invariant/order
~~~

如果 bridge 仍知道完整 A→B→C 順序，T2 不算完成。

## 9.3 Settings / Corner Presentation Owner

建議：

~~~text
phase6_settings_presentation.py
~~~

或 T0 證明應深化既有 phase6_settings_panel.py 時，直接深化既有 panel，不能建立第二 owner。

責任：

- structure widgets；
- EndCap FW widgets；
- assembly settings widgets；
- symmetry widgets；
- bottom-wrap widgets；
- Corner widgets；
- drawing-edge widgets；
- presentation-only visibility/editability/lifecycle。

Hard：

~~~text
SETTINGS_DOMAIN_STATE_OWNER=0
SETTINGS_TRANSITION_LOGIC=0
MANUFACTURING_FORMULA=0
CORE_REVERSE_PRESENTATION_IMPORTS=0
~~~

## 9.4 Registry Presentation Owner

建議：

~~~text
phase6_registry_panel.py
~~~

責任：

- raw/display reversible presentation adapter；
- form state；
- rule tree；
- joint form；
- candidate presentation；
- 2D/3D preview UI plumbing；
- matrix / promotion controls；
- window lifecycle。

Hard：

~~~text
REGISTRY_FORMULA_OWNER=0
REGISTRY_SCHEMA_OWNER=0
CERTIFICATION_DECISION_OWNER=0
RAW_ID_MUTATION=0
~~~

## 9.5 Workspace Shell / Persistent Controls

建議：

~~~text
phase6_workspace_shell.py
~~~

責任：

- project toolbar presentation；
- transaction buttons；
- visual controls；
- fullscreen UI；
- status projection；
- persistent top area；
- output controls presentation；
- text scale UI；
- sticky chrome。

Hard：

~~~text
PROJECT_PERSISTENCE_OWNER=0
OUTPUT_GEOMETRY_OWNER=0
NAVIGATION_STATE_OWNER=0
UI_LAYOUT_SEMANTIC_CHANGE=0
~~~

## 9.6 Assembly Presentation Owner

建議：

~~~text
phase6_assembly_panel.py
~~~

責任：

- assembly part rows；
- nested groups；
- detail expand/collapse；
- visibility controls；
- physical-piece detail presentation；
- formed/blank/corner display vars；
- scroll/bind ownership；
- diagnostics menu/status presentation。

Hard：

~~~text
ASSEMBLY_GEOMETRY_SOLVE=0
MANUFACTURING_MUTATION=0
VISIBILITY_CHANGES_PHYSICAL_PRESENCE=0
VISIBILITY_CHANGES_DATUM=0
VISIBILITY_CHANGES_COLLISION_SOURCE=0
PRESENTATION_LABEL_AS_IDENTITY=0
DUPLICATE_SCROLL_BINDING=0
~~~

## 9.7 Operator Workspace Presentation Owner

建議：

~~~text
phase6_operator_workspace.py
~~~

責任：

- content switch；
- structure-tree widgets；
- physical-piece selector widgets；
- active part presentation；
- corner-data navigation；
- corner-data canvas lifecycle；
- home / assembly / corner-data page transition presentation。

Hard：

~~~text
NAVIGATION_DOMAIN_OWNER=0
REMEMBERED_CHILD_AS_MANUFACTURING_IDENTITY=0
AGGREGATE_PARENT_REWRITE=0
CORNER_DATA_MANUFACTURING_MUTATION=0
VIEW_RECREATE_MUTATES_AUTHORITY=0
~~~

---

# 10. Bridge target

Phase 5 結束後 fold_designer_bridge.py 合法責任：

- composition lookup/access；
- top-level Tk root/event wiring；
- explicit app↔capability adaptation；
- public compatibility imports / re-exports；
- legacy properties / thin delegation；
- installation of existing facade；
- unavoidable top-level command routing。

不再擁有：

- pure derived topology；
- physical identity reconstruction；
- derived-part refresh algorithm/order；
- large Settings/Corner widget builders；
- Registry form implementation；
- Assembly panel implementation；
- Operator Workspace page implementation；
- duplicate project/navigation/diagnostic semantics。

合法 compatibility：

~~~text
old symbol
→ imported/delegated canonical implementation
~~~

非法 compatibility：

~~~text
old symbol
→ second behavior implementation
~~~

---

# 11. Size / coupling metrics

Phase 5 不以 LOC 定義 deep module。

因此不設：

~~~text
bridge <= arbitrary N lines
~~~

這種沒有 architecture authority 的硬目標。

T0 / T8 仍必須報：

- bridge lines；
- top-level defs/classes；
- phase6 defs；
- self count；
- unique attrs；
- facade bindings；
- compatibility wrappers；
- Tk roots；
- unknown owner count。

Blocking gates：

~~~text
UNKNOWN_BRIDGE_OWNERS=0
SHALLOW_MOVE_ONLY_OWNERS=0
DUPLICATE_CANONICAL_OWNERS=0
DUPLICATE_PRESENTATION_STATE_OWNERS=0
REVERSE_BRIDGE_IMPORTS=0
NEW_APP_OWNER_DEREF_IN_DEEP_MODULES=0
DIRECT_CLASS_ASSIGNMENTS=0
FACADE_BINDINGS_GROWTH=0
~~~

Bridge quantitative metrics至少不得高於 root。

而且每個 accepted extraction 必須證明對應責任真的從 bridge ownership map 消失。

~~~text
LOC decreased
but responsibility still bridge-owned
→ FAIL
~~~

---

# 12. Phase 5 execution rules

Spec accepted 後，每個 implementation task：

~~~text
fresh branch
→ fresh predecessor readback
→ RED characterization
→ intended RED proof
→ minimal GREEN
→ focused regression
→ task-scoped A/B
→ protected invariant
→ physical-part/DXF final gate when triggered
→ non-force integration
→ production readback
→ durable accepted checkpoint
~~~

禁止：

- 未 accepted predecessor 疊下一 task；
- movable branch 當 baseline；
- pre-spec #416/#417 當 accepted evidence；
- baseline failure 未分類就改 production；
- validation output 反向當 manufacturing input；
- docs-only push 誤觸 one-shot QA；
- workflow 未 terminal 就 accepted；
- 沒 concrete RUN 就 WAITING_REMOTE；
- force-push production；
- cleanup 後不做 drift audit。

## 12.1 Default integration model

預設：

~~~text
T0 accepted
→ T1 accepted + integrated + readback
→ T2
→ ...
→ T7
→ T8 root cumulative
~~~

每 task predecessor：

~~~text
PREDECESSOR = immediately previous accepted production SHA
~~~

若 T0 發現 concurrent production 造成固定-root isolation需求，可建立明確 amendment，但：

- fixed root 不變；
- amendment 必須 durable；
- 不得 silent baseline substitution；
- cumulative T8 仍對固定 root。

---

# 13. Task chain

以下 task 只有 spec accepted 後才能建立 owning Issues。

## P5-T0 — Canonical bridge ownership / deletion-test census

目的：

> 建立 Phase 5 唯一 machine-readable ownership truth；不做 extraction。

每個 top-level symbol記錄：

- start/end/span；
- pure/stateful/Tk/io/render；
- direct dependencies；
- callback roots；
- state reads/writes；
- owner candidate；
- compatibility role；
- deletion-test result。

Ownership buckets 至少：

~~~text
COMPOSITION_COMPATIBILITY
PURE_DERIVED_TOPOLOGY
DERIVED_PARTS_CONTROLLER
SETTINGS_CORNER_PRESENTATION
REGISTRY_PRESENTATION
WORKSPACE_SHELL
ASSEMBLY_PRESENTATION
OPERATOR_WORKSPACE_PRESENTATION
PROJECT_LIFECYCLE_DELEGATION
PHASE4_FINAL_SCENE_COMPAT
UNKNOWN
~~~

Pre-spec artifact disposition：

- pre-spec census tooling；
- #416 code pattern；
- tests/workflows；
- reusable-as-tooling-only 여부。

Hard：

~~~text
PRE_SPEC_IMPLEMENTATION_ACCEPTED_AS_EVIDENCE=0
~~~

Required output：

~~~text
docs/superpowers/checkpoints/phase5-t0-bridge-ownership.md
.scratch/phase5-t0-bridge-ownership.json
~~~

Acceptance：

~~~text
ROOT_SHA_EXACT=1
BRIDGE_BLOB_RECORDED=1
CANONICAL_CENSUS_SCRIPT_RECORDED=1
UNKNOWN_OWNER_COUNT=0
PROTECTED_MANIFEST_COMPLETE=1
DELETION_TEST_COMPLETE=1
PRODUCTION_BEHAVIOR_CHANGE=0
~~~

T0 會凍結 T1～T7 exact symbol membership。

## P5-T1 — Pure Derived Topology / Operator Projection

目的：建立 pure projection owner。

RED：

~~~text
same immutable input
→ predecessor projection fingerprint
→ candidate projection fingerprint
→ equal
~~~

Hard：

~~~text
SELF_REFS=0
TK_REFS=0
BRIDGE_IMPORTS=0
APP_OWNER_DEREF=0
WORKSPACE_MUTATION=0
MANUFACTURING_SOLVE=0
~~~

必驗：

- aggregate box_body；
- exact physical child；
- one/two/three-piece；
- receiving multi-door；
- base plate；
- divider；
- parent→child→parent identity；
- duplicate label 不影響 stable identity。

## P5-T2 — Derived Parts Controller / Editor Sequencing

目的：將 derived-part reconciliation / editor commit sequencing 收進 deep controller。

GREEN 要求：

~~~text
bridge knows capability request
controller knows internal ordering
~~~

不得變成：

~~~text
bridge:
controller.a()
controller.b()
controller.c()
~~~

Hard：

~~~text
BRIDGE_DERIVED_SEQUENCE_OWNERSHIP=0
CONTROLLER_TK_WIDGET_CONSTRUCTION=0
CONTROLLER_GEOMETRY_FORMULA_DUPLICATION=0
VALIDATION_MAGIC_NUMBER=0
~~~

必驗：

- stable physical IDs；
- Receiving/Vault；
- multi-door；
- multipart box body；
- linked EndCap profiles；
- active child editor；
- 2D/3D identity；
- project round-trip；
- config invariant。

## P5-T3 — Settings / Corner Presentation Deepening

目的：保留 Phase 4 Settings core；把 bridge-owned widget builders 收進 presentation owner。

Hard：

~~~text
SETTINGS_CORE_SEMANTIC_DELTA=0
SETTINGS_CORE_REVERSE_PRESENTATION_IMPORTS=0
SETTINGS_PRESENTATION_DOMAIN_OWNER=0
CORNER_MECHANICAL_SEMANTIC_DELTA=0
REGISTRY_FORMULA_DELTA=0
~~~

Real-Tk A/B：

- widget parent/order；
- visible/hidden；
- enabled/disabled；
- trace/bind；
- edit；
- confirm/cancel；
- defaults；
- family switch；
- text scale；
- resize/scroll；
- no duplicate callbacks。

## P5-T4 — Registry Presentation Deepening

目的：讓 Registry controller 保持 semantic owner，form/window/tree/preview 成為 presentation owner。

A/B：

- raw token identity；
- display translation；
- form collect；
- stale/current candidate；
- 2D preview；
- 3D validate/preview；
- formula matrix；
- promote；
- joint add/delete；
- tree selection。

Hard：

~~~text
REGISTRY_CONTROLLER_REVERSE_PANEL_IMPORTS=0
RAW_REGISTRY_ID_MUTATION=0
REGISTRY_FORMULA_SEMANTIC_DELTA=0
CERTIFIED_RULE_DELTA=0
DISPLAY_STRING_AS_AUTHORITY=0
~~~

## P5-T5 — Workspace Shell / Persistent Controls

目的：抽離 application chrome，不重寫 Project / Output / Lifecycle semantics。

Hard：

~~~text
PROJECT_SEMANTIC_DELTA=0
OUTPUT_SEMANTIC_DELTA=0
LIFECYCLE_EVENT_ORDER_DELTA=0
LAYOUT_AUTHORITY_DELTA=0
~~~

必驗 current layout authority：

- top area；
- left single scroll owner；
- physical selector true visibility；
- medium/large text；
- no clipping；
- no duplicate geometry manager；
- keyboard actions unchanged。

## P5-T6 — Assembly Presentation Deepening

目的：將 assembly rows/groups/details/visibility/scroll/diagnostics 收進 presentation owner。

Hard：

~~~text
ASSEMBLY_PANEL_MANUFACTURING_AUTHORITY=0
ASSEMBLY_PANEL_GEOMETRY_SOLVE=0
VISIBILITY_MUTATES_PHYSICAL_PRESENCE=0
VISIBILITY_MUTATES_DATUM=0
VISIBILITY_MUTATES_COLLISION=0
DUPLICATE_SCROLL_BINDING=0
DUPLICATE_RENDER_TRIGGER=0
~~~

Real-Tk 必驗：

- group collapse/expand；
- part detail collapse/expand；
- physical-piece nested rows；
- visibility；
- scroll；
- diagnostics；
- selected/disabled；
- receiving multi-door；
- multipart box body；
- divider/base plate；
- resize/text scale。

## P5-T7 — Operator Workspace Presentation + Bridge Seam Compression

目的：把 content/navigation presentation 抽離，最後壓薄 compatibility seam。

候選：

- content switch；
- structure tree；
- physical-piece selector；
- active part presentation；
- corner-data panel/canvas lifecycle；
- home/assembly/corner-data page presentation。

同時 cleanup：

- redundant thin wrappers；
- duplicate compatibility mirrors；
- no-value pass-through；
- composition lookup consolidation。

公開 legacy caller 需要的 symbol 可 re-export/delegate。

Hard：

~~~text
NAVIGATION_DOMAIN_DUPLICATION=0
AGGREGATE_PARENT_REWRITE=0
REMEMBERED_CHILD_AUTHORITY_LEAK=0
CORNER_DATA_VIEW_MUTATES_MANUFACTURING=0
REVERSE_BRIDGE_IMPORTS=0
DIRECT_CLASS_ASSIGNMENTS=0
FACADE_BINDINGS_GROWTH=0
UNKNOWN_BRIDGE_OWNERS=0
SHALLOW_MOVE_ONLY_OWNERS=0
~~~

## P5-T8 — Final cumulative root-baseline A/B / cleanup / closure

固定 baseline：

~~~text
BASELINE =
396bfd96524a44a178c29bbefaf1b7c0437c119f
~~~

Candidate：

~~~text
CANDIDATE =
T7_ACCEPTED_PRODUCTION_SHA
~~~

上面是 forward placeholder。

Dispatch 前必須：

1. fresh-read T7 accepted checkpoint；
2. fresh-read production；
3. 驗 production == T7 accepted SHA，或依正式 isolation amendment驗 accepted candidate；
4. workflow/evidence 寫入 actual 40-char SHA；
5. re-read；
6. literal placeholder 不得存在 executable QA input。

Gate：

~~~text
T8_CANDIDATE_PLACEHOLDER_PRESENT=0
T8_CANDIDATE_EQUALS_ACCEPTED_T7=1
~~~

T8 branch只可擁有：

- QA harness；
- classifier；
- baseline compatibility probes；
- evidence；
- temporary workflow。

不得修 production behavior。

---

# 14. T8 cumulative matrix

## 14.1 Static architecture

- T0 ownership map exact；
- pure topology purity；
- derived controller ownership；
- Settings/Corner presentation direction；
- Registry presentation direction；
- Workspace shell direction；
- Assembly presentation direction；
- Operator Workspace direction；
- existing composition root single-owner；
- no reverse bridge import；
- no app owner deref；
- no duplicate state owner；
- no display-string authority leak；
- no direct class wiring；
- no facade binding growth；
- no unknown ownership；
- no move-only shallow wrappers。

## 14.2 Derived topology A/B

- physical part IDs；
- aggregate parent；
- child projection；
- selector keys；
- structure hierarchy；
- dynamic IDs；
- multipart profile/dimension projection；
- duplicate-label identity。

## 14.3 Derived sequencing/editor A/B

- settings refresh；
- model/family switch；
- active part switch；
- physical child editor commit；
- linked profile rebuild；
- topology expansion/contraction；
- Save/Reload；
- workspace dirty；
- one authoritative refresh path。

## 14.4 Settings / Corner UI parity

- structure；
- FW；
- bottom-wrap；
- assembly；
- symmetry；
- corner；
- edge controls；
- defaults；
- external settings/model；
- stale revision；
- confirm/cancel；
- text scale；
- layout/scroll。

## 14.5 Registry parity

- raw/display reversible mapping；
- rule form；
- preconditions；
- source/formula；
- candidate freshness；
- 2D preview；
- 3D preview/validation；
- matrix；
- promote；
- rule tree；
- joint form；
- certified file digest unchanged。

## 14.6 Workspace shell parity

- toolbar；
- keyboard；
- transaction controls；
- fullscreen；
- visual controls；
- status；
- output controls；
- persistent top；
- sticky structure；
- text scale；
- current layout contract。

## 14.7 Assembly parity

- rows/groups；
- collapse/detail；
- visibility；
- physical-piece nested rows；
- scroll；
- diagnostics；
- formal drawing cleanliness；
- receiving multi-door；
- divider/base plate；
- hidden piece manufacturing presence unchanged。

## 14.8 Operator Workspace parity

- home；
- input/content switch；
- structure tree；
- aggregate parent；
- physical child selector；
- active part；
- corner-data navigation/canvas；
- assembly page；
- return paths；
- hidden/visible view freshness；
- view recreate zero manufacturing mutation。

## 14.9 Protected parity

- Phase 2 manufacturing；
- Phase 3 Workspace/navigation；
- Phase 3 Project/persistence；
- Phase 3 Registry/diagnostics；
- Phase 3 Corner Data；
- lifecycle/update-intent；
- Phase 4 Settings；
- Phase 4 Final Scene；
- composition root；
- certified relief Registry；
- DXF；
- config；
- project round-trip；
- cabinet-family policy；
- DM6 annotation semantics。

## 14.10 Full regression

~~~text
baseline Headless
candidate Headless

baseline Xvfb
candidate Xvfb
~~~

Inherited baseline failures可存在。

要求：

~~~text
candidate-only failure = 0
candidate-only error = 0
~~~

## 14.11 Physical-part / DXF final gate

Phase 5 修改 bridge / GUI / presentation，會影響操作員看見、切換、回讀 physical part，因此 Final Acceptance 必須交接：

~~~text
驗證板件與DXF
~~~

至少：

- current physical parts enumeration；
- aggregate vs physical children；
- 2D / single3D / assembly identity；
- actual DXF export → reopen → compare；
- Save→Reload；
- multipart逐件；
- expected/actual DXF file count；
- config invariant。

Focused UI GREEN 不能取代此 gate。

---

# 15. Final classifier

T8 至少輸出：

~~~text
NEW_HEADLESS=[]
NEW_XVFB=[]
NEW_HEADLESS_ERRORS=[]
NEW_XVFB_ERRORS=[]

UNEXPLAINED_TOPOLOGY_DELTA=0
UNEXPLAINED_DERIVED_SEQUENCE_DELTA=0
UNEXPLAINED_SETTINGS_UI_DELTA=0
UNEXPLAINED_REGISTRY_UI_DELTA=0
UNEXPLAINED_WORKSPACE_SHELL_DELTA=0
UNEXPLAINED_ASSEMBLY_UI_DELTA=0
UNEXPLAINED_OPERATOR_WORKSPACE_DELTA=0
UNEXPLAINED_PROJECT_DELTA=0
UNEXPLAINED_EVENT_ORDER_DELTA=0
UNEXPLAINED_MANUFACTURING_DELTA=0
UNEXPLAINED_FINAL_SCENE_DELTA=0
UNEXPLAINED_DXF_DELTA=0

PROTECTED_DRIFT=0

PRE_SPEC_IMPLEMENTATION_ACCEPTED_AS_EVIDENCE=0
UNKNOWN_BRIDGE_OWNERS=0
SHALLOW_MOVE_ONLY_OWNERS=0
DUPLICATE_CANONICAL_OWNERS=0
DUPLICATE_PRESENTATION_STATE_OWNERS=0

REVERSE_BRIDGE_IMPORTS=0
NEW_APP_OWNER_DEREF_IN_DEEP_MODULES=0
DIRECT_CLASS_ASSIGNMENTS=0
FACADE_BINDINGS_GROWTH=0

PURE_TOPOLOGY_SELF_REFS=0
PURE_TOPOLOGY_TK_REFS=0
PURE_TOPOLOGY_BRIDGE_IMPORTS=0

DERIVED_CONTROLLER_WIDGET_CONSTRUCTION=0
DERIVED_CONTROLLER_GEOMETRY_AUTHORITY=0
BRIDGE_DERIVED_SEQUENCE_OWNERSHIP=0

SETTINGS_CORE_REVERSE_PRESENTATION_IMPORTS=0
SETTINGS_PRESENTATION_DOMAIN_OWNER=0

REGISTRY_PRESENTATION_FORMULA_OWNER=0
DISPLAY_STRING_AS_AUTHORITY=0

ASSEMBLY_PRESENTATION_MANUFACTURING_AUTHORITY=0
VISIBILITY_MUTATES_PHYSICAL_PRESENCE=0
VISIBILITY_MUTATES_DATUM=0
VISIBILITY_MUTATES_COLLISION=0

REMEMBERED_CHILD_AUTHORITY_LEAK=0
AGGREGATE_PARENT_REWRITE=0
VIEW_RECREATE_MUTATES_AUTHORITY=0

T8_CANDIDATE_PLACEHOLDER_PRESENT=0
T8_CANDIDATE_EQUALS_ACCEPTED_T7=1

PHASE5_DECISION=GREEN
~~~

T8 同時輸出 bridge/current owners metrics 作 observation；不以任意 LOC target 取代 classifier。

---

# 16. Event-order / View freshness invariant

Phase 3 / Phase 4 accepted ordering：

~~~text
geometry:
publish
→ full

display/camera:
publish
→ committed
~~~

View freshness：

~~~text
authoritative commit/apply
→ visible view refresh exactly once
~~~

Hidden View：

~~~text
no eager refresh
~~~

Replayed/stale revision：

~~~text
no-op
~~~

若 extraction 造成：

- duplicate publish；
- duplicate render；
- duplicate refresh；
- missing refresh；
- hidden eager refresh；
- widget-to-widget sync；
- view recreate mutation；

直接 RED。

---

# 17. RED handling

RED 先分類：

~~~text
requirement regression
production regression
stale contract
stale test oracle
stale fixture
harness/setup
baseline inherited debt
~~~

只有真 requirement / production regression 才改 production。

責任 routing：

~~~text
pure topology
→ T1

derived sequencing/editor
→ T2

Settings/Corner presentation
→ T3

Registry presentation
→ T4

Workspace shell
→ T5

Assembly presentation
→ T6

Operator Workspace / bridge compatibility
→ T7
~~~

流程：

~~~text
focused remediation branch
→ exact RED
→ minimal GREEN
→ focused regression
→ task A/B
→ protected invariant
→ non-force integration
→ readback
→ rerun cumulative
~~~

T8 branch禁止 patch product behavior。

---

# 18. Protected manifest

T0 建立逐檔 machine-readable manifest。

每筆：

~~~text
path
blob SHA / digest
owner category
allowed task exception
~~~

至少包含：

## Manufacturing

~~~text
phase6_manufacturing_cache.py
phase6_manufacturing_contracts.py
phase6_manufacturing_geometry.py
phase6_manufacturing_service.py
phase6_manufacturing_adapter.py
~~~

## Phase 3

~~~text
phase6_workspace_navigation_controller.py
phase6_project_controller.py
phase6_registry_diagnostics_controller.py
phase6_corner_data_view_adapter.py
gui_modules/application/command_router.py
gui_modules/application/lifecycle.py
gui_modules/application/state_sync.py
~~~

## Phase 4 Settings

~~~text
phase6_settings_contracts.py
phase6_settings_transitions.py
phase6_settings_service.py
phase6_settings_transaction_controller.py
phase6_settings_panel.py
~~~

## Phase 4 Final Scene

~~~text
phase6_final_scene_contracts.py
phase6_final_scene_projection.py
phase6_final_scene_renderer.py
phase6_final_scene_view.py
gui_modules/application/fold_designer_adapter.py
~~~

## Other

- config.ini；
- certified relief Registry；
- Cabinet Family policy；
- project schema/serializer；
- DXF baselines；
- DM6 semantic identity source/tests；
- physical-part identity/navigation contracts；
- Issue163/164 current UI layout contracts。

若 task 合法修改 protected presentation file，manifest 必須記 allowed exception + semantic invariant，不能把它從 manifest 移除。

---

# 19. Temporary QA / cleanup

每 task：

- one-shot workflow 不得被 docs/evidence push重觸發；
- acceptance terminal 後移除 task-only workflow/helper；
- tested-head → closing-head drift audit；
- production/test source無 drift才 accepted；
- durable checkpoint寫回。

T8 GREEN後：

1. 移除 temporary T8 workflows；
2. 移除 classifier / probe / helper；
3. pre-spec tooling若不再需要則移除；
4. tested candidate → cleaned candidate drift audit；
5. production readback；
6. physical-part/DXF final evidence；
7. issue closure guard；
8. close T8；
9. close Phase 5 master。

---

# 20. Completion definition

Phase 5 只有以下全部成立才完成：

~~~text
SPEC accepted

T0 accepted
T1 accepted + integrated + readback
T2 accepted + integrated + readback
T3 accepted + integrated + readback
T4 accepted + integrated + readback
T5 accepted + integrated + readback
T6 accepted + integrated + readback
T7 accepted + integrated + readback

T8 cumulative GREEN
physical-part/DXF final gate GREEN
temporary QA cleaned
tested→closing drift GREEN
production readback exact
no force push
no baseline substitution
~~~

Architecture completion：

~~~text
Pure topology:
- one canonical pure owner
- no Tk/self/bridge dependency

Derived sequencing:
- controller owns ordering invariant
- bridge no longer scripts internal sequence

Settings/Corner:
- presentation ownership explicit
- Phase4 core unchanged

Registry:
- presentation ownership explicit
- controller semantics unchanged
- raw/certified authority unchanged

Workspace shell:
- chrome presentation explicit
- project/output/lifecycle semantics unchanged

Assembly:
- presentation owner explicit
- identity/navigation/visibility/manufacturing separated

Operator Workspace:
- presentation owner explicit
- navigation domain owner unchanged
- aggregate parent / physical child semantics unchanged

Bridge:
- composition access
- top-level Tk event wiring
- explicit adaptation
- legacy compatibility only

No giant catch-all replacement
No move-only Middle Man
No duplicate canonical owner
~~~

---

# 21. 建議正式 Issue chain

只有本規格 accepted 後才建立。

~~~text
Phase 5 Master
WHD Fold Designer Phase 5 — Bridge Surface Decomposition / Capability Deep Modules & Presentation Boundaries

T0
Phase 5 T0 — Canonical bridge ownership / deletion-test census

T1
Phase 5 T1 — Pure Derived Topology / Operator Projection

T2
Phase 5 T2 — Derived Parts Controller / Editor Sequencing

T3
Phase 5 T3 — Settings / Corner Presentation Deepening

T4
Phase 5 T4 — Registry Presentation Deepening

T5
Phase 5 T5 — Workspace Shell / Persistent Controls

T6
Phase 5 T6 — Assembly Presentation Deepening

T7
Phase 5 T7 — Operator Workspace Presentation + Bridge Seam Compression

T8
Phase 5 T8 — Final cumulative root-baseline A/B / cleanup / closure
~~~

---

# 22. 建議 branch pattern

Spec accepted 後才使用：

~~~text
refactor/issue<id>-phase5-t0-ownership-20260920
refactor/issue<id>-phase5-t1-derived-topology-20260920
refactor/issue<id>-phase5-t2-derived-controller-20260920
refactor/issue<id>-phase5-t3-settings-presentation-20260920
refactor/issue<id>-phase5-t4-registry-presentation-20260920
refactor/issue<id>-phase5-t5-workspace-shell-20260920
refactor/issue<id>-phase5-t6-assembly-presentation-20260920
refactor/issue<id>-phase5-t7-operator-workspace-20260920
qa/issue<id>-phase5-t8-cumulative-20260920
~~~

---

# 23. 最重要的執行原則

Phase 5 不是：

~~~text
把 bridge 拆成更多檔
~~~

Phase 5 是：

~~~text
knowledge / invariant / state
→ 真 owner

interface
→ 穩定 test surface

presentation
→ 只投影 authoritative state

domain/manufacturing
→ 不依賴 presentation

compatibility
→ 不建立第二份 behavior

bridge
→ composition + top-level events + compatibility
~~~

成功標準不是「少幾千行」。

成功標準是：

~~~text
下一次修改某個 capability 時
開發者不必再理解整個 fold_designer_bridge.py
~~~

以及：

~~~text
刪掉新的 deep module
→ complexity 會散回 callers
~~~

這才代表 module 真正吸收了複雜度。

**ownership 沒變乾淨，LOC 再小也不算完成。**

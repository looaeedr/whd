# WHD Fold Designer Phase 5 規格書
## Bridge Surface Decomposition / Explicit Presentation & Compatibility Boundaries

**狀態：Draft for review — implementation blocked until accepted**  
**日期：2026-09-20**  
**Repository：`looaeedr/whd`**  
**Production branch：`cleanup/2d-3d-sync`**

---

# 0. Phase 5 固定起點

Phase 5 正式規格起點：

```text
PHASE5_ROOT_BASELINE =
396bfd96524a44a178c29bbefaf1b7c0437c119f
```

此 SHA 為：

1. Phase 4 已 cumulative GREEN、post-merge smoke GREEN、#397/#388 已關閉之後的 production；
2. pre-spec census tooling 曾被誤先 merge 進 production；
3. spec-authority guardrail 已修正並 merge 後的 production HEAD。

此 root **不可因後續 production 漂移任意替換**。

若 Phase 5 spec accepted 之後，其他不相關工作先進入 production：

- Phase 5 T1～T7 每個 task 的 predecessor 仍依本規格 accepted chain；
- T8 cumulative baseline 仍固定為 `PHASE5_ROOT_BASELINE`；
- 不得把較新的 production HEAD 偷換成 cumulative baseline；
- 若必須 reconcile concurrent production，需以 post-GREEN reconciliation 處理，不可替換 root evidence。

---

## 0.1 Pre-spec contamination / exploratory work disposition

在本規格建立前，曾誤啟動：

- #413 — pre-spec Phase 5 master draft；
- #414 — pre-spec T0 census bootstrap；
- #416 / PR #417 — pre-spec derived-topology exploratory extraction；
- pre-spec census tool / workflow 已進 production；
- #416 / PR #417 **未進 production**。

以上全部遵守：

```text
PRE_SPEC_EXPLORATORY_WORK != ACCEPTED_PHASE5_EVIDENCE
```

正式規則：

1. #416 / PR #417 不得 merge；
2. #416 的 RED / GREEN run 不得直接當正式 T1 acceptance；
3. pre-spec census script / workflow 可以在正式 T0 被**重新驗證後採用**，但不可因已存在就宣稱 T0 完成；
4. 正式 T0 必須在 spec accepted 後 fresh-run；
5. 若正式 T0 發現 pre-spec tooling 與本規格 canonical metric / protected manifest 不一致，必須修正或替換；
6. 不得以「已經做過」跳過 RED / intended RED / GREEN / A/B / protected invariant。

---

# 1. Phase 5 目的

Phase 3 已將多個高階 owner 從 `fold_designer_bridge.py` 抽出：

- Workspace / Navigation
- Settings Transaction
- Project / Persistence
- Registry / Diagnostics
- 2D Corner Data View
- 3D Final Scene View
- Lifecycle / Update Intent / Facade wiring

Phase 4 進一步將兩個最高風險 deep owner 分解：

## Settings

```text
mutable controller
→ immutable contracts
→ pure transitions
→ service / explicit effects
→ compatibility facade
```

## Final Scene

```text
owner=self + dynamic service bag
→ typed dependencies
→ pure projection
→ renderer/runtime
→ explicit result/effects
```

Phase 5 **不重做 Phase 3 / Phase 4**。

Phase 5 的真正目標是：

> 將 `fold_designer_bridge.py` 中仍然持有的 derived topology、operator projection、presentation construction、registry form、assembly panel、workspace chrome、content navigation、project/output UI wiring 與 legacy compatibility seams，依 ownership 再分解，使 bridge 真正回到 composition / event wiring / compatibility shell。

Phase 5 要證明：

```text
bridge-owned pure projection
→ pure projection owner

bridge-owned stateful derived-part sync
→ explicit controller/service owner

bridge-owned large Tk presentation builders
→ presentation adapter / panel owner

bridge-owned registry form orchestration
→ registry presentation owner

bridge-owned assembly presentation
→ assembly presentation owner

bridge-owned workspace chrome/navigation UI
→ workspace presentation owner

bridge-owned compatibility mirrors/wrappers
→ read-through delegation / thin seam

fold_designer_bridge.py
→ composition + Tk event wiring + compatibility only
```

---

# 2. Phase 5 起始 census

以 `PHASE5_ROOT_BASELINE` fresh-read：

```text
fold_designer_bridge.py

LINE_COUNT                  = 9460
TOP_LEVEL_DEF_CLASS_COUNT   = 344
_PHASE6_TOP_LEVEL_DEF_COUNT = 286
LITERAL_SELF_REF_COUNT      = 1423
UNIQUE_SELF_ATTR_COUNT      = 332
BRIDGE_BLOB_SHA             = 7ddbcec24693238772edb9209c271c57cdbe23f3
```

此表格是 Draft mirror。

正式 T0 必須建立 machine-readable source of truth。

---

## 2.1 Canonical metric

正式 T0 必須使用 canonical script：

```text
tools/phase5_bridge_census.py
```

若沿用 pre-spec 版本，必須先驗：

- script content / SHA；
- metric definition；
- root baseline；
- bridge blob SHA；
- source drift；
- protected manifest。

canonical 定義：

```text
LINE_COUNT
= canonical UTF-8 source splitlines 行數

TOP_LEVEL_DEF_CLASS_COUNT
= AST module.body 中 FunctionDef / AsyncFunctionDef / ClassDef 數

_PHASE6_TOP_LEVEL_DEF_COUNT
= module.body 中 name.startswith("_phase6_") 的 FunctionDef / AsyncFunctionDef 數

LITERAL_SELF_REF_COUNT
= source text regex self.([A-Za-z_][A-Za-z0-9_]*) match 數

UNIQUE_SELF_ATTR_COUNT
= 上述 attribute name 去重數
```

T0 必須額外輸出：

- 每個 top-level symbol start/end/span；
- 每個 `_phase6_*` ownership bucket；
- imports / reverse imports；
- direct app owner dereference；
- Tk / ttk / bind / trace / after ownership；
- compatibility mirror / wrapper；
- composition root references；
- unknown ownership count。

---

# 3. 現況問題定義

## 3.1 Bridge 已不再只是 compatibility shell

Phase 4 規格宣告 bridge 的目標角色為：

```text
Tk wiring
transaction coordination
scene/view adapter
legacy compatibility re-export
```

但 Phase 5 root 仍有：

```text
9460 lines
344 top-level def/class
286 _phase6_* top-level defs
1423 literal self.*
332 unique self attrs
```

Bridge 仍同時包含：

- pure part-key / hierarchy projection；
- multi-door projection；
- box-body physical-piece profile projection；
- authoritative derived-part synchronization；
- linked endcap/profile rebuild；
- Settings presentation wiring；
- Corner presentation wiring；
- registry translation/form/preview/promote UI；
- global/persistent toolbar construction；
- output controls；
- assembly diagnostics/presentation/collapsible panel；
- structure tree / piece selector；
- corner-data presentation shell；
- operator editor/value commit wiring；
- home screen construction；
- project/UI keyboard wrappers；
- update-intent compatibility wrappers。

這已超出單純 composition / compatibility shell。

---

## 3.2 Pure projection 與 app-owned state 仍混在 bridge

目前 bridge 仍含可獨立於 Tk/app 的邏輯，例如：

- door part projection；
- physical-piece key predicates；
- operator part selector projection；
- hierarchy projection；
- reverse fold traversal；
- box-body physical-piece profile projection；
- derived-part identity / label projection。

同一檔案也含 app/Tk/stateful path。

Phase 5 必須先把 pure projection 與 stateful synchronization 分離，不得把兩者一起搬到新的巨型 owner。

---

## 3.3 Presentation layer 大量存在於 bridge

目前 bridge 仍直接建立或刷新大量 Tk UI：

- Settings / structure / endcap / assembly / corner controls；
- registry forms；
- keyboard/project toolbar；
- persistent top area；
- output controls；
- assembly collapsible groups；
- structure tree；
- physical piece selector；
- corner-data canvas/panel；
- home view。

這些是 presentation responsibility，不應與 domain projection / project persistence / final scene owner 混為一體。

---

## 3.4 Compatibility seam 仍偏厚

Phase 3 / Phase 4 已建立多個正式 owner，但 bridge 仍有：

- mirror sync；
- state collect/build snapshot；
- thin-but-numerous wrappers；
- legacy field adapter；
- view property；
- publish/update wrappers。

Phase 5 不要求破壞 legacy caller，但要求：

```text
compatibility != duplicate ownership
```

若 legacy surface 必須保留：

- source of truth 只能有一份；
- bridge 使用 delegation / read-through；
- 不得再持有第二份 mutable state。

---

# 4. Phase 5 不做的事

Phase 5 是 **behavior-preserving architectural refactor**。

以下禁止順手修改：

- CornerType 機械語意；
- EndCap FW 公式；
- Fold Profile 公式；
- receiving / vault / cabinet family geometry；
- manufacturing solver ownership；
- divider / door / base plate / inner-door geometry；
- DXF schema / 基準檔幾何；
- config.ini defaults / semantics；
- project schema / serialization semantics；
- registry formula semantics；
- assembly joint semantics；
- part selector semantics；
- output stock / export semantics；
- keyboard shortcut semantics；
- 2D / 3D 顯示內容 redesign；
- UI layout redesign；
- 中文文案 redesign；
- assembly panel 功能 redesign；
- corner-data workflow redesign；
- update-intent/event order semantics。

若 cumulative acceptance 發現功能 regression：

```text
不得在大工單順手修功能
→ 定位責任 task
→ focused remediation
```

---

# 5. Protected owners / protected surfaces

Phase 5 原則上 frozen：

## Phase 4 Settings

```text
phase6_settings_contracts.py
phase6_settings_transitions.py
phase6_settings_service.py
phase6_settings_transaction_controller.py
phase6_settings_panel.py
```

允許：

- presentation port / adapter 接線最小 signature adaptation；
- import compatibility；
- test path update。

禁止：

- 把 state ownership 拉回 bridge；
- core 反向 import 新 presentation；
- 重寫 transition semantics。

---

## Phase 4 Final Scene

```text
phase6_final_scene_contracts.py
phase6_final_scene_projection.py
phase6_final_scene_renderer.py
phase6_final_scene_view.py
```

允許：

- composition/presentation adapter 接線；
- compatibility import；
- test path update。

禁止：

- 恢復 owner=self；
- 恢復 dynamic services dict；
- projection / renderer 回到 bridge；
- deep module import bridge。

---

## Phase 3 lower-coupling owners

```text
phase6_workspace_navigation_controller.py
phase6_project_controller.py
phase6_registry_diagnostics_controller.py
phase6_corner_data_view_adapter.py
```

Phase 5 可以建立新的 presentation adapter 依賴這些 owner。

禁止這些 owner 反向依賴 presentation/bridge。

---

## Phase 2 manufacturing

```text
phase6_manufacturing_cache.py
phase6_manufacturing_contracts.py
phase6_manufacturing_geometry.py
phase6_manufacturing_service.py
phase6_manufacturing_adapter.py
```

必须 semantic delta = 0。

---

## Other protected surfaces

至少：

- `config.ini`；
- 基準 DXF；
- cabinet-family policy；
- project schema / serializer；
- lifecycle/update-intent contracts；
- facade compatibility surface；
- operator part keys；
- UI visible text；
- keyboard command names；
- scene payload field names。

---

# 6. Dependency direction

Phase 5 必須維持：

```text
domain / pure projection / transition
        ↓
controller / service
        ↓
presentation adapter / panel
        ↓
application composition
        ↓
fold_designer_bridge compatibility seam
```

禁止：

```text
pure projection → bridge
controller/service → bridge
controller/service → Tk panel
domain → Tk
presentation owner → app owner dereference through generic self
new module → dynamic bridge service lookup
deep owner → fold_designer_bridge
```

Presentation/Tk module可以：

- import Tk/ttk；
- 建 widget；
- bind/trace/scroll；
- 讀 typed projection；
- 發出 typed intent / explicit callback port。

但：

```text
presentation does not own domain truth
```

---

# 7. Target architecture

Phase 5 的模組名稱是 **suggested target**；T0 可以依 live ownership census微調名稱，但不得改 ownership boundary 而不修規格。

---

## 7.1 Derived topology / operator projection

建議：

```text
phase6_derived_topology.py
```

負責 pure projection：

- door-part projection；
- physical-piece key classification；
- operator selector projection；
- structure hierarchy rows；
- reverse fold traversal；
- box-body physical-piece profile projection；
- derived physical-part identity；
- stable operator-facing labels/projections（若純）。

Hard rule：

```text
self.* = 0
Tk import = 0
bridge import = 0
app owner = 0
workspace mutation = 0
renderer mutation = 0
```

不得：

- solve manufacturing；
- mutate app；
- commit editor state；
- sync linked parts。

---

## 7.2 Derived-part synchronization / physical-part editing

建議：

```text
phase6_derived_parts_controller.py
```

或若 T0 證明責任更適合既有 owner，可建立等價 named controller。

負責：

- authoritative derived-part synchronization；
- linked endcap/profile rebuild；
- physical-piece editor state commit；
- linked profile refresh；
- derived source fingerprint / reconciliation coordination。

必須依賴 canonical manufacturing / structure / topology owners。

不得：

- duplicated geometry formula；
- direct Tk widget construction；
- final-scene rendering；
- registry presentation。

---

## 7.3 Settings / Corner presentation seam

建議：

```text
phase6_settings_presentation.py
```

或拆成：

```text
phase6_settings_presenter.py
phase6_corner_settings_presenter.py
```

若 T0 census 證明兩者 coupling 不宜同 owner，必須拆開。

負責 presentation/wiring：

- structure/endcap/assembly/corner controls；
- settings panel extension composition；
- visible editability/visibility projection；
- UI callbacks → typed request/intent；
- read-only projection → widget presentation。

不得：

- own Settings core state；
- duplicate Settings transition logic；
- mutate project/manufacturing directly；
- import bridge。

---

## 7.4 Registry presentation

建議：

```text
phase6_registry_panel.py
```

負責：

- token/formula/source/precondition presentation；
- rule form collection；
- 2D/3D preview UI plumbing；
- candidate current/stale presentation；
- rule tree UI；
- promote/add/delete form controls；
- floating registry form window。

依賴：

```text
phase6_registry_diagnostics_controller
→ explicit presentation DTO / actions
```

禁止 registry controller 反向 import panel。

---

## 7.5 Workspace chrome / persistent controls

建議：

```text
phase6_workspace_shell.py
```

負責 UI chrome：

- keyboard binding adapter；
- project toolbar；
- transaction buttons；
- visual controls；
- fullscreen presentation；
- global persistent controls；
- output controls；
- persistent top area；
- status bar；
- text scale presentation。

不得：

- own project persistence semantics；
- own output geometry；
- own navigation domain state。

---

## 7.6 Assembly presentation

建議：

```text
phase6_assembly_panel.py
```

負責：

- assembly diagnostics presentation；
- assembly group projection；
- part visibility controls；
- scroll/bind ownership；
- group/detail expand/collapse；
- assembly part panel refresh；
- box-body piece detail presentation；
- assembly view composition shell。

不得：

- compute assembly geometry；
- own joint semantics；
- mutate manufacturing solver；
- duplicate final-scene projection。

---

## 7.7 Workspace content / operator navigation presentation

建議：

```text
phase6_operator_workspace.py
```

負責：

- content switch；
- structure tree presentation；
- physical-piece selector presentation；
- active operator part activation UI；
- corner-data navigation presentation；
- corner-data canvas lifecycle；
- home view presentation；
- input/content page switching。

Domain navigation仍由：

```text
phase6_workspace_navigation_controller.py
phase6_part_navigation.py
phase6_corner_data_view_adapter.py
```

擁有。

---

## 7.8 Project / lifecycle compatibility seam

Project / persistence 不重新建立新 owner。

Bridge 中仍存在的：

- collect workspace state；
- build project snapshot；
- load/save/save-as wrapper；
- diagnostic file wrapper；
- export-dirty wrapper；
- publish / update-intent / preview wrappers；

Phase 5 應壓成：

```text
bridge thin delegation
→ existing project/lifecycle/composition owner
```

若 wrapper 不提供 compatibility value，應移除。

若 public caller 仍需要 symbol：

- bridge 可 re-export；
- 不得保留第二套 behavior implementation。

---

# 8. Bridge target

Phase 5 結束後 `fold_designer_bridge.py` 的合法責任：

```text
application composition access
Tk root / top-level event wiring
legacy compatibility imports/re-exports
thin delegation wrappers
facade installation
explicit boundary adaptation
```

不再直接擁有：

```text
pure derived topology
derived-part synchronization engine
large Settings/Corner presentation builders
registry form implementation
assembly panel implementation
workspace chrome builders
operator workspace/home/corner-data presentation
duplicated project/lifecycle behavior
```

Hard semantic gates：

```text
NEW_REVERSE_BRIDGE_IMPORTS=0
NEW_DYNAMIC_SERVICE_BAGS=0
NEW_APP_OWNER_DEREF_IN_DEEP_MODULES=0
DUPLICATE_DOMAIN_OWNERS=0
DUPLICATE_PRESENTATION_STATE_OWNERS=0
DIRECT_CLASS_MONKEY_PATCH_GROWTH=0
FACADE_BINDINGS_GROWTH=0
```

---

# 9. Size / coupling targets

數字 gate 不取代 semantic gate。

## 9.1 Root

```text
lines        = 9460
top-level    = 344
_phase6 defs = 286
self.*       = 1423
unique attrs = 332
```

## 9.2 Phase 5 target

T7 accepted production 目標：

```text
fold_designer_bridge.py

LINE_COUNT                  <= 6000
TOP_LEVEL_DEF_CLASS_COUNT   <= 240
_PHASE6_TOP_LEVEL_DEF_COUNT <= 180
LITERAL_SELF_REF_COUNT      <= 950
UNIQUE_SELF_ATTR_COUNT      <= 220
```

以上為 **machine hard target draft**。

若實際 T0 census 證明某一數字會迫使：

- duplicate owner；
- compatibility break；
- semantic rewrite；
- another giant catch-all owner；

則只能在 spec review 階段修 target，不得 implementation 過程自行放寬。

---

## 9.3 New-module anti-dump gate

Phase 5 不接受：

```text
把 3000 行 bridge
→ 搬進一個 3000 行 phase6_misc.py
```

每個新 owner 必須：

- responsibility coherent；
- dependency direction legal；
- 明確 state owner；
- 明確 presentation/domain boundary。

T8 必須輸出新 owner census：

- lines；
- self refs；
- unique attrs；
- Tk imports；
- bridge imports；
- app owner deref；
- public exports。

---

# 10. Execution authority / process

本規格遵守已 merge 的：

```text
EXECUTION_SCOPE_AUTHORITY_GATE_V1
SPEC_AUTHORITY_GATE_V1
```

在本規格為 Draft 時：

```text
SPECIFICATION_REQUIRED
```

允許：

- read production；
- census；
- spec drafting/review；
- candidate boundary analysis。

禁止：

- implementation issue chain；
- implementation branch；
- product/runtime code change；
- RED/GREEN implementation；
- production merge。

只有本規格被明確 accepted 後，才進 T0。

---

## 10.1 每個 implementation task

每一 task：

```text
fresh branch
→ predecessor exact readback
→ RED characterization
→ intended RED proof
→ minimal GREEN
→ focused regression
→ task-scoped A/B
→ protected invariant
→ non-force production integration
→ production readback
→ durable accepted checkpoint
```

禁止：

- 從未 accepted branch 疊下一 task；
- 偷換 predecessor；
- force-push production；
- 用 exploratory branch 當 predecessor；
- baseline 本來紅卻不分類；
- run 未 terminal 就宣稱 accepted；
- 沒有 concrete RUN 就宣稱驗收中。

---

# 11. Task chain

正式 task issue **只能在 spec accepted 後建立**。

---

## P5-T0 — Canonical bridge ownership census / preflight

目的：

- fresh-run root census；
- formalize ownership map；
- protected manifest；
- pre-spec tooling disposition；
- unknown ownership = 0。

Required output：

```text
docs/superpowers/checkpoints/phase5-t0-bridge-ownership.md
.scratch/phase5-t0-bridge-ownership.json
```

必須記錄：

### Bridge

- every top-level def/class；
- every `_phase6_*`；
- span；
- self refs；
- Tk reachability；
- app owner deref；
- callback roots；
- mirror/writeback；
- composition role；
- owner bucket。

### Candidate buckets

至少：

- composition/compatibility；
- pure derived topology；
- derived synchronization/editor；
- Settings/Corner presentation；
- Registry presentation；
- Workspace chrome；
- Assembly presentation；
- Operator workspace/navigation presentation；
- Project/lifecycle delegation；
- Final Scene compatibility；
- unknown。

Acceptance：

```text
ROOT_SHA_EXACT=1
BRIDGE_BLOB_SHA_RECORDED=1
UNKNOWN_OWNER_COUNT=0
PROTECTED_MANIFEST_COMPLETE=1
PRE_SPEC_EXPLORATORY_ACCEPTED_AS_EVIDENCE=0
PRODUCTION_SOURCE_DRIFT=0
```

T0 不做 product extraction。

---

## P5-T1 — Pure derived topology / operator projection extraction

建立或正式採用：

```text
phase6_derived_topology.py
```

正式範圍由 T0 owner map 決定，但至少覆蓋純：

- door projection；
- physical-piece identity；
- hierarchy/selector projection；
- reverse traversal；
- physical-piece profile projection。

RED：

```text
old bridge behavior fingerprint
==
candidate owner fingerprint
```

Hard purity：

```text
SELF_REFS=0
TK_IMPORTS=0
BRIDGE_IMPORTS=0
APP_OWNER_DEREF=0
WORKSPACE_MUTATION=0
MANUFACTURING_SOLVE=0
```

Pre-spec #416 implementation不得直接 merge；正式 T1 必須由 T0 accepted predecessor fresh branch 重做/重採並重新驗證。

---

## P5-T2 — Derived-part synchronization / physical-part editor ownership

建立：

```text
phase6_derived_parts_controller.py
```

或 T0 accepted equivalent。

搬移：

- authoritative derived-part synchronization；
- linked endcap/profile refresh/rebuild；
- editor-value commit sequencing；
- physical-piece profile commit；
- derived-source reconciliation。

不得：

- Tk widget construction；
- geometry formula duplication；
- renderer mutation；
- registry UI。

必驗：

- 1/2/3-piece box body；
- receiving family；
- multi-door；
- base plate；
- divider；
- linked endcaps；
- active physical-piece switching；
- profile edit round-trip；
- 2D/3D identity parity。

---

## P5-T3 — Settings / Corner presentation extraction

建立 presentation owner。

搬移 presentation-only responsibility：

- structure/endcap/assembly settings controls；
- symmetry controls；
- receiving bottom-wrap controls；
- corner settings controls；
- Settings panel extension wiring；
- visible editability/visibility projection。

Core source of truth仍在 Phase 4 Settings owners。

Hard gates：

```text
SETTINGS_CORE_REVERSE_PRESENTATION_IMPORTS=0
SETTINGS_CORE_STATE_DUPLICATION=0
PRESENTATION_DOMAIN_FORMULA_DUPLICATION=0
BRIDGE_SETTINGS_WIDGET_BUILDERS_REMAINING=0
```

Real-Tk parity：

- local edit；
- defaults；
- structure；
- FW；
- bottom-wrap；
- assembly；
- corner；
- external settings/model；
- UI text scale；
- confirm/cancel；
- dirty/update ordering。

---

## P5-T4 — Registry presentation extraction

建立：

```text
phase6_registry_panel.py
```

搬移：

- registry text presentation；
- formula/source/precondition form；
- candidate form；
- 2D preview；
- 3D validation/preview UI；
- formula matrix UI；
- promote；
- rule tree；
- joint form；
- registry window lifecycle。

Controller 不改 formula semantics。

Acceptance：

```text
REGISTRY_CONTROLLER_REVERSE_PANEL_IMPORTS=0
REGISTRY_FORMULA_SEMANTIC_DELTA=0
REGISTRY_PROJECT_DELTA=0
REGISTRY_2D_PREVIEW_DELTA=0
REGISTRY_3D_PREVIEW_DELTA=0
```

---

## P5-T5 — Workspace chrome / persistent controls extraction

建立：

```text
phase6_workspace_shell.py
```

搬移 presentation：

- keyboard shortcut adapter；
- project toolbar；
- transaction buttons；
- visual controls；
- fullscreen UI；
- global persistent controls；
- status bar；
- output controls；
- persistent top area；
- text-scale UI；
- sticky structure chrome。

Project/output semantics仍在 existing owners。

Real-Tk 必驗：

- toolbar；
- save/open/fullscreen shortcuts；
- transaction buttons；
- text-size medium/large；
- output controls；
- resize；
- clipping；
- focus/selected/disabled states。

---

## P5-T6 — Assembly presentation extraction

建立：

```text
phase6_assembly_panel.py
```

搬移：

- assembly diagnostics presentation；
- joint diagnostic menu；
- visibility controls；
- mousewheel ownership；
- presentation group projection；
- part detail state；
- box-body piece detail state；
- panel refresh；
- assembly page UI shell。

Hard gates：

```text
ASSEMBLY_PANEL_GEOMETRY_SOLVE=0
ASSEMBLY_PANEL_MANUFACTURING_MUTATION=0
ASSEMBLY_PANEL_FINAL_SCENE_FORMULA_DUPLICATION=0
DUPLICATE_SCROLL_BINDINGS=0
DUPLICATE_RENDER_TRIGGER=0
```

必驗：

- assembly collapsed/expanded defaults；
- part visibility；
- parent-child groups；
- mousewheel；
- selected/disabled state；
- diagnostics；
- receiving multi-door；
- divider/base plate；
- physical-piece details。

---

## P5-T7 — Operator workspace / navigation presentation + bridge seam compression

建立：

```text
phase6_operator_workspace.py
```

或 T0 accepted equivalent。

搬移：

- content switch；
- structure tree UI；
- physical-piece selector UI；
- active operator part UI；
- corner-data navigation/canvas；
- home page presentation；
- operator editor presentation。

同時做 bridge seam compression：

- redundant thin wrapper移除；
- project/lifecycle wrapper壓薄；
- read-through compatibility；
- composition access統一；
- legacy symbols以 import/re-export保留。

Hard gates：

```text
REVERSE_BRIDGE_IMPORTS=0
DIRECT_CLASS_WIRING=0
FACADE_BINDINGS_GROWTH=0
DUPLICATE_NAVIGATION_OWNERS=0
DUPLICATE_PROJECT_OWNERS=0
DUPLICATE_CORNER_DATA_OWNERS=0
```

Bridge quantitative target在此 task首次成為 blocking gate。

---

## P5-T8 — Final cumulative Phase 5 A/B / cleanup / closure

固定 cumulative baseline：

```text
BASELINE =
396bfd96524a44a178c29bbefaf1b7c0437c119f
```

Candidate：

```text
CANDIDATE =
T7_ACCEPTED_PRODUCTION_SHA
```

`T7_ACCEPTED_PRODUCTION_SHA` 是 placeholder。

T8 dispatch 前：

1. read T7 accepted checkpoint；
2. production readback == T7 accepted SHA；
3. 將 workflow/evidence placeholder換成實際 40-char SHA；
4. readback證明 placeholder已消失。

Gate：

```text
T8_CANDIDATE_PLACEHOLDER_PRESENT=0
T8_CANDIDATE_EQUALS_T7_ACCEPTED_PRODUCTION=1
```

---

# 12. T8 必跑矩陣

## Static architecture

- new pure topology purity；
- derived controller direction；
- Settings presentation direction；
- Registry presentation direction；
- Workspace shell direction；
- Assembly panel direction；
- Operator workspace direction；
- no reverse bridge imports；
- no app owner deep deref；
- no duplicate state/domain owner；
- no direct monkey-patch growth；
- bridge census targets。

## Derived topology A/B

- door identities；
- box-body physical pieces；
- operator selector keys；
- hierarchy；
- reverse traversal；
- physical-piece profiles；
- receiving sign semantics；
- dimensions；
- labels/part identity。

## Derived synchronization/editor A/B

- authoritative derived parts；
- linked endcap；
- profile refresh；
- active piece editor；
- physical-piece commit；
- project round-trip；
- 2D/3D part identity。

## Settings/Corner UI parity

- structure；
- FW；
- bottom-wrap；
- assembly；
- symmetry；
- corner；
- external sync；
- editability/visibility；
- transaction behavior；
- text scale。

## Registry parity

- form presentation；
- formula raw/display；
- preconditions；
- source；
- candidate stale/current；
- preview 2D；
- preview 3D；
- matrix；
- promote；
- rule tree；
- joint form。

## Workspace shell parity

- toolbar；
- keyboard；
- transaction buttons；
- visual controls；
- fullscreen；
- persistent controls；
- output；
- status；
- resize/text scale。

## Assembly parity

- groups；
- visibility；
- collapse；
- detail；
- scroll；
- diagnostics；
- joint menu；
- box-body pieces；
- receiving/multi-door；
- divider/base plate。

## Operator workspace parity

- home；
- input/content switch；
- structure tree；
- selector；
- physical-piece activation；
- corner-data navigation；
- corner-data canvas；
- return paths；
- editor commit。

## Protected parity

- Phase 2 manufacturing；
- Phase 3 workspace/navigation；
- Phase 3 project/persistence；
- Phase 3 registry diagnostics；
- Phase 3 corner-data；
- Phase 3 lifecycle/update-intent；
- Phase 4 Settings；
- Phase 4 Final Scene；
- config/DXF；
- project schema/round-trip；
- cabinet-family policy。

## Full regression

```text
baseline Headless
candidate Headless

baseline Xvfb
candidate Xvfb
```

不要求 inherited baseline 全綠。

要求：

```text
candidate-only failure = 0
candidate-only error = 0
```

---

# 13. Final classifier

T8 classifier 至少輸出：

```text
NEW_HEADLESS=[]
NEW_XVFB=[]
NEW_HEADLESS_ERRORS=[]
NEW_XVFB_ERRORS=[]

UNEXPLAINED_TOPOLOGY_DELTA=0
UNEXPLAINED_DERIVED_SYNC_DELTA=0
UNEXPLAINED_SETTINGS_UI_DELTA=0
UNEXPLAINED_CORNER_UI_DELTA=0
UNEXPLAINED_REGISTRY_UI_DELTA=0
UNEXPLAINED_WORKSPACE_UI_DELTA=0
UNEXPLAINED_ASSEMBLY_UI_DELTA=0
UNEXPLAINED_OPERATOR_WORKSPACE_DELTA=0
UNEXPLAINED_PROJECT_DELTA=0
UNEXPLAINED_EVENT_ORDER_DELTA=0
UNEXPLAINED_MANUFACTURING_DELTA=0
UNEXPLAINED_FINAL_SCENE_DELTA=0

PROTECTED_DRIFT=0

UNKNOWN_BRIDGE_OWNERS=0
DUPLICATE_DOMAIN_OWNERS=0
DUPLICATE_PRESENTATION_STATE_OWNERS=0

REVERSE_BRIDGE_IMPORTS=0
NEW_DYNAMIC_SERVICE_BAGS=0
NEW_APP_OWNER_DEREF_IN_DEEP_MODULES=0
DIRECT_CLASS_WIRING=0
FACADE_BINDINGS_GROWTH=0

BRIDGE_LINES_OVER_LIMIT=0
BRIDGE_TOP_LEVEL_OVER_LIMIT=0
BRIDGE_PHASE6_DEFS_OVER_LIMIT=0
BRIDGE_SELF_REFS_OVER_LIMIT=0
BRIDGE_UNIQUE_ATTRS_OVER_LIMIT=0

T8_CANDIDATE_PLACEHOLDER_PRESENT=0
T8_CANDIDATE_EQUALS_T7_ACCEPTED_PRODUCTION=1

PRE_SPEC_EXPLORATORY_ACCEPTED_AS_EVIDENCE=0

PHASE5_DECISION=GREEN
```

---

# 14. Event-order invariant

Phase 3 / Phase 4 accepted ordering保持：

```text
geometry:
publish
→ full

display/camera:
publish
→ committed
```

Phase 5 任何 presentation extraction 若改變：

- publish ordering；
- committed render ordering；
- update-intent coalescing；
- preview ordering；
- dirty ordering；

直接 RED。

除非另立功能變更工單，不接受「看起來等價但事件順序不同」。

---

# 15. UI / Real-Tk parity

Phase 5 涉及大量 presentation extraction，因此 Headless 不足。

T3～T7 與 T8 必跑 real-Tk/Xvfb。

最低客觀 gate：

- required widget exists；
- widget order / parent container identity符合 baseline；
- visibility state equal；
- selected/disabled/focus state equal；
- no clipping；
- no unexpected scrollbar；
- expected scrollbar remains；
- no duplicate binding；
- no duplicate trace；
- no duplicate event connection；
- no duplicate render；
- scroll target equal；
- keyboard shortcut target equal。

Screenshot review 可作補充，但不可取代 machine parity。

---

# 16. RED handling

若 task / T8 發現 regression，先定位責任 task：

```text
pure topology
→ T1

derived synchronization/editor
→ T2

Settings/Corner presentation
→ T3

Registry presentation
→ T4

Workspace chrome
→ T5

Assembly presentation
→ T6

operator workspace / bridge seam
→ T7
```

流程：

```text
focused remediation branch
→ focused RED
→ minimal GREEN
→ focused regression
→ task A/B
→ protected invariant
→ non-force integration
→ readback
→ rerun cumulative
```

禁止：

```text
T8 branch直接修 production behavior
```

T8 branch只允許：

- QA harness；
- classifier；
- baseline compatibility probe；
- evidence；
- temporary workflow。

---

# 17. Protected manifest

T0 必須建立逐檔 manifest。

至少：

## Phase 2 manufacturing

```text
phase6_manufacturing_cache.py
phase6_manufacturing_contracts.py
phase6_manufacturing_geometry.py
phase6_manufacturing_service.py
phase6_manufacturing_adapter.py
```

## Phase 3

```text
phase6_workspace_navigation_controller.py
phase6_project_controller.py
phase6_registry_diagnostics_controller.py
phase6_corner_data_view_adapter.py
gui_modules/application/lifecycle.py
gui_modules/application/state_sync.py
gui_modules/application/command_router.py
```

T0 必須 fresh-resolve實際存在檔案，不可假設。

## Phase 4 Settings

```text
phase6_settings_contracts.py
phase6_settings_transitions.py
phase6_settings_service.py
phase6_settings_transaction_controller.py
phase6_settings_panel.py
```

## Phase 4 Final Scene

```text
phase6_final_scene_contracts.py
phase6_final_scene_projection.py
phase6_final_scene_renderer.py
phase6_final_scene_view.py
```

## Other

- `config.ini`；
- DXF 基準檔；
- project schema/serializer；
- cabinet-family policy；
- accepted Phase 4 checkpoints/contracts；
- event-order contracts。

每筆：

```text
path
blob SHA / digest
owner category
allowed task exceptions
```

---

# 18. Temporary QA cleanup

每 task accepted 前：

- temporary task workflow可保留到 A/B完成；
- accepted checkpoint前移除 task-only artifacts；
- production readback證明 cleanup不改 behavior。

T8 GREEN後：

1. 移除 temporary T8 workflow；
2. 移除 temporary classifier/helper；
3. 清理 pre-spec exploratory branch/PR引用；
4. production readback；
5. candidate source unchanged；
6. final closure gate；
7. close T8；
8. close Phase 5 master。

---

# 19. Completion definition

Phase 5 只有以下全部成立才算完成：

```text
SPEC accepted

T0 accepted + readback
T1 accepted + integrated + readback
T2 accepted + integrated + readback
T3 accepted + integrated + readback
T4 accepted + integrated + readback
T5 accepted + integrated + readback
T6 accepted + integrated + readback
T7 accepted + integrated + readback

T8 cumulative GREEN

temporary QA cleaned
pre-spec exploratory work not reused as acceptance
production readback exact
no force push
no baseline substitution
```

Ownership completion：

```text
Derived topology:
- pure owner established
- bridge definition removed

Derived sync/editor:
- explicit controller owner
- no Tk construction
- no duplicated geometry

Settings/Corner:
- presentation owner established
- core ownership unchanged

Registry:
- presentation owner established
- controller semantics unchanged

Workspace:
- chrome/persistent presentation owner established
- project/navigation semantics unchanged

Assembly:
- presentation owner established
- no geometry/manufacturing ownership

Operator workspace:
- navigation presentation separated from navigation domain owner

Bridge:
- composition/compatibility shell
- quantitative gates GREEN
- no new reverse imports
- no duplicate owners
```

---

# 20. 建議正式工單標題

**注意：以下工單只能在 spec accepted 後建立。**

```text
Phase 5 Master
WHD Fold Designer Phase 5 — Bridge Surface Decomposition / Explicit Presentation & Compatibility Boundaries

T0
Phase 5 T0 — Canonical bridge ownership census + protected preflight

T1
Phase 5 T1 — Pure derived topology / operator projection extraction

T2
Phase 5 T2 — Derived-part synchronization / physical-part editor ownership

T3
Phase 5 T3 — Settings / Corner presentation extraction

T4
Phase 5 T4 — Registry presentation extraction

T5
Phase 5 T5 — Workspace chrome / persistent controls extraction

T6
Phase 5 T6 — Assembly presentation extraction

T7
Phase 5 T7 — Operator workspace extraction + bridge seam compression

T8
Phase 5 T8 — Final cumulative root-baseline A/B / cleanup / closure
```

---

# 21. 建議 branch pattern

**Spec accepted 後才使用：**

```text
refactor/issue<id>-phase5-t0-preflight-20260920
refactor/issue<id>-phase5-t1-derived-topology-20260920
refactor/issue<id>-phase5-t2-derived-controller-20260920
refactor/issue<id>-phase5-t3-settings-presentation-20260920
refactor/issue<id>-phase5-t4-registry-presentation-20260920
refactor/issue<id>-phase5-t5-workspace-shell-20260920
refactor/issue<id>-phase5-t6-assembly-panel-20260920
refactor/issue<id>-phase5-t7-operator-workspace-20260920
qa/issue<id>-phase5-t8-cumulative-20260920
```

---

# 22. 最重要的執行原則

Phase 5 不是：

```text
bridge 太大
→ 隨便找一塊搬出去
```

也不是：

```text
continuity 要求不停
→ 可以自己創造下一個 Phase
```

Phase 5 要證明：

```text
accepted spec
→ approved ownership boundary
→ approved task graph
→ autonomous execution inside that scope
```

以及：

```text
pure projection
→ pure owner

stateful synchronization
→ explicit controller

Tk construction
→ presentation owner

domain owner
→ no Tk / no bridge

presentation owner
→ no domain truth

compatibility
→ read-through / delegation

fold_designer_bridge.py
→ composition + event wiring + compatibility
```

**沒有 accepted spec，不開始 implementation。**

**沒有 ownership 變乾淨，即使 bridge 行數下降，也不算 Phase 5 完成。**

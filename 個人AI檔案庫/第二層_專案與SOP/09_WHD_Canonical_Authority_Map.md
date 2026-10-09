---
whd_doc_role: CURRENT
whd_contract: canonical-authority-map
whd_canonical: null
whd_schema: WHD_DOC_META_V1
whd_doc_id: WHD-SOP-CANONICAL-AUTHORITY-MAP
---

# WHD Canonical Authority Map

<!-- WHD_AUTHORITY_MAP_V1 -->

本文件只回答穩定的工程 contract 目前由哪一個 path 擁有，以及同一 contract 下哪些 artifacts 是 REFERENCE / MIRROR / HISTORICAL。它不複製各 domain 的完整規格、不保存 ticket acceptance narrative，也不把 validation evidence 升格成 production authority。

## Authority roles

- `CURRENT`：該 contract 唯一現行 canonical owner；同一 contract 只能有一個 CURRENT。
- `REFERENCE`：背景、方法、incident evidence 或延伸說明；不得覆蓋 CURRENT。
- `MIRROR`：相容入口／導覽；必須 pointer-only 指回 canonical owner。
- `HISTORICAL`：被取代或日期化 evidence；不得參與 current routing。

若 REFERENCE / MIRROR / HISTORICAL 與 CURRENT owner 衝突，以 CURRENT owner 為準。若 CURRENT owner 要搬移，必須在同一變更中完成新 owner、舊 owner 降級與永久 guard 更新，禁止暫留雙 CURRENT。

## Machine-readable authority rows

<!-- WHD_AUTHORITY contract=canonical-authority-map role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md -->

<!-- WHD_AUTHORITY contract=push-delivery-skill role=CURRENT path=.agents/skills/engineering/推推/SKILL.md -->
<!-- WHD_AUTHORITY contract=root-local-first-workflow role=CURRENT path=.agents/skills/engineering/root-local-first/SKILL.md -->
<!-- WHD_AUTHORITY contract=deterministic-repo-migration role=CURRENT path=.agents/skills/engineering/deterministic-repo-migration/SKILL.md -->
<!-- WHD_AUTHORITY contract=agent-startup-process role=CURRENT path=AGENTS.md -->
<!-- WHD_AUTHORITY contract=agent-startup-process role=MIRROR path=handoff/00_AI_HANDOFF_README.md canonical=AGENTS.md -->
<!-- WHD_AUTHORITY contract=knowledge-preflight role=CURRENT path=AGENTS.md -->

<!-- WHD_AUTHORITY contract=phase6-startup-baseline-model role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/10_WHD啟動基準型號規則.md -->
<!-- WHD_AUTHORITY contract=phase6-assembly-shared-content-presentation role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/11_WHD組合體SharedContent呈現規則.md -->
<!-- WHD_AUTHORITY contract=fold-designer-bridge-ownership role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md -->

<!-- WHD_AUTHORITY contract=manufacturing-architecture role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md -->
<!-- WHD_AUTHORITY contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md -->

<!-- WHD_AUTHORITY contract=phase6-dimension-semantics role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md -->
<!-- WHD_AUTHORITY contract=phase6-dimension-semantics role=MIRROR path=07_Phase6尺寸語意與標準截角母規則.md canonical=個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md -->

<!-- WHD_AUTHORITY contract=manufacturing-layer-classification role=CURRENT path=加工層分類與定義.md -->
<!-- WHD_AUTHORITY contract=manufacturing-layer-classification role=MIRROR path=標準基準檔格式.md canonical=加工層分類與定義.md -->


<!-- WHD_AUTHORITY contract=workstation-poweroff-safety role=CURRENT path=tools/workstation_poweroff_gate.py -->
<!-- WHD_AUTHORITY contract=ha-poweroff-projection role=CURRENT path=tools/whd_poweroff_ha_bridge.py -->
<!-- WHD_AUTHORITY contract=local-durability-machine role=CURRENT path=tools/local_durability_gate.py -->



<!-- WHD_AUTHORITY contract=issue-closure role=REFERENCE path=個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md -->

<!-- WHD_AUTHORITY contract=skill-routing role=CURRENT path=.agents/skills/skill_registry.json -->
<!-- WHD_AUTHORITY contract=skill-classification role=CURRENT path=.agents/skills/skill_catalog.json -->

<!-- WHD_AUTHORITY contract=pitfall-ledger role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md -->
<!-- WHD_AUTHORITY contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md -->

## localX integration and publication authority

- Repository work is made and validated locally on `localX` in `/workspace/whd`.
- `origin/localX` can be used as backup; it does not grant permission to publish X.
- Only a current explicit user `/推推` authorizes publication to `cleanup/2d-3d-sync` (X), subject to exact PR and commit verification.
- No task execution transaction, lease, work-slot, or control-plane preflight is required for local modifications.

## Permanent routing boundaries

- Executable enforcement 由對應 executable CURRENT owner 負責；文件 marker 或測試字串不得冒充 machine state。
- `skill-routing` 與 `skill-classification` 分別由 registry / catalog 擁有；README 只做 navigation。
- `fold-designer-bridge-ownership` 只擁有 composition/bootstrap/presentation owner boundary；不得覆蓋 geometry、manufacturing、Registry formula、project persistence 等 domain CURRENT owner。
- `pitfall-ledger` 的 routing ownership 留在本 Map；實際 pitfall artifacts 全部保持 REFERENCE / incident evidence，不建立平行 process/domain CURRENT。
- 日期化 acceptance、migration、combined guard 與 ticket provenance 留在 `docs/superpowers/verification/`、`docs/superpowers/checkpoints/`、Git history 或 GitHub Issue，不進本 Map 的 normative body。

### local-durability-machine

- Executable CURRENT owner：`tools/local_durability_gate.py`。
- 只根據 fresh local-machine snapshot 分類 `LOCAL_CLEAN_SYNCED / LOCAL_DIRTY_RECOVERABLE / LOCAL_DIRTY_CONFLICT / LOCAL_UNPUSHED / LOCAL_MUTATION_IN_PROGRESS / LOCAL_MACHINE_UNAVAILABLE`。
- Remote clean state 不得覆蓋 dirty / unknown local truth；local evidence 不完整時 fail closed 為 `LOCAL_DIRTY_CONFLICT / LOCAL_STATE_CONFLICT`。
- `LOCAL_MACHINE_UNAVAILABLE` 必須投影 `ERROR / LOCAL_MACHINE_UNREACHABLE`，不得假裝 remote clean 或與 conflict 混用。
- 此 owner 不負責 planned handoff、scheduler takeover 或 power-off aggregation。

### interactive-runtime-liveness

- Executable CURRENT owner：`tools/interactive_runtime_liveness.py`。
- Interactive markers 固定為 `WHD_INTERACTIVE_RUNTIME_LIVENESS_V1` / `WHD_INTERACTIVE_RUNTIME_END_V1`。
- Heartbeat / END 目前仍維持 #679 parser 的相容欄位 `issue + slot_id + worker + invocation_identity + conversation_identity + claim_blob_sha + branch + head_sha + executor_source=chat`；END identity drift fail closed。
- `conversation_identity=UNAVAILABLE` 不構成有效 interactive liveness evidence；generic `executor_source=chat` 也不能取代 exact provenance。
- Scheduler 的 `WHD_SCHEDULER_RUNTIME_*` 仍由 `tools/scheduler_runtime_liveness.py` 獨立擁有；兩者不得互相冒充。

### workstation-poweroff-safety

- Executable CURRENT owner：`tools/workstation_poweroff_gate.py`。
- Public machine seam：`evaluate --snapshot` 與 `validate-safe`；兩者都必須 side-effect-free，不得執行 GitHub/claim/Guard/HA/Windows mutation。
- Gate result domain 固定為 `SAFE / NOT_SAFE / ERROR`；unknown、parser failure、dependency failure 或不可觀測 local state 一律 fail closed，禁止轉成 `SAFE`。
- `SAFE` receipt 必須綁 `poweroff_request_id + evidence_revision`；request/revision drift 或 receipt 非 SAFE 時 validator 必須失效。
- Guard transaction、scheduler readiness、checkpoint HEAD/next_action、local runtime durability 與所有 local-dependent slots 聚合都由此 executable owner 判定；HA/Node-RED 只能消費 projection，不得另建平行 safety state machine。
- `LOCAL_MACHINE_UNAVAILABLE` 的 canonical projection 是 `ERROR / LOCAL_MACHINE_UNREACHABLE`；不得與 `LOCAL_STATE_CONFLICT` 混用。

- 真正 Windows shutdown actuator 不屬本 contract；此 owner 只提供 machine safety decision。

### ha-poweroff-projection

- Executable CURRENT owner：`tools/whd_poweroff_ha_bridge.py`。
- Transport 選定 `NODE_RED_EXEC`：既有家庭自動化能力已有 Node-RED，但 repository 在本次 acceptance 沒有 canonical REST / MQTT / whd-monitor server owner；因此採用 thin exec transport，避免新增常駐 server 或第二套 state machine。
- Input request schema 固定為 `WHD_HANDOFF_REQUEST_V1`；HA / Node-RED 只搬運 `poweroff_request_id + evidence_revision + requested_at_epoch_seconds + timeout_seconds` 與 gate receipt，不推導 Git / claim / checkpoint / Guard state。
- Projection schema 固定為 `WHD_HA_POWER_OFF_PROJECTION_V1`，結果域只允許 `SAFE / NOT_SAFE / ERROR`；projection transport marker 固定為 `NODE_RED_EXEC`。
- `SAFE` 唯一可接受來源是 `tools/workstation_poweroff_gate.py::validate_safe_receipt` 對 current `poweroff_request_id + evidence_revision` 的成功驗證；舊 request / 舊 revision 的 SAFE 一律 fail closed。
- Freshness 由 request 的 `requested_at_epoch_seconds + timeout_seconds` 決定；超時固定投影 `ERROR / TIMEOUT`。Malformed / unknown receipt 固定投影 `ERROR`，不得轉成 SAFE。
- `NOT_SAFE` / `ERROR` receipt 只做 fail-closed transport projection，不得升格。Projection 本身 side-effect-free；同一 current request 在 timeout 前可安全 retry，timeout 後必須建立 fresh request。
- HA / Node-RED 不是 WHD authority，也不得重建 claim/checkpoint/Guard evaluator。此 contract 不連接真正 Windows shutdown actuator。

## Change contract

新增或搬移 authority 時：

1. 先決定穩定 contract id 與唯一 CURRENT owner。
2. 舊入口若仍保留，只能降為 `REFERENCE` / `MIRROR` / `HISTORICAL`；MIRROR 必須 pointer-only。
3. 更新本 Map 的 machine-readable rows。
4. 只在必要時更新直接相關 Skill / router / AI Library navigation。
5. 跑永久 authority uniqueness、mirror pointer、metadata 與 routing guards。
6. 驗證只能判斷 authority 是否一致，不得反過來創造 domain truth。

### whd-chatgpt-scheduled-resume / execution control plane

- AI Library MIRROR/reference: `個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md`
- record/store: `tools/execution_record.py` + `tools/execution_record_store.py`
- scheduler/exit: `tools/execution_scheduler_view.py` + `tools/execution_invocation_exit.py`
- work-slot: `tools/execution_work_slot_view.py`
- explicit READY ingress: `tools/execution_dispatch_ingress.py`
- mutation policy: `tools/execution_authority_policy.py`
- runtime observability (NON_AUTHORITY): `coord/monitor-v2:.dispatch/monitor/runtime/*.json`，schema=`WHD_RUNTIME_OBSERVATION_V1`；只供 whd-monitor/HA 顯示 WAKE/PROGRESS/EXIT，不得授權 execution mutation。
- default interactive slot gate: 未指定 slot 的 USER_EXPLICIT + EXECUTE_TICKET 正規化為 `worker.slot.0`；explicit `/工作1/2/3` 與 scheduler lane 不受覆蓋。

ready-index只作 DERIVED_CACHE_ONLY。所有舊 workflow Skills只作 pointer/bridge。2026-09-28前的舊 ownership/prewrite/heartbeat/finalization語意為HISTORICAL；保留 transports已 fail-closed。

Generation fencing：只有 current generation + canonical branch + expected fingerprint/head具有authority；舊generation寫入為ORPHAN_WRITE，可salvage工程成果但不可直接accept。

<!-- ISSUE693_COMBINED_ACCEPTANCE_WRITEBACK_V1 -->
## #693 Combined Acceptance durable readback

- domain: `authority_map`
- accepted chain: `#687/#688/#689/#690/#691/#692 -> #693`
- integration source head: `64a64d4a0ee8adae81396eaef52c16db97b57d4f`
- historical retained invariant at #693 acceptance time: production/trusted governance parity was machine-readable and unknown divergence failed closed.
- this writeback records durable acceptance/readback only; it does not create a second authority or state machine.
- deployment/readback manifest: `docs/governance/issue693_combined_acceptance_writeback_manifest.json`

<!-- WHD_PHASE7_OWNERSHIP_WRITEBACK_V1 -->
## Phase 7 accepted ownership map

Phase 7 Large Module Decomposition 的 CURRENT routing 結論如下。這些 rows 只描述穩定 owner boundary；ticket、run、commit 與 LOC 數字只作 provenance，不是 domain truth。

- **P7-A / Fold Designer Bridge residual**：`fold_designer_bridge.py` 只保留 bounded bootstrap / lifecycle / legacy-host / evidence-backed compatibility surface。update scheduler owner 是 `gui_modules.application.command_router`；唯一 composition wiring root 是 `gui_modules/application/fold_designer_adapter.py::Phase6FoldDesignerComposition`；workspace/navigation 由 `phase6_workspace_navigation_controller.py` / `phase6_designer_workspace.py` 擁有；FinalScene 由 `phase6_final_scene_view.py` + composition adapter 擁有；Settings presentation 由 `phase6_settings_panel.py` +既有 Settings composition services 擁有。
- **P7-B / Phase6ApplicationHost**：`gui.py::Phase6ApplicationHost` 是 thin application host/composition surface；Door Layout state/transaction owner 是 `gui_modules/application/door_layout_controller.py::Phase6DoorLayoutController`；Door presentation owner 是 `gui_modules/parts/panels/door.py`；render acquisition/presentation 由 `gui_modules/application/render_snapshots.py` + `gui_modules/rendering/door_view.py` 擁有。
- **P7-C / ae.py**：`ae_engine/ae.py` 是 legacy/public compatibility facade；DXF serialization owner 是 `ae_engine/dxf_serialization.py`；baseline source/cache/resource owners 是 `ae_engine/baseline_source.py` + `ae_engine/baseline_resources.py`；baseline-to-scene adapter owner 是 `ae_engine/baseline_scene_adapters.py`。
- **P7-D / manufacturing_api**：`ae_engine/manufacturing_api.py` 是 thin public facade；verification / export / request-precedence / render-data orchestration 分別由 `ae_engine/manufacturing_verification.py`、`ae_engine/manufacturing_export.py`、`ae_engine/manufacturing_requests.py`、`ae_engine/manufacturing_render.py` 擁有。
- **P7-E / assembly_collision**：`ae_engine/assembly_collision.py` 是 thin shared collision/backprojection compatibility facade；generic collision/backprojection owner 是 `ae_engine/collision_backprojection.py`；Divider relief solver owner 是 `ae_engine/divider_relief_solver.py`；EndCap world-relief solver owner 是 `ae_engine/endcap_world_relief_solver.py`。
- **P7-F / explicit-joint manufacturing**：`phase6_manufacturing_geometry.py::_phase6_resolve_explicit_joint_reliefs` 保持 thin compatibility/manufacturing facade；bounded explicit-joint orchestration owner 是 `phase6_explicit_joint_pipeline.py`；canonical collision/backprojection solver truth 仍在 `ae_engine.assembly_collision`；world/cut geometry truth 仍由 `phase6_manufacturing_geometry.py` 的 canonical helpers 透過 bounded ops 注入。
- **P7-G / Settings presentation**：**KEEP_CURRENT_BOUNDARY**。CURRENT presentation owner 是 `phase6_settings_panel.py::Phase6SettingsPanel`；唯一 construction/wiring root 是 `Phase6FoldDesignerComposition`；`fold_designer_bridge.py` 僅保留 compatibility projection/dataflow delegates；canonical Settings mutation/state authority 留在既有 transaction/service/application owners；pure Settings→Profile planning owner 是 `phase6_settings_profile_projection.py`。
- **DM8-B0 / Part Session compatibility orchestration**：CURRENT application compatibility orchestration owner 是 `gui_modules/application/fold_designer_part_session.py::Phase6PartSessionOwner`。它只擁有 part activation/save 的 sequencing 與 compatibility effect ordering；navigation/workspace identity 仍由 `Phase6WorkspaceNavigationController` / `Phase6DesignerWorkspace` 擁有，project persistence仍由既有 project/session owners擁有，update scheduling仍由 `gui_modules.application.command_router` 擁有，render/manufacturing/Settings/domain truth均不移入 Part Session owner。Historical #448/#526 的「不建立新 Part Editor domain owner」invariant仍有效；其 activation/save body location lock 已由 merged #1321 supersede，#1324 僅為未合併 governance residue。

- **DM8-C2 製造場景公開 access CURRENT（X 已驗收）**：ae_engine/manufacturing_scene_access.py 的 owner_render_data、replace_owner_render_data 是 receiving_joint_marking.py 與 receiving_pairing_marking.py 的公開 seam。ResolvedManufacturingGeometry、CUTTING/MARKING 幾何公式、DXF 和 FinalScene 真值仍由原 manufacturing/domain owner 唯一持有，scene access 不形成第二套求解權責。
- **DM8-B1/B2 Fold Designer Capability CURRENT（X 已驗收）**：唯一 Phase6FoldDesignerComposition root 仍在 gui_modules/application/fold_designer_adapter.py，具體 bounded ports 由 fold_designer_composition_state.py 的 build_capability_owners 組裝，fold_designer_capability_owners.py 只提供 Project、Settings、Workspace、Registry、Receiving、AssemblyCorner 狹義 application capability，禁止完整 app/service bag、second root、reverse Bridge import。Bridge 必要 callers 走 composition.capabilities 的 workspace/settings/registry 接口；不再恢復無使用者薄路由。原 Project persistence、Settings transaction、Workspace navigation、Registry rule、manufacturing geometry 與 FinalScene owner 不變；#1341/#396 與 #1386 測試使用結構式權責、不再要求固定 routed-method/LOC 數字。
- **發布證據 REFERENCE**：使用者當次 /推推 授權 PR #1457，WHD Change Lane Gate 與 Canonical Product Regression Run 37911058569 SUCCESS；GitHub 原生正式 X merge SHA ddfe789f54c865cca1a77ce143d79e0ef141ff29，tree 98d42b1bef8c1b6077eacfaada183216cfe33967。日期化證據留 docs/governance/DM8_LOCALX_COMBINED_ACCEPTANCE_STATUS_20261009.md，不是第二個 CURRENT。


永久 invariant：reverse-import Bridge = 0、duplicate production owner = 0、second composition root = 0、full-app service-bag owner interface = 0。後續變更若要搬移上述 owner，必須走 deletion-test / authority writeback / permanent guard；不得只靠 wrapper rename 或 facade forwarding 宣稱 ownership 已移動。

Accepted provenance：Phase 7 child chain #613/#617/#618/#620/#621/#623/#624/#625；Combined Acceptance owner #626，combined regression run `36277114074` GREEN @ `77429fa487166e0598c2f00e4d5ff1fa2d837219`。

<!-- ISSUE702_MUTATING_TOOLCALL_CRASH_RECOVERY_WRITEBACK_V1 -->
## Assembly-relief persisted state / replay contract

- CURRENT persisted-state contract owner：`phase6_assembly_relief_state.py`。
- Owner 只負責 deterministic profile/source fingerprint、family-structure fingerprint、Certified rule revision replay validity、persisted source matching、atomic Head/Tail state construction，以及已保存 CUTTING polygon 的 replay eligibility/materialization。
- `gui_modules/application/manufacturing_adapter.py` 只蒐集 current manufacturing/workspace context 並 delegate replay 判定；不得重新實作 Registry revision / source identity / profile equality 規則。
- `fold_designer_bridge.py` 的 runtime solve / workspace collection 仍是 bounded application/effect seam；persisted source-signature / serialization / source-match implementation 已 delegate 到同一 owner，不得形成第二份 contract。
- `ae_engine.certified_relief_registry` 仍唯一擁有 Certified formula/rule/revision authority；`phase6_assembly_relief_state.py` 只驗 current revision 是否仍可 replay，不得建立或修改 Registry rule。
- collision/backprojection、manufacturing geometry、placement、Final Material 與 DXF geometry authority不在此 owner；validation evidence不得回灌製造公式。

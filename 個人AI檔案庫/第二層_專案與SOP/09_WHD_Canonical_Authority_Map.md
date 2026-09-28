---
whd_doc_role: CURRENT
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
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
<!-- WHD_AUTHORITY contract=flow-v2-execution role=CURRENT path=.agents/skills/engineering/flow-v2-execution/SKILL.md -->
<!-- WHD_AUTHORITY contract=flow-v2-record-model role=CURRENT path=tools/execution_record.py -->
<!-- WHD_AUTHORITY contract=flow-v2-record-store role=CURRENT path=tools/execution_record_store.py -->
<!-- WHD_AUTHORITY contract=flow-v2-atomic-transaction role=CURRENT path=tools/control_transaction.py -->
<!-- WHD_AUTHORITY contract=flow-v2-action-contract role=CURRENT path=tools/execution_action_contract.py -->
<!-- WHD_AUTHORITY contract=flow-v2-scheduler-view role=CURRENT path=tools/execution_scheduler_view.py -->
<!-- WHD_AUTHORITY contract=flow-v2-scheduler-startup-bundle role=CURRENT path=tools/scheduler_startup_bundle.py -->
<!-- WHD_AUTHORITY contract=flow-v2-control-step-sequence role=CURRENT path=tools/control_transaction_step_executor.py -->
<!-- WHD_AUTHORITY contract=flow-v2-invocation-exit role=CURRENT path=tools/execution_invocation_exit.py -->
<!-- WHD_AUTHORITY contract=flow-v2-authority-policy role=CURRENT path=tools/execution_authority_policy.py -->

<!-- WHD_AUTHORITY contract=work-root-gate-validation role=CURRENT path=tools/work_root_gate.py -->
<!-- WHD_AUTHORITY contract=agent-startup-process role=CURRENT path=AGENTS.md -->
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

<!-- WHD_AUTHORITY contract=continuous-execution-machine role=HISTORICAL path=tools/continuity_controller.py -->
<!-- WHD_AUTHORITY contract=continuous-execution-machine role=REFERENCE path=個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md -->

<!-- WHD_AUTHORITY contract=workstation-poweroff-safety role=CURRENT path=tools/workstation_poweroff_gate.py -->\n<!-- WHD_AUTHORITY contract=ha-poweroff-projection role=CURRENT path=tools/whd_poweroff_ha_bridge.py -->
<!-- WHD_AUTHORITY contract=local-durability-machine role=CURRENT path=tools/local_durability_gate.py -->
<!-- WHD_AUTHORITY contract=interactive-runtime-liveness role=CURRENT path=tools/interactive_runtime_liveness.py -->

<!-- WHD_AUTHORITY contract=continuous-execution-operations role=MIRROR path=.agents/skills/engineering/executable-continuity-controller/SKILL.md -->
<!-- WHD_AUTHORITY contract=continuous-execution-operations role=REFERENCE path=個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md -->

<!-- WHD_AUTHORITY contract=remote-qa-monitoring role=CURRENT path=.agents/skills/engineering/monitoring-remote-qa/SKILL.md -->

<!-- WHD_AUTHORITY contract=issue-closure role=MIRROR path=.agents/skills/engineering/issue-closure-gate/SKILL.md -->
<!-- WHD_AUTHORITY contract=issue-closure role=REFERENCE path=個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md -->

<!-- WHD_AUTHORITY contract=skill-routing role=CURRENT path=.agents/skills/skill_registry.json -->
<!-- WHD_AUTHORITY contract=skill-classification role=CURRENT path=.agents/skills/skill_catalog.json -->

<!-- WHD_AUTHORITY contract=pitfall-ledger role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md -->
<!-- WHD_AUTHORITY contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md -->

## Work-root bootstrap authority

- canonical workspace root identity/data lives in Google Drive at `/Google Drive/WHD`.
- canonical external gate: `/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json`.
- repository pointer-only mirror: `.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json`; it exists only so GitHub-only / scheduler runtimes can read the same root identity before general repo discovery.
- machine validator: `tools/work_root_gate.py`.
- interactive/chat runtime must read the Google Drive canonical gate + Current Source Manifest; GitHub-only / `SCHEDULER_LANE` uses the mirror and may not reinterpret GitHub checkout, `/mnt/data`, `/`, or Library `/WHD` as the default workspace root.
- Flow v2 mutation startup evidence must include `WHD_WORK_ROOT_GATE_EVIDENCE_V1`; missing/mismatched root identity fails closed before ExecutionRecord state read.

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
- Heartbeat / END 必須綁 exact `issue + slot_id + worker + invocation_identity + conversation_identity + claim_blob_sha + branch + head_sha + executor_source=chat`；END identity drift fail closed。
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

- AI Library CURRENT reference: `個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md`
- operational CURRENT owner: `.agents/skills/engineering/flow-v2-execution/SKILL.md`
- native semantic state: `coord/execution-v2:.dispatch/execution/issue-<N>.json`
- record/store: `tools/execution_record.py` + `tools/execution_record_store.py`
- atomic mutation: `tools/control_transaction.py`
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
- retained invariant: Production/trusted governance parity is machine-readable and unknown divergence fails closed.
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

永久 invariant：reverse-import Bridge = 0、duplicate production owner = 0、second composition root = 0、full-app service-bag owner interface = 0。後續變更若要搬移上述 owner，必須走 deletion-test / authority writeback / permanent guard；不得只靠 wrapper rename 或 facade forwarding 宣稱 ownership 已移動。

Accepted provenance：Phase 7 child chain #613/#617/#618/#620/#621/#623/#624/#625；Combined Acceptance owner #626，combined regression run `36277114074` GREEN @ `77429fa487166e0598c2f00e4d5ff1fa2d837219`。

<!-- ISSUE702_MUTATING_TOOLCALL_CRASH_RECOVERY_WRITEBACK_V1 -->
## Mutating toolcall crash-recovery — HISTORICAL → Flow v2 mapping

#702 的 crash-boundary經驗保留為歷史來源；CURRENT semantics已由 Flow v2 atomic transaction吸收。所有 side effect 綁 generation/fingerprint/head/target並 fresh readback；effect已存在就 RECONCILE，不 replay；identity/outcome不明就 CONFLICT/FAILED。

<!-- WHD_OUTAGE_RECOVERY_REPLAY_SAFETY_V1 -->
### outage-recovery-replay-safety

CURRENT owner是 Flow v2 ExecutionRecord + atomic transaction + generation fencing。
- exact active remote run仍是lock。
- unknown side-effect outcome先RECONCILE，禁止猜測/replay。
- local-only未持久化狀態不可由remote clean狀態反推。
- overlapping/late runtime以generation fencing隔離；舊generation只可作donor evidence。
- planned HANDOFF使用同一native record，不建立平行ownership database。

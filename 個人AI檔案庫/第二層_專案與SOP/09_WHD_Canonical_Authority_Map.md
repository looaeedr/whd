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

<!-- WHD_AUTHORITY contract=continuous-execution-machine role=CURRENT path=tools/continuity_controller.py -->
<!-- WHD_AUTHORITY contract=continuous-execution-machine role=REFERENCE path=個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md -->

<!-- WHD_AUTHORITY contract=continuous-execution-operations role=CURRENT path=.agents/skills/engineering/executable-continuity-controller/SKILL.md -->
<!-- WHD_AUTHORITY contract=continuous-execution-operations role=REFERENCE path=個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md -->

<!-- WHD_AUTHORITY contract=remote-qa-monitoring role=CURRENT path=.agents/skills/engineering/monitoring-remote-qa/SKILL.md -->

<!-- WHD_AUTHORITY contract=issue-closure role=CURRENT path=.agents/skills/engineering/issue-closure-gate/SKILL.md -->
<!-- WHD_AUTHORITY contract=issue-closure role=REFERENCE path=個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md -->

<!-- WHD_AUTHORITY contract=skill-routing role=CURRENT path=.agents/skills/skill_registry.json -->
<!-- WHD_AUTHORITY contract=skill-classification role=CURRENT path=.agents/skills/skill_catalog.json -->

<!-- WHD_AUTHORITY contract=pitfall-ledger role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md -->
<!-- WHD_AUTHORITY contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md -->

## Permanent routing boundaries

- Executable enforcement 由對應 executable CURRENT owner 負責；文件 marker 或測試字串不得冒充 machine state。
- `skill-routing` 與 `skill-classification` 分別由 registry / catalog 擁有；README 只做 navigation。
- `fold-designer-bridge-ownership` 只擁有 composition/bootstrap/presentation owner boundary；不得覆蓋 geometry、manufacturing、Registry formula、project persistence 等 domain CURRENT owner。
- `pitfall-ledger` 的 routing ownership 留在本 Map；實際 pitfall artifacts 全部保持 REFERENCE / incident evidence，不建立平行 process/domain CURRENT。
- 日期化 acceptance、migration、combined guard 與 ticket provenance 留在 `docs/superpowers/verification/`、`docs/superpowers/checkpoints/`、Git history 或 GitHub Issue，不進本 Map 的 normative body。

## Change contract

新增或搬移 authority 時：

1. 先決定穩定 contract id 與唯一 CURRENT owner。
2. 舊入口若仍保留，只能降為 `REFERENCE` / `MIRROR` / `HISTORICAL`；MIRROR 必須 pointer-only。
3. 更新本 Map 的 machine-readable rows。
4. 只在必要時更新直接相關 Skill / router / AI Library navigation。
5. 跑永久 authority uniqueness、mirror pointer、metadata 與 routing guards。
6. 驗證只能判斷 authority 是否一致，不得反過來創造 domain truth。

### whd-chatgpt-scheduled-resume

- AI Library CURRENT owner: `個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md`
- Executable state owner: `tools/continuity_controller.py`
- Operational Skill owner: `.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- Remote QA bridge: `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`
- Development execution bridge: `.agents/skills/engineering/執行開發任務/SKILL.md`
- Primary wake/executor: hourly ChatGPT scheduled re-entry
- GitHub Actions schedule role: watchdog / lease / remote-state safety net only

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


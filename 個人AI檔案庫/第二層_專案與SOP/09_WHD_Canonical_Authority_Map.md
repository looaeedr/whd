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

<!-- WHD_AUTHORITY contract=workstation-poweroff-safety role=CURRENT path=tools/workstation_poweroff_gate.py -->
<!-- WHD_AUTHORITY contract=local-durability-machine role=CURRENT path=tools/local_durability_gate.py -->
<!-- WHD_AUTHORITY contract=interactive-runtime-liveness role=CURRENT path=tools/interactive_runtime_liveness.py -->

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

<!-- ISSUE646_AUTHORITY_MAP_V1 -->
## #646 authority map additions

- Guard transaction / duplicate GREEN / expired recovery：tools/execution_claim_guard.py
- stale/takeover + delegated/helper traversal：tools/stale_claim_takeover.py
- checkpoint/turn-exit/closure/fingerprint：tools/continuity_controller.py
- scheduler heartbeat selector：tools/scheduler_runtime_liveness.py
- trusted remote turn-exit：.github/workflows/whd-turn-exit-gate.yml
- trusted remote finalization：.github/workflows/whd-remote-finalization.yml
- orchestration responsibility：.agents/skills/engineering/派工/SKILL.md

Prompt/Skill/AI Library不得複製第二套 state machine。Interactive heartbeat/liveness + exact provenance 已由 `tools/interactive_runtime_liveness.py` 擁有；scheduler lane + invocation 仍由 `tools/scheduler_runtime_liveness.py` 擁有。兩者 namespace / identity 不得混用；generic executor_source 永遠不等於 exact runtime provenance。

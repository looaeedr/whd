# #209 T5 Preflight Evidence

[當前角色：T5 實作者]

Parent: #203
Depends on: #208 CLOSED / completed
Accepted parent head: `a098498d7459e974bbf18a5573e6b209eaeb4404`
Branch: `refactor/issue209-part-panels-20260914`

READ_SKILL: UI設計與去AI味
READ_SKILL: 程式碼庫設計
READ_SKILL: Python測試實務
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: 驗證板件與DXF
READ_SKILL: phase6-assembly-view-boundaries
READ_SKILL: phase6-release-packaging
READ_PROCESS: AGENTS.md Phase6 Knowledge Preflight / Branch-First / dispatch / issue closure
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: release_required_artifacts.json

## T5 authoritative boundaries reread
- physical identity, operator navigation, and renderer visibility are distinct responsibilities;
- multi-piece body keeps one top-level `箱身` navigation entry while nested child tabs retain stable physical identities;
- 2D/3D active-child navigation must round-trip the same physical child;
- child visibility changes renderer mask only; it must not remove manufacturing/collision/persistence geometry or alter world placement;
- Receiving side/back physical child commit authority differs from W split-body projection authority;
- part panels may present selectors/inputs and forward intent, but must not become geometry/state/persistence authority.

## Full-gate release evidence reread
- full/release QA must be fail-closed and preserve execution-tree provenance;
- `.scratch/**` is temporary evidence and never package authority;
- `config.ini` remains protected and UPDATE-forbidden;
- required artifacts/policy come from machine-readable `release_required_artifacts.json`, not from chat memory;
- this T5 acceptance is not a release package build, but its full-gate classification still requires the release skill/reference evidence.

## T5 dependency gate
Before moving any widget construction:
1. inventory selector/panel symbols and callers;
2. classify each as pure presentation / widget construction / event forwarding / authoritative mutation;
3. only pure presentation or widget construction with an explicit callback/command seam may move;
4. state-changing callbacks must return to the `gui.py` orchestrator;
5. no Event Bus, Store, duplicated model, geometry authority, or physical identity redefinition;
6. Receiving/Vault, single/multipart, Divider/Door/Base Plate and selector/visibility behavior require L1/L4 acceptance.

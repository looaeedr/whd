# 2026-09-11 Skill Stack × Issue #104 Integration Evidence

Task: 將已驗收的中文 Skill identity／寫技能／派工／找技能 stack 整合到最新 `cleanup/2d-3d-sync`，不得回退 Issue #104 的 DXF verifier tolerance authority。

## Integration basis

- production target snapshot: `cleanup/2d-3d-sync @ 424bbc166ea8ff472c044410a78b2449d877c71e`
- accepted Skill stack tip: `feat/add-find-skill-20260910 @ d35a3fe9da7eb895267b2a57237d2f44f2fe2fda`
- reconciled Skill-side head: `16f5e9cd123de0b1841617e2f0b70eef4ecec1fe`
- merged engineering tree: `cfd44693aca3186eb136b17f053b7076c09123a5`
- deterministic two-parent merge commit: `574c4c4f1cbdbe75733ad181ff0e3a3b75132d88`
- integration branch: `integration/skill-stack-onto-issue104-20260911`

Parents of the merge commit:
1. `424bbc166ea8ff472c044410a78b2449d877c71e` — latest production target snapshot
2. `16f5e9cd123de0b1841617e2f0b70eef4ecec1fe` — accepted Skill stack with explicit verifier reconciliation

## Required source evidence read

- `AGENTS.md`
- `.agents/skills/skill_registry.json`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`
- `.agents/skills/engineering/驗證板件與DXF/SKILL.md`
- `.agents/skills/engineering/寫技能/SKILL.md`
- `.agents/skills/engineering/派工/SKILL.md`
- `.agents/skills/engineering/掃描深模組/SKILL.md`
- `.agents/skills/productivity/找技能/SKILL.md`
- `.agents/skills/engineering/phase6-release-packaging/SKILL.md`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: release_required_artifacts.json

## Conflict resolution authority

The only material overlapping Skill authority found against the newer target was `.agents/skills/engineering/驗證板件與DXF/SKILL.md`.

The integration result intentionally keeps both valid rule sets:

1. Skill-stack rules:
   - `修改DXF` is not a WHD project Skill;
   - validation cannot replace editing capability;
   - Receiving Divider manufacturing authority is certified `CROSS（十字截角）＋參數` / Registry / approved reference DXF;
   - collision/backprojection remains shadow verification and cannot override a Registry HIT.
2. Issue #104 rules from latest production:
   - production manufacturing snap and verifier numerical-equivalence tolerance are separate authorities;
   - verifier may reconnect only inside its own `coordinate_tolerance`;
   - any gap greater than verifier tolerance remains detectable as `CUTTING_MISMATCH`;
   - real Receiving door DXF roundtrip coverage remains required via `tests/test_receiving_door_dxf_roundtrip.py`.
3. Current-target Skill `.agents/skills/engineering/截角資料入口收斂/SKILL.md` is retained in the merged engineering tree.

## Deterministic tree audit

Target `424bbc166...` → integration merge `574c4c4f...` is `ahead`, `behind_by=0`. The file-level delta is limited to the intended Skill stack: 30 Skill/router/evidence/contract/AI/release-policy paths; no production Python, GUI, Bridge, DXF registry, baseline geometry or config file is replaced by the old Skill branch.

Skill-side reconciled head `16f5e9cd...` → integration merge `574c4c4f...` is also `ahead`, `behind_by=0`; the integration contains the newer target's Issue 94–104 production/test work, including `ae_engine/dxf_acceptance.py`, `gui.py`, `fold_designer_bridge.py`, `tests/test_receiving_door_dxf_roundtrip.py`, current AI DXF tolerance boundary, and `截角資料入口收斂`.

## Remote QA history

### Run 1 — Preflight evidence gate

- run: `34586357202`
- head: `ba227c82dc0e4af01d0c9098296430bd6f24099c`
- terminal: **FAILURE**
- classification: **Preflight evidence incomplete; not a product/contract failure**.
- setup/dependencies/config snapshot succeeded; `config.ini` before SHA was `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.
- missing evidence reported by Preflight:
  - Skill `phase6-corner-3d-model-integrity`
  - `基準檔/截角資料庫/README_母規則說明.md`
  - `基準檔/截角資料庫/certified_relief_rules.json`
  - `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
  - `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- all missing authorities were then read and are explicitly recorded above; no production/Skill/test logic was changed for this failure.

## Remote QA scope

One-shot workflow: `.github/workflows/skill-stack-issue104-integration-20260911.yml`

Required matrix:
- Chinese Skill identity/content contract
- `修改DXF` project-scope contract
- `找技能` contract
- `寫技能` contract + Preflight route
- `派工` timeout / 30-second / remote-QA contract
- `掃描深模組` language/source contracts
- Phase6 Skill Preflight gate
- release packaging + integrity gates
- current `tests/test_dxf_acceptance.py`
- current `tests/test_receiving_door_dxf_roundtrip.py`
- explicit reconciliation marker guard
- `config.ini` before/after SHA invariant
- `git diff --exit-code` after tests

## Acceptance state

Replacement QA triggered by this evidence update. Do not merge into `cleanup/2d-3d-sync` until the locked replacement run is terminal GREEN, the one-shot workflow is removed and re-read as 404, and tested-head → cleaned-head drift is limited to QA cleanup/evidence only.

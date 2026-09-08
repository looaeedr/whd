# DM2 Phase6 Knowledge Preflight Evidence

Task: Issue #52 DM2 — 收斂 Divider Family/Fold/FW Physical Geometry Contract
Branch: `work/dm2-divider-physical-contract`

## Required skill verification

- VERIFIED_SKILL: phase6-corner-3d-model-integrity
- Read: `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
- Applied constraints: canonical manufacturing geometry remains the single geometry source; do not fix only renderer/2D; 2D/single-3D/assembly-3D/DXF/Save-Reload must remain aligned; true physical semantics must not be replaced by bbox/world-axis guesses; `config.ini` must not drift.

## Required references

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- Key guard: FW is an independent physical/source-of-truth dimension and must not be merged/reallocated as an arbitrary fold segment; production topology must not branch on fixed segment counts; same effective FW must feed 2D/3D/CornerPolicy/FinalScene/DXF/project.

READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
- Key guard: Skill controls how AI changes code; certified registry controls manufacturing relief answers. Do not create a second relief formula. Outside dimensions and material segment dimensions are distinct.

READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
- Key guard: Registry HIT is canonical manufacturing relief; semantic target/geometry inputs remain authoritative. DM2 does not change certified formulas, product dimensions, or hole positions.

READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
- Key guard: certified geometry cannot be replaced by 3D discovery; formed FW may be shadow evidence but not runtime CUTTING oracle; receiving family scope must not leak as a global rule; 2D/3D/assembly/save-reload consume canonical material.

## Planned files declared to Preflight

- `docs/superpowers/plans/2026-09-08-divider-physical-contract.md`
- `ae_engine/door_dividers.py`
- `ae_engine/manufacturing_api.py`
- `fold_designer_bridge.py`
- `tests/test_dm1_divider_physical_contract.py`
- `tests/test_issue40_divider_6p4_shared_datum.py`
- `tests/test_assembly_collision_integration.py`

## Non-goals

- No product dimension change.
- No hole-position change.
- No new relief authority.
- No Receiving-only sink workaround.
- AI Library / Skill formal authority writeback remains DM5 scope.

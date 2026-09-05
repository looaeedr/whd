# Formed FW Registry / 3D Relief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make formed Box Body FW the certified 3D assembly relief source of truth for OVERLAY and invalidate stale persisted relief.

**Architecture:** Resolve formed FW once from the current Box Body Fold Profile, declare it as a geometry input in the Certified Relief Registry, and let the certified evaluator produce X-only relief while keeping EndCap Y semantics independent. Persisted relief becomes a versioned cache validated against the same formed-FW/profile/registry signature.

**Tech Stack:** Python 3, dataclasses, JSON registry, Shapely, Tk/Xvfb, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-formed-fw-registry-3d-relief-design.md`

## Global Constraints

- Do not modify `config.ini`.
- Do not hard-code 29; derive formed FW from current Box Body Fold Profile + thickness.
- Do not alter INSERT / INSERT_OVERLAY semantics.
- EndCap material FW stays independent from Box Body formed FW.
- Final delivery must pass real `金庫型貼外.p6fold`, full assembly intent matrix, zero-penetration, 2D/3D/assembly, and Save/Reload gates.

---

### Task 1: Lock the formed-FW manufacturing invariant

**Files:**
- Modify: `tests/test_certified_relief_registry_completion.py`
- Create: `tests/test_overlay_formed_fw_registry_contract.py`
- Fixture: `tests/fixtures/vault_overlay_w400_t2_fw25.p6fold`

**Interfaces:**
- Consumes: `formed_box_body_fw_widths(profile, thickness)`.
- Produces: regression contract top 29/342/29 and bottom 3/394/3.

- [ ] Write failing tests that require registry OVERLAY to declare formed-FW geometry input and require the real fixture to resolve top X cut to 29, not 25/40.
- [ ] Run only these tests and record the expected RED failures.
- [ ] Keep the real uploaded `.p6fold` as the fixture source, not a synthetic scalar-only case.

### Task 2: Make Registry own the formed-FW rule

**Files:**
- Modify: `基準檔/截角資料庫/certified_relief_rules.json`
- Modify: `基準檔/截角資料庫/certified_relief_rules.schema.json`
- Modify: `ae_engine/certified_relief_registry.py`
- Test: `tests/test_certified_relief_registry_schema_v2.py`
- Test: `tests/test_overlay_formed_fw_registry_contract.py`

**Interfaces:**
- Consumes: Box Body X profile + sheet thickness.
- Produces: OVERLAY certified rule whose X result equals formed FW and whose Y result remains based on EndCap FW.

- [ ] Add explicit `geometry_inputs: ["BOX_BODY_FORMED_FW"]` to OVERLAY rule and parser/schema validation.
- [ ] Change the OVERLAY evaluator so flat-X `side_fold = formed_fw - endcap_fw`; `resolve_corner_relief()` then yields X=`formed_fw` while Y remains unchanged.
- [ ] Reject the certified result when formed FW cannot be resolved rather than silently falling back to nominal side folds.
- [ ] Run registry schema/evaluator tests GREEN.

### Task 3: Version and validate committed relief cache

**Files:**
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py`
- Test: `tests/test_certified_relief_runtime_contract.py`
- Test: `tests/test_overlay_formed_fw_registry_contract.py`

**Interfaces:**
- Produces: `RELIEF_CONTRACT_VERSION = 2`; source signature contains `box_body_formed_fw` and per-part active registry revision.
- Consumes: same formed-FW resolver used by Registry.

- [ ] Add failing tests proving legacy/stale 40-mm committed cuts are rejected when version/fingerprint/revision is absent or mismatched.
- [ ] Serialize contract version, formed FW and registry rule revisions with committed relief.
- [ ] Replay only when all scalar/profile/formed-FW/registry signatures match; otherwise return empty cuts so fresh solve runs.
- [ ] Run persistence tests GREEN.

### Task 4: Make resolved 3D geometry enforce the rule

**Files:**
- Modify: `ae_engine/resolved_manufacturing_geometry.py` or current resolved-geometry owner discovered in code.
- Modify: `ae_engine/assembly_collision.py` only if needed for post-solve collision validation.
- Test: `tests/test_resolved_manufacturing_geometry.py`
- Test: `tests/test_assembly_collision_integration.py`
- Test: `tests/test_overlay_formed_fw_registry_contract.py`

**Interfaces:**
- Consumes: certified canonical relief and current assembly solids.
- Produces: one resolved manufacturing geometry consumed by all render/export paths.

- [ ] Add failing test that certified OVERLAY 29-mm relief is used by resolved geometry and post-solve penetration is zero.
- [ ] Ensure certified rule is canonical and 3D solver shadow validates it without replacing it with old 25/40 geometry.
- [ ] Fail/mark conflict if certified geometry still penetrates instead of silently accepting it.
- [ ] Run resolved geometry + collision tests GREEN.

### Task 5: Full data-chain regression and documentation

**Files:**
- Modify: `.agents/skills/engineering/phase6-overlay-relief-basis/SKILL.md`
- Modify: `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- Modify: `release_required_artifacts.json`
- Create: `docs/superpowers/verification/2026-08-29-formed-fw-registry-3d-relief.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: release evidence and future-agent guardrails.

- [ ] Replace prior incorrect 25/40 guidance with material FW vs formed FW distinction.
- [ ] Run real fixture 2D/single3D/assembly equality and Save→Reload.
- [ ] Run registry-driven INSERT / OVERLAY / INSERT_OVERLAY Head/Tail matrix, pre-solve collision, post-solve zero penetration.
- [ ] Run release integrity and verify `config.ini` hash unchanged.
- [ ] Package FULL + cumulative UPDATE with same Asia/Taipei timestamp; UPDATE includes `個人AI檔案庫/**` and excludes `config.ini`.

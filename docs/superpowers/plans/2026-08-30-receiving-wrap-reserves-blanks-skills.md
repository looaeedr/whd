# Receiving WRAP Reserves, Blanks, and Skills Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. This workspace is a non-Git isolated project copy, so file snapshots and test checkpoints replace commits.

**Goal:** Make receiving EndCap bottom WRAP an explicit linked lower-face option with adjustable X/Y reserves, keep WRAP manufacturing distinct from INSERT/OVERLAY/INSERT_OVERLAY, expose canonical unfolded blank data for every sheet-metal part, and relocate all project skills to `.agents/skills/` while strengthening the 3D/corner-change skill contract.

**Architecture:** Receiving side/back split remains the Box Body structural SOT. Head/Tail retain their existing Assembly Intent, while a receiving-only lower-face WRAP flag and reserve values live in canonical receiving structure state and are linked by default across Head/Tail. Certified relief formulas consume those explicit reserve values; known Registry HITs are canonical and 3D only shadow-validates them. Blank dimensions are measured from each part's final canonical material rather than recomputed by a second formula.

**Tech Stack:** Python 3, Tkinter, Shapely, pytest, JSON registry, Phase6 FinalScene/Manufacturing API.

**Spec:** Approved in-chat design, 2026-08-30 conversation.

## Global Constraints

- Traditional Chinese UI text.
- Never modify `config.ini`.
- Receiving Box Body remains `THREE_PIECE_SIDE_BACK_SPLIT`; WRAP is not a Box Body structure or EndCap Assembly Intent.
- Receiving lower WRAP is a Head/Tail lower-face option and participates in Head/Tail linkage.
- Known certified corner formulas are not rediscovered on every draw; 3D is discovery on MISS and shadow validation on HIT.
- 2D, Single3D, Assembly3D, DXF/NC and blank display consume one canonical manufacturing geometry.
- Head/Tail settings may be linked, but their final material/blank is always measured independently.
- All project skills must live under `.agents/skills/`.
- Any skill touching corner relief or 3D visualization must require 3D-model truth, pre/post collision checks, 2D/3D equality, save/reload, and registry-driven regression.

---

### Task 1: Canonical receiving lower-WRAP state and adjustable reserves

**Files:**
- Modify: `ae_engine/cabinet_types/receiving.py`
- Modify: `phase6_box_body_structure.py`
- Modify: `ae_engine/certified_relief_registry.py`
- Modify: `基準檔/截角資料庫/certified_relief_rules.json`
- Test: `tests/test_receiving_bottom_wrap_registry.py`

**Interfaces:**
- Produces `bottom_relief_reserves(state) -> tuple[float,float]`
- Produces `set_bottom_relief_reserves(state, reserve_u=None, reserve_v=None) -> dict`
- Produces `bottom_external_wrap_enabled(state) -> bool`
- Produces `set_bottom_external_wrap(state, enabled) -> dict`
- Formula variables include `reserve_u`, `reserve_v`.

- [ ] Run the existing reserve/WRAP tests and verify RED because production state/evaluator is incomplete.
- [ ] Add receiving side/back config defaults `bottom_external_wrap=True`, `bottom_relief_reserve_u=2.0`, `bottom_relief_reserve_v=1.0`.
- [ ] Add pure receiving getters/setters that normalize state and preserve unrelated configuration.
- [ ] Add `reserve_u/reserve_v` to the formula evaluator whitelist and runtime variables.
- [ ] Change `RECEIVING_ENDCAP_BOTTOM_INSERT_OVERLAY_WRAP_V1` to use `side_fold + rear_bend - reserve_u`, `ybottom1 - reserve_v`, `side_fold`, `reserve_v` and update display/source metadata.
- [ ] Make receiving bottom registry replacement conditional on lower WRAP being enabled.
- [ ] Run receiving registry tests GREEN.

### Task 2: Head/Tail lower-WRAP linkage and locked-parameter UI

**Files:**
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py` only where main-GUI serialization must carry the same canonical state.
- Test: add/modify focused Fold Designer receiving tests.

**Interfaces:**
- Consumes receiving canonical structure state from Task 1.
- UI shows `下方外側包覆`, `X 預留`, `Y 預留` only inside the parameter-unlocked receiving EndCap controls.
- WRAP + reserves are one linked setting source for Head/Tail; settings sync by linkage, final geometry does not copy polygons.

- [ ] Write failing UI/state tests for visibility, editability, and Head/Tail linkage.
- [ ] Add locked-parameter controls without putting WRAP in the Assembly Intent menu.
- [ ] Commit edits through the existing structure-state transaction path and invalidate resolved manufacturing cache.
- [ ] Ensure save/reload snapshots preserve the receiving lower-WRAP values.
- [ ] Run focused GUI tests in fresh Xvfb processes.

### Task 3: Canonical unfolded blank information for every sheet-metal part

**Files:**
- Modify: `ae_engine/manufacturing_api.py`
- Modify: `fold_designer_bridge.py`
- Modify: `gui.py` only if shared rendering needs a main-GUI consumer.
- Test: new `tests/test_canonical_unfolded_blank_info.py` plus existing part tests.

**Interfaces:**
- Produces one helper that measures final `PartRenderData.material` bounds/area and returns blank width, height, area.
- Multi-piece Box Body returns one blank record per resolved physical piece.
- Head and Tail are measured independently from their own final material.

- [ ] Write failing tests for Box Body pieces, Head, Tail, Door and representative auxiliary sheet-metal parts.
- [ ] Implement blank measurement from canonical final material only.
- [ ] Replace any operator label that derives size from raw profiles when canonical render data is available.
- [ ] Verify linked Head/Tail settings can still produce different blank records when their final material differs.
- [ ] Run 2D/manufacturing blank regressions.

### Task 4: Move project skills to `.agents/skills/` and strengthen corner/3D skill contract

**Files:**
- Move: `skills/**` -> `.agents/skills/**`
- Modify: `.agents/skills/engineering/phase6-assembly-view-boundaries/SKILL.md`
- Modify: `.agents/skills/engineering/phase6-overlay-relief-basis/SKILL.md`
- Modify/create: `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
- Modify references: `release_required_artifacts.json`, tests, docs/current logs where operational paths are active.

**Interfaces:**
- All active project skill paths start `.agents/skills/`.
- Corner/3D integrity skill requires registry-driven assembly matrix, pre-solve visible collision, post-solve zero illegal penetration, 2D/Single3D/Assembly3D equality, save/reload, and no packaging on failure.

- [ ] Write/update skill path contract tests to expect `.agents/skills/`.
- [ ] Move the full skill tree preserving relative structure.
- [ ] Update executable/checker paths and machine-readable release policy.
- [ ] Add corner/3D model integrity skill and cross-reference it from existing related skills.
- [ ] Run skill/release policy tests GREEN.

### Task 5: Full regression and delivery evidence

**Files:**
- Modify: `修改日誌/20260830.md`
- Modify: `AI_HANDOFF.md`, `CONTEXT.md`, `目前主要任務.md` as needed.

**Interfaces:**
- Produces verified working tree; package only if all required regressions pass.

- [ ] Run `py_compile` for changed Python files.
- [ ] Run receiving/WRAP/Registry/piece-level tests.
- [ ] Run INSERT/OVERLAY/INSERT_OVERLAY/WRAP registry-driven collision matrix with Head/Tail.
- [ ] Run save/reload and canonical 2D/3D/blank tests.
- [ ] Run GUI tests in clean Xvfb processes separate from headless Matplotlib tests.
- [ ] Confirm `config.ini` SHA256 is unchanged.
- [ ] Record any remaining failures; do not package if any required regression is red.

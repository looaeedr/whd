# Issue #350 T5 — canonical manufacturing orchestration extraction

## Identity
- Master: #344
- Task: #350 / T5
- Predecessor: #349 accepted HEAD `fa88bca65791bfa4839197be3e81bbebf289e5a5`
- Branch: `refactor/issue350-manufacturing-orchestration-20260918`
- Current accepted code SHA before QA cleanup: `d019f85de981e2630483d63ce4463e4346998af1`

## Move-only scope
Canonical owner: `phase6_manufacturing_geometry.py`

Moved from bridge:
- `_phase6_resolve_family_divider_reliefs`
- `_phase6_resolve_manufacturing_geometry`

Authorized dependency rewiring:
- bridge wrapper name → canonical `phase6_part_navigation.is_box_body_physical_piece_key`
- bound-method first for:
  - `_phase6_mesh_profiles_for_part`
  - `_phase6_operator_finished_dimensions`
  - `_phase6_scene_query_payload_for_part`
  - `_phase6_publish_live_state`
- legacy direct-call facade compatibility preserved by bridge-injected callbacks; owner still imports bridge **0 times**

The stale DM3 source-ownership assertion was updated to inspect `phase6_manufacturing_geometry`, its new canonical owner.

## LOC
- bridge before T5: **9,644**
- bridge after T5 + compatibility wiring: **9,284**
- net bridge reduction: **360 lines**
- manufacturing owner after T5: **1,646 lines**

## RED
RUN `35359665964`
- **3 FAIL**
- expected extraction-contract gaps:
  - orchestration not yet owner-defined
  - three self-bound bridge helpers not yet class-wired
  - canonical part-navigation identifier not yet used

## Focused GREEN
RUN `35362452260`
- T5 orchestration extraction contract: **PASS**
- proves:
  - single canonical owner
  - zero reverse bridge import
  - required class wiring
  - canonical part-navigation name

## Broader parity
RUN `35362531299`

Headless:
- **140 PASS / 16 SKIP / 0 FAIL**

Xvfb:
- **154 PASS / 2 DESELECTED / 0 FAIL**
- deselected nodes are exactly the inherited T1 contract in
  `config/issue346_t1_xvfb_failure_contract.json`

No new manufacturing/joint-relief failure was introduced.

## Compatibility finding
Existing characterization calls `bridge._phase6_resolve_manufacturing_geometry(app)` with lightweight `SimpleNamespace` facades. Pure bound-method lookup alone would break those accepted callers. T5 therefore keeps bound-method lookup as primary and adds a bridge-injected fallback registry with zero reverse import. This is compatibility wiring only; no manufacturing formula, state schema, solver policy, or persistence semantics changed.

## Conclusion
T5 accepted: canonical manufacturing orchestration now lives in `phase6_manufacturing_geometry.py`; bridge retains only callback/view integration and compatibility wiring. Phase 2 DTO/service redesign remains out of scope.

Next: #351 / T6.

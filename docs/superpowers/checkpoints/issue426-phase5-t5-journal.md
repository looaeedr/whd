# Phase 5 / Issue #426 T5 Journal

## Authority

- MASTER_ID: `#413`
- TASK_ID: `#426 / T5`
- TARGET_X: `cleanup/2d-3d-sync`
- FROZEN_X_BASE_SHA: `396bfd96524a44a178c29bbefaf1b7c0437c119f`
- ACCEPTED_PREDECESSOR: `#425 @ 5581b091cd891bd725577dfc60376cf35bc13e63`
- WORK_ORDER_BRANCH: `refactor/issue413-phase5-assembly-presentation-20260920`
- Requirement Authority: Phase 5 v1.7 accepted master #413
- T5 scope: refresh/mount parity, final Bridge compression, rebuild-safe legacy compatibility.

## Knowledge Preflight

Exact planned changed files:
- `phase6_assembly_presentation.py`
- `fold_designer_bridge.py`
- `tests/process/test_issue426_phase5_t5_bridge_compression.py`
- `.github/workflows/qa-issue426-phase5-t5.yml`
- `docs/superpowers/checkpoints/issue426-phase5-t5-journal.md`

Router result on accepted predecessor:

```text
REQUIRED_SKILLS=9
REQUIRED_REFERENCES=8
KNOWLEDGE_PREFLIGHT_RC=0
```

READ_SKILL: Python測試實務
READ_SKILL: UI設計與去AI味
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: 驗證板件與DXF

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
SUPPORTING_REFERENCE_READ: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

## Accepted T0 Artifact Consumed

Source of truth for T5 baseline:
- #421 accepted HEAD: `b31409e7c1736df31bd554afe4ac779d49b30aaa`
- RUN: `35486472231`
- Artifact: `10598365413`
- digest: `sha256:5ef01ce632f44da1d83073cffd5986a6b53e84eb2cf55aa6707baa0252c427c6`
- files consumed: `census.json`, `census.md`

T0 exact Assembly boundary:
```text
FUNCTION_COUNT=15
LINE_SPAN=563
SELF_REFS=79
TK_REFS=70
EVENT_BIND_LAYOUT_REFS=38
```

Boundary symbols:
1. `_phase6_refresh_box_body_piece_info_rows`
2. `_phase6_on_assembly_part_visibility_changed`
3. `_phase6_scroll_assembly_parts`
4. `_phase6_bind_assembly_scroll`
5. `_phase6_assembly_presentation_groups`
6. `_phase6_current_assembly_panel_part_keys`
7. `_phase6_refresh_assembly_parts_panel_if_topology_changed`
8. `_phase6_set_assembly_part_details_open`
9. `_phase6_toggle_assembly_part_details`
10. `_phase6_set_assembly_presentation_group_open`
11. `_phase6_toggle_assembly_presentation_group`
12. `_phase6_set_box_body_piece_details_open`
13. `_phase6_toggle_box_body_piece_details`
14. `_phase6_refresh_assembly_parts_panel`
15. `_phase6_show_assembly`

At T5 predecessor the same 15 symbols remain, but T2–T4 have already compressed nearly all row/piece/collapse/scroll/visibility implementation into panel/presentation owners. No wrapper-count growth is authorized.

## Exact T0 Refresh Call-Site Baseline

Exactly five semantic call sites must remain:

```text
_phase6_refresh_profiles_from_settings
  → _phase6_refresh_assembly_parts_panel_if_topology_changed

_phase6_on_baseline_model_changed
  → _phase6_refresh_assembly_parts_panel_if_topology_changed

_phase6_refresh_assembly_parts_panel_if_topology_changed
  → _phase6_refresh_assembly_parts_panel

_fix11_init
  → _phase6_refresh_assembly_parts_panel

_fix11_refresh_part_buttons
  → _phase6_refresh_assembly_parts_panel
```

T5 explicitly forbids:
- adding a sixth trigger;
- removing any of these five;
- converting direct refresh callers into topology-skip callers;
- adding unchanged-topology skip optimization beyond the fixed-root conditional helper.

## Exact T0 Mount / Unmount Behavior Baseline

Fixed-root T0 recorded ten construction/mount rows. T2 legitimately moved construction ownership to `Phase6AssemblyPanel`; T5 must preserve behavior, not resurrect Bridge Tk construction.

Behavioral mount transitions that remain authoritative:
- `_phase6_show_assembly`: obtain `assembly_parts_panel`; if not managed, `pack(fill=BOTH, expand=True, pady=(0, 8))`.
- `_phase6_show_corner_data`: `assembly_parts_panel.pack_forget()`.
- `_fix11_activate_part`: when leaving Assembly for a real part, `assembly_parts_panel.pack_forget()`.

No new Assembly mount/unmount trigger is authorized.

## Legacy Attribute Compatibility Baseline

T0 proved external/current readers for the Assembly aliases, including:
- `assembly_parts_panel`
- `assembly_parts_canvas`
- `assembly_parts_content`
- `assembly_part_visible_vars`
- `assembly_box_body_piece_visible_vars`
- `assembly_part_corner_vars`
- `assembly_part_formed_vars`
- `assembly_part_blank_vars`
- BoxBody piece formed/blank/corner vars
- row/detail/group section/detail/button registries

T2–T4 established rebuild-safe panel-owned long-lived dicts and Bridge aliases. T5 must not replace them with one-time copied dicts.

## Corner Snapshot Decision

T0 classification for `_phase6_last_assembly_corner_dimension_texts`:
- current Bridge writer exists;
- test reader exists: `tests/test_phase6_corner_dimension_controls.py`;
- dynamic getattr reader count is zero.

Therefore the T5 deletion precondition `READ_COUNT=0` is NOT met. The compatibility snapshot is retained.

## T5 Compression Decision

At predecessor, the only remaining direct Assembly presentation implementation among compression targets is:
`_phase6_assembly_presentation_groups`, which still loops over `AssemblyPresentationModel.entries` and builds compatibility tuples inside Bridge.

T5 will move that compatibility projection into the pure `phase6_assembly_presentation.py` owner and make the Bridge symbol a thin delegate.

The following remain in Bridge by design:
- refresh call-site/event orchestration;
- workspace/snapshot → presentation-model composition;
- Assembly mount/unmount transition;
- display-mode-aware render action target;
- legacy compatibility aliases/wrappers.

These are allowed composition/mount/event/compatibility seams, not presentation implementation.

## Prohibited

- no UI redesign;
- no refresh optimization;
- no change to the five T0 refresh triggers;
- no change to Assembly/Corner Data/real-part mount transitions;
- no removal of `_phase6_last_assembly_corner_dimension_texts`;
- no right-side Assembly diagnostics refactor;
- no generic service bag;
- no reverse Bridge import;
- no manufacturing/project ownership change.

## State

```text
STATE=RED
HEAD=5581b091cd891bd725577dfc60376cf35bc13e63
RUN_ID=RUN_NOT_CREATED
NEXT_ACTION=Add focused T5 requirement RED for pure grouping projection + exact T0 refresh/mount/legacy compatibility gates.
```

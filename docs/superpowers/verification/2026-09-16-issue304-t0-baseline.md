---
whd_doc_role: CURRENT
whd_contract: ci-sharding-t0-baseline-verification
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #304 T0 Baseline Timing + Authoritative Inventory — Verification Evidence

Date: 2026-09-16 (Asia/Taipei)
Parent: #303
Task: #304
Measurement head: `2a99806493c69f4a6c9142d43dd502c7eb65757a`
Workflow: `Issue304 T0 Legacy Baseline v2`
Run: `35092857584`
Job: `104783053670`
Artifact: `10445586630` (`issue304-t0-baseline-evidence-v2`)
Artifact digest: `sha256:d27bbb5dddbba7b10364c830875e4289d362a7f256dc6e1b425b2bf320166d77`

## Acceptance result

T0 baseline acceptance is GREEN on the exact measurement head above. The final fail-closed workflow gate completed successfully.

- Authoritative full collection: **2153**
- Lane union: **2153**
- Missing from union: **0**
- Extra in union: **0**
- Governance: **191/191 terminal GREEN**
- All non-Xvfb functional lanes: **terminal GREEN**
- Xvfb UI: **113 collected = 100 PASS / 13 FAIL**
- Xvfb child rc: **1**
- Xvfb classification: **INHERITED_BASELINE_RED**
- Classifier started: **true**
- Classifier rc: **0**
- Classifier terminal: **GREEN**
- Config/DXF invariant: **GREEN**
- Tracked-authority invariant: **GREEN**
- Tracked worktree clean: **GREEN**

No sharding was enabled in T0. The runner preserves the legacy serial lane order so these timings remain the pre-optimization baseline.

## Timing baseline

Queue delay is reported separately from execution time.

- Queue delay: **0.0 s**
- `EXECUTION_WALL_CLOCK`: **759.365 s** (~12m39.4s)
- `END_TO_END_WALL_CLOCK`: **763.365 s** (~12m43.4s)

| Lane | Collected | Terminal result | Wall-clock |
|---|---:|---|---:|
| governance | 191 | GREEN | 4.103 s |
| unit | 79 | GREEN | 4.079 s |
| geometry | 550 | GREEN | 18.081 s |
| projection | 96 | GREEN | 6.598 s |
| persistence | 40 | GREEN | 3.902 s |
| dxf | 15 | GREEN | 3.371 s |
| architecture | 10 | GREEN | 3.122 s |
| ui_headless | 223 | GREEN | 10.364 s |
| integration | 836 | GREEN | 30.966 s |
| xvfb_ui | 113 | 100 PASS / 13 inherited FAIL | **617.117 s** |

Xvfb consumes about 81% of the measured runner execution time and is the dominant optimization target. Integration is the next largest lane at ~31 s, but it is an order of magnitude smaller than Xvfb.

The internal pytest Xvfb terminal line reported `13 failed, 100 passed, 2040 deselected` in **611.92 s**; the lane wrapper wall-clock was **617.117 s**.

## Slowest observed Xvfb nodes

Top observed call durations from `--durations=30`:

1. `23.56s` — `tests/test_phase6_receiving_multipart_integration.py::test_receiving_joint_shrinks_features_round_trip_from_designer_to_project`
2. `21.78s` — `tests/test_phase6_receiving_multipart_integration.py::test_receiving_multipart_project_round_trip_preserves_joints_shrinks_features_and_piece_identity`
3. `20.43s` — `tests/test_issue124_structure_tree.py::test_structure_tree_survives_all_text_scales_resize_and_real_scroll_commands`
4. `13.11s` — `tests/test_phase6_t25_combined_receiving_acceptance.py::test_combined_receiving_operator_path_from_live_family_switch`
5. `11.99s` — `tests/test_phase6_receiving_followup_20260830.py::test_receiving_endcap_switching_does_not_accumulate_thickness_or_blank_size`
6. `11.38s` — `tests/test_issue63_regression_red.py::test_issue63_physical_piece_fold_edit_survives_save_switch_and_resync`
7. `10.73s` — `tests/test_issue63_regression_red.py::test_issue63_receiving_has_three_independent_physical_box_body_fold_editors`
8. `10.72s` — `tests/test_phase6_t11_family_preset_switching.py::test_fold_designer_known_models_reset_presets_while_custom_carries_current_values`
9. `10.61s` — `tests/test_issue63_regression_red.py::test_issue63_receiving_box_body_physical_pieces_are_real_3d_input_contexts`
10. `9.94s` — `tests/test_phase6_t21_live_switch_selector.py::test_live_switch_vault_to_receiving_refreshes_door_and_base_selector_semantics_and_callbacks`

## Exact inherited Xvfb RED set and terminal signatures

The 13-node failed set exactly matches the accepted inherited baseline set; `xvfb_missing_expected=[]` and `xvfb_extra_failed=[]`.

1. `tests/test_phase6_gui_3d_integrity_20260830.py::test_real_box_body_2d_annotations_do_not_overlap_each_other_or_material` — `AssertionError: phase6_finished_dimensions; assert ()`
2. `tests/test_phase6_receiving_edge_controls_gui.py::test_endcap_four_edge_controls_live_on_drawing_edges_even_when_parameters_locked` — expected TOP/BOTTOM/LEFT/RIGHT edge hosts, observed empty set.
3. `tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_four_shrinks_live_on_drawing_edges_and_bend_stays_in_settings_panel` — expected TOP/BOTTOM/LEFT/RIGHT edge hosts, observed empty set.
4. `tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_edge_shrink_commit_uses_canonical_settings_transaction_and_updates_dimensions` — `KeyError: 'TOP'`.
5. `tests/test_phase6_t02_endcap_edge_controls.py::test_head_settings_publish_four_edge_controls_directly_from_registry` — expected TOP/BOTTOM/LEFT/RIGHT, observed empty set.
6. `tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics` — expected four edge selector semantics, observed empty tuple.
7. `tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_fold_designer_controls_and_edge_selectors_update_on_text_size_changed` — `Host for TOP should be mapped`, `winfo_ismapped()==0`.
8. `tests/test_phase6_t22_settings_vertical_scroll.py::test_medium_unlocked_settings_uses_real_vertical_scroll_owner_and_scrollable_viewport` — last rows unreachable: `page_bottom=660`, `viewport_bottom=46`.
9. `tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[head]` — `head TOP host not viewable`, `winfo_viewable()==0`.
10. `tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[tail]` — `tail TOP host not viewable`, `winfo_viewable()==0`.
11. `tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[head]` — expected four edge selector semantics, observed empty tuple.
12. `tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[tail]` — expected four edge selector semantics, observed empty tuple.
13. `tests/test_phase6_t25_combined_receiving_acceptance.py::test_combined_receiving_operator_path_from_live_family_switch` — `winfo_viewable()==0`.

## Governance recovery history

Two earlier T0 attempts were rejected as harness/governance evidence, not accepted as the baseline:

- Run `35091089077`: fail-closed preflight correctly rejected missing required Skill/reference evidence before lane execution.
- Run `35091528069`: full baseline executed, but four Governance nodes failed because three newly added T0/spec documents incorrectly gave non-MIRROR `CURRENT` documents self-referential `whd_canonical` values.

That metadata defect was repaired without changing test or production semantics. Repair run `35092786439` completed SUCCESS and strict governance was GREEN; repair commit: `74c4b41c55a73fb3a76c650a79a38131b28d6f41`. The accepted measurement run `35092857584` then proved Governance GREEN on the governance-clean head.

## Production / scope boundary

T0 did not merge or write to `cleanup/2d-3d-sync`. A fresh readback during closing observed production at `2bbf59fbb2ff2e79c67d9817964d3ff6213b2228` (`docs(#302): harden connector production-write guard`), an unrelated external production movement after the T0 branch was created. T0 does not treat that unrelated movement as its own mutation and does not rebase onto moving production.

T0 changed CI measurement/docs authority only; it did not change production geometry, UI behavior, persistence, DXF semantics, or test assertions for speed.

## Handoff contract to #305 / T1

#305 must branch from the exact final accepted #304 evidence head after fresh closing verification, not from moving production and not directly from the measurement SHA if the permanent evidence commit is newer.

T1 scope remains manifest/tooling only: canonical node-id normalization, deterministic SHA-256 HRW/Rendezvous ownership, authoritative shard-count configuration, full reconciliation, stable manifest digests, and tests proving deterministic ownership. Execution remains effectively legacy/serial until later tasks.

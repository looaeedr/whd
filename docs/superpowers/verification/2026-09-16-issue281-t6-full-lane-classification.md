---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #281 T6 Full-Lane Validation / RED Classification Evidence

Date: 2026-09-16 (Asia/Taipei)
Parent: #274
Predecessor: #280

## Exact authority

- T5 accepted parent: `153455d5cbc81d2443802fb09c0cca0714ef8c0d`
- Initial T6 full-lane candidate: `48f66b41d3fc6f05c2c74c01226c7583c22cb914`
- Initial full-lane RUN: `35055812031`
- Fresh same-runner A/B RUN: `35064919302`
- Governance recovery RUN: `35065146354`

## Initial full-lane collection

`FULL_COUNT=2153`, `UNION_COUNT=2153`, `MISSING_FROM_UNION=[]`, `EXTRA_IN_UNION=[]`.

Initial terminal lane results:

- governance: 191 collected, 4 failed / 187 passed
- unit: 79 collected, 77 passed / 2 skipped
- geometry: 550 collected, 499 passed / 51 skipped
- projection: 96 collected, 95 passed / 1 skipped
- persistence: 40 collected, 31 passed / 9 skipped
- dxf: 15 collected, 15 passed
- architecture: 10 collected, 8 passed / 2 skipped
- ui_headless: 223 collected, 133 passed / 90 skipped
- integration: 836 collected, 727 passed / 109 skipped
- xvfb_ui: 113 collected, 13 failed / 100 passed

Protected config.ini / DXF hashes and tracked tree remained GREEN.

## Governance RED classification and repair

The four governance failures were classified `GOVERNANCE_FAILURE`. They were reproduced on both the exact T5 parent and T6 candidate, but were not accepted as an inherited exception because they were actionable documentation-governance debt.

Root causes:

1. `docs/plans/2026-09-15-test-cleanup-t4-acceptance.md` missing `WHD_DOC_META_V1` frontmatter.
2. `docs/plans/2026-09-15-test-cleanup-t4-gui-characterization-retirement.md` missing `WHD_DOC_META_V1` frontmatter.
3. `docs/superpowers/verification/2026-09-16-issue280-permanent-test-move-acceptance.md` missing `WHD_DOC_META_V1` frontmatter.
4. `docs/superpowers/verification/2026-09-15-issue280-reconciliation-audit.md` and `docs/superpowers/verification/2026-09-15-issue280-test-move-manifest.md` incorrectly both declared `CURRENT` for `verification-provenance`.

Recovery used only documentation metadata: historical verification records were marked `HISTORICAL` / `verification-provenance`. RUN `35065146354` completed SUCCESS with the complete governance lane GREEN and `PRODUCTION_TEST_DXF_CONFIG_DRIFT=0`.

## Xvfb RED classification

Fresh A/B RUN `35064919302` executed the exact failing nodes on:

- parent: `153455d5cbc81d2443802fb09c0cca0714ef8c0d`
- candidate: `48f66b41d3fc6f05c2c74c01226c7583c22cb914`

The run proved:

- `ISSUE281_AB_STATE_MATCH=GREEN`
- `ISSUE281_AB_GOVERNANCE_NODE_SIGNATURE_MATCH=GREEN`
- `ISSUE281_AB_XVFB_NODE_SIGNATURE_MATCH=GREEN`
- `CLASSIFICATION_GOVERNANCE=GOVERNANCE_FAILURE`
- `CLASSIFICATION_XVFB=INHERITED_BASELINE_RED`

The exact inherited Xvfb node set is:

1. `tests/test_phase6_gui_3d_integrity_20260830.py::test_real_box_body_2d_annotations_do_not_overlap_each_other_or_material`
2. `tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_edge_shrink_commit_uses_canonical_settings_transaction_and_updates_dimensions`
3. `tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_four_shrinks_live_on_drawing_edges_and_bend_stays_in_settings_panel`
4. `tests/test_phase6_receiving_edge_controls_gui.py::test_endcap_four_edge_controls_live_on_drawing_edges_even_when_parameters_locked`
5. `tests/test_phase6_t02_endcap_edge_controls.py::test_head_settings_publish_four_edge_controls_directly_from_registry`
6. `tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics`
7. `tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_fold_designer_controls_and_edge_selectors_update_on_text_size_changed`
8. `tests/test_phase6_t22_settings_vertical_scroll.py::test_medium_unlocked_settings_uses_real_vertical_scroll_owner_and_scrollable_viewport`
9. `tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[head]`
10. `tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[tail]`
11. `tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[head]`
12. `tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[tail]`
13. `tests/test_phase6_t25_combined_receiving_acceptance.py::test_combined_receiving_operator_path_from_live_family_switch`

No production source, geometry authority, DXF authority, persistence/schema authority, or runtime physical-part identity was changed to make these historical GUI contracts green.

## Final gate

T6 final acceptance must rerun the complete lane collection on the recovered candidate. Every non-Xvfb lane must be GREEN. The Xvfb lane may be RED only if the failed node set is exactly the 13 A/B-proven inherited nodes above, with no extra failure and no missing classification. Config.ini / DXF / tracked-tree invariants must remain GREEN.

"""Canonical root/CI product regression slice for WHD.

This runner owns the reusable product acceptance coverage that previously lived
in branch/issue-specific GitHub Actions workflows.  The canonical root and PR
CI call this same command; workflow YAML must not duplicate the pytest list.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "python tools/product_ci_regression.py"

PYTEST_PATHS = (
    # #1795: live Tk Main GUI / 3D revision, initialization, runtime-only sync.
    "tests/test_phase6_sync_envelope.py",
    # #1792: canonical full-file GUI/3D runtime performance acceptance.
    "tests/test_phase6_gui_performance_contract.py",
    # #1794: immutable DXF reload/source-fail gate + derived invalidation.
    "tests/test_phase6_derived_cache_owner.py",
    "tests/test_phase6_part_switch_performance.py",
    # CADCraft experimental DXF viewer must not modify the existing Hole Editor.
    "tests/test_cadcraft_hole_editor_preview.py",
    "tests/test_cadcraft_hole_editor_tk_opt_in.py",
    # #1817: cached per-Bay Receiving preview must track adjacent Joint and
    # preceding world placements, but not unrelated trailing W/H/D.
    "tests/test_issue1817_preview_dependency_cache.py",
    # #1819: loaded .p6fold projects must retire old Bay scene/material caches.
    "tests/test_phase6_project_controller.py::test_issue1819_loading_project_releases_prior_designer_derived_scenes",
    "tests/test_phase6_project_controller.py::test_issue1819_failed_project_load_preserves_current_valid_cache",
    "tests/test_issue1819_manufacturing_cache_bounds.py",
    "tests/test_issue1819_real_manufacturing_dxf_parity.py",
    "tests/test_issue1819_manufacturing_cache_rss_plateau.py",
    "tests/test_issue1819_settings_scroll_callback_lifecycle.py",
    "tests/test_manufacturing_mesh_reuse.py",
    "tests/test_fold_mapping_preparation_performance.py",
    "tests/process/test_product_ci_sharding.py",
    "tests/test_issue1464_custom_manufacturing.py",
    "tests/test_issue1465_quantity_ui.py",
    "tests/test_issue1466_quantity_bom.py",
    "tests/test_issue1467_quantity_dxf_groups.py",
    "tests/test_issue1468_quantity_check.py",
    "tests/test_issue1501_nfb_check_quantity_gate.py",
    "tests/test_issue1501_nfb_manifest_ui.py",
    "tests/test_issue1501_receiving_nfb_partial_ui_export.py",
    "tests/test_issue1501_highlighted_partial_dxf_dispatcher.py",
    "tests/test_issue1501_live_partial_writer.py",
    "tests/test_issue1502_nfb_base_batch_export_gate.py",
    "tests/test_issue1503_deferred_pad_ear_manufacturing.py",
    # #1503/#1504: PAD+real Base full-T mating, per-tier CHECK/Q DXF/BOM,
    # normal Tk 2D and source guards must run BEFORE a localX PR merges.
    # The PAD push-only workflow is supplementary, not the PR merge gate.
    "tests/test_receiving_nfb_pad_pair_manufacturing.py",
    "tests/test_receiving_pad_native_tk_operator_selector.py",
    "tests/test_receiving_flat_pad_source_routing.py",
    "tests/test_receiving_nfb_pad_generator.py",
    "tests/test_receiving_nfb_pad_depth_policy_tiers.py",
    "tests/test_receiving_nfb_pad_part.py",
    "tests/test_receiving_nfb_pad_operator_parts.py",
    "tests/test_receiving_nfb_pad_delivery.py",
    "tests/test_receiving_nfb_pad_assembly_preview.py",
    "tests/test_receiving_nfb_pad_preview_cache.py",
    "tests/test_receiving_nfb_pad_real_renderer.py",
    "tests/test_receiving_nfb_pad_base_mating.py",
    "tests/test_receiving_flat_base_single_nfb_true_z.py",
    "tests/test_receiving_nfb_depth_surface_policy.py",
    # #1503: per-tier physical Base Plate skin + EAR target Z unified regression.
    "tests/test_receiving_tier_ear_assembly_xy.py",
    "tests/test_receiving_tier_ear_z_targets.py",
    # #1503: every source-defined layer ear must be its own real geometry and XY/Z owner.
    "tests/test_receiving_tier_fixing_plate_owner_ids.py",
    # #1503: actual folded 3D Base Plate skin must match EACH source EAR target.
    "tests/test_issue1503_actual_assembly_ear_contact_receipt.py",
    "tests/test_issue1503_revised_bend_formed_skins.py",
    # #1503: formed T2 BEND23 actual assembly 3D overlay / no false MFG.
    "tests/test_issue1503_formed_fixing_plate_3d_assembly_view.py",
    # #1503: only real bent flange skin may define side-panel weld contact.
    "tests/test_issue1503_formed_ear_side_contact.py",
    # #1503: side-owned physical UV contact and CUTTING/BEND conflict proof.
    "tests/test_issue1503_real_side_uv_backprojection.py",
    "tests/test_issue1503_side_marking_preview_collision.py",
    # #1503: selected GUI side 2D-only EAR marks, never manufacturing part.
    "tests/test_issue1503_real_side_piece_2d_preview.py",
    # #1503: actual opposed EAR+SIDE skin fit, never weld release.
    "tests/test_issue1503_real_ear_side_weld_skin_mating.py",
    # #1503 source EAR/SIDE CHECK-only DXF must roundtrip as an atomic pair.
    "tests/test_issue1503_ear_side_check_only_dxf.py",
    # #1503 real operator GUI CHECK-only entry is separate from manufacturing.
    "tests/test_issue1503_ear_side_check_gui_entry.py",
    # #1503: real GUI invocation and side CHECK UV parity after project reload.
    "tests/test_issue1503_ear_side_check_gui_e2e_save_reload.py",
    # #1503: actual Primary 3D Tk startup must SHOW the operator button.
    "tests/test_issue1503_primary_real_tk_check_button.py",
    # #1503 real physical SIDE sheet-only manufacturing marking (not full box/PAD).
    "tests/test_issue1503_side_only_production_marking.py",
    "tests/test_issue1503_side_only_mfg_gui.py",
    # #1503: normal selected-DXF auto side weld MARKING, no extra UI buttons.
    "tests/test_issue1503_auto_side_marks_in_normal_export.py",
    # #1503 Windows real project-open UAT: current per-hole CSV V5 identity survives .p6fold v3.
    "tests/test_issue1503_nfb_v5_p6fold_roundtrip.py",
    # #1500/#1503/#1504: old .p6fold native Tk source→Confirm All→
    # real Base/EAR 2D/3D/SIDE marks→Save/Reload, and original saved
    # BasePlate source retention. These must run on *PR* exact HEAD.
    "tests/test_issue1503_reopen_base_presence.py",
    "tests/test_issue1503_saved_project_gui_red.py",
    "tests/test_receiving_two_tier_physical_base_parts.py",
    # #1503 actual native Tk Confirm All -> physical CSV NFB -> 2D/3D
    # Base Plates and true four EAR-side 3D MARKING, including multi candidate
    # storage-before-Apply and per-Bay physical isolation. Exact CI required:
    # source DTO-only GREEN is NOT a substitute for these real GUI tests.
    "tests/test_issue1503_csv_committed_config.py",
    "tests/test_issue1503_quantity_nfb_source_owner.py",
    "tests/test_issue1503_nfb_manufacturing_transport.py",
    "tests/test_issue1503_single_gui_real_tier_2d3d.py",
    "tests/test_issue1503_primary_2d_ear_source_authority.py",
    "tests/test_receiving_fold_designer_ear_side_marks.py",
    "tests/test_receiving_base_source_owned_part_session.py",
    "tests/test_receiving_fresh_family_autosource.py",
    "tests/test_issue1503_primary_receiving_base_plate_source.py",
    "tests/test_issue1503_multi_candidate_nfb_apply_gui.py",
    "tests/test_issue1503_multi_nfb_bay_isolation.py",
    # #1901 GUI must consume actual #1502 source-owned multi-tier PartSpecs.
    "tests/test_issue1901_csv_v5_gui_real_tier_sources.py",
    "tests/test_issue1494_nfb_x_shadow_projection.py",
    # Current owner-confirmed W800/2=360 must exercise real editor, Base+DXF.
    "tests/test_receiving_w800_two_nfb_360.py",
    "tests/test_issue1496_index_color_evidence.py",
    "tests/test_issue1496_nfb_dxf_source.py",
    # Native originals require explicit WHD_NFB_SWITCH_INDEX_CSV /
    # WHD_NFB_400_SOURCE_DXF and are not present on PR CI. Mandatory
    # canonical JUnit forbids skipped cases: select only deterministic tests.
    "tests/test_issue1496_nfb_index_unique_sources.py::test_csv_filenames_are_unique_per_brand_not_per_model_or_dimensions",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_case_insensitive_dedupe_only_within_same_brand",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_no_directory_traversal_and_unrecognized_cells_are_diagnostic",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_batch_actual_source_is_read_once_and_missing_is_unknown",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_brand_columns_required_and_no_metadata_column_interpreted_as_dxf",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_real_uploaded_42_row_index_golden_manifest_is_consistent",
    "tests/test_issue1496_nfb_index_unique_sources.py::test_no_matching_file_is_sentinel_not_corrupt_dxf_filename",
    "tests/test_issue1496_real_nfb_source_observation.py::test_source_witness_has_traceable_region_partition_and_no_false_certs",
    "tests/test_issue1496_nfb_source_inventory_report.py",
    "tests/test_issue1497_w800_three_canonical_cutting.py",
    "tests/test_issue1497_w800_three_ui_worldx.py",
    "tests/test_issue1498_nfb_part_readiness.py",
    # #1500 persisted NFB UI-1B submit/copy/Undo used to be absent from the
    # canonical run despite full PR GREEN. Keep exact, no-skip transaction,
    # world-X/source, and genuine 723-mm DXF lifecycle checks here.
    "tests/test_issue1500_nfb_transactions.py",
    "tests/test_issue1500_nfb_ui1b_bridge.py",
    "tests/test_issue1500_nfb_worldx_runtime.py",
    "tests/test_issue1500_real_nfb_dxf_lifecycle.py",
    "tests/test_issue1500_nfb_operator_gui_transactions.py",
    "tests/test_issue1504_v14_ac_traceability.py",
    # One reconciliation of 79 original unsigned ACs to actual CI source tests;
    # 4 source-scoped signed only; real GUI/MFG and old-reader gates remain.
    "tests/test_issue1504_79ac_batch_acceptance_gate.py",
    "tests/test_issue1504_ac30_current_nominal_no_fake_cutting.py",
    "tests/test_issue1504_brand_inheritance_current_csv.py",
    "tests/test_issue1504_current_nfb_y_ac10_swt02.py",
    "tests/test_issue1502_current_csv_pad_check_q_provenance.py",
    "tests/test_issue1504_ac25_reselection_nominal_x.py",
    # #1504 AC-22/SWT-15: current CSV V5 UI unknown-X and actual Bay/Quantity
    # .p6fold persistent identity, explicit zero/NONE, no fake approval.
    "tests/test_issue1504_ac22_swt15_current_x_persistence.py",
    # #1504 batched current CSV V5 editor Undo/cancel → independent quantity
    # versions → real project Save/Reload/rotation, source fail-closed.
    "tests/test_issue1504_batched_current_nfb_transactions.py",
    # #1504: real Single/Quantity Confirm All validates detached NFB+Family
    # before any live version mutation; rejects bad source/geometry atomically.
    "tests/test_issue1504_quantity_nfb_confirm_atomic.py",
    # #1504 source-owned V5 NFB independent slot identities, ordering and
    # X, quarter-turn inheritance, no mirrors or nominal-to-MFG promotion.
    "tests/test_issue1504_swt03_nfb05_current_unit_rotation.py",
    "tests/test_issue1504_legacy_fixture_real_gui_gate_cycle.py",
    "tests/test_issue1504_quantity_ear_z_set_identity.py",
    # #1504 exact function audit uncovered these five previously unselected
    # UI-1A / native-source preview / MFG-1 preflight owner suites.
    "tests/test_issue1491_nfb_ui1a.py",
    # #1503 depth-only PAD predicate: exact 1 layer / 2 units / unequal CSV depths.
    "tests/test_receiving_switch_model_catalog_20261011.py",
    "tests/test_issue1492_nfb_real_dxf_preview.py",
    "tests/test_issue1493_nfb_draft_transactions.py",
    "tests/test_issue1497_nfb_cutting_preflight.py",
    "tests/test_issue1497_configured_nfb_manufacturing_release.py",
    "tests/process/test_issue1504_required_nfb_regression_selectors.py",
    # #1504 discovered these three owner regressions were absent from canonical
    # even though test cases existed: actual 1100 Y, saved NFB schema,
    # source-scoped per-piece partial export. No duplicate selectors.
    "tests/test_issue1495_receiving_nfb_y_projection.py",
    "tests/test_issue1499_nfb_persistence.py",
    "tests/test_issue1501_nfb_export_manifest.py",
    # #1502 actual BasePlatePartSpec -> EAR slots -> verified NFB -> FinalScene -> DXF.
    # These were missing from the canonical product run: a GREEN alone did not
    # exercise the new production geometry. Optional customer DXF replays are
    # deliberately excluded until those original files are available.
    "tests/test_issue1502_existing_base_nfb_assembly.py",
    "tests/test_issue1502_receiving_existing_base_plate_patterns.py",
    "tests/test_issue1502_receiving_base_family_routing.py",
    "tests/test_issue1502_receiving_gui_base_bridge.py",
    "tests/test_issue1502_live_nfb_base_partial_export.py",
    "tests/test_issue1502_nfb_door_base_pair_receipt.py",
    "tests/test_issue1502_atomic_door_base_pair_dxf.py",
    "tests/test_issue1502_paired_real_dxf_check_q.py",
    "tests/test_issue1502_editable_nfb_source_format.py",
    "tests/test_issue1502_receiving_single_base_workspace.py",
    "tests/test_issue1502_nfb_base_source_projection.py",
    # V5 CSV is the current source of NFB openings and screw pitches.
    # #1502's source-derived plate selection and actual standalone V5 DXF
    # were previously OMITTED from mandatory Product Regression despite
    # source/GUI changes. Run both in every CI shard manifest, fail closed.
    "tests/test_issue1502_source_derived_center_base.py",
    "tests/test_issue1502_csv_v5_part_only_manufacturing.py",
    # The normal 2D/3D selection and source-owned installed AssemblyScene
    # must be checked as well as manufacturing DXF: visible part != release.
    "tests/test_issue1502_primary_2d_committed_base_visibility.py",
    "tests/test_issue1502_csv_finalscene_installed_assembly.py",
    "tests/test_issue1502_v5_csv_base_x_stable.py",
    # Same V5 CSV source geometry on separate, truly owned NFB-tier plates.
    "tests/test_issue1502_v5_csv_tier_bases.py",
    "tests/test_issue1502_v5_csv_check_q_preview.py",
    "tests/test_issue1502_nfb_ear_base_assembly_contract.py",
    "tests/test_issue1502_nfb_finalscene_composite.py",
    # Mandatory actual 2D/3D/DXF acceptance for current numeric CSV source:
    # The earlier CI list omitted these new production tests, so GREEN did
    # not establish saved-DXF reopen, EAR, quantity or multi-Bay coverage.
    "tests/test_issue1502_csv_is_only_normal_finalscene_source.py",
    "tests/test_issue1502_current_csv_original_pair_dxf.py",
    "tests/test_issue1502_current_csv_original_two_tier_dxf.py",
    "tests/test_issue1503_signed_formed_fixed_plate_normal_dxf.py",
    "tests/test_issue1502_single_button_full_csv_receiving_export.py",
    "tests/test_issue1502_quantity_current_csv_full_batch.py",
    "tests/test_issue1502_current_csv_multi_bay_once.py",
    "tests/test_issue1502_multibay_original_gui_export_integration.py",
    "tests/test_issue1502_two_tier_csv_left_without_manual_base.py",
    "tests/test_issue1502_gui_tier_source_export_checkbox.py",
    "tests/test_issue1502_source_side_crossing_mark_dxf.py",
    "tests/test_issue1502_lower_four_nfb_mount_source.py::test_only_original_lower_four_circles_are_mounting_screws",
    "tests/test_issue1502_lower_four_nfb_mount_source.py::test_source_lower_circle_mismatch_cannot_guess_a_quartet",
    "tests/test_issue1502_lower_four_nfb_mount_source.py::test_native_lower_screw_needs_matching_upper_NFB_source_identity",
    "tests/test_issue1502_nfb_upper_base_native_process.py::test_shihlin_upper_native_color30_cutting_lines_are_closed_without_new_edges",
    "tests/test_issue1502_nfb_upper_base_native_process.py::test_bad_color30_graph_and_ambiguous_process_color_fail_closed",
    "tests/test_issue1502_nfb_upper_base_native_process.py::test_marking_can_remain_open_without_becoming_cutting",
    "tests/test_issue1502_nfb_upper_base_native_process.py::test_exact_source_sha_and_upper_anchor_must_match",
    "tests/test_issue1502_nfb_source_regions.py::test_native_groups_keep_aci212_upper_and_lower_separately",
    "tests/test_issue1502_nfb_source_regions.py::test_cross_boundary_source_entity_is_ambiguous_not_auto_assigned",
    "tests/test_issue1502_nfb_source_regions.py::test_hash_handle_size_and_upper_lower_owner_fail_closed",
    "tests/test_issue1502_nfb_source_regions.py::test_insert_complex_group_is_not_silently_flattened_into_a_plate",
    "tests/test_issue1469_v15_acceptance.py",
    "tests/test_issue390_settings_contracts.py",
    "tests/test_issue500_settings_profile_projection.py::test_issue500_requires_frozen_request_and_plan_contracts",
    "tests/test_issue500_settings_profile_projection.py::test_issue500_pure_projection_is_deterministic_and_carries_required_plan_fields",
    "tests/test_issue1463_receiving_modes.py",
    "tests/test_issue357_manufacturing_result_contracts.py",
    "tests/test_issue356_manufacturing_adapter.py",
    "tests/test_issue371_t7_update_runtime_behavior.py",
    "tests/test_issue1462_custom_parts.py",
    "tests/test_issue1461_receiving_2d_settings.py",
    "tests/test_issue1331_receiving_shared_settings.py::test_real_settings_preview_exports_every_piece_and_reload_keeps_each_bay",
    "tests/test_issue1460_quantity_model.py",
    "tests/process/test_issue533_c1_anti_regrowth.py",
    "tests/test_dm1_divider_physical_contract.py",
    "tests/test_dm3_divider_canonical_relief_contract.py",
    "tests/test_dm4_divider_resolved_sinks.py",
    "tests/test_issue39_divider_relief.py",
    "tests/test_issue63_regression_red.py",
    "tests/test_issue71_divider_relief_components.py",
    "tests/test_issue74_divider_side_front_penetration.py",
    # Retired mirrored-LEFT +T relief must never silently re-enter CUTTING.
    "tests/test_issue83_divider_cross_registry.py",
    # /debug: 7mm C slot / real first-22 Z witness must be truly selected.
    "tests/test_receiving_C_slot_22mm_real_world_debug.py",
    "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
    # Tk/Xvfb contract: real mapped modal windows, highlights and multi-Bay apply.
    "tests/test_receiving_multi_settings_stage_20261010.py::test_issue1791_main_sketch_configure_burst_coalesces_one_idle_paint",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_issue1791_cancelled_idle_redraw_never_paints_destroyed_canvas",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_modal_fullscreen_strict_controls_apply_and_highlight",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_compact_candidates_and_set_controls_use_original_combobox",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_sketch_multi_highlights_drive_existing_endcap_edits_without_link_buttons",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_last_highlight_can_be_cleared_without_implicit_reselection",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_inner_door_version_applies_to_both_highlighted_bays",
    # #1818: real Tk reentrant preview requests must never render stale
    # geometry or write stale errors after candidate switch / window close.
    "tests/test_receiving_multi_settings_stage_20261010.py::test_issue1818_real_cut_preview_latest_selection_wins_during_reentrant_provider",
    # #1818: 3D FinalScene last valid operator choice wins after nested Tk
    # callbacks, and old provider failures must never repaint the newer view.
    "tests/test_phase6_3d_operator_view.py::test_issue1818_reentrant_3d_render_only_publishes_latest_view",
    # Real live designer viewport/camera interaction, not a mocked canvas.
    "tests/test_phase6_3d_view_regressions.py::test_real_tk_3d_only_layout_scroll_zoom_and_unfolded_size_label",
    # True rendered 3D geometry hit, not currently highlighted sidebar part.
    "tests/test_phase6_3d_mesh_hole_entry.py",
    "tests/test_issue1640_mode_navigation.py::test_mode_toggle_and_manager_stay_operable_without_forced_window_exit",
    "tests/test_issue1640_floating_scroll.py::test_real_popup_reuses_one_nonmodal_toplevel_without_applying_candidate",
    "tests/test_receiving_weld_ear_mounting.py",
    # Revised uploaded 固定片.dxf T2 actual BEND23 and moved CUTTING slots.
    "tests/test_issue1503_revised_fixed_plate_source_bend.py",
    "tests/test_issue1050_receiving_mother_plate_marking.py",
    "tests/test_receiving_inner_frame_last_flange_contact.py",
    "tests/test_phase6_t15_inner_door_panels.py",
    "tests/test_issue1901_inner_door_feature_candidates.py",
    "tests/test_issue1901_receiving_editor_commit_boundary.py",
    # NFB subtab is draft-only; main Confirm routes by the actual entry, not project mode.
    "tests/test_receiving_nfb_entry_scoped_transactions.py",
    "tests/test_issue1901_receiving_settings_editor_buttons.py",
    "tests/test_issue1901_verified_nfb_editor_import.py",
    "tests/test_issue1901_single_quantity_source_proof.py",
    "tests/test_issue1901_csv_native_editor.py",
    # CSV recheck invalidates old physical GUI scenes and source label.
    "tests/test_issue1901_csv_preview_invalidation.py",
    "tests/test_issue1901_inner_editor_atomic_confirm.py",
    # User: Receiving inner door holes belong to original Hole Editor; no duplicate CSV opening popups.
    "tests/test_receiving_inner_editor_no_csv_opening_popup.py",
    "tests/test_receiving_native_nfb_tab_flow.py",
    "tests/test_receiving_nfb_main_canvas_visual.py",
    # #1504 native NFB full-preview invalid index cannot alter live HoleEditor
    # draft, existing operator holes, Undo or Cancel All transactions.
    "tests/test_issue1504_native_nfb_preview_transaction.py",
    "tests/test_phase6_t16_receiving_placement.py",
    "tests/test_phase6_t17_receiving_inner_door_80.py",
    "tests/test_issue1113_receiving_joint_lock_geometry.py",
    "tests/test_issue1114_receiving_pairing_marking.py",
    "tests/test_corner_parameter_lock.py",
    "tests/test_issue509_receiving_horizontal_marking.py",
    "tests/test_issue510_receiving_back_panel_modes.py",
    "tests/test_dxf_acceptance.py::test_saved_dxf_acceptance_passes_exact_roundtrip",
    "tests/test_multipart_dxf_acceptance.py::test_resolved_saved_dxf_acceptance_reopens_every_physical_part",
    "tests/test_resolved_manufacturing_export.py::test_resolved_dxf_export_uses_exact_canonical_render_data_without_rebuilding",
    # Mandatory 3D operator OUTSIDE -> material BEND -> OUTSIDE round-trip gate.
    "tests/test_outside_bend_bidirectional_hard_gate.py",
    "tests/test_final_scene_input_to_assembly_direction.py::test_physical_3d_input_preview_never_reads_back_from_assembly",
    "tests/test_final_scene_input_to_assembly_direction.py::test_manufacturing_adapter_reads_active_3d_input_not_assembly_result",
    "tests/test_phase6_3d_single_source_renderer.py::test_2d_and_3d_equal_door_state_share_exact_render_data_object",
    # Real W800, single & assembled doors, and all FinalScene skins must be grid-free.
    "tests/test_receiving_smooth_3d_no_mesh_triangulation.py::test_real_receiving_all_panels_shaded_without_triangle_edges",
    # Real raster check: translucent sheet facets render without seams.
    "tests/test_phase6_gridless_surface_opacity.py",
    "tests/test_receiving_smooth_3d_no_mesh_triangulation.py::test_flat_part_keeps_authoritative_bend_and_marking_with_no_mesh_lines",
    "tests/test_receiving_smooth_3d_no_mesh_triangulation.py::test_single_door_cutting_rims_and_bends_without_mesh_edge_overlay",
    "tests/test_receiving_smooth_3d_no_mesh_triangulation.py::test_outer_door_assembly_renders_real_cutting_rim_and_source_bend",
    "tests/test_phase6_3d_single_source_renderer.py::test_all_final_scene_parts_do_not_restore_triangle_grid_overlays",
    "tests/test_phase6_assembly_3d_view.py::test_final_scene_assembly_uses_box_body_world_mesh_as_head_tail_mating_datum",
    # All certified assembly intents: real Tk/Xvfb 2D/3D, collision-probe opt-in and reload parity.
    "tests/test_phase6_assembly_registry_gui_matrix.py",
    # Corner-policy rule duplicates must fail closed, using the real policy owner.
    "tests/test_certified_relief_registry_completion.py",
    # #1796: real Tk Main GUI and connected Designer persistence boundaries.
    "tests/test_phase6_project_file.py::test_global_save_save_as_and_open_round_trip_project_without_forcing_3d",
    "tests/test_phase6_project_file.py::test_main_connected_designer_project_save_as_persists_current_live_canonical_state",
    "tests/test_phase6_project_file.py::test_project_round_trip_preserves_verified_joint_relief_state",
    "tests/test_phase6_project_file.py::test_p6fold_round_trip_preserves_receiving_bottom_wrap_linkage_and_reserves",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tracked_invariants() -> dict[str, str]:
    paths = [ROOT / "config.ini"]
    baseline = ROOT / "基準檔"
    if baseline.exists():
        paths.extend(sorted(p for p in baseline.rglob("*.dxf") if p.is_file()))
    return {p.relative_to(ROOT).as_posix(): _sha256(p) for p in paths if p.exists()}


def _source_authority_scan() -> None:
    # Hard gate also guards canonical selector removal: every product PR run
    # MUST exercise the inverse dimensional contract and 3D-input precedence.
    required = (
        "tests/test_outside_bend_bidirectional_hard_gate.py",
        "tests/test_final_scene_input_to_assembly_direction.py::test_physical_3d_input_preview_never_reads_back_from_assembly",
        "tests/test_final_scene_input_to_assembly_direction.py::test_manufacturing_adapter_reads_active_3d_input_not_assembly_result",
    )
    missing = sorted(set(required).difference(PYTEST_PATHS))
    if missing:
        raise RuntimeError(f"OUTSIDE_BEND_BIDIRECTIONAL_HARD_GATE_MISSING: {missing}")

    text = (ROOT / "ae_engine/assembly_collision.py").read_text(encoding="utf-8")
    stale = (
        "PHYSICAL_COLLISION_PLUS_TARGET_T_OVER_2",
        '"target_half_thickness"',
        '"solid_depth"',
        "PHYSICAL_PRIMARY_BOUNDARY_PLUS_SOURCE_COLLISION_SPAN",
    )
    found = [token for token in stale if token in text]
    if found:
        raise RuntimeError(f"stale divider authority remains: {found}")
    if "from tests" in text or "import tests" in text:
        raise RuntimeError("production assembly_collision.py imports tests")


def _run_bridge_guard() -> None:
    # This guard compares against an immutable historical Git baseline using
    # ``git show``.  A non-Git external-storage root may intentionally have no .git
    # metadata, so root verification runs the same behavioral regression test
    # but defers this Git-history-only proof to clean PR CI.
    if not (ROOT / ".git").exists():
        print("PHASE6_BRIDGE_HISTORY_GUARD=DEFERRED_TO_PR_CI_NO_GIT_METADATA")
        return
    with tempfile.TemporaryDirectory(prefix="whd-product-ci-") as tmp:
        out = Path(tmp) / "phase6-bridge-anti-regrowth.json"
        proc = subprocess.run(
            [
                sys.executable,
                "tools/phase6_bridge_anti_regrowth_guard.py",
                "--root", ".",
                "--baseline", "docs/architecture/phase6_bridge_anti_regrowth_baseline.json",
                "--c0-record", "docs/superpowers/checkpoints/issue532-c0-final-classification.json",
                "--json-out", str(out),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.returncode != 0 or "PHASE6_BRIDGE_ANTI_REGROWTH_GREEN" not in proc.stdout:
            raise RuntimeError("phase6 bridge anti-regrowth guard failed")



# #1817: measured 2026-10-17 exact HEAD b7c06bdb full Product Regression
# run 39015604209 showed round-robin shard pytest durations 346.88/146.53/
# 101.31 seconds. These are three whole-file heavy suites, never split test
# cases or modify expectations. Move them by observed cost while preserving
# every canonical selector exactly once and the existing runner/count contract.
# Other shard counts continue using the original deterministic interleave.
_THREE_SHARD_SUITES = {
    "tests/test_issue517_receiving_live_switch_ui_export_marking.py": 2,
    "tests/test_issue1463_receiving_modes.py": 1,
    "tests/test_issue1469_v15_acceptance.py": 0,
}


def shard_paths(index: int, count: int) -> tuple[str, ...]:
    """Partition the exact canonical case selectors, never sample or drop any."""
    if count < 1 or count > len(PYTEST_PATHS) or not 0 <= index < count:
        raise ValueError(f"invalid regression shard {index}/{count}")
    if count != 3:
        return PYTEST_PATHS[index::count]
    return tuple(
        path for position, path in enumerate(PYTEST_PATHS)
        if _THREE_SHARD_SUITES.get(path, position % count) == index
    )


def _pytest_command(junit_path=None, paths=None) -> list[str]:
    selected = tuple(PYTEST_PATHS if paths is None else paths)
    if not selected:
        raise ValueError("product regression shard cannot be empty")
    command = [sys.executable, "-m", "pytest", "-vv", "--disable-warnings",
               "--durations=15", *selected]
    if junit_path is not None:
        command.extend(("--junitxml", str(junit_path), "-o", "junit_logging=system-out"))
    # Each shard has its own isolated GitHub runner, filesystem and display.
    # A stale DISPLAY value alone does not prove Tk is usable.
    xvfb = shutil.which("xvfb-run")
    return [xvfb, "-a", *command] if xvfb else command


def _merge_shard_junit(paths: list[Path], count: int, output: Path) -> None:
    """Join all disjoint shard artifacts before FULL canonical CPR/AC verification."""
    if count < 2 or len(paths) != count:
        raise ValueError("all expected shard reports are mandatory")
    expected = {f"shard-{i}.xml" for i in range(count)}
    if {path.name for path in paths} != expected:
        raise ValueError("duplicate, missing or unexpected shard report")
    combined = ET.Element("testsuites")
    for path in sorted(paths, key=lambda p: int(p.stem.split("-")[-1])):
        root = ET.parse(path).getroot()
        cases = root.findall(".//testcase")
        if not cases:
            raise ValueError(f"empty shard JUnit: {path}")
        for case in cases:
            if any(case.find(status) is not None
                   for status in ("failure", "error", "skipped")):
                raise ValueError(f"non-green shard JUnit: {path}")
        suite = ET.SubElement(combined, "testsuite", {
            "name": path.stem,
            "tests": str(len(cases)),
        })
        for case in cases:
            suite.append(case)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(combined).write(output, encoding="utf-8", xml_declaration=True)


def _verify_full_receipt(report: Path) -> None:
    from whd_v15_acceptance_evidence import verify
    receipt = verify(report)
    print(f"WHD_V15_ACCEPTANCE_GREEN requirements={len(receipt['requirements'])} "
          f"passed_cases={receipt['passed_cases']}", flush=True)


def run(index: int = 0, count: int = 1, junit_out: Path | None = None) -> int:
    selected = shard_paths(index, count)
    before = _tracked_invariants()
    _source_authority_scan()
    _run_bridge_guard()
    with tempfile.TemporaryDirectory(prefix="whd-v15-acceptance-") as tmp:
        report = junit_out or (Path(tmp) / "product-regression.xml")
        report.parent.mkdir(parents=True, exist_ok=True)
        # Verbose case names identify a stalled selector. Bound a complete
        # shard to 15 minutes rather than leaving the runner stuck until its
        # 50-minute job cancellation; timeout remains a hard CI failure.
        try:
            rc = subprocess.call(_pytest_command(report, selected), cwd=ROOT, timeout=900)
        except subprocess.TimeoutExpired:
            print(f"WHD_SHARD_TIMEOUT shard={index}/{count} limit=900s", flush=True)
            rc = 124
        if rc == 0:
            if count == 1:
                _verify_full_receipt(report)
            else:
                print(f"WHD_SHARD_GREEN shard={index}/{count} "
                      f"selectors={len(selected)}", flush=True)
    after = _tracked_invariants()
    if before != after:
        changed = sorted(set(before) | set(after))
        changed = [path for path in changed if before.get(path) != after.get(path)]
        raise RuntimeError(f"product regression mutated tracked invariants: {changed}")
    return rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--junit-out", type=Path)
    parser.add_argument("--merge-junit", action="append", type=Path, default=[])
    args = parser.parse_args()
    if args.merge_junit:
        if args.junit_out is None:
            parser.error("--merge-junit requires --junit-out")
        if args.shard_index != 0:
            parser.error("--merge-junit cannot select a shard")
        _merge_shard_junit(args.merge_junit, args.shard_count, args.junit_out)
        _verify_full_receipt(args.junit_out)
        return 0
    return run(index=args.shard_index, count=args.shard_count,
               junit_out=args.junit_out)


if __name__ == "__main__":
    raise SystemExit(main())

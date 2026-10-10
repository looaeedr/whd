# WHD v1.5 CPR／AC 整合驗收對照（#1469）

本表連結既有單一 owner 與真 GUI／CAD parser 測試；表格存在不代表驗收通過。
必須使用 `tools/whd_v15_acceptance_evidence.py` 核对當次完整 Product Regression JUnit，
拒絕缺項、skip、failure、error 或不存在的測試。完成證據由實際來源摘要及執行結果綁定。

正式箱型範圍依可見下拉選项：金庫型、受電箱、自訂；RO／未知只屬相容資料契約探測。
內門 1／2 層沿用 [#1331](https://github.com/looaeedr/whd/issues/1331) 的開關配置設定；
原案明示實際開關配置與開孔另案接入。本驗收確認共同設定、保存與實際存在的物理 BOM，
不把「2 層」擅自轉成第二片內門或件數倍數。

| 需求 | 原施工工單 | 當次必須執行的測試 |
|---|---|---|
| CPR-01 | #1461 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| CPR-02 | #1462 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1462_custom_parts.py::test_real_designer_add_rename_save_reload_keeps_top_level_custom` |
| CPR-03 | #1464 | `tests/test_issue1464_custom_manufacturing.py::test_outside_mapping_axis_precision_real_scene_mesh_dxf`<br>`tests/test_issue1464_custom_manufacturing.py::test_no_unknown_key_fallback_no_guessed_assembly_and_real_resolver` |
| CPR-04 | #1465 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| CPR-05 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| CPR-06 | #1460 | `tests/test_issue1460_quantity_model.py::test_insert_after_selection_deep_copy_and_delete_selection`<br>`tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| CPR-07 | #1461 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1461_receiving_2d_settings.py::test_two_dimensional_preview_gates_selection_and_reuses_canonical_artists` |
| CPR-08 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| CPR-09 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1460_quantity_model.py::test_project_persists_active_quantity_only` |
| CPR-10 | #1467 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1467_quantity_dxf_groups.py::test_same_outline_and_hole_count_cannot_hide_machining_differences` |
| CPR-11 | #1468 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1468_quantity_check.py::test_uppercase_single_q_at_formal_center_and_parser_reopen` |
| CPR-12 | #1468 | `tests/test_issue1468_quantity_check.py::test_center_collision_deterministically_avoids_final_primitives`<br>`tests/test_issue1468_quantity_check.py::test_no_readable_space_fails_before_io_and_preserves_existing_bytes` |
| CPR-13 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| CPR-14 | #1460 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1460_quantity_model.py::test_counts_and_last_version_protection` |
| CPR-15 | #1466 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1466_quantity_bom.py::test_real_quantity_bom_30_plus_20_custom_100_and_read_only` |
| CPR-16 | #1465 | `tests/test_issue1465_quantity_ui.py::test_quantity_classifier_rejects_shared_edits`<br>`tests/test_issue1463_receiving_modes.py::test_common_edits_share_all_versions_and_validate_unselected_anchor` |
| CPR-17 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save`<br>`tests/test_issue1460_quantity_model.py::test_insert_after_selection_deep_copy_and_delete_selection` |
| CPR-18 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1463_receiving_modes.py::test_invalid_first_dimensions_leave_mode_and_every_buffer_unchanged` |
| CPR-19 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1463_receiving_modes.py::test_quantity_only_reload_requires_reverse_confirmation_and_saves_no_inactive_mode` |
| CPR-20 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1463_receiving_modes.py::test_real_gui_cancel_switch_common_edit_and_active_only_save`<br>`tests/test_issue1463_receiving_modes.py::test_common_edits_share_all_versions_and_validate_unselected_anchor` |
| AC-01 | #1461 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-02 | #1461 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1461_receiving_2d_settings.py::test_two_dimensional_preview_gates_selection_and_reuses_canonical_artists` |
| AC-03 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-04 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-05 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save`<br>`tests/test_issue1460_quantity_model.py::test_insert_after_selection_deep_copy_and_delete_selection` |
| AC-06 | #1464 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1464_custom_manufacturing.py::test_outside_mapping_axis_precision_real_scene_mesh_dxf` |
| AC-07 | #1467 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` |
| AC-08 | #1467 | `tests/test_issue1467_quantity_dxf_groups.py::test_same_outline_and_hole_count_cannot_hide_machining_differences` |
| AC-09 | #1468 | `tests/test_issue1468_quantity_check.py::test_center_collision_deterministically_avoids_final_primitives` |
| AC-10 | #1468 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1468_quantity_check.py::test_staged_q_corruption_never_replaces_existing_dxf` |
| AC-11 | #1460 | `tests/test_issue1460_quantity_model.py::test_legacy_project_becomes_one_version_without_losing_holes`<br>`tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-12 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1463_receiving_modes.py::test_real_gui_cancel_switch_common_edit_and_active_only_save`<br>`tests/test_issue1463_receiving_modes.py::test_invalid_unselected_feature_blocks_before_manufacturing_cache_lookup` |
| AC-13 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save`<br>`tests/test_issue1460_quantity_model.py::test_three_distinct_versions_save_reload_and_unsaved_count` |
| AC-14 | #1460 | `tests/test_issue1460_quantity_model.py::test_legacy_project_becomes_one_version_without_losing_holes` |
| AC-15 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-16 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-17 | #1466 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1466_quantity_bom.py::test_real_quantity_bom_30_plus_20_custom_100_and_read_only` |
| AC-18 | #1463 | `tests/test_issue1463_receiving_modes.py::test_common_edits_share_all_versions_and_validate_unselected_anchor`<br>`tests/test_issue1463_receiving_modes.py::test_real_gui_cancel_switch_common_edit_and_active_only_save` |
| AC-19 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| AC-20 | #1468 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` |
| AC-21 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-22 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| AC-23 | #1466 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` |
| AC-24 | #1465 | `tests/test_issue1465_quantity_ui.py::test_quantity_classifier_rejects_shared_edits`<br>`tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| AC-25 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1463_receiving_modes.py::test_invalid_first_dimensions_leave_mode_and_every_buffer_unchanged` |
| AC-26 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom` |
| AC-27 | #1465 | `tests/test_issue1465_quantity_ui.py::test_real_gui_quantity_controls_holes_and_manual_save` |
| AC-28 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |
| AC-29 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile`<br>`tests/test_issue1463_receiving_modes.py::test_invalid_first_dimensions_leave_mode_and_every_buffer_unchanged` |
| AC-30 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_selectable_family_save_reload_real_output_custom_bom`<br>`tests/test_issue1463_receiving_modes.py::test_real_gui_cancel_switch_common_edit_and_active_only_save` |
| AC-31 | #1463 | `tests/test_issue1463_receiving_modes.py::test_common_edits_share_all_versions_and_validate_unselected_anchor`<br>`tests/test_issue1463_receiving_modes.py::test_real_gui_cancel_switch_common_edit_and_active_only_save` |
| AC-32 | #1463 | `tests/test_issue1469_v15_acceptance.py::test_real_legacy_multibay_session_restore_reverse_initialization_and_2d_profile` |

Machine mapping: `issue1469-v15-acceptance-matrix.json`。
真 GUI 效能 receipt 包含 resolve、build、DXF read、FinalScene、render、calculation、geometry redraw 與 wall time。
要求已載入的 2D 選取／hover／zoom 在共同資料未變時前七項為 0；主畫面 3D 保持既有 owner。
工單結案另外要求子工單 PR exact-head CI、localX merge/readback，以及 AI Library authority map／pitfall ledger durable readback。

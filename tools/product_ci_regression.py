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
    "tests/test_issue1494_nfb_x_shadow_projection.py",
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
    "tests/test_issue1504_v14_ac_traceability.py",
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
    "tests/test_issue1502_nfb_ear_base_assembly_contract.py",
    "tests/test_issue1502_nfb_finalscene_composite.py",
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
    # /debug: 7mm C slot / real first-22 Z witness must be truly selected.
    "tests/test_receiving_C_slot_22mm_real_world_debug.py",
    "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
    # Tk/Xvfb contract: real mapped modal windows, highlights and multi-Bay apply.
    "tests/test_receiving_multi_settings_stage_20261010.py::test_modal_fullscreen_strict_controls_apply_and_highlight",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_compact_candidates_and_set_controls_use_original_combobox",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_sketch_multi_highlights_drive_existing_endcap_edits_without_link_buttons",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_last_highlight_can_be_cleared_without_implicit_reselection",
    "tests/test_receiving_multi_settings_stage_20261010.py::test_inner_door_version_applies_to_both_highlighted_bays",
    "tests/test_issue1640_mode_navigation.py::test_mode_toggle_and_manager_stay_operable_without_forced_window_exit",
    "tests/test_issue1640_floating_scroll.py::test_real_popup_reuses_one_nonmodal_toplevel_without_applying_candidate",
    "tests/test_receiving_weld_ear_mounting.py",
    "tests/test_issue1050_receiving_mother_plate_marking.py",
    "tests/test_receiving_inner_frame_last_flange_contact.py",
    "tests/test_phase6_t15_inner_door_panels.py",
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
    "tests/test_phase6_assembly_3d_view.py::test_final_scene_assembly_uses_box_body_world_mesh_as_head_tail_mating_datum",
    # All certified assembly intents: real Tk/Xvfb 2D/3D, collision-probe opt-in and reload parity.
    "tests/test_phase6_assembly_registry_gui_matrix.py",
    # Corner-policy rule duplicates must fail closed, using the real policy owner.
    "tests/test_certified_relief_registry_completion.py",
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
    # ``git show``.  The canonical Drive root intentionally has no .git
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



def shard_paths(index: int, count: int) -> tuple[str, ...]:
    """Partition the exact canonical case selectors, never sample or drop any."""
    if count < 1 or count > len(PYTEST_PATHS) or not 0 <= index < count:
        raise ValueError(f"invalid regression shard {index}/{count}")
    return PYTEST_PATHS[index::count]


def _pytest_command(junit_path=None, paths=None) -> list[str]:
    selected = tuple(PYTEST_PATHS if paths is None else paths)
    if not selected:
        raise ValueError("product regression shard cannot be empty")
    command = [sys.executable, "-m", "pytest", "-q", "--disable-warnings",
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
        rc = subprocess.call(_pytest_command(report, selected), cwd=ROOT)
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

"""Canonical root/CI product regression slice for WHD.

This runner owns the reusable product acceptance coverage that previously lived
in branch/issue-specific GitHub Actions workflows.  The canonical root and PR
CI call this same command; workflow YAML must not duplicate the pytest list.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "python tools/product_ci_regression.py"

PYTEST_PATHS = (
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
    "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
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
    "tests/test_phase6_3d_single_source_renderer.py::test_2d_and_3d_equal_door_state_share_exact_render_data_object",
    "tests/test_phase6_assembly_3d_view.py::test_final_scene_assembly_uses_box_body_world_mesh_as_head_tail_mating_datum",
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


def _pytest_command() -> list[str]:
    command = [sys.executable, "-m", "pytest", "-q", *PYTEST_PATHS]
    # Prefer an isolated virtual display whenever available.  A DISPLAY value
    # alone is not proof that Tk can connect (headless runtimes often inherit
    # a stale :0).
    xvfb = shutil.which("xvfb-run")
    if xvfb:
        return [xvfb, "-a", *command]
    return command


def run() -> int:
    before = _tracked_invariants()
    _source_authority_scan()
    _run_bridge_guard()
    rc = subprocess.call(_pytest_command(), cwd=ROOT)
    after = _tracked_invariants()
    if before != after:
        changed = sorted(set(before) | set(after))
        changed = [path for path in changed if before.get(path) != after.get(path)]
        raise RuntimeError(f"product regression mutated tracked invariants: {changed}")
    return rc


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

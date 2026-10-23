"""#1504 regression anti-regrowth: previously omitted v1.4 owner tests run in CI.

Eight owner slices existed long before combined acceptance but were not
selected by tools/product_ci_regression.py. Passing unrelated NFB suites was
not proof that Y, Save/Reload or partial manifest contracts were checked.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tools.product_ci_regression import PYTEST_PATHS

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "tests/test_issue1491_nfb_ui1a.py",
    "tests/test_issue1492_nfb_real_dxf_preview.py",
    "tests/test_issue1493_nfb_draft_transactions.py",
    "tests/test_issue1497_nfb_cutting_preflight.py",
    "tests/test_issue1497_configured_nfb_manufacturing_release.py",
    "tests/test_issue1495_receiving_nfb_y_projection.py",
    "tests/test_issue1499_nfb_persistence.py",
    "tests/test_issue1501_nfb_export_manifest.py",
    "tests/test_issue1500_nfb_transactions.py",
    "tests/test_issue1500_nfb_ui1b_bridge.py",
    "tests/test_issue1500_nfb_worldx_runtime.py",
    "tests/test_issue1500_real_nfb_dxf_lifecycle.py",
    "tests/test_issue1504_v14_ac_traceability.py",
    "tests/test_issue1504_ac30_current_nominal_no_fake_cutting.py",
)


def test_owner_regressions_are_exactly_once_in_canonical_product_ci():
    for candidate in REQUIRED:
        assert PYTEST_PATHS.count(candidate) == 1, candidate


def test_all_newly_selected_owner_regression_files_have_live_test_functions():
    for candidate in REQUIRED[:8]:
        source = ROOT / candidate
        assert source.is_file()
        nodes = ast.parse(source.read_text(encoding="utf-8")).body
        tests = [n for n in nodes
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith("test_")]
        assert len(tests) >= 5, candidate


# #1503 PAD used to run only on a post-merge localX push. Every product
# manufacturing/assembly/GUI test must also execute on the PR exact HEAD.
# This is intentionally separate from the old 8-owner regression contract.
REQUIRED_PAD = (
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
)


def test_pad_part_only_mfg_and_real_operator_suites_cannot_disappear_from_pr_ci():
    for candidate in REQUIRED_PAD:
        assert PYTEST_PATHS.count(candidate) == 1, candidate
        source = ROOT / candidate
        assert source.is_file(), candidate
        nodes = ast.parse(source.read_text(encoding="utf-8")).body
        assert any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test_") for n in nodes
        ), candidate


# #1500/#1504: old Receiving project end-to-end native Tk and saved
# physical Base source used to be present in repo but absent from PR CI.
# Keep the real file-based/GUI regression alive rather than sign an AC by path.
REQUIRED_LEGACY_GUI = (
    "tests/test_issue1503_reopen_base_presence.py",
    "tests/test_issue1503_saved_project_gui_red.py",
)


def test_actual_legacy_receiving_gui_and_reopen_regressions_run_before_merge():
    for candidate in REQUIRED_LEGACY_GUI:
        assert PYTEST_PATHS.count(candidate) == 1, candidate
        source = ROOT / candidate
        assert source.is_file(), candidate
        functions = [node.name for node in ast.parse(
            source.read_text(encoding="utf-8")
        ).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("test_")]
        assert len(functions) >= 4, (candidate, functions)
    text = (ROOT / REQUIRED_LEGACY_GUI[1]).read_text(encoding="utf-8")
    # Preserve the real native operator path, not a shim or synthetic-only test.
    for needle in ("load_phase6_project(", "last_unified_hole_editor",
                   "確定全部", "save_project_file_as", "query_assembly_render_data"):
        assert needle in text, needle

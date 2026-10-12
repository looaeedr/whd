"""#1504 regression anti-regrowth: previously omitted v1.4 owner tests run in CI.

These three owner slices existed long before combined acceptance but were not
selected by tools/product_ci_regression.py. Passing unrelated NFB suites was
not proof that Y, Save/Reload or partial manifest contracts were checked.
"""
from __future__ import annotations

import ast
from pathlib import Path

from tools.product_ci_regression import PYTEST_PATHS

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "tests/test_issue1495_receiving_nfb_y_projection.py",
    "tests/test_issue1499_nfb_persistence.py",
    "tests/test_issue1501_nfb_export_manifest.py",
    "tests/test_issue1500_nfb_transactions.py",
    "tests/test_issue1500_nfb_ui1b_bridge.py",
    "tests/test_issue1500_nfb_worldx_runtime.py",
    "tests/test_issue1500_real_nfb_dxf_lifecycle.py",
    "tests/test_issue1504_v14_ac_traceability.py",
)


def test_owner_regressions_are_exactly_once_in_canonical_product_ci():
    for candidate in REQUIRED:
        assert PYTEST_PATHS.count(candidate) == 1, candidate


def test_all_newly_selected_owner_regression_files_have_live_test_functions():
    for candidate in REQUIRED[:3]:
        source = ROOT / candidate
        assert source.is_file()
        nodes = ast.parse(source.read_text(encoding="utf-8")).body
        tests = [n for n in nodes
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith("test_")]
        assert len(tests) >= 5, candidate

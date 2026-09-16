from __future__ import annotations

import configparser
import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKERS = {
    "unit",
    "integration",
    "geometry",
    "projection",
    "persistence",
    "dxf",
    "ui",
    "xvfb",
    "architecture",
    "governance",
    "characterization",
    "legacy",
    "invariant",
    "requires_tk_display",
}
REQUIRED_PRIMARY_LANES = {
    "governance",
    "unit",
    "geometry",
    "projection",
    "persistence",
    "dxf",
    "architecture",
    "ui",
    "integration",
}


def _registered_markers() -> set[str]:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "pytest.ini", encoding="utf-8")
    raw = parser.get("pytest", "markers", fallback="")
    return {
        line.strip().split(":", 1)[0]
        for line in raw.splitlines()
        if line.strip()
    }


def _load_lane_policy():
    path = ROOT / "tools" / "test_lane_policy.py"
    assert path.is_file(), "T1 requires one canonical test-lane policy owner"
    spec = importlib.util.spec_from_file_location("test_lane_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pytest_ini_registers_required_taxonomy_markers():
    registered = _registered_markers()
    assert REQUIRED_MARKERS <= registered, sorted(REQUIRED_MARKERS - registered)


def test_lane_policy_declares_required_primary_lanes_and_selection_expressions():
    policy = _load_lane_policy()
    assert REQUIRED_PRIMARY_LANES == set(policy.PRIMARY_LANES)
    assert set(policy.LANE_EXPRESSIONS) == REQUIRED_PRIMARY_LANES
    assert policy.LANE_EXPRESSIONS["ui"] == "ui and not xvfb"
    assert policy.LANE_EXPRESSIONS["integration"] == "integration"


def test_lane_policy_classifies_representative_tests_without_excluding_them():
    policy = _load_lane_policy()
    cases = [
        ("tests/knowledge/test_metadata.py", False, "governance", set()),
        ("tests/process/test_claim.py", False, "governance", set()),
        ("tests/test_sheetmetal_geometry.py", False, "geometry", set()),
        ("tests/test_part_projection.py", False, "projection", set()),
        ("tests/test_project_reload.py", False, "persistence", set()),
        ("tests/test_dxf_roundtrip.py", False, "dxf", set()),
        ("tests/test_module_dependency.py", False, "architecture", set()),
        ("tests/test_phase6_ui_state_regressions.py", False, "ui", set()),
        ("tests/test_multi_door_gui.py", True, "ui", {"xvfb"}),
        ("tests/test_state_resolver.py", False, "unit", set()),
        ("tests/test_end_to_end_flow.py", False, "integration", set()),
    ]
    for path, requires_display, primary, secondary in cases:
        result = policy.classify_test(path=path, nodeid=f"{path}::test_case", requires_display=requires_display)
        assert result.primary == primary, (path, result)
        assert secondary <= set(result.secondary), (path, result)
        assert result.primary in policy.PRIMARY_LANES


def test_pytest_collection_hook_adds_taxonomy_without_replacing_display_skip_policy():
    text = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "def pytest_collection_modifyitems" in text
    assert "classify_test" in text
    assert "item.add_marker" in text
    assert "def pytest_runtest_setup" in text
    assert "def pytest_runtest_makereport" in text


def test_lane_audit_cli_bootstraps_repo_import_path():
    proc = subprocess.run(
        [sys.executable, "tools/test_lane_audit.py", "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout

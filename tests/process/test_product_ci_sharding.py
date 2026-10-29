"""Canonical regression sharding must preserve every selector and every case."""
from collections import Counter
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

import pytest

from tools.product_ci_regression import (
    PYTEST_PATHS, _merge_shard_junit, _pytest_command, shard_paths,
)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 7, 10, 20, len(PYTEST_PATHS)])
def test_each_selector_appears_in_exactly_one_shard(count):
    shards = [shard_paths(i, count) for i in range(count)]
    seen = Counter(path for shard in shards for path in shard)
    assert set(seen) == set(PYTEST_PATHS)
    assert all(n == 1 for n in seen.values())
    assert all(shards)
    if count not in (3, 10, 20):
        assert shards == [PYTEST_PATHS[i::count] for i in range(count)]
    elif count == 10:
        dedicated = (
            "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
            "tests/test_issue1469_v15_acceptance.py",
            "tests/test_issue1463_receiving_modes.py",
            "tests/test_issue1466_quantity_bom.py",
            "tests/test_phase6_t15_inner_door_panels.py",
        )
        for index, selector in enumerate(dedicated):
            assert shards[index] == (selector,)
        remainder = tuple(p for p in PYTEST_PATHS if p not in dedicated)
        for index in range(5, 10):
            assert shards[index] == remainder[(index - 5)::5]
    elif count == 20:
        dedicated = (
            "tests/test_issue517_receiving_live_switch_ui_export_marking.py",
            "tests/test_issue1469_v15_acceptance.py",
            "tests/test_issue1463_receiving_modes.py",
            "tests/test_issue1466_quantity_bom.py",
            "tests/test_phase6_t15_inner_door_panels.py",
            "tests/test_issue1112_receiving_set_bay_editor.py",
            "tests/test_issue1503_single_gui_real_tier_2d3d.py",
            "tests/test_issue63_regression_red.py",
            "tests/test_issue1465_quantity_ui.py",
            "tests/test_issue1500_receiving_candidate_main_save.py",
        )
        assert len(dedicated) == len(set(dedicated)) == 10
        for index, selector in enumerate(dedicated):
            assert shards[index] == (selector,)
        remainder = tuple(p for p in PYTEST_PATHS if p not in dedicated)
        for index in range(10, 20):
            assert shards[index] == remainder[(index - 10)::10]
    else:
        assert all(len(shard) >= 1 for shard in shards)
        expected = {
            "tests/test_issue517_receiving_live_switch_ui_export_marking.py": 2,
            "tests/test_issue1463_receiving_modes.py": 1,
            "tests/test_issue1469_v15_acceptance.py": 0,
            "tests/test_issue1466_quantity_bom.py": 1,
            "tests/test_phase6_t15_inner_door_panels.py": 0,
        }
        for selector, target in expected.items():
            assert selector in shards[target]
            assert all(selector not in shard for n, shard in enumerate(shards)
                       if n != target)
        for n, selector in enumerate(PYTEST_PATHS):
            if selector not in expected:
                assert selector in shards[n % 3]


def test_measured_rebalance_keeps_all_exact_selectors_unchanged_and_whole():
    # No selector may disappear or execute twice; the two measured heavy
    # files move as complete suites, not individual selected test functions.
    three = [shard_paths(index, 3) for index in range(3)]
    one = shard_paths(0, 1)
    assert len(one) == len(set(one))
    assert Counter(selector for shard in three for selector in shard) == Counter(one)
    assert three[1].count("tests/test_issue1466_quantity_bom.py") == 1
    assert three[0].count("tests/test_phase6_t15_inner_door_panels.py") == 1
    for index in range(3):
        if index != 1:
            assert "tests/test_issue1466_quantity_bom.py" not in three[index]
        if index != 0:
            assert "tests/test_phase6_t15_inner_door_panels.py" not in three[index]
    assert not any(selector.startswith("tests/test_issue1466_quantity_bom.py::")
                   or selector.startswith("tests/test_phase6_t15_inner_door_panels.py::")
                   for selector in one)


@pytest.mark.parametrize("index,count", [(-1, 3), (3, 3), (0, 0),
                                          (0, len(PYTEST_PATHS) + 1)])
def test_invalid_shard_fails_closed(index, count):
    with pytest.raises(ValueError, match="invalid regression shard"):
        shard_paths(index, count)



def test_twenty_shard_workflow_keeps_complete_exact_selectors_and_artifact_gate():
    # The matrix, execution count and receipt merge must agree. If
    # any JUnit artifact is missing, final acceptance must fail closed.
    workflow = (Path(__file__).resolve().parents[2]
                / ".github/workflows/whd-product-regression.yml").read_text(encoding="utf-8")
    assert "shard: [" + ", ".join(str(i) for i in range(20)) + "]" in workflow
    assert workflow.count("--shard-count 20") == 2
    assert "for shard in " + " ".join(str(i) for i in range(20)) + "; do" in workflow
    assert "name: whd-ci-shard-" in workflow
    for i in range(20):
        assert f"test -s junit/shard-{i}.xml" in workflow
        assert f"--merge-junit junit/shard-{i}.xml" in workflow

    shards = [shard_paths(i, 20) for i in range(20)]
    assert all(shards)
    assert Counter(selector for shard in shards for selector in shard) == Counter(PYTEST_PATHS)


def test_twenty_shard_final_junit_requires_every_file_and_all_green():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [root / f"shard-{i}.xml" for i in range(20)]
        for i, path in enumerate(paths):
            _report(path, [f"case_{i}"])
        output = root / "combined.xml"
        with pytest.raises(ValueError, match="mandatory"):
            _merge_shard_junit(paths[:-1], 20, output)
        _merge_shard_junit(paths[::-1], 20, output)
        assert len(ET.parse(output).getroot().findall(".//testcase")) == 20
        _report(paths[19], ["case_19"], failing=True)
        with pytest.raises(ValueError, match="non-green"):
            _merge_shard_junit(paths, 20, output)


def test_gui_performance_and_reentrant_save_contracts_cannot_be_omitted_from_ci():
    # #1792: whole-file selectors prevent the test-selection blind spot
    # uncovered while validating the #1790 Save regression.
    mandatory = {
        "tests/test_phase6_gui_performance_contract.py",
        "tests/test_phase6_part_switch_performance.py",
        "tests/test_issue371_t7_update_runtime_behavior.py",
    }
    assert mandatory.issubset(set(PYTEST_PATHS))
    assert len(PYTEST_PATHS) == len(set(PYTEST_PATHS))
    for path in mandatory:
        assert not any(item.startswith(path + "::") for item in PYTEST_PATHS)


def test_issue1795_sync_envelope_real_tk_suite_is_mandatory():
    # External revision, startup precedence and anti-echo are live Tk
    # acceptance contracts; static source checks cannot replace execution.
    assert "tests/test_phase6_sync_envelope.py" in PYTEST_PATHS


def test_issue1796_main_and_designer_project_roundtrip_is_canonical():
    """Final acceptance must really exercise both global and Designer Save paths."""
    required = {
        "tests/test_phase6_project_file.py::test_global_save_save_as_and_open_round_trip_project_without_forcing_3d",
        "tests/test_phase6_project_file.py::test_main_connected_designer_project_save_as_persists_current_live_canonical_state",
        "tests/test_issue1500_real_nfb_dxf_lifecycle.py",
    }
    assert required.issubset(set(PYTEST_PATHS))
    assert all(PYTEST_PATHS.count(selector) == 1 for selector in required)


def test_outside_bend_bidirectional_gate_cannot_be_omitted_from_product_ci():
    mandatory = {
        "tests/test_outside_bend_bidirectional_hard_gate.py",
        "tests/test_final_scene_input_to_assembly_direction.py::test_physical_3d_input_preview_never_reads_back_from_assembly",
        "tests/test_final_scene_input_to_assembly_direction.py::test_manufacturing_adapter_reads_active_3d_input_not_assembly_result",
    }
    assert mandatory.issubset(set(PYTEST_PATHS))


def _report(path: Path, names, *, failing=False):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for name in names:
        case = ET.SubElement(suite, "testcase", {
            "classname": "tests.test_dummy",
            "name": name,
        })
        if failing:
            ET.SubElement(case, "failure", {"message": "intentional"})
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_merge_retains_all_cases_without_skips_or_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        a, b, c = [base / f"shard-{i}.xml" for i in range(3)]
        _report(a, ["case_a", "case_b"])
        _report(b, ["case_c"])
        _report(c, ["case_d"])
        output = base / "combined.xml"
        _merge_shard_junit([c, a, b], 3, output)
        cases = ET.parse(output).getroot().findall(".//testcase")
        assert [x.get("name") for x in cases] == [
            "case_a", "case_b", "case_c", "case_d"
        ]


def test_merge_rejects_missing_duplicate_or_non_green_shards():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        a, b, c = [base / f"shard-{i}.xml" for i in range(3)]
        _report(a, ["a"])
        _report(b, ["b"])
        _report(c, ["c"])
        output = base / "combined.xml"
        with pytest.raises(ValueError, match="mandatory"):
            _merge_shard_junit([a, b], 3, output)
        with pytest.raises(ValueError, match="duplicate"):
            _merge_shard_junit([a, a, c], 3, output)
        _report(b, ["b"], failing=True)
        with pytest.raises(ValueError, match="non-green"):
            _merge_shard_junit([a, b, c], 3, output)


def test_pytest_command_uses_only_provided_selectors_and_reports_durations():
    command = _pytest_command(Path("sample.xml"), ("tests/test_issue1464_custom_manufacturing.py",))
    assert "--durations=15" in command
    assert "--junitxml" in command
    assert "tests/test_issue1464_custom_manufacturing.py" in command
    assert "tests/test_issue1465_quantity_ui.py" not in command

# Historical CI plan evidence remains immutable, but must not re-activate
# old preflight instructions or present fixed run metrics as today's status.
@pytest.mark.parametrize("historical_doc", [
    "docs/superpowers/plans/2026-09-15-issue280-permanent-test-reconciliation-and-move.md",
    "docs/superpowers/plans/2026-09-16-issue304-t0-baseline.md",
    "docs/superpowers/plans/2026-09-16-issue305-t1-shard-manifest.md",
    "docs/superpowers/plans/2026-09-16-issue306-t2-non-gui-sharding.md",
    "docs/superpowers/verification/2026-09-16-issue304-t0-baseline.md",
    "docs/superpowers/verification/2026-09-16-issue305-t1-shard-manifest.md",
    "docs/superpowers/verification/2026-09-16-issue306-t2-non-xvfb-sharding.md",
])
def test_closed_ci_history_current_role_has_scope_disclaimer(historical_doc):
    source = (Path(__file__).resolve().parents[2] / historical_doc).read_text(
        encoding="utf-8"
    )
    assert source.startswith("---\nwhd_doc_role: "), historical_doc
    header = source[:1200]
    if "whd_doc_role: CURRENT" in header:
        assert "文件時效界線" in header, historical_doc
        assert "不代表" in header or "不宣稱" in header, historical_doc



def test_retired_execution_ledger_cannot_require_phase6_claim_machine():
    text = (Path(__file__).resolve().parents[2]
            / "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md"
            ).read_text(encoding="utf-8-sig")
    assert "whd_doc_role: REFERENCE" in text[:300]
    assert "**CURRENT 永久防線**：parent/chain continuation" not in text
    assert "**當時的 Master-chain 防線（HISTORICAL／已退役）**" in text
    assert "**當時規格書 Preflight 規則（HISTORICAL／SUPERSEDED）**" in text
    assert "**當時的 stale claim 防線（HISTORICAL／已退役）**" in text
    assert "**當時的 scheduler lease 規則（HISTORICAL／已退役）**" in text
    assert "**當時普通工單（HISTORICAL／SUPERSEDED）**" in text


def test_verify_full_receipt_imports_package_qualified_evidence_module():
    from unittest.mock import patch
    from tools.product_ci_regression import _verify_full_receipt

    with patch("tools.whd_v15_acceptance_evidence.verify", return_value={
        "requirements": {"CPR-01": ["tests/test_a.py::test_x"]},
        "passed_cases": 1,
    }) as mock_verify:
        _verify_full_receipt(Path("dummy.xml"))
        mock_verify.assert_called_once_with(Path("dummy.xml"))


def test_release_test_runner_select_batch_isolates_remaining_suffix_after_first_half_passes():
    from tools.phase6_release_test_runner import select_batch

    class _StubJournal:
        def __init__(self, records):
            self._records = records

        def records(self):
            return self._records

    journal = _StubJournal([
        {"status": "failed", "nodeids": ["a", "b", "c", "d"]},
        {"status": "passed", "nodeids": ["a", "b"]},
    ])
    selected = select_batch(["c", "d", "e", "f"], journal, default_batch_size=4)
    assert selected == ["c", "d"]


def test_collected_nodeid_normalizes_windows_path_without_mutating_parameter_escapes():
    from tools.whd_v15_acceptance_evidence import _collected_nodeid

    original = r"tests\test_receiving_nfb_depth_surface_policy.py::test_case[\u58eb\u6797-refs0]"
    expected = r"tests/test_receiving_nfb_depth_surface_policy.py::test_case[\u58eb\u6797-refs0]"
    assert _collected_nodeid(original) == expected
    assert _collected_nodeid("tests/test_example.py::TestClass::test_case") == (
        "tests/test_example.py::TestClass::test_case"
    )
    assert _collected_nodeid("1802 tests collected") is None

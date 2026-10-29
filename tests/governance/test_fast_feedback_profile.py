"""Focused pytest command generation must never become a merge qualification."""
import json
import shlex
from pathlib import Path

import pytest

from tools.change_test_profile import build_fast_feedback, build_test_profile


def test_changed_test_file_creates_fast_command_without_weakening_full_gate():
    profile = build_test_profile(
        task="修正真 DXF BUG",
        changed_files=["ae_engine/ae_door_indicator.py", "tests/test_dxf_proof.py"],
        explicit_type="BUGFIX",
    )
    feedback = profile["fast_feedback"]
    assert feedback["status"] == "READY"
    assert feedback["test_selectors"] == ["tests/test_dxf_proof.py"]
    assert feedback["command"] == "python -m pytest -q --tb=short tests/test_dxf_proof.py"
    assert feedback["may_replace_full_gate"] is False
    assert profile["full_gate_kind"] == "PRODUCT_FULL_REGRESSION"
    assert profile["full_gate_required"] is True
    assert profile["exact_commands"] == ["python tools/product_ci_regression.py"]


def test_production_only_change_needs_explicit_reproducer_instead_of_guessing():
    feedback = build_fast_feedback(["gui.py"])
    assert feedback["status"] == "NEEDS_EXPLICIT_TEST"
    assert feedback["test_selectors"] == []
    assert feedback["command"] is None


def test_explicit_node_ids_are_deduplicated_and_shell_quoted():
    selectors = ["tests/test_safe.py::test_case[space value]",
                 "tests/test_safe.py::test_case[space value]"]
    feedback = build_fast_feedback(["gui.py"], feedback_tests=selectors)
    assert feedback["status"] == "READY"
    assert feedback["test_selectors"] == selectors[:1]
    assert shlex.split(feedback["command"])[4:] == selectors[:1]
    assert feedback["authority"] == "DEVELOPMENT_FEEDBACK_ONLY"


@pytest.mark.parametrize("bad", [
    "../tests/test_a.py", "/tmp/test_a.py", "tests/../test_a.py",
    "gui.py", "tests/test_a.py::", "tests/test_a.py::test_ok::",
    "tests/test_a.py\n--override-ini=evil",
])
def test_invalid_or_incomplete_selectors_fail_closed(bad):
    with pytest.raises(ValueError):
        build_fast_feedback(["gui.py"], feedback_tests=[bad])


def test_governance_feedback_does_not_upgrade_to_product_full():
    profile = build_test_profile(
        task="治理更新", changed_files=["tools/change_test_profile.py",
                                       "tests/governance/test_fast_feedback_profile.py"],
        explicit_type="GOVERNANCE",
    )
    assert profile["fast_feedback"]["status"] == "READY"
    assert profile["full_gate_kind"] == "GOVERNANCE_FULL_SUITE"


def test_contract_documents_feedback_as_non_qualifying():
    contract = json.loads((Path(__file__).resolve().parents[2]
                           / ".agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json").read_text(encoding="utf-8"))
    assert contract["classification"]["focused_tests_can_replace_full_gate"] is False
    assert contract["fast_feedback"]["final_exact_sha_ci"] == "UNCHANGED_REQUIRED"

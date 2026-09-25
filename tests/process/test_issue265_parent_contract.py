from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/task_chain_guard.py"
PARENT_CONTRACT = ROOT / "docs/governance/issue265-t2-parent-contract.json"
TASK_ID = "262"
STAGE_ID = "T2"
EXPECTED_PARENT = "c0e175ac87a265d91b44ab8f95508de2af016647"
CURRENT_X = "28ecd9908372aefd3aeda049fe3569b72d93f2e4"
SIBLING_HEAD = "2" * 40


def _load_guard():
    spec = importlib.util.spec_from_file_location("task_chain_guard_issue265", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract(**overrides):
    payload = {
        "task_id": TASK_ID,
        "stage_id": STAGE_ID,
        "expected_parent_sha": EXPECTED_PARENT,
        "expected_parent_issue": 264,
        "work_branch": "governance/issue265-t2-parent-contract",
    }
    payload.update(overrides)
    return payload


def _write_contract(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "parent.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_previous_accepted_head_is_the_only_valid_parent(tmp_path: Path) -> None:
    guard = _load_guard()
    result = guard.assert_parent_contract(
        _write_contract(tmp_path, _contract()),
        expected_task_id=TASK_ID,
        expected_stage_id=STAGE_ID,
        expected_parent_sha=EXPECTED_PARENT,
        actual_parent_sha=EXPECTED_PARENT,
        current_target_head_sha=CURRENT_X,
    )
    assert result.actual_parent_sha == EXPECTED_PARENT


def test_current_x_cannot_replace_previous_accepted_parent(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.TaskChainContractError, match="parent|current X|target"):
        guard.assert_parent_contract(
            _write_contract(tmp_path, _contract()),
            expected_task_id=TASK_ID,
            expected_stage_id=STAGE_ID,
            expected_parent_sha=EXPECTED_PARENT,
            actual_parent_sha=CURRENT_X,
            current_target_head_sha=CURRENT_X,
        )


def test_sibling_chain_head_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.TaskChainContractError, match="parent"):
        guard.assert_parent_contract(
            _write_contract(tmp_path, _contract()),
            expected_task_id=TASK_ID,
            expected_stage_id=STAGE_ID,
            expected_parent_sha=EXPECTED_PARENT,
            actual_parent_sha=SIBLING_HEAD,
            current_target_head_sha=CURRENT_X,
        )


def test_contract_cannot_silently_refresh_expected_parent(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_contract(tmp_path, _contract(expected_parent_sha=CURRENT_X))
    with pytest.raises(guard.TaskChainContractError, match="parent"):
        guard.assert_parent_contract(
            path,
            expected_task_id=TASK_ID,
            expected_stage_id=STAGE_ID,
            expected_parent_sha=EXPECTED_PARENT,
            actual_parent_sha=CURRENT_X,
            current_target_head_sha=CURRENT_X,
        )


def test_checked_in_t2_parent_contract_points_to_t1_acceptance() -> None:
    guard = _load_guard()
    result = guard.assert_parent_contract(
        PARENT_CONTRACT,
        expected_task_id=TASK_ID,
        expected_stage_id=STAGE_ID,
        expected_parent_sha=EXPECTED_PARENT,
        actual_parent_sha=EXPECTED_PARENT,
        current_target_head_sha=CURRENT_X,
    )
    assert result.expected_parent_sha == EXPECTED_PARENT

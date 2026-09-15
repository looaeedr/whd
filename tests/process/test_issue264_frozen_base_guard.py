from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/task_chain_guard.py"
FROZEN_BASE = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
ADVANCED_X = "1" * 40
TARGET = "cleanup/2d-3d-sync"
TASK_ID = "262"
CHAIN_CONTRACT = ROOT / "docs/governance/issue262-task-chain-contract.json"


def _load_guard():
    assert GUARD.is_file(), "#264 requires tools/task_chain_guard.py"
    spec = importlib.util.spec_from_file_location("task_chain_guard_issue264", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract(**overrides):
    payload = {
        "task_id": TASK_ID,
        "target": TARGET,
        "frozen_base_sha": FROZEN_BASE,
        "base_frozen": True,
    }
    payload.update(overrides)
    return payload


def _write_contract(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assert_contract(guard, path: Path, **overrides):
    kwargs = {
        "expected_task_id": TASK_ID,
        "expected_target": TARGET,
        "expected_base_sha": FROZEN_BASE,
        "observed_target_head_sha": FROZEN_BASE,
    }
    kwargs.update(overrides)
    return guard.assert_frozen_base_contract(path, **kwargs)


def test_canonical_x_and_frozen_base_are_accepted(tmp_path: Path) -> None:
    guard = _load_guard()
    contract = _assert_contract(guard, _write_contract(tmp_path, _contract()))
    assert contract.target == TARGET
    assert contract.frozen_base_sha == FROZEN_BASE


def test_x_may_advance_without_mutating_frozen_base(tmp_path: Path) -> None:
    guard = _load_guard()
    contract = _assert_contract(
        guard,
        _write_contract(tmp_path, _contract()),
        observed_target_head_sha=ADVANCED_X,
    )
    assert contract.frozen_base_sha == FROZEN_BASE
    assert contract.observed_target_head_sha == ADVANCED_X
    assert contract.target_advanced is True


def test_refreshing_contract_base_to_new_x_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_contract(tmp_path, _contract(frozen_base_sha=ADVANCED_X))
    with pytest.raises(guard.TaskChainContractError, match="base|frozen"):
        _assert_contract(guard, path, observed_target_head_sha=ADVANCED_X)


def test_target_identity_cannot_be_redefined(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_contract(tmp_path, _contract(target="main"))
    with pytest.raises(guard.TaskChainContractError, match="target|X"):
        _assert_contract(guard, path)


def test_callers_cannot_redefine_x_to_main(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_contract(tmp_path, _contract(target="main"))
    with pytest.raises(guard.TaskChainContractError, match="target|X"):
        guard.assert_frozen_base_contract(
            path,
            expected_task_id=TASK_ID,
            expected_target="main",
            expected_base_sha=FROZEN_BASE,
            observed_target_head_sha=FROZEN_BASE,
        )


def test_unfrozen_contract_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_contract(tmp_path, _contract(base_frozen=False))
    with pytest.raises(guard.TaskChainContractError, match="frozen|locked"):
        _assert_contract(guard, path)


def test_duplicate_json_key_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    guard = _load_guard()
    path = tmp_path / "contract.json"
    payload = json.dumps(_contract())
    path.write_text(payload[:-1] + ', "target": "main"}', encoding="utf-8")
    with pytest.raises(guard.TaskChainContractError, match="duplicate|ambiguous"):
        _assert_contract(guard, path)


def test_cli_reports_advanced_x_but_preserves_frozen_base(tmp_path: Path) -> None:
    path = _write_contract(tmp_path, _contract())
    result = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--contract",
            str(path),
            "--task-id",
            TASK_ID,
            "--target",
            TARGET,
            "--base-sha",
            FROZEN_BASE,
            "--current-target-sha",
            ADVANCED_X,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TASK_CHAIN_FROZEN_BASE_GREEN" in result.stdout
    assert f"frozen_base_sha={FROZEN_BASE}" in result.stdout
    assert f"current_target_sha={ADVANCED_X}" in result.stdout
    assert "target_advanced=true" in result.stdout


def test_checked_in_issue262_contract_is_frozen() -> None:
    guard = _load_guard()
    contract = guard.assert_frozen_base_contract(
        CHAIN_CONTRACT,
        expected_task_id=TASK_ID,
        expected_target=TARGET,
        expected_base_sha=FROZEN_BASE,
        observed_target_head_sha=FROZEN_BASE,
    )
    assert contract.frozen_base_sha == FROZEN_BASE

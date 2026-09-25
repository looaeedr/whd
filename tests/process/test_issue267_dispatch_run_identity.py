from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/task_chain_dispatch_run_guard.py"
CONTRACT = ROOT / "docs/governance/issue267-t4-dispatch-run-contract.json"
TASK_ID = "262"
BASE_SHA = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
PARENT_SHA = "82340556e32839e0040417aa9348e1e9de2a0d78"
CHAIN_HEAD = PARENT_SHA
TARGET = "X"
BRANCH = "governance/issue267-t4-dispatch-run-identity"
RUN_HEAD = "3" * 40


def _load_guard():
    assert GUARD.is_file(), "#267 requires tools/task_chain_dispatch_run_guard.py"
    spec = importlib.util.spec_from_file_location("task_chain_dispatch_run_guard_issue267", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract(**overrides):
    payload = {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "STAGE_ID": "T4",
        "BASE_SHA": BASE_SHA,
        "EXPECTED_PARENT_SHA": PARENT_SHA,
        "CHAIN_HEAD": CHAIN_HEAD,
        "TARGET": TARGET,
    }
    payload.update(overrides)
    return payload


def _write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assert_identity(guard, path: Path):
    return guard.assert_dispatch_identity(
        path,
        expected_task_id=TASK_ID,
        expected_base_sha=BASE_SHA,
        expected_parent_sha=PARENT_SHA,
        expected_chain_head=CHAIN_HEAD,
        expected_target=TARGET,
    )


def test_complete_dispatch_identity_is_accepted(tmp_path: Path) -> None:
    guard = _load_guard()
    result = _assert_identity(guard, _write_json(tmp_path, "contract.json", _contract()))
    assert result.task_id == TASK_ID
    assert result.target == TARGET


@pytest.mark.parametrize(
    "missing_key",
    ["TASK_ID", "BASE_SHA", "EXPECTED_PARENT_SHA", "CHAIN_HEAD", "TARGET"],
)
def test_each_required_dispatch_identity_field_fails_closed(tmp_path: Path, missing_key: str) -> None:
    guard = _load_guard()
    payload = _contract()
    payload.pop(missing_key)
    with pytest.raises(guard.DispatchRunIdentityError, match=missing_key):
        _assert_identity(guard, _write_json(tmp_path, "contract.json", payload))


def test_target_must_be_symbolic_x_not_branch_name(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.DispatchRunIdentityError, match="TARGET|target|X"):
        _assert_identity(
            guard,
            _write_json(tmp_path, "contract.json", _contract(TARGET="cleanup/2d-3d-sync")),
        )


def test_malformed_sha_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.DispatchRunIdentityError, match="BASE_SHA|40-char|SHA"):
        _assert_identity(
            guard,
            _write_json(tmp_path, "contract.json", _contract(BASE_SHA="not-a-sha")),
        )


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = tmp_path / "contract.json"
    raw = json.dumps(_contract())
    path.write_text(raw[:-1] + ', "TARGET": "main"}', encoding="utf-8")
    with pytest.raises(guard.DispatchRunIdentityError, match="duplicate|ambiguous"):
        _assert_identity(guard, path)


def test_remote_run_must_match_exact_branch_and_head(tmp_path: Path) -> None:
    guard = _load_guard()
    run_path = _write_json(
        tmp_path,
        "run.json",
        {"run_id": 123456789, "branch": BRANCH, "head_sha": RUN_HEAD},
    )
    run = guard.assert_remote_run_identity(
        run_path,
        expected_branch=BRANCH,
        expected_head_sha=RUN_HEAD,
    )
    assert run.run_id == 123456789


@pytest.mark.parametrize(
    ("branch", "head", "marker"),
    [
        ("wrong/branch", RUN_HEAD, "branch"),
        (BRANCH, "4" * 40, "head"),
    ],
)
def test_remote_run_identity_mismatch_fails_closed(
    tmp_path: Path, branch: str, head: str, marker: str
) -> None:
    guard = _load_guard()
    run_path = _write_json(
        tmp_path,
        "run.json",
        {"run_id": 123456789, "branch": branch, "head_sha": head},
    )
    with pytest.raises(guard.DispatchRunIdentityError, match=marker):
        guard.assert_remote_run_identity(
            run_path,
            expected_branch=BRANCH,
            expected_head_sha=RUN_HEAD,
        )


def test_invalid_run_id_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    run_path = _write_json(
        tmp_path,
        "run.json",
        {"run_id": 0, "branch": BRANCH, "head_sha": RUN_HEAD},
    )
    with pytest.raises(guard.DispatchRunIdentityError, match="run_id"):
        guard.assert_remote_run_identity(
            run_path,
            expected_branch=BRANCH,
            expected_head_sha=RUN_HEAD,
        )


def test_cli_no_run_is_exit_3_and_polling_forbidden(tmp_path: Path) -> None:
    contract = _write_json(tmp_path, "contract.json", _contract())
    result = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--contract",
            str(contract),
            "--task-id",
            TASK_ID,
            "--base-sha",
            BASE_SHA,
            "--expected-parent-sha",
            PARENT_SHA,
            "--chain-head",
            CHAIN_HEAD,
            "--target",
            TARGET,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3
    assert (
        "RUN NOT CREATED polling=FORBIDDEN "
        "next_action=EXECUTE_OR_FIX_PREREQUISITE"
    ) in result.stdout


def test_cli_green_binds_run_to_exact_branch_and_head(tmp_path: Path) -> None:
    contract = _write_json(tmp_path, "contract.json", _contract())
    run_path = _write_json(
        tmp_path,
        "run.json",
        {"run_id": 123456789, "branch": BRANCH, "head_sha": RUN_HEAD},
    )
    result = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--contract",
            str(contract),
            "--task-id",
            TASK_ID,
            "--base-sha",
            BASE_SHA,
            "--expected-parent-sha",
            PARENT_SHA,
            "--chain-head",
            CHAIN_HEAD,
            "--target",
            TARGET,
            "--run-evidence",
            str(run_path),
            "--run-branch",
            BRANCH,
            "--run-head-sha",
            RUN_HEAD,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TASK_CHAIN_DISPATCH_RUN_GREEN" in result.stdout
    assert f"branch={BRANCH}" in result.stdout
    assert f"head_sha={RUN_HEAD}" in result.stdout


def test_checked_in_t4_contract_pins_frozen_identity() -> None:
    guard = _load_guard()
    result = _assert_identity(guard, CONTRACT)
    assert result.task_id == TASK_ID
    assert result.base_sha == BASE_SHA
    assert result.expected_parent_sha == PARENT_SHA
    assert result.chain_head == CHAIN_HEAD
    assert result.target == TARGET

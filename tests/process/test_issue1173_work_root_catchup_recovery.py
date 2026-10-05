from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import tools.work_root_gate as gate


BRANCH = "cleanup/2d-3d-sync"


def _git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _out(path: Path, *args: str) -> str:
    return _git(path, *args).stdout.strip()


def _fixture(tmp_path: Path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    root = tmp_path / "root"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "init", "-b", BRANCH, str(seed)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _git(seed, "config", "user.name", "WHD Test")
    _git(seed, "config", "user.email", "whd@example.invalid")
    (seed / "tracked.txt").write_text("v1\n", encoding="utf-8")
    _git(seed, "add", "tracked.txt")
    _git(seed, "commit", "-m", "v1")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", BRANCH)

    subprocess.run(
        ["git", "clone", "--branch", BRANCH, str(remote), str(root)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _git(root, "config", "user.name", "WHD Test")
    _git(root, "config", "user.email", "whd@example.invalid")
    previous = _out(root, "rev-parse", "HEAD")

    (seed / "tracked.txt").write_text("v2\n", encoding="utf-8")
    _git(seed, "commit", "-am", "v2")
    _git(seed, "push", "origin", BRANCH)
    current = _out(seed, "rev-parse", "HEAD")
    tree = _out(seed, "rev-parse", "HEAD^{tree}")
    assert previous != current
    return root, seed, previous, current, tree


def _recover(monkeypatch, root: Path):
    return gate.recover_workspace_to_current_production(
        root_path=str(root),
        production_branch=BRANCH,
    )


def test_recovery_fast_forwards_clean_root_and_preserves_untracked_unpushed(monkeypatch, tmp_path):
    root, _seed, previous, current, tree = _fixture(tmp_path)
    pending = root / ".unpushed" / "docs" / "0" / "pending.txt"
    pending.parent.mkdir(parents=True)
    pending.write_text("keep\n", encoding="utf-8")

    receipt = _recover(monkeypatch, root)

    assert receipt["schema"] == "WHD_WORK_ROOT_RECOVERY_RECEIPT_V1"
    assert receipt["status"] == "VERIFIED"
    assert receipt["previous_head_sha"] == previous
    assert receipt["remote_head_sha"] == current
    assert receipt["root_head_sha"] == current
    assert receipt["root_tree_sha"] == tree
    assert receipt["execution_record_mutated"] is False
    assert _out(root, "rev-parse", "HEAD") == current
    assert pending.read_text(encoding="utf-8") == "keep\n"


def test_recovery_is_idempotent_when_root_is_already_current(monkeypatch, tmp_path):
    root, _seed, _previous, current, _tree = _fixture(tmp_path)
    first = _recover(monkeypatch, root)
    second = _recover(monkeypatch, root)
    assert first["root_head_sha"] == current
    assert second["previous_head_sha"] == current
    assert second["root_head_sha"] == current


def test_recovery_refuses_tracked_dirty_state(monkeypatch, tmp_path):
    root, _seed, _previous, _current, _tree = _fixture(tmp_path)
    (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(gate.WorkRootRecoveryError, match="tracked worktree/index changes"):
        _recover(monkeypatch, root)


def test_recovery_refuses_wrong_branch(monkeypatch, tmp_path):
    root, _seed, _previous, _current, _tree = _fixture(tmp_path)
    _git(root, "checkout", "-b", "wrong")
    with pytest.raises(gate.WorkRootRecoveryError, match="branch mismatch"):
        _recover(monkeypatch, root)


def test_recovery_refuses_diverged_local_history(monkeypatch, tmp_path):
    root, _seed, _previous, _current, _tree = _fixture(tmp_path)
    (root / "local-only.txt").write_text("local\n", encoding="utf-8")
    _git(root, "add", "local-only.txt")
    _git(root, "commit", "-m", "local-only")
    with pytest.raises(gate.WorkRootRecoveryError, match="history diverged"):
        _recover(monkeypatch, root)


def test_cli_ingress_returns_verified_recovery_receipt(monkeypatch, tmp_path, capsys):
    root, _seed, _previous, current, _tree = _fixture(tmp_path)
    rc = gate.main([
        "recover-current-production",
        "--root", str(root),
        "--production-branch", BRANCH,
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["schema"] == "WHD_WORK_ROOT_RECOVERY_RECEIPT_V1"
    assert payload["status"] == "VERIFIED"
    assert payload["root_head_sha"] == current


def test_cli_failure_is_nonzero_and_not_a_verified_receipt(monkeypatch, tmp_path, capsys):
    root, _seed, _previous, _current, _tree = _fixture(tmp_path)
    (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    rc = gate.main([
        "recover-current-production",
        "--root", str(root),
        "--production-branch", BRANCH,
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["schema"] == "WHD_WORK_ROOT_RECOVERY_RESULT_V1"
    assert payload["status"] == "FAILED"
    assert "tracked worktree/index changes" in payload["reason"]


def test_work_root_contract_binds_recovery_owner_and_policy():
    contract_path = Path(__file__).resolve().parents[2] / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    validated = gate.validate_gate_payload(payload)
    recovery = validated["root_identity_recovery"]
    assert recovery["owner"] == "tools/work_root_gate.py::recover_workspace_to_current_production"
    assert recovery["success_schema"] == "WHD_WORK_ROOT_RECOVERY_RECEIPT_V1"
    assert recovery["failure_schema"] == "WHD_WORK_ROOT_RECOVERY_RESULT_V1"
    assert recovery["policy"] == "TRACKED_CLEAN_FAST_FORWARD_ONLY_NO_EXECUTION_RECORD_MUTATION"
    assert recovery["terminal_gate"] is False
    assert recovery["closure_authority"] is False
    assert recovery["purpose"] == "OPTIONAL_WORKSPACE_BASELINE_CATCHUP"

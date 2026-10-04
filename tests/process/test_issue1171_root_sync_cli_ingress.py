from __future__ import annotations

import json
import subprocess
from pathlib import Path

import tools.post_integration_durability as durability


BRANCH = "cleanup/2d-3d-sync"


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


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

    (seed / "tracked.txt").write_text("v2\n", encoding="utf-8")
    _git(seed, "commit", "-am", "v2")
    _git(seed, "push", "origin", BRANCH)
    accepted_sha = _git(seed, "rev-parse", "HEAD")
    accepted_tree = _git(seed, "rev-parse", "HEAD^{tree}")

    record = {
        "issue": 1171,
        "generation": 2,
        "state": "DONE",
        "target_sha": accepted_sha,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": accepted_sha},
    }
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return root, record_path, accepted_sha, accepted_tree


def test_cli_ingress_emits_verified_receipt_only_after_exact_sync(monkeypatch, tmp_path, capsys):
    root, record_path, accepted_sha, accepted_tree = _fixture(tmp_path)
    monkeypatch.setattr(durability, "CANONICAL_ROOT", str(root))

    rc = durability.main([
        "--execution-record", str(record_path),
        "--accepted-tree-sha", accepted_tree,
        "--root", str(root),
        "--production-branch", BRANCH,
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["schema"] == "WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1"
    assert payload["status"] == "VERIFIED"
    assert payload["accepted_sha"] == accepted_sha
    assert payload["accepted_tree_sha"] == accepted_tree
    assert _git(root, "rev-parse", "HEAD") == accepted_sha


def test_cli_ingress_failure_is_nonzero_and_never_looks_verified(monkeypatch, tmp_path, capsys):
    root, record_path, _accepted_sha, accepted_tree = _fixture(tmp_path)
    monkeypatch.setattr(durability, "CANONICAL_ROOT", str(root))
    (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    rc = durability.main([
        "--execution-record", str(record_path),
        "--accepted-tree-sha", accepted_tree,
        "--root", str(root),
        "--production-branch", BRANCH,
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["schema"] == "WHD_CANONICAL_ROOT_SYNC_RESULT_V1"
    assert payload["status"] == "FAILED"
    assert "tracked worktree/index changes" in payload["reason"]
    assert payload.get("accepted_sha") is None


def test_cli_ingress_can_persist_machine_readable_receipt(monkeypatch, tmp_path, capsys):
    root, record_path, accepted_sha, accepted_tree = _fixture(tmp_path)
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(durability, "CANONICAL_ROOT", str(root))

    rc = durability.main([
        "--execution-record", str(record_path),
        "--accepted-tree-sha", accepted_tree,
        "--root", str(root),
        "--production-branch", BRANCH,
        "--output", str(output),
    ])

    capsys.readouterr()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["status"] == "VERIFIED"
    assert payload["root_head_sha"] == accepted_sha


def test_contract_binds_cli_ingress_to_current_owner():
    contract_path = Path(__file__).resolve().parents[2] / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    validated = durability.validate_contract(payload)
    ingress = validated["root_sync_ingress"]
    assert ingress["owner"] == "tools/post_integration_durability.py::main"
    assert ingress["success_schema"] == "WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1"
    assert ingress["failure_schema"] == "WHD_CANONICAL_ROOT_SYNC_RESULT_V1"

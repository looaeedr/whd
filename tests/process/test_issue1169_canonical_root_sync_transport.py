from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


def _write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _fixture(tmp_path: Path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    root = tmp_path / "root"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "init", "-b", BRANCH, str(seed)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _git(seed, "config", "user.name", "WHD Test")
    _git(seed, "config", "user.email", "whd@example.invalid")
    _write(seed / "tracked.txt", "v1\n")
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

    _write(seed / "tracked.txt", "v2\n")
    _git(seed, "commit", "-am", "v2")
    _git(seed, "push", "origin", BRANCH)
    accepted_sha = _git(seed, "rev-parse", "HEAD")
    accepted_tree = _git(seed, "rev-parse", "HEAD^{tree}")
    old_sha = _git(root, "rev-parse", "HEAD")
    assert old_sha != accepted_sha

    record = {
        "issue": 1169,
        "generation": 2,
        "state": "DONE",
        "target_sha": accepted_sha,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {
            "issue_closed": True,
            "merged_sha": accepted_sha,
        },
    }
    return root, record, accepted_sha, accepted_tree


def _sync(monkeypatch, root: Path, record, tree: str):
    monkeypatch.setattr(durability, "CANONICAL_ROOT", str(root))
    return durability.sync_canonical_root_to_accepted_head(
        execution_record=record,
        accepted_tree_sha=tree,
        root_path=str(root),
        production_branch=BRANCH,
    )


def test_sync_advances_exact_root_and_preserves_untracked_shared_zero(monkeypatch, tmp_path):
    root, record, accepted_sha, accepted_tree = _fixture(tmp_path)
    pending = root / ".unpushed" / "docs" / "0" / "pending.txt"
    pending.parent.mkdir(parents=True)
    _write(pending, "keep\n")

    receipt = _sync(monkeypatch, root, record, accepted_tree)

    assert _git(root, "rev-parse", "HEAD") == accepted_sha
    assert _git(root, "rev-parse", "HEAD^{tree}") == accepted_tree
    assert pending.read_text(encoding="utf-8") == "keep\n"
    assert receipt["schema"] == "WHD_CANONICAL_ROOT_SYNC_RECEIPT_V1"
    assert receipt["status"] == "VERIFIED"
    assert receipt["accepted_sha"] == accepted_sha
    assert receipt["root_head_sha"] == accepted_sha


def test_sync_refuses_tracked_dirty_state(monkeypatch, tmp_path):
    root, record, _accepted_sha, accepted_tree = _fixture(tmp_path)
    _write(root / "tracked.txt", "dirty\n")

    with pytest.raises(durability.RootSyncError, match="tracked worktree/index changes"):
        _sync(monkeypatch, root, record, accepted_tree)


def test_sync_refuses_wrong_checked_out_branch(monkeypatch, tmp_path):
    root, record, _accepted_sha, accepted_tree = _fixture(tmp_path)
    _git(root, "checkout", "-b", "wrong-branch")

    with pytest.raises(durability.RootSyncError, match="branch mismatch"):
        _sync(monkeypatch, root, record, accepted_tree)


def test_sync_refuses_remote_head_that_is_not_terminal_accepted_sha(monkeypatch, tmp_path):
    root, record, _accepted_sha, accepted_tree = _fixture(tmp_path)
    record = dict(record)
    closure = dict(record["closure"])
    closure["merged_sha"] = "a" * 40
    record["closure"] = closure

    with pytest.raises(durability.RootSyncError, match="canonical remote head mismatch"):
        _sync(monkeypatch, root, record, accepted_tree)


def test_sync_withholds_receipt_when_tree_readback_is_not_exact(monkeypatch, tmp_path):
    root, record, accepted_sha, _accepted_tree = _fixture(tmp_path)

    with pytest.raises(durability.RootSyncError, match="tree readback mismatch"):
        _sync(monkeypatch, root, record, "f" * 40)

    # The only allowed side effect was still synchronization to the exact
    # accepted remote commit; the incorrect tree assertion never receives a
    # VERIFIED durability receipt.
    assert _git(root, "rev-parse", "HEAD") == accepted_sha


def test_sync_requires_terminal_done_released_record_before_git_mutation(monkeypatch, tmp_path):
    root, record, _accepted_sha, accepted_tree = _fixture(tmp_path)
    record = dict(record)
    record["state"] = "ACTIVE"

    monkeypatch.setattr(durability, "CANONICAL_ROOT", str(root))
    with pytest.raises(ValueError, match="requires DONE"):
        durability.sync_canonical_root_to_accepted_head(
            execution_record=record,
            accepted_tree_sha=accepted_tree,
            root_path=str(root),
            production_branch=BRANCH,
        )

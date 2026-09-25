from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/task_chain_isolation_guard.py"


def _load_guard():
    assert GUARD.is_file(), "#266 requires tools/task_chain_isolation_guard.py"
    spec = importlib.util.spec_from_file_location("task_chain_isolation_issue266", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _commit(repo: Path, name: str, content: str) -> str:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"add {name}")
    return _git(repo, "rev-parse", "HEAD")


def _fixture_repo(tmp_path: Path) -> dict[str, str | Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "base")
    _git(repo, "config", "user.email", "qa@example.com")
    _git(repo, "config", "user.name", "QA")
    base = _commit(repo, "base.txt", "base\n")

    _git(repo, "switch", "-c", "x")
    x_head = _commit(repo, "x.txt", "newer x\n")

    _git(repo, "switch", "base")
    _git(repo, "switch", "-c", "sibling")
    sibling_head = _commit(repo, "sibling.txt", "sibling production change\n")

    _git(repo, "switch", "base")
    _git(repo, "switch", "-c", "chain")
    chain_parent = _commit(repo, "t1.txt", "t1\n")
    chain_head = _commit(repo, "t2.txt", "t2\n")

    return {
        "repo": repo,
        "base": base,
        "x": x_head,
        "sibling": sibling_head,
        "chain_parent": chain_parent,
        "chain_head": chain_head,
    }


def _contract(tmp_path: Path, fx: dict[str, str | Path], expected_parent: str) -> Path:
    path = tmp_path / "isolation.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "262",
                "stage_id": "T3",
                "frozen_base_sha": fx["base"],
                "expected_parent_sha": expected_parent,
                "external_dependency_policy": "STOP_REQUIRED",
            }
        ),
        encoding="utf-8",
    )
    return path


def _assert_clean(guard, tmp_path: Path, fx: dict[str, str | Path], *, head: str, expected_parent: str):
    return guard.assert_cross_chain_isolation(
        _contract(tmp_path, fx, expected_parent),
        repo=Path(fx["repo"]),
        chain_head_sha=head,
        current_target_head_sha=str(fx["x"]),
        forbidden_refs=[str(fx["sibling"])],
    )


def test_clean_frozen_lineage_is_allowed(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    result = _assert_clean(
        guard,
        tmp_path,
        fx,
        head=str(fx["chain_head"]),
        expected_parent=str(fx["chain_parent"]),
    )
    assert result.contaminating_commits == ()
    assert result.patch_collisions == ()


def test_merge_of_newer_x_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    repo = Path(fx["repo"])
    _git(repo, "switch", "chain")
    before = _git(repo, "rev-parse", "HEAD")
    _git(repo, "merge", "--no-ff", "x", "-m", "bad merge x")
    bad_head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(guard.IsolationError, match="merge|parent|current X|contamin"):
        _assert_clean(guard, tmp_path, fx, head=bad_head, expected_parent=before)


def test_rebase_or_restart_on_newer_x_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    repo = Path(fx["repo"])
    _git(repo, "switch", "-c", "bad-rebase", "x")
    bad_head = _commit(repo, "rebased.txt", "rebased onto x\n")
    with pytest.raises(guard.IsolationError, match="parent|current X|base|contamin"):
        _assert_clean(
            guard,
            tmp_path,
            fx,
            head=bad_head,
            expected_parent=str(fx["chain_head"]),
        )


def test_sibling_merge_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    repo = Path(fx["repo"])
    _git(repo, "switch", "chain")
    before = _git(repo, "rev-parse", "HEAD")
    _git(repo, "merge", "--no-ff", "sibling", "-m", "bad sibling merge")
    bad_head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(guard.IsolationError, match="merge|parent|sibling|contamin"):
        _assert_clean(guard, tmp_path, fx, head=bad_head, expected_parent=before)


def test_silent_sibling_cherry_pick_is_rejected_by_patch_id(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    repo = Path(fx["repo"])
    _git(repo, "switch", "chain")
    before = _git(repo, "rev-parse", "HEAD")
    _git(repo, "cherry-pick", str(fx["sibling"]))
    bad_head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(guard.IsolationError, match="patch|cherry|import|dependency"):
        _assert_clean(guard, tmp_path, fx, head=bad_head, expected_parent=before)


def test_base_replacement_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    fx = _fixture_repo(tmp_path)
    repo = Path(fx["repo"])
    _git(repo, "switch", "--orphan", "unrelated")
    for child in repo.iterdir():
        if child.name == ".git":
            continue
        if child.is_file():
            child.unlink()
    bad_head = _commit(repo, "unrelated.txt", "new root\n")
    with pytest.raises(guard.IsolationError, match="base|ancestor|lineage"):
        _assert_clean(
            guard,
            tmp_path,
            fx,
            head=bad_head,
            expected_parent=str(fx["chain_head"]),
        )


def test_checked_in_t3_contract_pins_frozen_base_and_t2_parent() -> None:
    guard = _load_guard()
    contract = guard.load_isolation_contract(
        ROOT / "docs/governance/issue266-t3-isolation-contract.json"
    )
    assert contract.task_id == "262"
    assert contract.stage_id == "T3"
    assert contract.frozen_base_sha == "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
    assert contract.expected_parent_sha == "59ee94b5320db3236c2f93d8a3aaed0fbca9219f"
    assert contract.external_dependency_policy == "STOP_REQUIRED"

"""Fail-closed cross-chain isolation guard for WHD task chains.

An active task chain is frozen to its creation base and may only advance through its
own accepted-parent lineage.  Newer X commits and commits from sibling task chains are
external dependencies: they must stop for explicit handling instead of being merged,
rebased, cherry-picked, or otherwise imported into the active chain.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_POLICY = "STOP_REQUIRED"


class IsolationError(RuntimeError):
    """Raised when frozen-lineage isolation cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise IsolationError(f"ambiguous isolation contract: duplicate JSON key {key!r}")
        payload[key] = value
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IsolationError(f"missing required isolation contract field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise IsolationError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


def _git(repo: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise IsolationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = (result.stderr or result.stdout).strip()
    raise IsolationError(f"cannot prove ancestry {ancestor} -> {descendant}: {detail}")


def _rev_list(repo: Path, range_spec: str) -> tuple[str, ...]:
    text = _git(repo, "rev-list", range_spec)
    if not text:
        return ()
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _parents(repo: Path, commit: str) -> tuple[str, ...]:
    text = _git(repo, "show", "-s", "--format=%P", commit)
    return tuple(text.split()) if text else ()


def _patch_id(repo: Path, commit: str) -> str | None:
    patch = _git(repo, "show", "--pretty=format:", "--patch", commit)
    if not patch.strip():
        return None
    result = subprocess.run(
        ["git", "-C", str(repo), "patch-id", "--stable"],
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise IsolationError(f"cannot compute stable patch-id for {commit}: {detail}")
    line = result.stdout.strip().splitlines()
    if not line:
        return None
    return line[0].split()[0]


@dataclass(frozen=True)
class IsolationContract:
    task_id: str
    stage_id: str
    frozen_base_sha: str
    expected_parent_sha: str
    external_dependency_policy: str


@dataclass(frozen=True)
class IsolationResult:
    task_id: str
    stage_id: str
    chain_head_sha: str
    current_target_head_sha: str
    contaminating_commits: tuple[str, ...]
    patch_collisions: tuple[str, ...]


def load_isolation_contract(path: Path) -> IsolationContract:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise IsolationError(f"isolation contract not found: {path}") from exc
    except IsolationError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise IsolationError(f"malformed isolation contract {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise IsolationError("malformed isolation contract: root must be an object")

    contract = IsolationContract(
        task_id=_require_text(payload, "task_id"),
        stage_id=_require_text(payload, "stage_id"),
        frozen_base_sha=_validate_sha(
            _require_text(payload, "frozen_base_sha"), "frozen base SHA"
        ),
        expected_parent_sha=_validate_sha(
            _require_text(payload, "expected_parent_sha"), "expected parent SHA"
        ),
        external_dependency_policy=_require_text(payload, "external_dependency_policy"),
    )
    if contract.external_dependency_policy != _REQUIRED_POLICY:
        raise IsolationError(
            "external dependency policy must be STOP_REQUIRED; silent import is forbidden"
        )
    return contract


def assert_cross_chain_isolation(
    contract_path: Path,
    *,
    repo: Path,
    chain_head_sha: str,
    current_target_head_sha: str,
    forbidden_refs: Iterable[str] = (),
) -> IsolationResult:
    """Prove an active chain contains only its frozen lineage and own new commits."""
    contract = load_isolation_contract(contract_path)
    repo = Path(repo)
    chain_head_sha = _validate_sha(chain_head_sha, "chain head SHA")
    current_target_head_sha = _validate_sha(current_target_head_sha, "current X head SHA")
    forbidden = tuple(_validate_sha(ref, "forbidden sibling ref SHA") for ref in forbidden_refs)

    # Broken ancestry means the chain has replaced its frozen base entirely.
    if not _is_ancestor(repo, contract.frozen_base_sha, chain_head_sha):
        raise IsolationError(
            "frozen base is not an ancestor of chain HEAD: base replacement/lineage drift"
        )

    # Every stage must be a single-parent child of the previously accepted stage.
    head_parents = _parents(repo, chain_head_sha)
    if head_parents != (contract.expected_parent_sha,):
        if len(head_parents) > 1:
            raise IsolationError(
                "merge commit detected at chain HEAD; cross-chain/current X merge is forbidden"
            )
        actual = head_parents[0] if head_parents else "<root>"
        raise IsolationError(
            "chain HEAD parent mismatch: "
            f"expected accepted parent={contract.expected_parent_sha}, actual={actual}"
        )

    chain_commits = _rev_list(repo, f"{contract.frozen_base_sha}..{chain_head_sha}")

    # No hidden merge may exist earlier in the active chain either.
    for commit in chain_commits:
        if len(_parents(repo, commit)) > 1:
            raise IsolationError(
                f"merge commit {commit} detected inside active chain; isolation contaminated"
            )

    target_commits = _rev_list(
        repo, f"{contract.frozen_base_sha}..{current_target_head_sha}"
    )
    forbidden_commits: list[str] = list(target_commits)
    sibling_commit_set: set[str] = set()
    for ref in forbidden:
        commits = _rev_list(repo, f"{contract.frozen_base_sha}..{ref}")
        forbidden_commits.extend(commits)
        sibling_commit_set.update(commits)

    contaminating: list[str] = []
    for commit in dict.fromkeys(forbidden_commits):
        if _is_ancestor(repo, commit, chain_head_sha):
            contaminating.append(commit)

    if contaminating:
        if current_target_head_sha in contaminating or any(
            commit in target_commits for commit in contaminating
        ):
            raise IsolationError(
                "current X/newer target commits contaminate the active frozen task chain: "
                + ", ".join(contaminating)
            )
        if any(commit in sibling_commit_set for commit in contaminating):
            raise IsolationError(
                "sibling task-chain commits contaminate the active chain: "
                + ", ".join(contaminating)
            )
        raise IsolationError(
            "cross-chain contaminating commits detected: " + ", ".join(contaminating)
        )

    # An ordinary cherry-pick changes commit identity, so ancestry alone cannot detect it.
    # Stable patch IDs catch equivalent production patches imported under new SHAs.
    chain_patch_ids: dict[str, str] = {}
    for commit in chain_commits:
        patch_id = _patch_id(repo, commit)
        if patch_id:
            chain_patch_ids[patch_id] = commit

    forbidden_patch_ids: dict[str, str] = {}
    for commit in dict.fromkeys(forbidden_commits):
        patch_id = _patch_id(repo, commit)
        if patch_id:
            forbidden_patch_ids[patch_id] = commit

    collisions = tuple(sorted(set(chain_patch_ids).intersection(forbidden_patch_ids)))
    if collisions:
        detail = ", ".join(
            f"patch={patch_id} chain={chain_patch_ids[patch_id]} external={forbidden_patch_ids[patch_id]}"
            for patch_id in collisions
        )
        raise IsolationError(
            "stable patch-id collision proves cherry-pick/import of an external dependency; "
            "STOP_REQUIRED: " + detail
        )

    return IsolationResult(
        task_id=contract.task_id,
        stage_id=contract.stage_id,
        chain_head_sha=chain_head_sha,
        current_target_head_sha=current_target_head_sha,
        contaminating_commits=(),
        patch_collisions=(),
    )

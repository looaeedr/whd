from __future__ import annotations

import pytest

from tools.branch_cleanup_ref_guard import (
    BranchCleanupGuardError,
    assert_delete_candidates_safe,
    protected_open_pr_refs,
)


def _pull(*, head: str, base: str) -> dict[str, object]:
    return {
        "number": 271,
        "state": "open",
        "head": {"ref": head},
        "base": {"ref": base},
    }


def test_protected_open_pr_refs_includes_head_and_base() -> None:
    pulls = [_pull(head="feature/head", base="integration/base")]

    assert protected_open_pr_refs(pulls) == {"feature/head", "integration/base"}


def test_delete_guard_rejects_open_pr_head() -> None:
    pulls = [_pull(head="feature/head", base="integration/base")]

    with pytest.raises(BranchCleanupGuardError, match="OPEN PR protected ref"):
        assert_delete_candidates_safe(["feature/head"], pulls)


def test_delete_guard_rejects_open_pr_base_regression() -> None:
    pulls = [_pull(head="feature/head", base="integration/base")]

    with pytest.raises(BranchCleanupGuardError, match="OPEN PR protected ref"):
        assert_delete_candidates_safe(["integration/base"], pulls)


def test_delete_guard_allows_unrelated_candidate() -> None:
    pulls = [_pull(head="feature/head", base="integration/base")]

    assert_delete_candidates_safe(["old/merged-branch"], pulls)


def test_multiple_open_prs_protect_union_of_both_sides() -> None:
    pulls = [
        _pull(head="feature/a", base="base/a"),
        _pull(head="feature/b", base="base/b"),
    ]

    assert protected_open_pr_refs(pulls) == {
        "feature/a",
        "base/a",
        "feature/b",
        "base/b",
    }


@pytest.mark.parametrize(
    "pull",
    [
        {"number": 1, "state": "open", "head": {"ref": "feature/head"}},
        {"number": 1, "state": "open", "base": {"ref": "base/main"}},
        {"number": 1, "state": "open", "head": {"ref": ""}, "base": {"ref": "base/main"}},
        {"number": 1, "state": "open", "head": {"ref": "feature/head"}, "base": {"ref": ""}},
    ],
)
def test_malformed_open_pr_ref_evidence_fails_closed(pull: dict[str, object]) -> None:
    with pytest.raises(BranchCleanupGuardError, match="malformed OPEN PR ref evidence"):
        protected_open_pr_refs([pull])

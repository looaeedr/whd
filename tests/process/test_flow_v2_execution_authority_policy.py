import pytest
from tools.execution_authority_policy import (
    CANONICAL_STATE_BRANCH,
    ExecutionAuthorityError,
    authorize_state_mutation,
    classify_execution_path,
    require_state_mutation_authority,
)


def test_native_records_only_write_on_canonical_state_branch():
    p = ".dispatch/execution/issue-684.json"
    assert authorize_state_mutation(branch=CANONICAL_STATE_BRANCH, path=p).allowed
    assert not authorize_state_mutation(branch="cleanup/2d-3d-sync", path=p).allowed


def test_ready_index_is_derived_but_may_be_written_only_on_state_branch():
    p = ".dispatch/execution/ready-index.json"
    d = authorize_state_mutation(branch=CANONICAL_STATE_BRANCH, path=p)
    assert d.allowed
    assert d.classification == "DERIVED_READY_INDEX"


@pytest.mark.parametrize("path", [
    ".dispatch/claims/issue-684.json",
    ".dispatch/checkpoints/issue-684.json",
])
def test_legacy_claim_checkpoint_are_audit_only_everywhere(path):
    assert classify_execution_path(path) == "LEGACY_AUDIT_ONLY"
    for branch in (CANONICAL_STATE_BRANCH, "coord/dispatch-claims", "cleanup/2d-3d-sync"):
        assert not authorize_state_mutation(branch=branch, path=path).allowed
        with pytest.raises(ExecutionAuthorityError):
            require_state_mutation_authority(branch=branch, path=path)


def test_non_execution_files_are_not_control_plane_state_mutations():
    d = authorize_state_mutation(branch=CANONICAL_STATE_BRANCH, path="tools/foo.py")
    assert d.classification == "NON_EXECUTION_STATE"
    assert not d.allowed

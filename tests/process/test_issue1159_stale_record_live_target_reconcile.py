from types import SimpleNamespace

import pytest

from tools.control_transaction import ControlTransactionConflict
import tools.control_transaction_request_ingress as ingress


OLD = "a" * 40
LIVE = "b" * 40
WORK = "c" * 40


def _record():
    return SimpleNamespace(
        issue=1112,
        source_branch="cleanup/2d-3d-sync",
        source_sha=OLD,
        work_branch="coord/issue1112-stale",
        head_sha=WORK,
        target_branch="cleanup/2d-3d-sync",
        target_sha=OLD,
    )


def _request(*, kind="RECONCILE", proof=True):
    effect = {}
    if proof:
        effect["stale_record_live_target_reconcile_proof"] = {
            "schema": ingress.STALE_RECORD_LIVE_TARGET_RECONCILE_PROOF_SCHEMA,
            "issue": 1112,
            "stale_source_branch": "cleanup/2d-3d-sync",
            "stale_source_sha": OLD,
            "stale_target_branch": "cleanup/2d-3d-sync",
            "stale_target_sha": OLD,
            "live_target_branch": "cleanup/2d-3d-sync",
            "live_target_sha": LIVE,
        }
    return {
        "kind": kind,
        "effect": effect,
        "startup_transition": {
            "issue": 1112,
            "branch": "cleanup/2d-3d-sync",
            "head_sha": LIVE,
        },
    }


def _stale_error():
    return ValueError(
        "STARTUP_TRANSITION_STALE_IDENTITY "
        "observed_branch=cleanup/2d-3d-sync "
        f"observed_head={LIVE}"
    )


def test_issue1159_reconcile_bridge_accepts_live_target_with_stale_ancestor_proof(monkeypatch):
    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: LIVE,
    )
    monkeypatch.setattr(
        ingress,
        "_is_ancestor",
        lambda repo, token, ancestor, descendant: ancestor == OLD and descendant == LIVE,
    )

    assert ingress._validate_stale_record_live_target_reconcile_bridge(
        request=_request(),
        record=_record(),
        repo="looaeedr/whd",
        token="token",
        stale_identity_error=_stale_error(),
    )


def test_issue1159_normal_startup_transition_stale_identity_stays_fail_closed():
    assert not ingress._validate_stale_record_live_target_reconcile_bridge(
        request=_request(kind="START_BRANCH"),
        record=_record(),
        repo="looaeedr/whd",
        token="token",
        stale_identity_error=_stale_error(),
    )


def test_issue1159_reconcile_bridge_rejects_live_target_drift(monkeypatch):
    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: "d" * 40,
    )
    monkeypatch.setattr(
        ingress,
        "_is_ancestor",
        lambda repo, token, ancestor, descendant: True,
    )

    with pytest.raises(ControlTransactionConflict, match="live target drift"):
        ingress._validate_stale_record_live_target_reconcile_bridge(
            request=_request(),
            record=_record(),
            repo="looaeedr/whd",
            token="token",
            stale_identity_error=_stale_error(),
        )


def test_issue1159_reconcile_bridge_rejects_missing_ancestry(monkeypatch):
    monkeypatch.setattr(
        ingress,
        "_read_branch_head",
        lambda repo, token, branch: LIVE,
    )
    monkeypatch.setattr(
        ingress,
        "_is_ancestor",
        lambda repo, token, ancestor, descendant: False,
    )

    with pytest.raises(ControlTransactionConflict, match="stale target is not ancestor"):
        ingress._validate_stale_record_live_target_reconcile_bridge(
            request=_request(),
            record=_record(),
            repo="looaeedr/whd",
            token="token",
            stale_identity_error=_stale_error(),
        )

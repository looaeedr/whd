from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools.execution_entry_contract import rebind_scheduler_phase6_preflight_receipt
from tools.phase6_preflight_push_request import normalize_push_request
from tools.phase6_remote_preflight import run_remote_preflight

ROOT = Path(__file__).resolve().parents[2]
A_LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
B_LANE = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
HEAD = "a" * 40
REQUEST_ID = "a20-issue1080-takeover-20261004T1324Z"
SOURCE_INVOCATION = "a20:issue1080:takeover:20261004T1324Z"


def _push_request():
    return {
        "schema": "WHD_REMOTE_PHASE6_PREFLIGHT_PUSH_REQUEST_V1",
        "request_id": REQUEST_ID,
        "issue": 1080,
        "lane_id": A_LANE,
        "worker": A_LANE,
        "invocation_identity": SOURCE_INVOCATION,
        "executor_source": "scheduler",
        "branch": "cleanup/2d-3d-sync",
        "head_sha": HEAD,
        "task": "take over stranded scheduler work and continue exact next_action",
        "changed_files": [],
    }


def _receipt(observed_at: datetime):
    normalized = normalize_push_request(
        _push_request(),
        request_branch="coord/preflight-requests-a",
    )
    return run_remote_preflight(
        normalized,
        run_id=37205546398,
        root=ROOT,
        observed_at=observed_at,
    )


def _rebind(receipt, *, now, lane=A_LANE, head=HEAD, invocation="a40:issue1080:takeover:next"):
    return rebind_scheduler_phase6_preflight_receipt(
        receipt,
        issue=1080,
        lane_id=lane,
        invocation_identity=invocation,
        branch="cleanup/2d-3d-sync",
        head_sha=head,
        request_id=REQUEST_ID,
        now=now,
    )


def test_push_receipt_carries_lane_and_source_invocation():
    observed = datetime(2026, 10, 4, 13, 25, 16, tzinfo=timezone.utc)
    receipt = _receipt(observed)
    assert receipt["lane_id"] == A_LANE
    assert receipt["invocation_identity"] == SOURCE_INVOCATION
    assert receipt["request_id"] == REQUEST_ID


def test_same_lane_next_invocation_can_rebind_green_within_40_minutes():
    observed = datetime(2026, 10, 4, 13, 25, 16, tzinfo=timezone.utc)
    current = observed + timedelta(minutes=20)
    rebound = _rebind(_receipt(observed), now=current)

    assert rebound["schema"] == "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1"
    assert rebound["status"] == "GREEN"
    assert rebound["issue"] == 1080
    assert rebound["invocation_identity"] == "a40:issue1080:takeover:next"
    assert rebound["branch"] == "cleanup/2d-3d-sync"
    assert rebound["head_sha"] == HEAD
    metadata = rebound["scheduler_rebind"]
    assert metadata["schema"] == "WHD_SCHEDULER_PHASE6_PREFLIGHT_REBIND_V1"
    assert metadata["lane_id"] == A_LANE
    assert metadata["request_id"] == REQUEST_ID
    assert metadata["source_invocation_identity"] == SOURCE_INVOCATION
    assert metadata["source_run_id"] == 37205546398
    assert metadata["max_age_seconds"] == 2400


def test_scheduler_green_rebind_expires_after_40_minutes():
    observed = datetime(2026, 10, 4, 13, 25, 16, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="expired"):
        _rebind(_receipt(observed), now=observed + timedelta(minutes=40, seconds=1))


def test_scheduler_green_rebind_rejects_cross_lane_and_head_drift():
    observed = datetime(2026, 10, 4, 13, 25, 16, tzinfo=timezone.utc)
    receipt = _receipt(observed)
    current = observed + timedelta(minutes=20)

    with pytest.raises(ValueError, match="lane/worker mismatch"):
        _rebind(receipt, now=current, lane=B_LANE)
    with pytest.raises(ValueError, match="head mismatch"):
        _rebind(receipt, now=current, head="b" * 40)


def test_trusted_ingress_fetches_bot_comment_before_rebind(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    observed = datetime.now(timezone.utc) - timedelta(minutes=5)
    receipt = _receipt(observed)
    comment_id = 5980441788
    comment = {
        "id": comment_id,
        "issue_url": "https://api.github.com/repos/looaeedr/whd/issues/1080",
        "user": {"login": "github-actions[bot]"},
        "body": "\n".join(
            [
                "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1",
                "~~~json",
                json.dumps(receipt),
                "~~~",
            ]
        ),
    }
    monkeypatch.setattr(ingress, "_fetch_issue_comment", lambda *args, **kwargs: comment)
    monkeypatch.setattr(ingress, "_read_branch_head", lambda *args, **kwargs: HEAD)

    intent = {
        "schema": "WHD_CONTROL_TRANSACTION_PUSH_INTENT_V1",
        "request_id": "issue1080-takeover-handoff-next",
        "issue": 1080,
        "kind": "HANDOFF",
        "lane_id": A_LANE,
        "invocation_identity": "a40:issue1080:takeover:next",
        "expected_coord_head": "c" * 40,
        "expected_generation": 4,
        "effect": {
            "owner_kind": "SCHEDULER",
            "owner_id": A_LANE,
            "lane_id": A_LANE,
        },
        "purpose": "continue trusted scheduler takeover after asynchronous Phase6 GREEN",
        "work_root_gate_evidence": {},
        "scheduler_preflight_receipt_ref": {
            "schema": "WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1",
            "comment_id": comment_id,
            "request_id": REQUEST_ID,
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
        },
    }
    resolved = ingress._resolve_scheduler_preflight_receipt_ref(
        intent,
        repo="looaeedr/whd",
        token="test-token",
    )
    assert resolved["preflight_evidence"]["invocation_identity"] == intent["invocation_identity"]
    assert resolved["preflight_evidence"]["scheduler_rebind"]["request_id"] == REQUEST_ID


def test_trusted_ingress_rejects_non_actions_comment(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    monkeypatch.setattr(ingress, "_read_branch_head", lambda *args, **kwargs: HEAD)
    monkeypatch.setattr(
        ingress,
        "_fetch_issue_comment",
        lambda *args, **kwargs: {
            "id": 123,
            "issue_url": "https://api.github.com/repos/looaeedr/whd/issues/1080",
            "user": {"login": "looaeedr"},
            "body": "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1\n~~~json\n{}\n~~~",
        },
    )
    intent = {
        "schema": "WHD_CONTROL_TRANSACTION_PUSH_INTENT_V1",
        "request_id": "issue1080-takeover-handoff-next",
        "issue": 1080,
        "kind": "HANDOFF",
        "lane_id": A_LANE,
        "invocation_identity": "a40:issue1080:takeover:next",
        "expected_coord_head": "c" * 40,
        "expected_generation": 4,
        "effect": {},
        "purpose": "test",
        "work_root_gate_evidence": {},
        "scheduler_preflight_receipt_ref": {
            "schema": "WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1",
            "comment_id": 123,
            "request_id": REQUEST_ID,
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
        },
    }
    with pytest.raises(Exception, match="author is not trusted Actions"):
        ingress._resolve_scheduler_preflight_receipt_ref(
            intent,
            repo="looaeedr/whd",
            token="test-token",
        )


def test_intent_loader_accepts_receipt_ref_instead_of_raw_preflight(tmp_path):
    import tools.control_transaction_request_ingress as ingress

    payload = {
        "schema": "WHD_CONTROL_TRANSACTION_PUSH_INTENT_V1",
        "request_id": "issue1080-next",
        "issue": 1080,
        "kind": "HANDOFF",
        "lane_id": A_LANE,
        "invocation_identity": "a40:issue1080:next",
        "expected_coord_head": "c" * 40,
        "expected_generation": 4,
        "effect": {},
        "purpose": "continue",
        "work_root_gate_evidence": {},
        "scheduler_preflight_receipt_ref": {
            "schema": "WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1",
            "comment_id": 5980441788,
            "request_id": REQUEST_ID,
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
        },
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = ingress._load_request(path)
    assert "scheduler_preflight_receipt_ref" in loaded
    assert "preflight_evidence" not in loaded

def test_trusted_ingress_rejects_live_branch_head_drift(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    monkeypatch.setattr(ingress, "_read_branch_head", lambda *args, **kwargs: "b" * 40)
    intent = {
        "schema": "WHD_CONTROL_TRANSACTION_PUSH_INTENT_V1",
        "request_id": "issue1080-takeover-handoff-next",
        "issue": 1080,
        "kind": "HANDOFF",
        "lane_id": A_LANE,
        "invocation_identity": "a40:issue1080:takeover:next",
        "expected_coord_head": "c" * 40,
        "expected_generation": 4,
        "effect": {},
        "purpose": "test",
        "work_root_gate_evidence": {},
        "scheduler_preflight_receipt_ref": {
            "schema": "WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1",
            "comment_id": 5980441788,
            "request_id": REQUEST_ID,
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
        },
    }
    with pytest.raises(Exception, match="live branch/head drift"):
        ingress._resolve_scheduler_preflight_receipt_ref(
            intent,
            repo="looaeedr/whd",
            token="test-token",
        )


from tools.control_transaction_request_builder import (
    SESSION_REUSE_SCHEMA,
    build_control_transaction_request,
)
from tools.control_transaction_request_ingress import _session_reuse_requested


def test_reconcile_can_reuse_same_live_admission_session():
    request = build_control_transaction_request(
        request_id="issue1197-anchor-repair",
        issue=1197,
        kind="RECONCILE",
        lane_id="chatgpt.flowv2.work0",
        invocation_identity="codex:issue1197:active",
        expected_coord_head="a" * 40,
        expected_generation=5,
        effect={"repair_already_merged_anchor_pr_number": 1205},
        reuse_admission_session=True,
    )

    assert request["session_reuse"] == {
        "schema": SESSION_REUSE_SCHEMA,
        "mode": "LIVE_LEASE_CONTINUATION",
    }
    assert _session_reuse_requested(request) is True
    assert "startup_evidence" not in request
    assert "preflight_evidence" not in request
    assert "startup_transition" not in request

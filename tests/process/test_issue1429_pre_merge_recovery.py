"""#1429: trusted pre-merge admission for already-delivered unmerged PR."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tools.control_transaction import (
    ControlTransactionConflict, execute_transaction, prepare_transaction,
)
from tools.control_transaction_production_executor import (
    ProductionExecutorError, recover_pre_merge_missing_record,
)
from tools.execution_record import execution_record_from_payload, execution_record_to_payload
from tools.flow_v2_pre_merge_recovery import (
    PROOF_SCHEMA, build_pre_merge_recovery_ready_record,
)

ISSUE = 1429
PR = 1430
HEAD = "b" * 40
TARGET = "a" * 40
LANE = "chatgpt.flowv2.work2"
NOW = "2026-10-08T12:55:00Z"
TEST_WORKFLOW = ".github/workflows/whd-product-regression.yml"


def evidence():
    return dict(
        repository="looaeedr/whd", issue=ISSUE, pr_number=PR, lane_id=LANE,
        slot_id="worker.slot.2",
        issue_readback={"number": ISSUE, "state": "open", "pull_request": None},
        pr_readback={
            "number": PR, "state": "open", "merged": False, "mergeable": True,
            "body": "Closes #1429",
            "head": {"ref": "work/issue-1429", "sha": HEAD,
                     "repo": {"full_name": "looaeedr/whd"}},
            "base": {"ref": "cleanup/2d-3d-sync", "sha": TARGET},
        },
        observed_target_sha=TARGET,
        required_checks=["Governance Mirror Hard Gate", "focused-control-plane"],
        check_conclusions={"Governance Mirror Hard Gate": "success", "focused-control-plane": "success"},
        expected_pr_head_sha=HEAD, expected_target_sha=TARGET,
        pr_closes_issue=True, observed_at=NOW,
    )


def record():
    return build_pre_merge_recovery_ready_record(**evidence())


def test_creates_only_unclaimed_ready_with_exact_pr_and_no_historical_qa():
    r = record()
    assert r.state == "READY" and r.generation == 1
    assert r.slot_id == "worker.slot.2"
    assert r.owner_kind == "UNCLAIMED" and r.lease is None
    assert r.qa.last_accepted_run is None and r.qa.accepted_head_sha is None
    assert r.head_sha == HEAD and r.work_branch == "work/issue-1429"
    assert r.source_sha == HEAD and r.target_sha == TARGET
    assert r.next_action.kind == "ACQUIRE"
    bound = r.next_action.args["post_acquire"]
    assert bound["kind"] == "START_QA"
    assert bound["args"]["post_accept_pr_number"] == PR
    assert r.recovery_history[0]["schema"] == PROOF_SCHEMA
    assert r.recovery_history[0]["historical_acquire_reconstructed"] is False
    assert r.recovery_history[0]["qa_history_reconstructed"] is False
    assert execution_record_from_payload(execution_record_to_payload(r)) == r


@pytest.mark.parametrize("change", [
    lambda x: x["issue_readback"].update(state="closed"),
    lambda x: x["issue_readback"].update(number=111),
    lambda x: x["issue_readback"].update(pull_request={"url": "wrong"}),
    lambda x: x["pr_readback"].update(state="closed"),
    lambda x: x["pr_readback"].update(merged=True),
    lambda x: x["pr_readback"].update(mergeable=False),
    lambda x: x["pr_readback"]["head"].update(sha="1" * 40),
    lambda x: x["pr_readback"]["head"]["repo"].update(full_name="evil/repo"),
    lambda x: x["pr_readback"]["base"].update(ref="main"),
    lambda x: x.update(expected_target_sha="f" * 40),
    lambda x: x.update(expected_pr_head_sha="f" * 40),
    lambda x: x.update(pr_closes_issue=False),
    lambda x: x.update(required_checks=[]),
    lambda x: x.update(repository="attacker/repo"),
    lambda x: x.update(observed_at="2026-10-08T12:55:00"),
    lambda x: x["check_conclusions"].update({"focused-control-plane": "failure"}),
])
def test_untrusted_stale_or_incomplete_delivery_fails_closed(change):
    x = evidence()
    change(x)
    with pytest.raises(ValueError):
        build_pre_merge_recovery_ready_record(**x)


def test_native_acquire_cannot_prewrite_historical_qa():
    r = record()
    plan = prepare_transaction(
        r, kind="ACQUIRE", transaction_id="issue1429:acquire",
        invocation_identity="current:new",
    )
    effect = {
        "owner_kind": "SCHEDULER", "owner_id": LANE, "lane_id": LANE,
        "slot_id": "worker.slot.2", "observed_at": NOW, "updated_at": NOW,
        "lease": {
            "token": "current-only", "invocation_identity": "current:new",
            "expires_at": "2026-10-08T13:09:00Z",
        },
        "next_action": r.next_action.args["post_acquire"],
    }
    claimed = execute_transaction(r, plan, effect=effect)
    assert claimed.state == "ACTIVE" and claimed.generation == 2
    assert claimed.next_action.kind == "START_QA"
    assert claimed.qa.last_accepted_run is None
    assert claimed.lease.invocation_identity == "current:new"


def test_production_recovers_missing_record_via_native_writer(monkeypatch):
    from tools import control_transaction_production_executor as prod

    writes = []
    states = {}
    monkeypatch.setattr(prod, "_load_state",
                        lambda *a: ("c" * 40, "d" * 40, dict(states)))
    monkeypatch.setattr(prod, "_api", lambda repo, verb, path, token:
                        evidence()["pr_readback"] if path.startswith("/pulls/") else evidence()["issue_readback"])
    monkeypatch.setattr(prod, "_read_branch_head", lambda *a: TARGET)
    monkeypatch.setattr(prod, "_required_checks_for_target", lambda *a: evidence()["required_checks"])
    monkeypatch.setattr(prod, "_check_conclusions_for_head", lambda *a: evidence()["check_conclusions"])
    monkeypatch.setattr(prod, "_pr_body_closes_issue", lambda *a: True)
    monkeypatch.setattr(prod, "_now",
                        lambda: datetime(2026, 10, 8, 12, 55, tzinfo=timezone.utc))

    def write(repo, token, branch, *, parent_sha, base_tree_sha, records, issue):
        assert parent_sha == "c" * 40 and issue == ISSUE and issue not in states
        states.update(records)
        writes.append(issue)
        return "e" * 40, "f" * 40

    monkeypatch.setattr(prod, "_write_state", write)
    result = recover_pre_merge_missing_record(
        repo="looaeedr/whd", token="test", coord_branch="coord/execution-v2",
        issue=ISSUE, lane_id=LANE,
        invocation_identity="current:new", expected_coord_head="c" * 40,
        supplied_effect={
            "authority_kind": "USER_EXPLICIT", "authority_ref": "user:adopt existing PR",
            "pr_number": PR, "expected_pr_head_sha": HEAD, "expected_target_sha": TARGET,
        },
    )
    assert result["post_state"] == "READY"
    assert result["post_next_action"] == "ACQUIRE"
    assert result["lease_invocation_identity"] is None
    assert writes == [ISSUE]
    with pytest.raises(ControlTransactionConflict):
        recover_pre_merge_missing_record(
            repo="looaeedr/whd", token="test", coord_branch="coord/execution-v2",
            issue=ISSUE, lane_id=LANE, invocation_identity="current:new",
            expected_coord_head="c" * 40,
            supplied_effect={"authority_kind": "USER_EXPLICIT",
                             "authority_ref": "user:adopt existing PR",
                             "pr_number": PR, "expected_pr_head_sha": HEAD,
                             "expected_target_sha": TARGET},
        )


def test_cannot_fake_claim_or_qa_by_supplied_effect(monkeypatch):
    from tools import control_transaction_production_executor as prod
    monkeypatch.setattr(prod, "_load_state",
                        lambda *a: ("c" * 40, "d" * 40, {}))
    with pytest.raises(ProductionExecutorError, match="user-explicit"):
        recover_pre_merge_missing_record(
            repo="looaeedr/whd", token="test", coord_branch="coord/execution-v2",
            issue=ISSUE, lane_id=LANE, invocation_identity="current:new",
            expected_coord_head="c" * 40,
            supplied_effect={"pr_number": PR, "expected_pr_head_sha": HEAD,
                             "expected_target_sha": TARGET},
        )

def test_legacy_successful_ci_may_be_consumed_only_after_actual_acquire(monkeypatch):
    from tools import control_transaction_production_executor as prod
    r = record()
    acquired = execute_transaction(r, prepare_transaction(
        r, kind="ACQUIRE", transaction_id="premerge:claim",
        invocation_identity="current:new",
    ), effect={
        "owner_kind": "SCHEDULER", "owner_id": LANE, "lane_id": LANE,
        "slot_id": "worker.slot.2", "observed_at": NOW, "updated_at": NOW,
        "lease": {"token": "current-only", "invocation_identity": "current:new",
                  "expires_at": "2026-10-08T13:09:00Z"},
        "next_action": r.next_action.args["post_acquire"],
    })
    calls = []
    def api(repo, verb, path, token):
        calls.append(path)
        return {"id": 9876, "head_sha": HEAD, "path": TEST_WORKFLOW,
                "status": "completed", "conclusion": "success"}
    monkeypatch.setattr(prod, "_api", api)
    monkeypatch.setattr(prod, "_now",
                        lambda: datetime(2026, 10, 8, 12, 55, tzinfo=timezone.utc))
    effect = prod._trusted_consume_qa_effect(
        "looaeedr/whd", "token", record=acquired,
        invocation_identity="current:new",
        supplied={"run_id": 9876, "next_state": "INTEGRATING",
                  "next_action": {"kind": "MERGE", "args": {
                      "pr_number": PR, "revalidation_workflow": TEST_WORKFLOW}},
                  "semantic_state": "QA_ACCEPTED"},
    )
    result = execute_transaction(acquired, prepare_transaction(
        acquired, kind="CONSUME_QA", transaction_id="premerge:consume",
        invocation_identity="current:new",
    ), effect=effect)
    assert calls == ["/actions/runs/9876"]
    assert result.qa.last_accepted_run == 9876
    assert result.qa.accepted_head_sha == HEAD
    assert result.next_action.kind == "MERGE"


def test_premerge_cannot_rewrite_old_owner_or_qa(monkeypatch):
    from tools import control_transaction_production_executor as prod
    monkeypatch.setattr(prod, "_load_state",
                        lambda *a: ("c" * 40, "d" * 40, {}))
    with pytest.raises(ProductionExecutorError, match="cannot import"):
        recover_pre_merge_missing_record(
            repo="looaeedr/whd", token="test", coord_branch="coord/execution-v2",
            issue=ISSUE, lane_id=LANE, invocation_identity="current:new",
            expected_coord_head="c" * 40,
            supplied_effect={
                "authority_kind": "USER_EXPLICIT", "authority_ref": "user:existing PR",
                "pr_number": PR, "expected_pr_head_sha": HEAD,
                "expected_target_sha": TARGET,
                "qa": {"last_accepted_run": 9876},
            },
        )

def test_gated_premerge_recovery_contract_keeps_separate_postmerge_route():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    skill = (root / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "MISSING_EXECUTION_RECORD_PRE_MERGE_RECOVERY_V1" in skill
    assert "MISSING_EXECUTION_RECORD_POST_DELIVERY_RECOVERY_V1" in skill
    assert "PRE_MERGE_MISSING_RECORD_BOOTSTRAP_HARD_GATE_V1" in agents
    doc = (root / "docs/governance/flow_v2_pre_merge_recovery.md").read_text(encoding="utf-8")
    assert "WHD_DOC_META_V1" in doc

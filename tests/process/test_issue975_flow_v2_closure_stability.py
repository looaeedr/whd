from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _root_gate_evidence(execution_mode: str = "INTERACTIVE") -> dict[str, object]:
    from tools.work_root_gate import (
        READ_MODE_GITHUB_MIRROR,
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )

    payload = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    if execution_mode == "INTERACTIVE":
        payload.pop("role", None)
        payload.pop("mirror_policy", None)
        payload.pop("canonical_source", None)
        mode = READ_MODE_GOOGLE_DRIVE
    else:
        mode = READ_MODE_GITHUB_MIRROR
    return build_work_root_gate_evidence(
        gate_payload=payload,
        read_mode=mode,
        execution_mode=execution_mode,
    )


def _integrating_record(*, target_sha: str = "d" * 40):
    from tools.execution_record import execution_record_from_payload

    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 22,
            "issue": 952,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work0",
            "lane_id": "chatgpt.flowv2.work0",
            "slot_id": "worker.slot.0",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "a" * 40,
            "work_branch": "governance/issue952-mirror-ancestry-reconciliation",
            "head_sha": "b" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": target_sha,
            "state": "INTEGRATING",
            "semantic_state": "MERGED_PENDING_ANCESTRY",
            "next_action": {
                "kind": "FINALIZE",
                "args": {},
                "display": "Finalize after accepted ancestry anchor",
            },
            "lease": None,
            "active_run": None,
            "transaction": None,
            "qa": {
                "last_accepted_run": 36459698995,
                "accepted_head_sha": "b" * 40,
            },
            "blocker": None,
            "closure": {
                "merged_sha": "d" * 40,
                "issue_closed": False,
                "released_at": None,
            },
            "chain": {
                "parent_issue": None,
                "next_issue": None,
                "next_action": None,
            },
            "recovery_history": [],
            "updated_at": "2026-09-28T17:56:00Z",
        }
    )


def test_issue975_request_builder_owns_startup_evidence_and_lane_mode():
    from tools.control_transaction_request_builder import (
        build_control_transaction_request,
    )
    from tools.execution_entry_contract import (
        build_startup_declaration,
        validate_startup_evidence,
    )

    issued = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)
    purpose = "Issue #975 canonical request builder regression"
    invocation = "interactive:work3:issue975:test"
    request = build_control_transaction_request(
        request_id="issue975-builder",
        issue=975,
        kind="RECONCILE",
        lane_id="chatgpt.flowv2.work3",
        invocation_identity=invocation,
        expected_coord_head="c" * 40,
        expected_generation=1,
        effect={"semantic_state": "TEST"},
        purpose=purpose,
        work_root_gate_evidence=_root_gate_evidence(),
        issued_at=issued,
    )

    evidence = validate_startup_evidence(
        request["startup_evidence"],
        invocation_identity=invocation,
        execution_mode="INTERACTIVE",
        now=issued,
    )
    assert evidence["declaration"] == build_startup_declaration(purpose=purpose)
    assert evidence["execution_mode"] == "INTERACTIVE"
    assert request["lane_id"] == "chatgpt.flowv2.work3"


def test_issue975_builder_rejects_unknown_lane_before_request_creation():
    from tools.control_transaction_request_builder import (
        build_control_transaction_request,
    )

    with pytest.raises(ValueError, match="unsupported request lane"):
        build_control_transaction_request(
            request_id="bad-lane",
            issue=975,
            kind="RECONCILE",
            lane_id="chatgpt.flowv2.work99",
            invocation_identity="interactive:bad",
            expected_coord_head="c" * 40,
            expected_generation=1,
            effect={},
            purpose="bad lane",
            work_root_gate_evidence=_root_gate_evidence(),
        )


def test_issue975_finalize_accepts_proven_descendant_target_without_reqa():
    from tools.control_transaction import execute_transaction, prepare_transaction

    record = _integrating_record()
    plan = prepare_transaction(record, kind="FINALIZE", transaction_id="tx-final-descendant")
    current_target = "e" * 40
    done = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-28T18:01:00Z",
            "observed_target_sha": current_target,
            "target_advance_proof": {
                "schema": "WHD_FLOW_V2_TARGET_ADVANCE_PROOF_V1",
                "target_branch": "cleanup/2d-3d-sync",
                "anchor_sha": "d" * 40,
                "observed_target_sha": current_target,
                "anchor_is_ancestor": True,
                "fresh_readback": True,
                "trusted_source": "control_transaction_production_executor",
            },
            "issue_closed": True,
            "issue_state": "closed",
            "issue_state_reason": "completed",
            "released_at": "2026-09-28T18:01:00Z",
        },
    )

    assert done.state == "DONE"
    assert done.target_sha == current_target
    assert done.closure.merged_sha == "d" * 40
    assert done.qa.accepted_head_sha == "b" * 40


def test_issue975_finalize_fails_closed_without_descendant_proof():
    from tools.control_transaction import (
        ControlTransactionError,
        execute_transaction,
        prepare_transaction,
    )

    record = _integrating_record()
    plan = prepare_transaction(record, kind="FINALIZE", transaction_id="tx-final-drift")
    with pytest.raises(ControlTransactionError, match="trusted descendant proof"):
        execute_transaction(
            record,
            plan,
            effect={
                "updated_at": "2026-09-28T18:01:00Z",
                "observed_target_sha": "e" * 40,
                "issue_closed": True,
                "issue_state": "closed",
                "issue_state_reason": "completed",
                "released_at": "2026-09-28T18:01:00Z",
            },
        )


def test_issue975_production_executor_proves_anchor_ancestry_from_live_target(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record()

    def fake_api(repo, method, path, token, payload=None):
        assert method == "GET"
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": "e" * 40}}
        if path.startswith("/compare/"):
            return {"merge_base_commit": {"sha": "d" * 40}}
        raise AssertionError(path)

    monkeypatch.setattr(executor, "_api", fake_api)
    result = executor._finalize_target_readback("looaeedr/whd", "token", record=record)
    assert result["observed_target_sha"] == "e" * 40
    proof = result["target_advance_proof"]
    assert proof["anchor_sha"] == "d" * 40
    assert proof["anchor_is_ancestor"] is True
    assert proof["trusted_source"] == "control_transaction_production_executor"


def test_issue975_production_executor_rejects_non_descendant_target(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record()

    def fake_api(repo, method, path, token, payload=None):
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": "e" * 40}}
        if path.startswith("/compare/"):
            return {"merge_base_commit": {"sha": "9" * 40}}
        raise AssertionError(path)

    monkeypatch.setattr(executor, "_api", fake_api)
    with pytest.raises(
        executor.ProductionExecutorError,
        match="outside accepted merge-anchor ancestry",
    ):
        executor._finalize_target_readback("looaeedr/whd", "token", record=record)


def test_issue975_live_lease_collision_is_retryable_conflict_semantics():
    from tools.control_transaction import (
        ControlTransactionConflict,
        execute_transaction,
        prepare_transaction,
    )
    from tools.execution_record import execution_record_from_payload

    payload = json.loads(json.dumps({
        **json.loads(json.dumps({
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 5,
            "issue": 975,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work3",
            "lane_id": "chatgpt.flowv2.work3",
            "slot_id": "worker.slot.3",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "a" * 40,
            "work_branch": "governance/issue975-flow-v2-closure-stability",
            "head_sha": "b" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "c" * 40,
            "state": "ACTIVE",
            "semantic_state": "IMPLEMENTING",
            "next_action": {"kind": "APPLY_COMMIT", "args": {}, "display": "continue"},
            "lease": {
                "token": "lease-old",
                "invocation_identity": "interactive:work3:issue975:old",
                "expires_at": "2026-09-28T18:10:00Z",
            },
            "active_run": None,
            "transaction": None,
            "qa": {"last_accepted_run": None, "accepted_head_sha": None},
            "blocker": None,
            "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
            "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
            "recovery_history": [],
            "updated_at": "2026-09-28T18:00:00Z",
        }))
    }))
    record = execution_record_from_payload(payload)
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-live-lease",
        invocation_identity="interactive:work3:issue975:new",
    )
    with pytest.raises(ControlTransactionConflict, match="live lease"):
        execute_transaction(
            record,
            plan,
            effect={
                "observed_at": "2026-09-28T18:05:00Z",
                "owner_kind": record.owner_kind,
                "owner_id": record.owner_id,
                "lane_id": record.lane_id,
                "slot_id": record.slot_id,
                "lease": {
                    "token": "lease-new",
                    "invocation_identity": "interactive:work3:issue975:new",
                    "expires_at": "2026-09-28T18:20:00Z",
                },
                "next_action": {
                    "kind": record.next_action.kind,
                    "args": record.next_action.args,
                    "display": record.next_action.display,
                },
                "semantic_state": record.semantic_state,
                "updated_at": "2026-09-28T18:05:00Z",
            },
        )


def test_issue975_ingress_classifies_races_for_fresh_read_retry():
    text = (ROOT / "tools/control_transaction_request_ingress.py").read_text(
        encoding="utf-8"
    )
    assert '"retryable": True' in text
    assert '"FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION"' in text
    assert '"STARTUP_EVIDENCE_INVALID"' in text
    assert '"semantic_effect_applied": False' in text


def test_issue975_ancestry_workflow_gets_required_check_before_protected_push():
    ancestry = (
        ROOT / ".github/workflows/whd-governance-ancestry-reconcile.yml"
    ).read_text(encoding="utf-8")
    mirror = (
        ROOT / ".github/workflows/whd-governance-mirror-gate.yml"
    ).read_text(encoding="utf-8")

    assert "actions: write" in ancestry
    assert "ANCESTRY_CANDIDATE_BRANCH" in ancestry
    assert "gh workflow run whd-governance-mirror-gate.yml" in ancestry
    assert "-f mode=ANCESTRY_CANDIDATE" in ancestry
    assert 'gh run watch "$RUN_ID" --exit-status' in ancestry
    required_gate = ancestry.index("Run required gate on exact ancestry candidate")
    protected_push = ancestry.index(
        "git push origin HEAD:refs/heads/cleanup/2d-3d-sync"
    )
    assert required_gate < protected_push

    assert "ANCESTRY_CANDIDATE" in mirror
    assert "Verify protected cleanup ancestry candidate" in mirror
    assert "ANCESTRY_CANDIDATE_PARENT_MISMATCH" in mirror
    assert "ANCESTRY_CANDIDATE_TREE_CHANGED" in mirror


def test_issue975_flow_skill_makes_anchor_descendant_and_builder_rules_global():
    text = (
        ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    ).read_text(encoding="utf-8")
    required = (
        "tools/control_transaction_request_builder.py",
        "MERGE_ANCHOR_DESCENDANT_FINALIZATION_V1",
        "accepted merge SHA is an anchor",
        "FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION",
        "ANCESTRY_CANDIDATE",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"missing Flow v2 systemic closure contract tokens: {missing}"


def test_issue975_trusted_finalize_derives_released_at_from_issue_closed_at(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record()
    closed_at = "2026-09-28T15:34:53Z"

    monkeypatch.setattr(
        executor,
        "_finalize_target_readback",
        lambda repo, token, record: {
            "observed_target_sha": record.target_sha,
        },
    )

    def fake_api(repo, method, path, token, payload=None):
        assert path == "/issues/952"
        assert method == "GET"
        return {
            "state": "closed",
            "state_reason": "completed",
            "closed_at": closed_at,
        }

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._ensure_issue_closed_for_finalize(
        "looaeedr/whd",
        "token",
        issue=952,
        record=record,
    )

    assert effect["issue_closed"] is True
    assert effect["issue_state"] == "closed"
    assert effect["issue_state_reason"] == "completed"
    assert effect["issue_closed_at"] == closed_at
    assert effect["released_at"] == closed_at


def test_issue975_trusted_finalize_released_at_overrides_caller_omission(monkeypatch):
    import tools.control_transaction_production_executor as executor
    from tools.control_transaction import execute_transaction, prepare_transaction

    record = _integrating_record()

    monkeypatch.setattr(
        executor,
        "_finalize_target_readback",
        lambda repo, token, record: {
            "observed_target_sha": record.target_sha,
        },
    )

    def fake_api(repo, method, path, token, payload=None):
        if path == "/issues/952" and method == "GET":
            return {
                "state": "closed",
                "state_reason": "completed",
                "closed_at": "2026-09-28T15:34:53Z",
            }
        raise AssertionError((method, path, payload))

    monkeypatch.setattr(executor, "_api", fake_api)

    caller_effect = {}
    trusted_effect = dict(caller_effect)
    trusted_effect.update(
        executor._ensure_issue_closed_for_finalize(
            "looaeedr/whd",
            "token",
            issue=952,
            record=record,
        )
    )
    plan = prepare_transaction(
        record,
        kind="FINALIZE",
        transaction_id="tx-finalize-trusted-release",
    )
    done = execute_transaction(record, plan, effect=trusted_effect)

    assert done.state == "DONE"
    assert done.closure.released_at == "2026-09-28T15:34:53Z"

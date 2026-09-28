from tools.execution_record import execution_record_from_payload
from tools.flow_v2_merge_precheck import MergePrecheckResult, TARGET_DRIFT
from tools import control_transaction_production_executor as executor


INVOCATION = "scheduler-a:40:test"
LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"


def _record(next_action):
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 8,
            "issue": 889,
            "execution_intent": "SCHEDULER_LANE",
            "owner_kind": "SCHEDULER",
            "owner_id": LANE,
            "lane_id": LANE,
            "slot_id": None,
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "1" * 40,
            "work_branch": "canary/issue889",
            "head_sha": "a" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "b" * 40,
            "state": "INTEGRATING",
            "semantic_state": "QA_ACCEPTED",
            "next_action": next_action,
            "lease": {
                "token": "lease-889",
                "invocation_identity": INVOCATION,
                "expires_at": "2099-09-29T00:00:00Z",
            },
            "active_run": None,
            "transaction": None,
            "qa": {
                "last_accepted_run": 123,
                "accepted_head_sha": "a" * 40,
            },
            "blocker": None,
            "closure": {
                "merged_sha": None,
                "issue_closed": False,
                "released_at": None,
            },
            "chain": {
                "parent_issue": None,
                "next_issue": None,
                "next_action": None,
            },
            "recovery_history": [],
            "updated_at": "2026-09-29T00:00:00Z",
        }
    )


def test_trusted_merge_redirects_target_drift_without_attempting_pr_merge(monkeypatch):
    record = _record(
        {
            "kind": "MERGE",
            "args": {
                "pr_number": 891,
                "head_sha": "a" * 40,
                "target_branch": "cleanup/2d-3d-sync",
                "revalidation_workflow": ".github/workflows/phase6-bridge-anti-regrowth.yml",
            },
            "display": "merge",
        }
    )
    precheck = MergePrecheckResult(
        TARGET_DRIFT,
        "target advanced",
        "c" * 40,
    )
    monkeypatch.setattr(
        executor,
        "_merge_precheck_readback",
        lambda *args, **kwargs: ({}, precheck),
    )

    effect = executor._trusted_merge_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INVOCATION,
        supplied={},
    )

    assert effect["merge_precheck_status"] == TARGET_DRIFT
    assert effect["target_sha"] == "c" * 40
    assert effect["next_action"]["kind"] == "SYNC_TARGET"
    assert effect["next_action"]["args"]["pr_number"] == 891


def test_trusted_sync_target_uses_github_merge_and_requires_exact_head_revalidation(monkeypatch):
    record = _record(
        {
            "kind": "SYNC_TARGET",
            "args": {
                "target_sha": "c" * 40,
                "pr_number": 891,
                "target_branch": "cleanup/2d-3d-sync",
                "qa_workflow": ".github/workflows/phase6-bridge-anti-regrowth.yml",
            },
            "display": "sync target",
        }
    )

    work_reads = iter(["a" * 40, "d" * 40])

    def fake_read_branch_head(repo, token, branch):
        if branch == "cleanup/2d-3d-sync":
            return "c" * 40
        assert branch == "canary/issue889"
        return next(work_reads)

    calls = []

    def fake_api(repo, method, path, token, payload=None):
        calls.append((method, path, payload))
        assert method == "POST"
        assert path == "/merges"
        assert payload["base"] == "canary/issue889"
        assert payload["head"] == "c" * 40
        return {"sha": "d" * 40}

    monkeypatch.setattr(executor, "_read_branch_head", fake_read_branch_head)
    monkeypatch.setattr(executor, "_api", fake_api)

    effect = executor._trusted_sync_target_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INVOCATION,
    )

    assert calls
    assert effect["head_sha"] == "d" * 40
    assert effect["target_sha"] == "c" * 40
    assert effect["semantic_state"] == "QA_INVALIDATED_BY_TARGET_SYNC"
    assert effect["next_action"]["kind"] == "START_QA"
    assert effect["next_action"]["args"]["post_accept_pr_number"] == 891

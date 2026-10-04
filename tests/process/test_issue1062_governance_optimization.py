from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _root_evidence(mode="INTERACTIVE"):
    from tools.work_root_gate import (
        DEFAULT_DRIVE_FOLDER_ID,
        EVIDENCE_SCHEMA,
        GATE_SCHEMA,
        REQUIRED_ROOT_ENTRIES,
        UNPUSHED_ROOT,
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "gate_schema": GATE_SCHEMA,
        "execution_mode": mode,
        "read_mode": "GOOGLE_DRIVE_CANONICAL" if mode == "INTERACTIVE" else "GITHUB_REPO_CONTRACT",
        "source": "/Google Drive/WHD/.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json",
        "provider": "google_drive",
        "library_path": "/Google Drive/WHD",
        "drive_folder_id": DEFAULT_DRIVE_FOLDER_ID,
        "root_entries": sorted(REQUIRED_ROOT_ENTRIES),
        "unpushed_root": UNPUSHED_ROOT,
        "status": "GREEN",
    }


def _preflight(*, issue=1062, invocation="chatgpt.flowv2.work1:inv-1", branch="cleanup/2d-3d-sync", head="a" * 40, observed=None):
    from tools.execution_entry_contract import build_phase6_preflight_evidence
    return build_phase6_preflight_evidence(
        issue=issue,
        invocation_identity=invocation,
        branch=branch,
        head_sha=head,
        required_skills=["flow-v2-execution", "root-local-first"],
        completed_skills=["flow-v2-execution", "root-local-first"],
        required_references=["authority-map"],
        completed_references=["authority-map"],
        observed_at=observed,
    )


def test_retired_continuity_identity_cannot_route_as_active_skill():
    from tools.phase6_skill_preflight import load_skill_registry, required_skills_for
    registry = load_skill_registry()
    routes = {route["id"]: route for route in registry["routes"]}
    retired = routes["executable-continuity-controller"]
    assert retired["routing_status"] == "RETIRED"
    assert retired["replacement_route_id"] == "flow-v2-execution"
    for task, changed in (
        ("legacy checkpoint resume", []),
        ("continuity controller", ["tools/continuity_controller.py"]),
    ):
        required = set(required_skills_for(task=task, changed_files=changed, registry=registry))
        assert "flow-v2-execution" in required
        assert "executable-continuity-controller" not in required


def test_skill_catalog_physically_classifies_legacy_continuity_as_retired():
    from tools.skill_catalog import classify_path, load_catalog
    catalog = load_catalog()
    assert classify_path(
        ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
        catalog,
    ) == "retired"


def test_preflight_must_be_complete_and_fresh():
    from tools.execution_entry_contract import build_phase6_preflight_evidence, validate_phase6_preflight_evidence
    now = datetime(2026, 10, 3, 7, 30, tzinfo=timezone.utc)
    good = _preflight(observed=now)
    assert validate_phase6_preflight_evidence(good, issue=1062, invocation_identity="chatgpt.flowv2.work1:inv-1", now=now)["status"] == "GREEN"
    incomplete = dict(good)
    incomplete["completed_skills"] = ["flow-v2-execution"]
    with pytest.raises(ValueError, match="incomplete"):
        validate_phase6_preflight_evidence(incomplete, issue=1062, invocation_identity="chatgpt.flowv2.work1:inv-1", now=now)
    with pytest.raises(ValueError, match="expired"):
        validate_phase6_preflight_evidence(good, issue=1062, invocation_identity="chatgpt.flowv2.work1:inv-1", now=now + timedelta(seconds=301))
    with pytest.raises(ValueError, match="incomplete"):
        build_phase6_preflight_evidence(
            issue=1062, invocation_identity="chatgpt.flowv2.work1:inv-1", branch="cleanup/2d-3d-sync", head_sha="a" * 40,
            required_skills=["flow-v2-execution"], completed_skills=[],
            required_references=[], completed_references=[], observed_at=now,
        )


def test_startup_transition_binds_startup_preflight_and_exact_record_identity():
    from tools.execution_entry_contract import (
        assert_startup_transition_matches_record,
        build_startup_evidence,
        build_startup_transition,
        validate_startup_transition,
    )
    started = datetime(2026, 10, 3, 7, 30, tzinfo=timezone.utc)
    startup = build_startup_evidence(
        purpose="continue issue 1062",
        invocation_identity="chatgpt.flowv2.work1:inv-1",
        work_root_gate_evidence=_root_evidence(),
        execution_mode="INTERACTIVE",
        issued_at=started,
    )
    preflight = _preflight(observed=started + timedelta(seconds=5))
    transition = build_startup_transition(
        startup_evidence=startup,
        preflight_evidence=preflight,
        invocation_identity="chatgpt.flowv2.work1:inv-1",
        issue=1062,
        execution_mode="INTERACTIVE",
        now=started + timedelta(seconds=5),
    )
    assert validate_startup_transition(
        transition,
        invocation_identity="chatgpt.flowv2.work1:inv-1",
        issue=1062,
        execution_mode="INTERACTIVE",
        now=started + timedelta(seconds=6),
    )["status"] == "READY_FOR_EXECUTION"
    assert assert_startup_transition_matches_record(
        transition,
        issue=1062,
        source_branch="cleanup/2d-3d-sync", source_sha="a" * 40,
        work_branch="work/issue-1062", head_sha="b" * 40,
        target_branch="cleanup/2d-3d-sync", target_sha="c" * 40,
    )
    with pytest.raises(ValueError, match="STALE_IDENTITY"):
        assert_startup_transition_matches_record(
            transition,
            issue=1062,
            source_branch="cleanup/2d-3d-sync", source_sha="d" * 40,
            work_branch="work/issue-1062", head_sha="b" * 40,
            target_branch="cleanup/2d-3d-sync", target_sha="c" * 40,
        )


def test_preflight_must_match_current_invocation_identity():
    from tools.execution_entry_contract import build_startup_evidence, build_startup_transition
    started = datetime(2026, 10, 3, 7, 30, tzinfo=timezone.utc)
    startup = build_startup_evidence(
        purpose="continue issue 1062",
        invocation_identity="chatgpt.flowv2.work1:inv-1",
        work_root_gate_evidence=_root_evidence(),
        execution_mode="INTERACTIVE",
        issued_at=started,
    )
    foreign = _preflight(invocation="chatgpt.flowv2.work1:other", observed=started - timedelta(seconds=1))
    with pytest.raises(ValueError, match="invocation mismatch"):
        build_startup_transition(
            startup_evidence=startup,
            preflight_evidence=foreign,
            invocation_identity="chatgpt.flowv2.work1:inv-1",
            issue=1062,
            execution_mode="INTERACTIVE",
            now=started,
        )

def test_request_builder_requires_preflight_and_emits_unified_transition():
    from tools.control_transaction_request_builder import build_control_transaction_request
    now = datetime(2026, 10, 3, 7, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="preflight_evidence"):
        build_control_transaction_request(
            request_id="r1", issue=1062, kind="ACQUIRE",
            lane_id="chatgpt.flowv2.work1", invocation_identity="chatgpt.flowv2.work1:inv-1",
            expected_coord_head="f" * 40, expected_generation=1, effect={},
            purpose="continue", work_root_gate_evidence=_root_evidence(), issued_at=now,
        )
    req = build_control_transaction_request(
        request_id="r2", issue=1062, kind="ACQUIRE",
        lane_id="chatgpt.flowv2.work1", invocation_identity="chatgpt.flowv2.work1:inv-1",
        expected_coord_head="f" * 40, expected_generation=1, effect={},
        purpose="continue", work_root_gate_evidence=_root_evidence(),
        preflight_evidence=_preflight(observed=now), issued_at=now,
    )
    assert req["startup_evidence"]["schema"] == "WHD_EXECUTION_ENTRY_EVIDENCE_V1"
    assert req["preflight_evidence"]["schema"] == "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1"
    assert req["startup_transition"]["schema"] == "WHD_EXECUTION_STARTUP_TRANSITION_V1"


def test_flow_v2_documents_single_startup_transition_gate():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "STARTUP_TRANSITION_GATE_V1",
        "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1",
        "WHD_EXECUTION_STARTUP_TRANSITION_V1",
        "STARTUP_TRANSITION_STALE_IDENTITY",
        "startup_evidence + preflight_evidence + startup_transition",
    ):
        assert marker in text

def _stale_release_record():
    from tools.execution_record import execution_record_from_payload

    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "issue": 1062,
            "generation": 44,
            "execution_intent": "EXECUTE_TICKET",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "0" * 40,
            "work_branch": "test/issue1062-product-full-regression-recovery",
            "head_sha": "a" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "a" * 40,
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work1",
            "lane_id": "chatgpt.flowv2.work1",
            "slot_id": None,
            "lease": {
                "token": "lease:1062:test",
                "invocation_identity": "chatgpt.flowv2.work1:stale",
                "expires_at": "2026-10-03T14:47:01Z",
            },
            "state": "ACTIVE",
            "semantic_state": "PATH_RESERVATION_RELEASED",
            "next_action": {
                "kind": "START_BRANCH",
                "args": {},
                "display": "stale continuation that must not run",
            },
            "active_run": None,
            "qa": {"last_accepted_run": None, "accepted_head_sha": None},
            "mutation_scope": {
                "target_branch": "cleanup/2d-3d-sync",
                "base_sha": "a" * 40,
                "write_paths": ["tools/execution_record.py"],
                "delete_paths": [],
                "reservation_state": "RELEASED",
            },
            "blocker": None,
            "closure": {
                "merged_sha": None,
                "released_at": None,
                "issue_closed": False,
            },
            "chain": {
                "parent_issue": 1059,
                "next_issue": None,
                "next_action": None,
            },
            "transaction": None,
            "updated_at": "2026-10-03T14:33:56Z",
            "recovery_history": [],
        }
    )


def test_issue1062_trusted_release_paths_deletes_zero_unique_stale_branch(monkeypatch):
    from urllib.error import HTTPError
    import tools.control_transaction_production_executor as executor

    record = _stale_release_record()
    exists = {"value": True}
    calls = []
    target_sha = "b" * 40

    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda repo, token, branch: target_sha,
    )

    def fake_api(repo, method, path, token, payload=None):
        calls.append((method, path))
        if path.startswith("/git/ref/heads/"):
            if exists["value"]:
                return {"object": {"sha": record.head_sha}}
            raise HTTPError(path, 404, "not found", None, None)
        if path.startswith("/branches/"):
            return {"protected": False, "commit": {"sha": record.head_sha}}
        if path.startswith("/compare/"):
            return {"merge_base_commit": {"sha": record.head_sha}}
        if method == "DELETE" and path.startswith("/git/refs/heads/"):
            exists["value"] = False
            return None
        raise AssertionError((method, path))

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._trusted_stale_release_effect(
        "looaeedr/whd",
        "token",
        record=record,
        records={record.issue: record},
        supplied={"reason": "stale reset", "delete_stale_work_branch": True},
    )

    assert effect["work_branch_exists"] is False
    assert effect["fresh_target_sha"] == target_sha
    assert effect["stale_work_branch_deleted"] is True
    assert effect["stale_work_branch_readback"] == "ABSENT"
    assert any(method == "DELETE" for method, _ in calls)


def test_issue1062_stale_branch_delete_requires_explicit_release_paths_intent(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _stale_release_record()
    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda repo, token, branch: "b" * 40,
    )
    monkeypatch.setattr(
        executor,
        "_api",
        lambda repo, method, path, token, payload=None: {"object": {"sha": record.head_sha}}
        if path.startswith("/git/ref/heads/")
        else {"protected": False, "commit": {"sha": record.head_sha}},
    )

    with pytest.raises(Exception, match="delete_stale_work_branch=true"):
        executor._trusted_stale_release_effect(
            "looaeedr/whd",
            "token",
            record=record,
            records={record.issue: record},
            supplied={"reason": "stale reset"},
        )


def test_issue1062_stale_branch_delete_rejects_protected_or_diverged_ref(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _stale_release_record()
    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda repo, token, branch: "b" * 40,
    )

    def protected_api(repo, method, path, token, payload=None):
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": record.head_sha}}
        if path.startswith("/branches/"):
            return {"protected": True, "commit": {"sha": record.head_sha}}
        raise AssertionError((method, path))

    monkeypatch.setattr(executor, "_api", protected_api)
    with pytest.raises(Exception, match="protected work branch"):
        executor._trusted_stale_release_effect(
            "looaeedr/whd",
            "token",
            record=record,
            records={record.issue: record},
            supplied={"reason": "stale reset", "delete_stale_work_branch": True},
        )

    def diverged_api(repo, method, path, token, payload=None):
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": record.head_sha}}
        if path.startswith("/branches/"):
            return {"protected": False, "commit": {"sha": record.head_sha}}
        if path.startswith("/compare/"):
            return {"merge_base_commit": {"sha": "c" * 40}}
        raise AssertionError((method, path))

    monkeypatch.setattr(executor, "_api", diverged_api)
    with pytest.raises(Exception, match="not contained in current target"):
        executor._trusted_stale_release_effect(
            "looaeedr/whd",
            "token",
            record=record,
            records={record.issue: record},
            supplied={"reason": "stale reset", "delete_stale_work_branch": True},
        )


def test_issue1062_flow_v2_documents_canonical_stale_branch_delete_transport():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    for marker in (
        "STALE_RELEASED_BRANCH_CLEANUP_TRANSPORT_V1",
        "delete_stale_work_branch=true",
        "work HEAD 是 current target ancestor",
        "DELETE 後必須再次 GET exact ref",
    ):
        assert marker in text

def test_issue1062_delete_stale_intent_is_rejected_outside_release_paths(tmp_path):
    from tools.control_transaction_request_builder import REQUEST_SCHEMA
    from tools.control_transaction_request_ingress import (
        ProductionExecutorError,
        _load_request,
    )

    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": "bad-delete-intent",
        "issue": 1062,
        "kind": "ACQUIRE",
        "lane_id": "chatgpt.flowv2.work1",
        "invocation_identity": "chatgpt.flowv2.work1:test",
        "expected_coord_head": "f" * 40,
        "expected_generation": 44,
        "effect": {"delete_stale_work_branch": True},
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ProductionExecutorError, match="only valid as true on RELEASE_PATHS"):
        _load_request(path)



def test_control_plane_regression_does_not_keep_retired_continuity_runtime_alive():
    runner = (ROOT / "tools/control_plane_regression.py").read_text(encoding="utf-8")
    for retired in (
        "tools/continuity_controller.py",
        "tools/scheduled_resume_executor.py",
        "tools/scheduled_resume_runtime.py",
        "tests/process/test_checkpoint_resume_contract.py",
        "tests/process/test_continuous_execution_durable_contract.py",
        "tests/process/test_issue952_governance_ancestry_reconcile.py",
    ):
        assert retired not in runner


def test_legacy_github_readers_fail_closed_without_remote_authority(monkeypatch):
    import tools.execution_claim_guard as claim_guard
    import tools.stale_claim_takeover as takeover

    for name in ("WHD_REMOTE_CONNECTION_AUTHORITY_JSON", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "looaeedr/whd")

    with pytest.raises(claim_guard.ExecutionClaimError, match="REMOTE_CONNECTION_DENIED"):
        claim_guard._github_api_json("issues/1")
    with pytest.raises(takeover.StaleTakeoverError, match="REMOTE_CONNECTION_DENIED"):
        takeover._github_api_json("issues/1")


def test_legacy_github_readers_delegate_to_current_remote_authority_gate(monkeypatch):
    import tools.execution_claim_guard as claim_guard
    import tools.stale_claim_takeover as takeover

    authority = {
        "schema": "WHD_REMOTE_CONNECTION_AUTHORITY_V1",
        "kind": "USER_EXPLICIT_REMOTE",
        "target": "GITHUB",
        "allowed_actions": ["READ"],
        "user_explicit": True,
        "lane": None,
        "user_authored_entry_contract": False,
    }
    monkeypatch.setenv("WHD_REMOTE_CONNECTION_AUTHORITY_JSON", json.dumps(authority))
    assert claim_guard._require_remote_connection_authority(action="READ")["target"] == "GITHUB"
    assert takeover._require_remote_connection_authority(action="READ")["target"] == "GITHUB"



def test_stale_machine_looking_root_artifacts_are_not_current():
    assert not (ROOT / ".flow-v2/execution-fence.json").exists()
    assert not (ROOT / ".tmp-gen10").exists()


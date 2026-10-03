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

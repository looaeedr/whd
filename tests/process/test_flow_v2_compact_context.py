"""Opt-in compact context never replaces Flow v2 canonical decisions."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from tools.execution_record import execution_record_from_payload
from tools.flow_v2_compact_context import (
    SCHEMA, build_compact_execution_context,
)
from tools.execution_scheduler_view import build_scheduler_view
from tools.issue_comment_progress import build_owner_progress_comment

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"


def _record():
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2", "version": 2, "generation": 11,
        "issue": 1382, "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER", "owner_id": LANE, "lane_id": LANE,
        "slot_id": "worker.slot.1", "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40, "work_branch": "work/issue-1382",
        "head_sha": "b" * 40, "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40, "state": "INTEGRATING",
        "semantic_state": "QA_INVALIDATED_BY_TARGET_SYNC",
        "next_action": {"kind": "START_QA", "args": {
            "workflow": ".github/workflows/whd-product-regression.yml"},
            "display": "Retest latest exact head"},
        "lease": {"token": "secret-lease", "invocation_identity": "worker:A",
                  "expires_at": "2026-10-08T12:10:00Z"},
        "qa": {"last_accepted_run": 123, "accepted_head_sha": "a" * 40},
        "closure": {"merged_sha": None, "issue_closed": False,
                    "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [], "updated_at": NOW.isoformat(),
    })


def test_compact_context_is_non_authority_and_does_not_leak_lease_token():
    record = _record()
    before = repr(record)
    result = build_compact_execution_context(record)
    assert result["schema"] == SCHEMA
    assert result["authority"] == "READ_ONLY_NON_AUTHORITY"
    assert result["next_action"]["kind"] == "START_QA"
    assert result["qa"]["accepted_for_current_head"] is False
    assert result["comment_clock"]["status"] == "UNKNOWN_NOT_FETCHED"
    assert "secret-lease" not in repr(result)
    assert repr(record) == before


def test_context_generation_or_head_change_recomputes_identity():
    original = _record()
    advanced = replace(original, generation=12, head_sha="d" * 40)
    first = build_compact_execution_context(original)
    second = build_compact_execution_context(advanced)
    assert first["provenance"]["record_fingerprint"] != second["provenance"]["record_fingerprint"]
    assert second["branch"]["head_sha"] == "d" * 40
    assert second["qa"]["accepted_for_current_head"] is False


def test_fresh_comments_use_exact_existing_owner_gate():
    record = _record()
    note = build_owner_progress_comment(
        issue=record.issue, generation=record.generation,
        owner_kind=record.owner_kind, owner_id=record.owner_id,
        work_branch=record.work_branch, head_sha=record.head_sha,
        lane_id=record.lane_id, slot_id=record.slot_id,
        event="PROGRESS", done="QA started", work="Inspecting run",
        next_step="Read checks")
    old = {"id": 42, "body": note, "user": {"login": "looaeedr"},
           "created_at": (NOW - timedelta(seconds=601)).isoformat()}
    result = build_compact_execution_context(
        record, now=NOW, issue_comments=[old], trusted_comment_authors={"looaeedr"})
    assert result["comment_clock"]["intervention_candidate"] is True
    assert result["comment_clock"]["comment_id"] == 42
    wrong = {**old, "user": {"login": "untrusted"}}
    denied = build_compact_execution_context(
        record, now=NOW, issue_comments=[wrong], trusted_comment_authors={"looaeedr"})
    assert denied["comment_clock"]["intervention_candidate"] is False


def test_comment_feed_requires_clock_and_provenance():
    with pytest.raises(ValueError):
        build_compact_execution_context(_record(), issue_comments=[])


def test_opt_in_scheduler_is_behaviorally_identical_to_legacy():
    record = _record()
    params = dict(lane_id=LANE, invocation_identity="worker:A", now=NOW.isoformat())
    old = build_scheduler_view([record], **params)
    new = build_scheduler_view([record], context_mode="COMPACT", **params)
    assert old.compact_context is None
    assert new.compact_context is not None
    assert new.compact_context["provenance"]["record_generation"] == 11
    assert replace(new, compact_context=None) == old
    with pytest.raises(ValueError):
        build_scheduler_view([record], context_mode="SILENT", **params)

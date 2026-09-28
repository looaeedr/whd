import json
from pathlib import Path

import pytest

from tools.execution_ready_index import build_ready_index
from tools.scheduler_startup_bundle import (
    SCHEMA,
    SchedulerStartupBundleError,
    build_scheduler_startup_bundle,
    bundle_matches_coord_head,
    validate_scheduler_startup_bundle,
)

ROOT = Path(__file__).resolve().parents[2]


def _root_evidence():
    mirror = json.loads(
        (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").read_text(encoding="utf-8")
    )
    return {
        "schema": "WHD_WORK_ROOT_GATE_EVIDENCE_V1",
        "gate_schema": mirror["schema"],
        "gate_status": mirror["status"],
        "read_mode": "GITHUB_MIRROR",
        "execution_mode": "SCHEDULER_LANE",
        "source": ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json",
        "provider": "google_drive",
        "library_path": "/Google Drive/WHD",
        "drive_folder_id": "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_",
        "current_source_manifest_file_id": "1NnUvzJGz7_SPpHvQ_IJvGR-3QgwbMfGCfgfj1hlpD9U",
    }


def test_no_work_bundle_skips_project_startup_and_remote_preflight():
    bundle = build_scheduler_startup_bundle(
        [],
        lane_id="scheduler.6ab13fa557fc8191935c671214b865e2",
        invocation_identity="scheduler-a:00:issue990:no-work",
        now="2026-09-28T23:00:00Z",
        coord_head="a" * 40,
        work_root_gate_evidence=_root_evidence(),
        ready_index=build_ready_index([]),
    )

    assert bundle["schema"] == SCHEMA
    assert bundle["projection"]["decision"] == "NO_EXECUTABLE_WORK"
    assert bundle["no_work_fast_path"] is True
    assert bundle["requires_project_startup"] is False
    assert bundle["requires_phase6_preflight"] is False
    assert bundle["fast_exit"] == "NO_EXECUTABLE_WORK"
    validate_scheduler_startup_bundle(
        bundle,
        lane_id="scheduler.6ab13fa557fc8191935c671214b865e2",
        invocation_identity="scheduler-a:00:issue990:no-work",
    )


def test_bundle_can_be_reused_after_preflight_only_when_coord_head_is_unchanged():
    bundle = build_scheduler_startup_bundle(
        [],
        lane_id="scheduler.e58ea936e7d0b12bd0d475314709d6f1",
        invocation_identity="scheduler-b:B15:issue990:bootstrap",
        now="2026-09-28T23:00:00Z",
        coord_head="b" * 40,
        work_root_gate_evidence=_root_evidence(),
    )
    assert bundle_matches_coord_head(bundle, "b" * 40) is True
    assert bundle_matches_coord_head(bundle, "c" * 40) is False


def test_bundle_rejects_tampered_projection_fingerprint():
    bundle = build_scheduler_startup_bundle(
        [],
        lane_id="scheduler.6ab13fa557fc8191935c671214b865e2",
        invocation_identity="scheduler-a:20:issue990:tamper",
        now="2026-09-28T23:00:00Z",
        coord_head="d" * 40,
        work_root_gate_evidence=_root_evidence(),
    )
    bundle["projection"]["decision"] = "READY_CANDIDATES"
    with pytest.raises(SchedulerStartupBundleError, match="fingerprint mismatch"):
        validate_scheduler_startup_bundle(
            bundle,
            lane_id="scheduler.6ab13fa557fc8191935c671214b865e2",
            invocation_identity="scheduler-a:20:issue990:tamper",
        )

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIRROR = ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"


def _mirror_payload():
    return json.loads(MIRROR.read_text(encoding="utf-8"))


def _canonical_payload():
    payload = _mirror_payload()
    payload.pop("role", None)
    payload.pop("mirror_policy", None)
    payload.pop("canonical_source", None)
    return payload


def test_repository_mirror_points_to_exact_google_drive_root_gate():
    from tools.work_root_gate import (
        CANONICAL_GATE_FILE_ID,
        CANONICAL_GATE_LIBRARY_PATH,
        DEFAULT_DRIVE_FOLDER_ID,
        DEFAULT_LIBRARY_PATH,
        READ_MODE_GITHUB_MIRROR,
        validate_gate_payload,
    )

    payload = _mirror_payload()
    validated = validate_gate_payload(payload, read_mode=READ_MODE_GITHUB_MIRROR)
    assert validated["role"] == "MIRROR"
    assert validated["mirror_policy"] == "POINTER_ONLY"
    assert validated["canonical_source"]["library_path"] == CANONICAL_GATE_LIBRARY_PATH
    assert validated["canonical_source"]["drive_file_id"] == CANONICAL_GATE_FILE_ID
    assert validated["default_work_root"]["library_path"] == DEFAULT_LIBRARY_PATH
    assert validated["default_work_root"]["drive_folder_id"] == DEFAULT_DRIVE_FOLDER_ID


def test_interactive_requires_canonical_drive_gate_and_scheduler_requires_repo_mirror():
    from tools.work_root_gate import (
        READ_MODE_GITHUB_MIRROR,
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )

    drive = build_work_root_gate_evidence(
        gate_payload=_canonical_payload(),
        read_mode=READ_MODE_GOOGLE_DRIVE,
        execution_mode="INTERACTIVE",
    )
    assert drive["source"] == "/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json"

    scheduler = build_work_root_gate_evidence(
        gate_payload=_mirror_payload(),
        read_mode=READ_MODE_GITHUB_MIRROR,
        execution_mode="SCHEDULER_LANE",
    )
    assert scheduler["source"] == ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json"

    with pytest.raises(ValueError, match="interactive startup"):
        build_work_root_gate_evidence(
            gate_payload=_mirror_payload(),
            read_mode=READ_MODE_GITHUB_MIRROR,
            execution_mode="INTERACTIVE",
        )


def test_root_gate_rejects_container_library_and_github_as_implicit_root():
    from tools.work_root_gate import READ_MODE_GOOGLE_DRIVE, validate_gate_payload

    for bad in ("/mnt/data", "/WHD", "/", "GitHub repository checkout"):
        payload = _canonical_payload()
        payload["default_work_root"] = dict(payload["default_work_root"])
        payload["default_work_root"]["library_path"] = bad
        with pytest.raises(ValueError, match="work-root"):
            validate_gate_payload(payload, read_mode=READ_MODE_GOOGLE_DRIVE)


def test_agents_places_work_root_bootstrap_before_phase6_preflight():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    root_gate = text.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V1")
    phase6 = text.index("# 0. 啟動硬閘門")
    assert root_gate < phase6
    assert "/Google Drive/WHD" in text
    assert "WHD_WORK_ROOT_HARD_GATE_V1.json" in text
    assert "CURRENT_SOURCE_MANIFEST_READ" in text


def test_flow_v2_project_startup_reads_root_gate_before_ai_library_and_preflight():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(
        encoding="utf-8"
    )
    section = text.split("## PROJECT_STARTUP_HARD_GATE_V1", 1)[1].split(
        "<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->", 1
    )[0]
    assert section.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V1") < section.index(
        "AI_LIBRARY_SEARCHED"
    )
    assert "GOOGLE_DRIVE_CANONICAL" in section
    assert "GITHUB_MIRROR" in section
    assert "WHD_WORK_ROOT_GATE_EVIDENCE_V1" in section


def test_every_flow_v2_execution_bridge_routes_through_canonical_flow_startup():
    skill_root = ROOT / ".agents/skills/engineering"
    bridged = []
    for path in skill_root.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        if "FLOW_V2_EXECUTION_BRIDGE_V1" not in text:
            continue
        bridged.append(path)
        assert "flow-v2-execution" in text, path
        assert (
            "whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md" in text
            or "PROJECT_STARTUP_HARD_GATE_V1" in text
        ), path
    assert len(bridged) >= 9


def test_startup_evidence_requires_validated_root_gate_before_ingress():
    from datetime import datetime, timezone

    from tools.execution_entry_contract import build_startup_evidence, validate_startup_evidence
    from tools.work_root_gate import (
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
    )

    gate = build_work_root_gate_evidence(
        gate_payload=_canonical_payload(),
        read_mode=READ_MODE_GOOGLE_DRIVE,
        execution_mode="INTERACTIVE",
    )
    evidence = build_startup_evidence(
        purpose="Issue #961 root-gate validation",
        invocation_identity="interactive:work0:issue961",
        execution_mode="INTERACTIVE",
        work_root_gate_evidence=gate,
        issued_at=datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc),
    )
    validated = validate_startup_evidence(
        evidence,
        invocation_identity="interactive:work0:issue961",
        now=datetime(2026, 9, 28, 16, 1, tzinfo=timezone.utc),
    )
    assert validated["work_root_gate"]["schema"] == "WHD_WORK_ROOT_GATE_EVIDENCE_V1"

    tampered = dict(evidence)
    tampered.pop("work_root_gate")
    with pytest.raises(ValueError, match="startup evidence missing fields"):
        validate_startup_evidence(
            tampered,
            invocation_identity="interactive:work0:issue961",
            now=datetime(2026, 9, 28, 16, 1, tzinfo=timezone.utc),
        )


def test_authority_map_declares_machine_owner_for_work_root_gate():
    text = (
        ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
    ).read_text(encoding="utf-8")
    assert "contract=work-root-gate-validation role=CURRENT path=tools/work_root_gate.py" in text
    assert "/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json" in text


def test_root_gate_rejects_duplicated_mutable_current_source_state():
    from tools.work_root_gate import READ_MODE_GOOGLE_DRIVE, validate_gate_payload

    payload = _canonical_payload()
    payload["current_synced_source"] = {
        "repository": "looaeedr/whd",
        "branch": "cleanup/2d-3d-sync",
        "sha": "a" * 40,
        "tree_sha": "b" * 40,
    }
    with pytest.raises(ValueError, match="must not duplicate mutable current source state"):
        validate_gate_payload(payload, read_mode=READ_MODE_GOOGLE_DRIVE)


def test_repository_mirror_tracks_stable_drive_gate_payload_hash():
    payload = _mirror_payload()
    assert (
        payload["canonical_source"]["canonical_payload_sha256"]
        == "6c5fb106798b593df723b8d4ff4ed99e1ab14f7ca4dc20c20ce6f8580a46ea4e"
    )


def test_interactive_work_path_is_always_below_drive_work_prefix():
    from tools.work_root_gate import (
        DEFAULT_WORK_PREFIX,
        build_interactive_work_path,
        validate_interactive_workspace_path,
    )

    path = build_interactive_work_path(issue=996, source_sha="a" * 40)
    assert path == f"{DEFAULT_WORK_PREFIX}/issue-996/{'a' * 12}"
    assert validate_interactive_workspace_path(path) == path

    with pytest.raises(ValueError, match="interactive workspace must be under"):
        validate_interactive_workspace_path("/mnt/data/whd")


def test_flow_v2_requires_workspace_first_execution_not_only_root_identity():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "WORKSPACE_EXECUTION_POLICY_V1" in text
    assert "/Google Drive/WHD/work/..." in text
    assert "build_interactive_work_path" in text
    assert "GitHub checkout" in text
    assert "manifest stale" in text

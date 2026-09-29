import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIRROR = ROOT / ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
SKILL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"

CANONICAL_GATE_PATH = "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
CANONICAL_ROOT = "/Google Drive/WHD"
ROOT_WORK_SURFACE = "/Google Drive/WHD/work"


def _canonical_payload():
    return {
        "schema": "WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1",
        "version": 1,
        "status": "CURRENT",
        "workspace": "WHD",
        "depends_on": {
            "schema": "WHD_WORK_ROOT_HARD_GATE_V1",
            "library_path": "/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json",
            "drive_file_id": "1eTePIN97fHAu-RPDtVRfqrAHP2zRTPmH",
        },
        "canonical_root": {
            "provider": "google_drive",
            "library_path": CANONICAL_ROOT,
            "drive_folder_id": "1z-P-VXPd1xjK-PS3Jj7RreT2BLEmDvf_",
        },
        "execution_policy": {
            "mode": "ROOT_LOCAL_FIRST",
            "treat_root_as_local_workspace": True,
            "root_work_surface": ROOT_WORK_SURFACE,
            "runtime_materialization_policy": "MAY_MATERIALIZE_CANONICAL_ROOT_LOCALLY_IF_IDENTITY_AND_SOURCE_PROVENANCE_ARE_PRESERVED",
            "source_bootstrap": "CURRENT_SOURCE_MANIFEST",
            "pre_git_write_git_access": ["READ", "FETCH", "COMPARE"],
            "forbidden_before_root_green": [
                "CREATE_OR_UPDATE_FILE",
                "CREATE_COMMIT",
                "UPDATE_REF",
                "PUSH",
                "MERGE",
            ],
            "required_before_git_write": [
                "ROOT_SOURCE_CURRENT",
                "ROOT_MUTATIONS_COMPLETE",
                "ROOT_TEST_CLASSIFIED",
                "ROOT_TESTS_GREEN",
                "ROOT_DIFF_FROZEN",
            ],
            "git_write_unlock_state": "GIT_WRITE_UNLOCKED",
            "push_payload_policy": "EXACT_TESTED_DIFF_ONLY",
            "on_target_drift": "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE",
            "remote_ci_role": "POST_PUSH_VERIFICATION_NOT_FIRST_TEST_SURFACE",
        },
        "test_classification": {
            "GOVERNANCE_OR_SKILL": [
                "FOCUSED_CONTRACT",
                "PREFLIGHT_REGISTRY",
                "AFFECTED_PROCESS_REGRESSION",
            ],
            "BUGFIX": ["REPRO_RED", "FOCUSED_REGRESSION", "AFFECTED_SUBSYSTEM"],
            "UPDATE_OR_FEATURE": [
                "NEW_CONTRACT",
                "FOCUSED_UNIT",
                "AFFECTED_INTEGRATION",
            ],
            "CORE_OR_HIGH_RISK": ["FULL_RELEVANT_REGRESSION"],
        },
        "fail_closed": {
            "on_root_not_current": "ROOT_LOCAL_SOURCE_NOT_CURRENT",
            "on_pre_git_write_before_green": "ROOT_LOCAL_GIT_WRITE_LOCKED",
            "on_target_drift": "ROOT_LOCAL_TARGET_DRIFT_REQUIRES_RETEST",
            "action": "STOP_BEFORE_GIT_WRITE",
        },
    }


def test_machine_gate_accepts_canonical_policy_and_starts_git_write_locked():
    from tools.root_local_first_gate import (
        READ_MODE_GOOGLE_DRIVE,
        build_root_local_first_entry_evidence,
        validate_entry_gate_payload,
    )

    payload = validate_entry_gate_payload(
        _canonical_payload(), read_mode=READ_MODE_GOOGLE_DRIVE
    )
    evidence = build_root_local_first_entry_evidence(
        gate_payload=payload,
        read_mode=READ_MODE_GOOGLE_DRIVE,
        execution_mode="INTERACTIVE",
    )
    assert evidence["schema"] == "WHD_ROOT_LOCAL_FIRST_ENTRY_EVIDENCE_V1"
    assert evidence["execution_policy"] == "ROOT_LOCAL_FIRST"
    assert evidence["git_write_state"] == "LOCKED_UNTIL_ROOT_TESTS_GREEN"
    assert evidence["root_work_surface"] == ROOT_WORK_SURFACE


def test_completion_evidence_unlocks_only_after_green_and_frozen_diff():
    from tools.root_local_first_gate import (
        build_root_local_completion_evidence,
        validate_root_local_completion_evidence,
    )

    with pytest.raises(ValueError, match="ROOT_TESTS_GREEN"):
        build_root_local_completion_evidence(
            source_sha="a" * 40,
            root_diff_sha256="b" * 64,
            changed_files=["AGENTS.md"],
            test_classification="GOVERNANCE_OR_SKILL",
            completed_states=[
                "ROOT_SOURCE_CURRENT",
                "ROOT_MUTATIONS_COMPLETE",
                "ROOT_TEST_CLASSIFIED",
                "ROOT_DIFF_FROZEN",
            ],
        )

    evidence = build_root_local_completion_evidence(
        source_sha="a" * 40,
        root_diff_sha256="b" * 64,
        changed_files=["AGENTS.md"],
        test_classification="GOVERNANCE_OR_SKILL",
        completed_states=[
            "ROOT_SOURCE_CURRENT",
            "ROOT_MUTATIONS_COMPLETE",
            "ROOT_TEST_CLASSIFIED",
            "ROOT_TESTS_GREEN",
            "ROOT_DIFF_FROZEN",
        ],
    )
    validated = validate_root_local_completion_evidence(evidence)
    assert validated["git_write_state"] == "GIT_WRITE_UNLOCKED"
    assert validated["push_payload_policy"] == "EXACT_TESTED_DIFF_ONLY"


def test_gate_rejects_git_write_permission_before_root_green():
    from tools.root_local_first_gate import READ_MODE_GOOGLE_DRIVE, validate_entry_gate_payload

    payload = _canonical_payload()
    payload["execution_policy"]["pre_git_write_git_access"].append("PUSH")
    with pytest.raises(ValueError, match="pre-Git-write"):
        validate_entry_gate_payload(payload, read_mode=READ_MODE_GOOGLE_DRIVE)


def test_gate_requires_target_drift_to_resync_and_retest():
    from tools.root_local_first_gate import READ_MODE_GOOGLE_DRIVE, validate_entry_gate_payload

    payload = _canonical_payload()
    payload["execution_policy"]["on_target_drift"] = "CONTINUE"
    with pytest.raises(ValueError, match="target drift"):
        validate_entry_gate_payload(payload, read_mode=READ_MODE_GOOGLE_DRIVE)


def test_repository_mirror_points_to_drive_canonical_gate_and_hash():
    from tools.root_local_first_gate import READ_MODE_GITHUB_MIRROR, validate_entry_gate_payload

    payload = json.loads(MIRROR.read_text(encoding="utf-8"))
    validated = validate_entry_gate_payload(payload, read_mode=READ_MODE_GITHUB_MIRROR)
    assert validated["role"] == "MIRROR"
    assert validated["mirror_policy"] == "POINTER_ONLY"
    assert validated["canonical_source"]["library_path"] == CANONICAL_GATE_PATH
    assert len(validated["canonical_source"]["canonical_payload_sha256"]) == 64


def test_agents_orders_root_local_entry_gate_before_phase6_and_forbids_early_git_write():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    root_identity = text.index("WORK_ROOT_BOOTSTRAP_HARD_GATE_V1")
    local_first = text.index("ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1")
    phase6 = text.index("# 0. 啟動硬閘門")
    assert root_identity < local_first < phase6
    assert "LOCKED_UNTIL_ROOT_TESTS_GREEN" in text
    assert "EXACT_TESTED_DIFF_ONLY" in text
    assert "RESYNC_ROOT_AND_RETEST_BEFORE_GIT_WRITE" in text


def test_root_local_first_skill_is_routable_and_release_durable():
    skill = SKILL.read_text(encoding="utf-8")
    assert "name: root-local-first" in skill
    assert "ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1" in skill
    assert "GitHub Actions" in skill
    assert "不是第一個測試面" in skill

    registry = json.loads((ROOT / ".agents/skills/skill_registry.json").read_text(encoding="utf-8"))
    route = next(item for item in registry["routes"] if item["id"] == "root-local-first")
    assert route["required_skills"] == ["root-local-first"]

    release = json.loads((ROOT / "release_required_artifacts.json").read_text(encoding="utf-8"))
    assert ".agents/skills/engineering/root-local-first/SKILL.md" in release["mandatory_update_files"]
    assert ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json" in release["mandatory_update_files"]
    assert "tools/root_local_first_gate.py" in release["mandatory_update_files"]


def test_phase6_release_branch_gate_defers_git_branch_until_root_green():
    text = (ROOT / ".agents/skills/engineering/phase6-release-packaging/SKILL.md").read_text(
        encoding="utf-8"
    )
    section = text.split("## Branch-first modification gate", 1)[1].split("\n## ", 1)[0]
    assert "ROOT_LOCAL_FIRST" in section
    assert "ROOT_TESTS_GREEN" in section
    assert "Git work branch" in section
    assert "before the first write" not in section.lower()


def test_canonical_payload_hash_is_stable_for_drive_upload():
    raw = json.dumps(_canonical_payload(), ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert len(digest) == 64

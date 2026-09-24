from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/execution_claim_guard.py"
DISPATCH_SKILL = ROOT / ".agents/skills/engineering/派工/SKILL.md"
WRITING_SKILL = ROOT / ".agents/skills/engineering/寫技能/SKILL.md"
AGENTS = ROOT / "AGENTS.md"
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/execution_claim_hard_gate_pitfall.md"
BASE_SHA = "e0a82f28f4ce3204c9fae56326f34f1a0964851f"
HEAD_SHA = "6c1189a1b991bad2c953a5fbc95f0acda903b5d5"
WORK_BRANCH = "fix/issue256-execution-claim-hard-gate-20260914"


def _load_guard():
    assert GUARD.is_file(), "#256 requires tools/execution_claim_guard.py"
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue256", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(**overrides):
    payload = {
        "issue": 256,
        "issue_url": "https://github.com/looaeedr/whd/issues/256",
        "worker": "chatgpt",
        "work_branch": WORK_BRANCH,
        "claimed_at": "2026-09-14T15:23:10Z",
        "base_sha": BASE_SHA,
        "head_sha": HEAD_SHA,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-14T22:29:31Z",
        "remote_qa": None,
        "next_action": "continue",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _write_claim(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_checkpoint(tmp_path: Path) -> Path:
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "issue": "256",
                "branch": WORK_BRANCH,
                "head_sha": HEAD_SHA,
                "state": "RUNNING",
                "next_action": "continue",
            }
        ),
        encoding="utf-8",
    )
    return path


def _assert_claim(guard, path: Path, **overrides):
    kwargs = {
        "issue": 256,
        "worker": "chatgpt",
        "branch": WORK_BRANCH,
        "action": "write",
        "expected_base_sha": BASE_SHA,
        "expected_head_sha": HEAD_SHA,
        "changed_files": ("tools/example.py",),
    }
    kwargs.update(overrides)
    return guard.assert_execution_claim(path, **kwargs)


def test_owner_on_claimed_branch_is_allowed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    claim = _assert_claim(guard, path)
    assert claim.worker == "chatgpt"
    assert claim.work_branch == WORK_BRANCH

def test_recovering_phase_is_active_for_same_owner(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim(phase="RECOVERING"))
    claim = _assert_claim(guard, path)
    assert claim.phase == "RECOVERING"



def test_missing_claim_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.ExecutionClaimError, match="not found|missing"):
        _assert_claim(guard, tmp_path / "missing.json")


def test_competing_worker_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    with pytest.raises(guard.ExecutionClaimError, match="owner|worker"):
        _assert_claim(guard, path, worker="other-worker")


def test_competing_branch_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    with pytest.raises(guard.ExecutionClaimError, match="branch"):
        _assert_claim(guard, path, branch="fix/competing-issue256-branch", action="qa-dispatch")


def test_explicit_delegated_qa_branch_is_allowed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim(delegated_branches=["qa/issue256-focused-20260914"]))
    claim = _assert_claim(
        guard,
        path,
        branch="qa/issue256-focused-20260914",
        action="qa-dispatch",
    )
    assert "qa/issue256-focused-20260914" in claim.delegated_branches


def test_issue_or_url_mismatch_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim(issue=255))
    with pytest.raises(guard.ExecutionClaimError, match="issue"):
        _assert_claim(guard, path, action="branch-create")


def test_malformed_claim_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, {"issue": 256, "worker": "chatgpt"})
    with pytest.raises(guard.ExecutionClaimError, match="missing|required|malformed"):
        _assert_claim(guard, path)


def test_duplicate_json_key_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    guard = _load_guard()
    path = tmp_path / "claim.json"
    payload = json.dumps(_claim())
    path.write_text(payload[:-1] + ', "worker": "other-worker"}', encoding="utf-8")
    with pytest.raises(guard.ExecutionClaimError, match="duplicate|ambiguous"):
        _assert_claim(guard, path)


def test_unknown_phase_is_rejected_as_ambiguous_state(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim(phase="MAYBE"))
    with pytest.raises(guard.ExecutionClaimError, match="phase|state|ambiguous"):
        _assert_claim(guard, path)


def test_stale_head_sha_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    stale = "a4a2264dc9bb39c363531fe9e94caa37c3f55c03"
    path = _write_claim(tmp_path, _claim(head_sha=stale))
    with pytest.raises(guard.ExecutionClaimError, match="head|stale"):
        _assert_claim(guard, path)


def test_base_sha_mismatch_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    wrong_base = "0" * 40
    path = _write_claim(tmp_path, _claim(base_sha=wrong_base))
    with pytest.raises(guard.ExecutionClaimError, match="base"):
        _assert_claim(guard, path)


def test_cli_write_requires_changed_file_identity_and_owner(tmp_path: Path) -> None:
    path = _write_claim(tmp_path, _claim())
    checkpoint = _write_checkpoint(tmp_path)
    common = [
        sys.executable,
        str(GUARD),
        "--claim",
        str(path),
        "--issue",
        "256",
        "--branch",
        WORK_BRANCH,
        "--action",
        "write",
        "--base-sha",
        BASE_SHA,
        "--head-sha",
        HEAD_SHA,
    ]

    missing_path = subprocess.run(
        [*common, "--worker", "chatgpt"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing_path.returncode == 2
    assert "EXECUTION_CLAIM_GUARD_ERROR" in missing_path.stdout
    assert "changed-file" in missing_path.stdout.lower()

    owner = subprocess.run(
        [
            *common,
            "--worker",
            "chatgpt",
            "--changed-file",
            "tools/example.py",
            "--checkpoint",
            str(checkpoint),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert owner.returncode == 0, owner.stdout + owner.stderr
    assert "EXECUTION_CLAIM_GUARD_GREEN" in owner.stdout

    intruder = subprocess.run(
        [*common, "--worker", "other-worker", "--changed-file", "tools/example.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert intruder.returncode == 2
    assert "EXECUTION_CLAIM_GUARD_ERROR" in intruder.stdout


def test_cli_skill_write_requires_canonical_writing_skill_preflight_evidence(tmp_path: Path) -> None:
    path = _write_claim(tmp_path, _claim())
    checkpoint = _write_checkpoint(tmp_path)
    skill_path = ".agents/skills/engineering/派工/SKILL.md"
    common = [
        sys.executable,
        str(GUARD),
        "--claim",
        str(path),
        "--issue",
        "256",
        "--worker",
        "chatgpt",
        "--branch",
        WORK_BRANCH,
        "--action",
        "write",
        "--base-sha",
        BASE_SHA,
        "--head-sha",
        HEAD_SHA,
        "--changed-file",
        skill_path,
    ]

    missing = subprocess.run(common, capture_output=True, text=True, check=False)
    assert missing.returncode == 2
    assert "EXECUTION_CLAIM_GUARD_ERROR" in missing.stdout
    assert "preflight" in missing.stdout.lower()
    assert "寫技能" in missing.stdout

    incomplete_evidence = tmp_path / "incomplete-preflight.md"
    incomplete_evidence.write_text(
        "\n".join(
            [
                "派工",
                "issue-closure-gate",
                "phase6-release-packaging",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md",
                "READ_REFERENCE: release_required_artifacts.json",
            ]
        ),
        encoding="utf-8",
    )
    incomplete = subprocess.run(
        [*common, "--preflight-evidence", str(incomplete_evidence)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert incomplete.returncode == 2
    assert "寫技能" in incomplete.stdout

    complete_evidence = tmp_path / "complete-preflight.md"
    complete_evidence.write_text(
        "\n".join(
            [
                "寫技能",
                "派工",
                "issue-closure-gate",
                "phase6-release-packaging",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
                "READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md",
                "READ_REFERENCE: release_required_artifacts.json",
            ]
        ),
        encoding="utf-8",
    )
    complete = subprocess.run(
        [
            *common,
            "--preflight-evidence",
            str(complete_evidence),
            "--checkpoint",
            str(checkpoint),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert complete.returncode == 0, complete.stdout + complete.stderr
    assert "EXECUTION_CLAIM_GUARD_GREEN" in complete.stdout


def test_dispatch_skill_requires_executable_prewrite_gate() -> None:
    text = DISPATCH_SKILL.read_text(encoding="utf-8")
    assert "EXECUTION_CLAIM_PREWRITE_HARD_GATE" in text
    assert "tools/execution_claim_guard.py" in text
    assert "branch-create" in text
    assert "qa-dispatch" in text
    assert "base SHA" in text
    assert "stale" in text


def test_ai_pitfall_records_claim_acquisition_is_not_enough() -> None:
    assert PITFALL.is_file()
    text = PITFALL.read_text(encoding="utf-8")
    assert "atomic claim" in text.lower()
    assert "pre-write" in text.lower() or "prewrite" in text.lower()
    assert "非 owner" in text or "non-owner" in text.lower()


def test_skill_prewrite_gate_is_visible_in_project_authorities() -> None:
    dispatch = DISPATCH_SKILL.read_text(encoding="utf-8")
    writing = WRITING_SKILL.read_text(encoding="utf-8")
    agents = AGENTS.read_text(encoding="utf-8")
    pitfall = PITFALL.read_text(encoding="utf-8")

    for text in (dispatch, writing, agents):
        assert "--changed-file" in text
        assert "--preflight-evidence" in text
        assert "寫技能" in text
        assert ".agents/skills/**/SKILL.md" in text

    assert "Skill write" in pitfall
    assert "changed-file" in pitfall
    assert "preflight evidence" in pitfall.lower()

from pathlib import Path

from tools.change_test_profile import build_test_profile
from tools.control_plane_regression import COMMAND, PYTEST_PATHS

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_governance_profile_and_github_workflow_use_same_exact_runner():
    profile = build_test_profile(
        task="governance fix",
        changed_files=["tools/control_transaction_request_ingress.py"],
        explicit_type="GOVERNANCE",
    )
    assert profile["exact_commands"] == [COMMAND]
    workflow = _text(".github/workflows/whd-control-plane-regression.yml")
    assert f"run: {COMMAND}" in workflow
    assert "python -m pytest -q \\" not in workflow
    assert "Compile control-plane owners" not in workflow


def test_canonical_runner_covers_identity_and_root_local_contracts():
    assert "tests/process/test_issue724_report_handler_identity_prefix.py" in PYTEST_PATHS
    assert "tests/process/test_root_local_first_entry_hard_gate.py" in PYTEST_PATHS
    assert "tests/process/test_issue1022_root_ci_parity.py" in PYTEST_PATHS


def test_retryable_control_transaction_conflict_is_not_workflow_failure():
    workflow = _text(".github/workflows/whd-control-transaction-v2-request.yml")
    for token in ('if [ "$rc" -eq 3 ]', "result.get('result') != 'CONFLICT'", "result.get('retryable') is not True", 'exit 0'):
        assert token in workflow
    assert "retryable Flow v2 conflict preserved in artifact" in workflow


def test_all_report_surfaces_require_slot_in_user_visible_identity():
    for rel in (
        ".agents/skills/engineering/工作槽/SKILL.md",
        ".agents/skills/engineering/排程模擬/SKILL.md",
        ".agents/skills/engineering/寫排程/SKILL.md",
    ):
        body = _text(rel)
        section = body.split("REPORT_HANDLER_IDENTITY_PREFIX_V1", 1)[1]
        assert "slot=<worker.slot.N|NONE|UNBOUND>" in section
        assert "owner=<exact owner|NONE>" in section
        assert "第一行" in section
        assert "不建立 execution authority" in section


def test_control_plane_workflow_triggers_on_work_slot_identity_regression():
    workflow = _text(".github/workflows/whd-control-plane-regression.yml")
    assert ".agents/skills/engineering/工作槽/SKILL.md" in workflow
    assert "tests/process/test_issue724_report_handler_identity_prefix.py" in workflow


def test_root_gate_requires_machine_test_receipt():
    gate = _text("tools/root_local_first_gate.py")
    contract = _text(".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json")
    skill = _text(".agents/skills/engineering/root-local-first/SKILL.md")
    for token in ("WHD_TEST_EXECUTION_RECEIPT_V1", "manifest_digest", "exact_commands"):
        assert token in gate
        assert token in contract
    assert "裸 `tests_green=true`" in skill


def test_connector_rejection_requires_fresh_reclassification_before_permanent_blocker():
    skill = _text(".agents/skills/engineering/root-local-first/SKILL.md")
    pitfall = _text("個人AI檔案庫/踩坑庫/git_connector_target_write_pitfall.md")
    for text in (skill, pitfall):
        assert "RETRYABLE_UNCLASSIFIED" in text
        assert "create_branch" in text
        assert "update_ref" in text
        assert "permanent" in text

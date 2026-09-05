from pathlib import Path


def _skill_text() -> str:
    path = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
    return path.read_text(encoding="utf-8")


def test_dispatching_skill_requires_process_group_cleanup_and_timeout_classification():
    text = _skill_text()
    assert "process group" in text.lower()
    assert "killpg" in text.lower() or "整個 process group" in text
    assert "complete_teardown_timeout" in text
    assert "incomplete_timeout" in text
    assert "不得重跑已完成" in text or "禁止為了方便重跑已通過" in text


def test_dispatching_skill_requires_journal_resume_and_collection_identity_guard():
    text = _skill_text()
    assert "journal" in text.lower()
    assert "collection SHA" in text or "collection sha" in text.lower()
    assert "拒絕沿用舊 journal" in text
    assert "只跑 pending" in text


def test_dispatching_skill_distinguishes_pytest_summary_from_wrapper_timeout():
    text = _skill_text()
    assert "pytest summary" in text
    assert "wrapper" in text
    assert "TIMEOUT" in text
    assert "真 RED" in text


def test_dispatching_timeout_skill_and_contract_are_mandatory_release_artifacts():
    import json

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "release_required_artifacts.json").read_text(encoding="utf-8"))
    mandatory = set(manifest.get("mandatory_update_files") or ())
    assert ".agents/skills/engineering/派工/SKILL.md" in mandatory
    assert "tests/test_dispatching_skill_timeout_contract.py" in mandatory


def test_dispatching_skill_requires_xvfb_parent_death_guard_for_outer_hard_kill():
    text = _skill_text()
    assert "SIGKILL" in text
    assert "parent-death" in text.lower() or "PDEATHSIG" in text


def test_dispatching_skill_requires_full_pytest_summary_before_complete_teardown_timeout():
    text = _skill_text()
    assert "完整 PASS summary" in text
    assert "只看到點號" in text or "只有點號" in text
    assert "不得標記 complete_teardown_timeout" in text


def test_dispatching_skill_requires_checkpoint_provenance_guard_before_resume():
    text = _skill_text()
    for required in (
        "checkpoint provenance",
        "execution tree fingerprint",
        "最近已驗收 checkpoint",
        "混合狀態",
    ):
        assert required in text


def test_dispatching_skill_requires_30_second_progress_reporting_without_stopping_work():
    text = _skill_text()
    for required in (
        "每 30 秒",
        "目前工單",
        "最新測試",
        "不得中斷",
    ):
        assert required in text

    implement_path = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "engineering" / "執行開發任務" / "SKILL.md"
    implement_text = implement_path.read_text(encoding="utf-8")
    for required in (
        "每 30 秒",
        "目前工單",
        "最新測試",
        "不得中斷",
    ):
        assert required in implement_text

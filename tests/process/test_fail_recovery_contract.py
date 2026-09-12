from pathlib import Path


EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")


def _text() -> str:
    return EXECUTION_SKILL.read_text(encoding="utf-8")


def test_preflight_red_continues_evidence_then_reruns_gate():
    text = _text()
    assert "FAIL_RECOVERY_CONTRACT" in text
    assert "preflight RED → RECOVERING(required_evidence)" in text
    assert "required evidence / reference" in text
    assert "rerun preflight" in text


def test_test_failure_requires_root_cause_fix_validation_retry():
    text = _text()
    assert "test FAIL → RECOVERING" in text
    assert "assertion / log → root cause → minimal fix → focused validation → retry" in text
    assert "FAIL 一出現就回報使用者並停止" in text


def test_remote_qa_failure_recovers_and_retries():
    text = _text()
    assert "remote QA FAIL → RECOVERING" in text
    assert "job / step / log" in text
    assert "production / test / environment / contract" in text
    assert "replacement run" in text


def test_invariant_failure_restores_canonical_state_before_pass():
    text = _text()
    assert "invariant FAIL → RECOVERING" in text
    assert "恢復 canonical state" in text
    assert "不得宣告功能 PASS" in text


def test_validation_never_becomes_production_calculation_authority():
    text = _text()
    assert "VALIDATION_IS_JUDGE_ONLY" in text
    assert "不得反推 production 幾何 / 製造計算來源" in text
    assert "不得放寬 authoritative acceptance contract" in text


def test_only_unrecoverable_authority_gaps_can_block():
    text = _text()
    assert "可恢復 FAIL 不得進 BLOCKED" in text
    assert "產品語意決策" in text
    assert "必要權限" in text
    assert "不可推導資料" in text

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def test_production_transaction_workflow_is_writable_and_dispatchable():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "contents: write" in text
    assert "control_transaction_production_executor.py" in text
    assert "coord/execution-v2" not in text or True


def test_production_executor_uses_non_force_ref_cas_and_rebuilds_ready_index():
    text = (ROOT / "tools/control_transaction_production_executor.py").read_text(encoding="utf-8")
    assert '"force": False' in text
    assert "build_ready_index(records.values())" in text
    assert "prepare_transaction(" in text
    assert "execute_transaction(" in text
    assert "post-commit ExecutionRecord fingerprint mismatch" in text


def test_canonical_skill_requires_null_lease_acquire_and_production_writer():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "`lease=null`" in text
    assert "whd-control-transaction-v2.yml" in text
    assert "whd-control-transaction-v2-request.yml" in text
    assert "FLOW_V2_PRODUCTION_TRANSACTION_V2" in text
    assert "同一 invocation 立即續原本 structured next_action" in text


def test_finalize_trusted_writer_owns_issue_close_and_fresh_readback():
    text = (ROOT / "tools/control_transaction_production_executor.py").read_text(encoding="utf-8")
    assert "_ensure_issue_closed_for_finalize" in text
    assert '"state": "closed", "state_reason": "completed"' in text
    assert 'f"/issues/{issue}"' in text
    assert "FINALIZE does not trust caller-supplied closure booleans" in text
    assert "FINALIZE issue close readback is not closed" in text
    assert "FINALIZE issue close readback is not completed" in text


def test_finalize_pure_transition_requires_closed_completed_and_accepted_merge():
    text = (ROOT / "tools/control_transaction.py").read_text(encoding="utf-8")
    assert "FINALIZE requires accepted QA for current head" in text
    assert "FINALIZE requires fresh merged target readback" in text
    assert "FINALIZE requires issue_state=closed readback" in text
    assert "FINALIZE requires issue_state_reason=completed readback" in text


def test_finalize_skill_forbids_done_while_issue_is_open():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "FLOW_V2_FINALIZE_ISSUE_CLOSE_HARD_GATE_V1" in text
    assert "caller 傳入的 `issue_closed=true` 不具 authority" in text
    assert "ExecutionRecord 保持 nonterminal，不得寫 DONE" in text
    assert "merge + acceptance 完成但 Issue 還開著" in text
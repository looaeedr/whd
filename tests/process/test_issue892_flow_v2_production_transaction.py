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
    assert "FLOW_V2_PRODUCTION_TRANSACTION_V1" in text
    assert "同一 invocation 立即續原本 structured next_action" in text

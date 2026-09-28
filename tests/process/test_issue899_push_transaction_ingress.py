from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_push_request_workflow_is_scheduler_compatible():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2-request.yml").read_text(encoding="utf-8")
    assert "coord/transaction-requests-a" in text
    assert "coord/transaction-requests-b" in text
    assert ".dispatch/transaction-request.json" in text
    assert "contents: write" in text
    assert "issues: write" in text
    assert "control_transaction_request_ingress.py" in text


def test_request_ingress_binds_coord_head_and_generation():
    text = (ROOT / "tools/control_transaction_request_ingress.py").read_text(encoding="utf-8")
    assert "WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1" in text
    assert "expected_coord_head" in text
    assert "expected_generation" in text
    assert "coord head drift" in text
    assert "generation drift" in text
    assert "execute_one(" in text


def test_manual_production_workflow_can_finalize_issues():
    text = (ROOT / ".github/workflows/whd-control-transaction-v2.yml").read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "issues: write" in text


def test_canonical_skill_uses_push_request_not_scheduler_workflow_dispatch():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "FLOW_V2_PRODUCTION_TRANSACTION_V2" in text
    assert "coord/transaction-requests-a" in text
    assert "coord/transaction-requests-b" in text
    assert "expected_coord_head" in text
    assert "expected_generation" in text
    assert "scheduler不得依賴 connector 未提供的 workflow_dispatch" in text


def test_seed_request_is_noop_without_execution_state(monkeypatch):
    import tools.control_transaction_request_ingress as ingress

    def _unexpected_load(*args, **kwargs):
        raise AssertionError("SEED must not read or mutate coord/execution-v2")

    monkeypatch.setattr(ingress, "_load_state", _unexpected_load)
    request = {
        "schema": ingress.REQUEST_SCHEMA,
        "request_id": "seed-test",
        "issue": 0,
        "kind": "SEED",
        "lane_id": "scheduler.seed-test",
        "invocation_identity": "bootstrap-seed",
        "expected_coord_head": "",
        "expected_generation": 0,
        "effect": {},
    }
    result = ingress.execute_request(
        request=request,
        repo="looaeedr/whd",
        token="unused-for-seed",
        coord_branch="coord/execution-v2",
    )
    assert result["result"] == "APPLIED"
    assert result["reason"] == "SEED_NOOP"
    assert result["transaction"] == {"status": "RECONCILED", "kind": "SEED"}

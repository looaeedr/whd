from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents" / "contracts" / "WHD_DM8_RUNTIME_FACADE_DECISION_V1.json"
RATIONALE = ROOT / "docs" / "superpowers" / "checkpoints" / "issue1379-o2-runtime-facade-design.md"
SEMANTIC_OWNER = ROOT / "tools" / "control_transaction.py"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_issue1379_selects_plan_effect_adapter_without_second_semantic_owner():
    payload = _contract()

    assert payload["schema"] == "WHD_DM8_RUNTIME_FACADE_DECISION_V1"
    assert payload["status"] == "CURRENT_DESIGN_DECISION"
    assert payload["decision"] == "PLAN_EFFECT_ADAPTER"
    assert payload["semantic_owner"] == "tools/control_transaction.py"
    assert payload["public_semantic_validation_owner"] == "tools/control_transaction.py"
    assert payload["implementation_target"] == "tools/control_transaction_runtime.py"

    owner_source = SEMANTIC_OWNER.read_text(encoding="utf-8")
    assert "Pure WHD Flow v2 atomic control-transaction semantics." in owner_source
    assert "It does not call GitHub, Drive, Actions, or any other side-effecting transport." in owner_source


def test_issue1379_external_mutation_scope_is_exact_and_excludes_repo_content_writers():
    payload = _contract()

    assert set(payload["pre_transition_external_mutation_paths"]) == {
        "MERGE",
        "SYNC_TARGET",
        "FINALIZE",
        "RELEASE_PATHS",
    }
    assert payload["explicitly_excluded_from_runtime_facade_external_mutation_scope"] == [
        "START_BRANCH",
        "APPLY_COMMIT",
    ]
    assert set(payload["path_classes"]) == {
        "READBACK_ONLY",
        "PRE_TRANSITION_EXTERNAL_MUTATION",
    }


def test_issue1379_readback_only_fence_is_pre_provider_mutation():
    payload = _contract()
    fence = payload["readback_only_fence"]

    assert fence["error"] == "RuntimeMutationFenceError"
    assert "must raise before any provider mutation branch" in fence["rule"]
    assert "ALREADY_MERGED" in fence["merge"]
    assert "PUT" in fence["merge"]
    assert "POST /merges" in fence["sync_target"]
    assert "PATCH" in fence["finalize"]
    assert "DELETE" in fence["release_paths"]


def test_issue1379_retry_contract_reuses_effect_only_for_unrelated_coord_cas():
    retry = _contract()["retry_contract"]

    assert retry["provider_effect_resolution"] == "exactly once per immutable plan attempt"
    assert "do not replay provider mutation" in retry["unrelated_coord_cas"]
    assert "fresh semantic rebuild" in retry["same_issue_drift"]
    assert "facade does not own coord CAS retry state" in retry["responsibility"]


def test_issue1379_design_it_twice_records_all_three_options_and_rejections():
    text = RATIONALE.read_text(encoding="utf-8")

    assert "Option A — command-style single runtime entry" in text
    assert "Option B — typed runtime object" in text
    assert "Option C — pure plan + effect adapter" in text
    assert "**Selected.**" in text
    assert "PLAN_EFFECT_ADAPTER" in text
    assert "There is no second semantic owner and no second state machine." in text

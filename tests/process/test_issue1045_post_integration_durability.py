import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json"


def _record(*, state="DONE", lease=None, reservation="RELEASED", next_action=None):
    return {
        "issue": 1045,
        "generation": 3,
        "state": state,
        "target_sha": "a" * 40,
        "lease": lease,
        "next_action": next_action,
        "mutation_scope": {"reservation_state": reservation},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def _root_receipt():
    from tools.post_integration_durability import build_root_sync_receipt
    return build_root_sync_receipt(
        accepted_sha="a" * 40,
        accepted_tree_sha="b" * 40,
        root_head_sha="a" * 40,
        root_tree_sha="b" * 40,
    )


def _lane_receipt(state="EMPTY"):
    from tools.post_integration_durability import build_lane_delivery_receipt
    return build_lane_delivery_receipt(
        lane="docs", issue=1045, generation=7, merged_sha="a" * 40,
        manifest_digest="c" * 64, delivered_paths=["AGENTS.md"],
        lane_state_after=state,
    )


def test_v2_contract_keeps_execution_authority_in_flow_v2_and_retires_v1():
    from tools.post_integration_durability import validate_contract
    payload = validate_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))
    retired_v1 = ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json"
    assert payload["execution_state_owner"] == "WHD_EXECUTION_RECORD_V2"
    assert payload["required_order"][-1] == "DURABLE_CLEANUP_COMPLETE"
    assert payload["canonical_root"] == "/Google Drive/WHD"
    assert payload["root_sync_transport"] == "tools/post_integration_durability.py::sync_canonical_root_to_accepted_head"
    assert not retired_v1.exists()


def test_root_sync_receipt_requires_exact_accepted_head_and_tree():
    from tools.post_integration_durability import build_root_sync_receipt
    assert _root_receipt()["status"] == "VERIFIED"
    with pytest.raises(ValueError, match="HEAD"):
        build_root_sync_receipt(
            accepted_sha="a" * 40, accepted_tree_sha="b" * 40,
            root_head_sha="d" * 40, root_tree_sha="b" * 40,
        )
    with pytest.raises(ValueError, match="tree"):
        build_root_sync_receipt(
            accepted_sha="a" * 40, accepted_tree_sha="b" * 40,
            root_head_sha="a" * 40, root_tree_sha="d" * 40,
        )


def test_lane_delivery_receipt_requires_finalized_shared_zero_state():
    from tools.post_integration_durability import build_lane_delivery_receipt
    assert _lane_receipt("EMPTY")["lane_state_after"] == "EMPTY"
    assert _lane_receipt("ROLLED_FORWARD")["lane_state_after"] == "ROLLED_FORWARD"
    with pytest.raises(ValueError, match="EMPTY or ROLLED_FORWARD"):
        build_lane_delivery_receipt(
            lane="docs", issue=1045, generation=7, merged_sha="a" * 40,
            manifest_digest="c" * 64, delivered_paths=["AGENTS.md"], lane_state_after="PENDING",
        )


def test_cleanup_tail_requires_done_root_sync_then_lane_finalization():
    from tools.post_integration_durability import classify_post_integration_durability
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=None, lane_delivery_receipt=None,
    )
    assert result["next_action"] == "SYNC_CANONICAL_ROOT_TO_ACCEPTED_HEAD"
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=_root_receipt(), lane_delivery_receipt=None,
    )
    assert result["next_action"] == "FINALIZE_DELIVERED_LANE_ZERO"
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=_root_receipt(), lane_delivery_receipt=_lane_receipt(),
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"


def test_nonterminal_or_live_record_never_completes_physical_cycle():
    from tools.post_integration_durability import classify_post_integration_durability
    for record in (
        _record(state="ACTIVE"),
        _record(lease={"owner": "worker.slot.0"}),
        _record(reservation="ACTIVE"),
        _record(next_action={"kind": "MERGE"}),
    ):
        result = classify_post_integration_durability(
            execution_record=record, root_sync_receipt=_root_receipt(), lane_delivery_receipt=_lane_receipt(),
        )
        assert result["state"] == "NOT_TERMINAL"
        assert result["next_action"] == "WAIT_EXECUTION_DONE"


def test_legacy_snapshot_and_work_active_are_not_current_authorities():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert set(contract["forbidden_current_authorities"]) == {
        "SOURCE_SNAPSHOT", "CURRENT_SOURCE_MANIFEST", "WORK_ACTIVE_ARCHIVE"
    }
    tool = (ROOT / "tools/post_integration_durability.py").read_text(encoding="utf-8")
    assert "/work/active" not in tool
    assert "/source/snapshots" not in tool
    assert "Current Source Manifest" not in tool


def test_root_local_skill_and_authority_map_point_to_v2_cleanup():
    skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(encoding="utf-8")
    authority = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    assert "POST_INTEGRATION_DURABILITY_HARD_GATE_V2" in skill
    assert "SYNC_CANONICAL_ROOT_TO_ACCEPTED_HEAD" in skill
    assert "FINALIZE_DELIVERED_LANE_ZERO" in skill
    assert "contract=post-integration-durability-v2 role=CURRENT path=tools/post_integration_durability.py" in authority

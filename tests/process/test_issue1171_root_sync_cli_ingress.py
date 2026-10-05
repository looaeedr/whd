import json
from pathlib import Path

from tools import post_integration_durability as durability

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json"


def _record():
    return {
        "issue": 1171,
        "generation": 1,
        "state": "DONE",
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def test_cli_ingress_is_retired_and_non_authoritative(tmp_path, capsys):
    record = tmp_path / "record.json"
    record.write_text(json.dumps(_record()), encoding="utf-8")
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
    ])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "RETIRED"
    assert payload["authority"] is False
    assert "CANONICAL_DRIVE_ROOT_SYNC_RETIRED" in payload["reason"]


def test_cli_retired_result_can_be_persisted(tmp_path):
    record = tmp_path / "record.json"
    out = tmp_path / "result.json"
    record.write_text(json.dumps(_record()), encoding="utf-8")
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
        "--output", str(out),
    ])
    assert rc == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "RETIRED"
    assert payload["authority"] is False


def test_contract_marks_old_root_sync_ingress_retired():
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["root_sync_transport"] == "RETIRED_USE_MIRROR_PIPELINE"
    assert payload["root_sync_ingress"]["status"] == "RETIRED"
    assert payload["root_sync_ingress"]["owner"] is None
    assert payload["root_sync_ingress"]["terminal_gate"] is False
    assert payload["drive_role"] == "MIRROR_BACKUP_ONLY"

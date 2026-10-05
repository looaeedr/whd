import json

from tools import post_integration_durability as durability


def _done_record():
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


def test_cli_ingress_is_retired_and_fails_closed(tmp_path, capsys):
    record = tmp_path / "record.json"
    record.write_text(json.dumps(_done_record()), encoding="utf-8")
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
    ])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FAILED"
    assert "CANONICAL_DRIVE_ROOT_SYNC_RETIRED" in payload["reason"]


def test_cli_ingress_persists_retired_failure_receipt(tmp_path, capsys):
    record = tmp_path / "record.json"
    output = tmp_path / "result.json"
    record.write_text(json.dumps(_done_record()), encoding="utf-8")
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
        "--output", str(output),
    ])
    assert rc == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "WHD_CANONICAL_ROOT_SYNC_RESULT_V1"
    assert payload["status"] == "FAILED"
    assert "CANONICAL_DRIVE_ROOT_SYNC_RETIRED" in payload["reason"]

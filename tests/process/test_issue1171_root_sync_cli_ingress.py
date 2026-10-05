import json

import tools.post_integration_durability as durability


def _record(tmp_path):
    payload = {
        "issue": 1171,
        "generation": 2,
        "state": "DONE",
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }
    path = tmp_path / "record.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_ingress_is_retired_and_never_emits_verified_root_sync(tmp_path, capsys):
    record = _record(tmp_path)
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["schema"] == "WHD_CANONICAL_ROOT_SYNC_RESULT_V1"
    assert payload["status"] == "FAILED"
    assert "CANONICAL_DRIVE_ROOT_SYNC_RETIRED_USE_MIRROR_PIPELINE" in payload["reason"]


def test_cli_failure_can_be_persisted_without_becoming_authority(tmp_path, capsys):
    record = _record(tmp_path)
    output = tmp_path / "result.json"
    rc = durability.main([
        "--execution-record", str(record),
        "--accepted-tree-sha", "b" * 40,
        "--output", str(output),
    ])
    capsys.readouterr()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert payload["status"] == "FAILED"
    assert "VERIFIED" not in payload.values()


def test_contract_marks_root_sync_as_optional_mirror_maintenance():
    payload = json.loads(
        (
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json"
        ).read_text(encoding="utf-8")
    )
    validated = durability.validate_contract(payload)
    assert validated["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert validated["root_sync_policy"]["mode"] == "OPTIONAL_MIRROR_MAINTENANCE"
    assert validated["root_sync_policy"]["terminal_gate"] is False

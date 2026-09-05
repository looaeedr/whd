# -*- coding: utf-8 -*-
import json
from pathlib import Path

from ae_engine.certified_relief_registry import (
    load_external_relief_rule_records,
    registered_certified_relief_rules,
)


def test_external_registry_json_and_schema_exist_and_load():
    root = Path(__file__).resolve().parents[1] / "基準檔" / "截角資料庫"
    data_path = root / "certified_relief_rules.json"
    schema_path = root / "certified_relief_rules.schema.json"
    assert data_path.is_file()
    assert schema_path.is_file()
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    records = load_external_relief_rule_records(data_path)
    assert records


def test_every_active_endcap_rule_has_v2_signature_formula_and_revision():
    records = {r["rule_id"]: r for r in load_external_relief_rule_records()}
    runtime_ids = {r.rule_id for r in registered_certified_relief_rules()}
    assert runtime_ids <= records.keys()
    for rule_id in runtime_ids:
        item = records[rule_id]
        assert item["revision"] >= 1
        assert item["joint_signature"]
        assert item["topology_levels"] in (1, 2)
        assert isinstance(item["formula"], dict) and item["formula"]
        assert item["trust_level"] in {"CERTIFIED", "CERTIFIED_FROM_3D"}

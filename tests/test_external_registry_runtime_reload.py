# -*- coding: utf-8 -*-
import json

from ae_engine import certified_relief_registry as registry


def test_runtime_rule_builder_loads_unknown_external_rule_with_data_evaluator(tmp_path):
    payload = {
        "schema_version": 2,
        "rules": [{
            "rule_id":"CUSTOM_WRAP_RULE", "revision":1, "trust_level":"CERTIFIED", "active":True,
            "cabinet_family":"ANY", "part_role":"HEAD_OR_TAIL", "joint_face":"TOP_LEFT",
            "assembly_intent":"INSERT_OVERLAY",
            "joint_signature":[
                {"relation":"INSERT_OVERLAY","subject_role":"HEAD_OR_TAIL","target_role":"BOX_SIDE","subject_region":"TOP_LEFT","target_region":"MATING_ZONE"},
                {"relation":"WRAP","subject_role":"HEAD_OR_TAIL","target_role":"REAR_PANEL","subject_region":"TOP_LEFT","target_region":"WRAP_ZONE"}
            ],
            "topology_levels":2,
            "preconditions":["ytop1_present","x_folded"],
            "formula":{"primary_u":"side_fold + FW","primary_v":"ytop1 + FW - T","secondary_u":"side_fold + T","secondary_depth":"2*T"},
            "source":"verified custom"
        }]
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rules = registry.build_runtime_relief_rules_from_external(path)
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "CUSTOM_WRAP_RULE"
    assert callable(rule.evaluator)
    assert [row["relation"] for row in rule.joint_signature] == ["INSERT_OVERLAY", "WRAP"]

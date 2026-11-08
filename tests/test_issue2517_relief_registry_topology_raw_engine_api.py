# -*- coding: utf-8 -*-
"""#2517 Registry topology is one Engine-owned stage count, never GUI int(float)."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import certified_relief_registry as owner
from gui_modules.application import fold_designer_composition_registry_edges as gui
from tests.test_relief_registry_candidate_backend import _candidate


class Field:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _gui_state(value, *, intent="INSERT_OVERLAY"):
    source = {
        "relief_registry_intent_var": intent,
        "relief_registry_topology_var": value,
        "relief_registry_target_role_var": "BOX_SIDE",
        "relief_registry_joint_face_var": "TOP_LEFT",
        "relief_registry_part_role_var": "HEAD_OR_TAIL",
        "relief_registry_extra_joint_var": "WRAP",
        "relief_registry_extra_target_role_var": "REAR_PANEL",
        "relief_registry_primary_u_var": "FW + T",
        "relief_registry_primary_v_var": "side_fold",
        "relief_registry_secondary_u_var": "0.5*T",
        "relief_registry_secondary_depth_var": "2*T",
        "relief_registry_preconditions_var": "ytop1_present",
        "relief_registry_rule_id_var": "RAW_TOPOLOGY_SAMPLE",
        "relief_registry_family_var": "ANY",
        "relief_registry_symmetry_var": "MIRROR_IF_GEOMETRY_SYMMETRIC",
        "relief_registry_source_var": "confirmed operator drawing",
    }
    app = SimpleNamespace(**{key: Field(v) for key, v in source.items()})
    return SimpleNamespace(app=app), source


@pytest.mark.parametrize(("raw", "expected"), [
    (1, 1), ("1", 1), (1.0, 1), ("1.0", 1),
    (2, 2), ("2", 2), (2.0, 2), ("2.00", 2), ("2e0", 2),
])
def test_public_engine_topology_normalizes_only_exact_physical_stage_count(raw, expected):
    assert api.normalize_operator_relief_topology_levels(raw) == expected
    assert ae_engine.normalize_operator_relief_topology_levels is api.normalize_operator_relief_topology_levels
    assert owner.normalize_operator_relief_topology_levels is api.normalize_operator_relief_topology_levels
    original = _candidate()
    original["topology_levels"] = raw if expected == 2 else 2
    before = deepcopy(original)
    validated = api.validate_operator_relief_registry_rule_record(original)
    assert validated["topology_levels"] == 2
    assert original == before
    assert json.loads(json.dumps(validated))["topology_levels"] == 2


@pytest.mark.parametrize("bad", [
    True, False, None, 0, -1, 3, 1.9, 2.1, "1.9", "2.1",
    "NaN", "inf", float("nan"), float("inf"), "bad", [],
])
def test_public_engine_candidate_and_evaluator_reject_raw_invalid_stages_without_writes(bad, tmp_path):
    original = _candidate()
    original["topology_levels"] = bad
    before = deepcopy(original)
    file = tmp_path / "candidates.json"
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        api.normalize_operator_relief_topology_levels(bad)
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        api.validate_operator_relief_registry_rule_record(original)
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        api.evaluate_operator_relief_registry_formula_record(original, {"T": 2.0, "FW": 25.0})
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        api.save_operator_relief_registry_candidate(original, path=file)
    assert not file.exists()
    assert original == before


@pytest.mark.parametrize("bad", [True, False, 0, -1, "1.9", "nan", "abc", 3])
def test_gui_raw_topology_is_not_truncated_to_registered_physical_stage(bad):
    host, raw = _gui_state(bad)
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        gui.registry_collect_rule_form(host)
    assert host.app.relief_registry_topology_var.get() == bad
    assert "int(" not in inspect.getsource(gui.registry_collect_rule_form).split("main_target =", 1)[0]


@pytest.mark.parametrize("raw", ["2", 2, "2.0", 2.0])
def test_gui_valid_topology_uses_exact_public_engine_stage_and_secondary_fields(raw):
    host, source = _gui_state(raw)
    record = gui.registry_collect_rule_form(host)
    assert record["topology_levels"] == api.normalize_operator_relief_topology_levels(raw) == 2
    assert record["formula"]["secondary_depth"] == "2*T"
    assert record["formula"]["secondary_u"] == "0.5*T"
    assert api.validate_operator_relief_registry_rule_record(record)["topology_levels"] == 2
    assert source["relief_registry_topology_var"] == raw


def test_gui_missing_topology_keeps_original_intent_default_but_explicit_zero_rejects():
    for missing in ("", None):
        host, _ = _gui_state(missing)
        assert gui.registry_collect_rule_form(host)["topology_levels"] == 2
    one_stage, _ = _gui_state("", intent="OVERLAY")
    record = gui.registry_collect_rule_form(one_stage)
    assert record["topology_levels"] == 1
    assert "secondary_u" not in record["formula"]
    zero, _ = _gui_state(0)
    with pytest.raises(owner.CertifiedReliefRegistryError, match="topology_levels"):
        gui.registry_collect_rule_form(zero)

# -*- coding: utf-8 -*-
"""#2517: Registry candidate writes and certification use only public Engine ports."""
from inspect import getsource
import json

import ae_engine
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import certified_relief_registry as owner
from gui_modules.application import fold_designer_composition_registry_edges as gui
from tests.test_relief_registry_candidate_backend import _candidate


PORTS = {
    "validate_operator_relief_registry_rule_record": owner._validate_editable_rule_record,
    "evaluate_operator_relief_registry_formula_record": owner.evaluate_relief_formula_record,
    "save_operator_relief_registry_candidate": owner.save_relief_rule_candidate,
    "promote_operator_relief_registry_candidate": owner.promote_relief_rule_candidate,
}


def test_public_api_exports_identical_canonical_registry_owner():
    for name, backend in PORTS.items():
        assert getattr(api, name) is backend
        assert getattr(ae_engine, name) is backend
        assert name in ae_engine.__all__


def test_public_formula_validation_and_evaluation_are_original_engine_results():
    record = _candidate()
    validated = api.validate_operator_relief_registry_rule_record(record)
    variables = {
        "T": 2.0, "FW": 25.0, "side_fold": 15.0,
        "ytop1": 16.0, "mating_width": 50.0,
    }
    assert validated == owner._validate_editable_rule_record(record)
    assert api.evaluate_operator_relief_registry_formula_record(
        validated, variables,
    ) == owner.evaluate_relief_formula_record(validated, variables)
    assert record == _candidate()


def test_invalid_original_formula_cannot_save_candidate(tmp_path):
    invalid = _candidate()
    invalid["formula"]["primary_u"] = "__import__('os').system('false')"
    before = json.dumps(invalid, sort_keys=True)
    path = tmp_path / "candidates.json"
    with pytest.raises(owner.CertifiedReliefRegistryError):
        api.save_operator_relief_registry_candidate(invalid, path=path)
    assert not path.exists()
    assert json.dumps(invalid, sort_keys=True) == before


def test_candidate_and_promotion_api_keep_real_registry_evidence_gate(tmp_path):
    candidates = tmp_path / "candidates.json"
    certified = tmp_path / "certified.json"
    before = _candidate()
    saved = api.save_operator_relief_registry_candidate(before, path=candidates)
    assert before == _candidate()
    assert saved["status"] == "CANDIDATE"
    assert saved["mutates_registry"] is False
    assert not certified.exists()
    candidate_bytes = candidates.read_bytes()
    invalid = {"matrix_passed": True, "cases": 9, "zero_penetration": True}
    with pytest.raises(owner.CertifiedReliefRegistryError, match="candidate-specific"):
        api.promote_operator_relief_registry_candidate(
            saved["candidate_id"], regression_evidence=invalid,
            candidates_path=candidates, certified_path=certified,
        )
    assert candidates.read_bytes() == candidate_bytes
    assert not certified.exists()

    evidence = dict(
        invalid, candidate_specific=True, candidate_id=saved["candidate_id"],
    )
    promoted = api.promote_operator_relief_registry_candidate(
        saved["candidate_id"], regression_evidence=evidence,
        candidates_path=candidates, certified_path=certified,
    )
    assert promoted["trust_level"] == "CERTIFIED"
    assert promoted["revision"] == 1
    assert owner.load_relief_rule_candidates(candidates)[0]["status"] == "PROMOTED"
    assert owner.load_external_relief_rule_records(certified)[0]["rule_id"] == before["rule_id"]


def test_actual_gui_events_delegate_all_four_registry_callbacks():
    expected = {
        gui.registry_validate_formula_form: (
            "validate_operator_relief_registry_rule_record",
            "evaluate_operator_relief_registry_formula_record",
        ),
        gui.registry_run_formula_matrix: (
            "validate_operator_relief_registry_rule_record",
            "evaluate_operator_relief_registry_formula_record",
        ),
        gui.registry_save_candidate_form: ("save_operator_relief_registry_candidate",),
        gui.registry_promote_form: ("promote_operator_relief_registry_candidate",),
    }
    for callback, names in expected.items():
        source = getsource(callback)
        assert "from ae_engine.certified_relief_registry" not in source
        for name in names:
            assert "manufacturing_api." + name in source
    source = getsource(gui.registry_save_candidate_form)
    assert "controller.save_candidate(" in source
    source = getsource(gui.registry_promote_form)
    assert "controller.promote_candidate(" in source

# -*- coding: utf-8 -*-
"""#2517 Fold Designer Registry and baseline source use public Engine owners."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
import fold_designer_bridge as bridge
from ae_engine import manufacturing_api as api
from ae_engine.certified_relief_registry import (
    CertifiedReliefRegistryError, load_external_relief_rule_records,
)
from ae_engine.corner_type_ui import normalize_custom_model_name
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController

BRIDGE = Path(__file__).resolve().parents[1] / "fold_designer_bridge.py"


def test_public_registry_loader_is_exact_certified_engine_owner():
    assert api.operator_load_certified_relief_rule_records is load_external_relief_rule_records
    assert ae_engine.operator_load_certified_relief_rule_records is load_external_relief_rule_records
    assert "operator_load_certified_relief_rule_records" in ae_engine.__all__
    current = api.operator_load_certified_relief_rule_records()
    assert current == load_external_relief_rule_records()
    assert isinstance(current, tuple) and current
    assert all(row.get("rule_id") and row.get("revision") for row in current)


def test_bridge_registry_rows_equal_original_engine_and_controller_is_detached(monkeypatch):
    owner = Phase6RegistryDiagnosticsController()
    host = SimpleNamespace()
    monkeypatch.setattr(bridge, "_phase6_registry_diagnostics", lambda _: owner)
    expected = list(load_external_relief_rule_records())
    original = deepcopy(expected)
    rows = bridge._phase6_registry_load_rule_rows(host)
    assert rows == expected
    assert expected == original
    assert owner.rule_records == {
        f"{row['rule_id']}@{row['revision']}": row for row in expected
    }
    assert host._phase6_registry_rule_records == owner.rule_records
    rows[0]["rule_id"] = "INVALID_UI_MUTATION"
    assert owner.rule_records == {
        f"{row['rule_id']}@{row['revision']}": row for row in expected
    }


def test_invalid_registry_file_fails_closed_and_preserves_existing_rows(tmp_path):
    ctrl = Phase6RegistryDiagnosticsController()
    ctrl.load_rule_records(loader=api.operator_load_certified_relief_rule_records)
    before = ctrl.rule_records
    damaged = tmp_path / "invalid-certified-registry.json"
    damaged.write_text('{"schema_version": 1, "rules": []}', encoding="utf-8")
    unchanged = damaged.read_bytes()
    with pytest.raises(CertifiedReliefRegistryError):
        ctrl.load_rule_records(
            loader=lambda: api.operator_load_certified_relief_rule_records(damaged)
        )
    assert ctrl.rule_records == before
    assert damaged.read_bytes() == unchanged


@pytest.mark.parametrize("model,expected", (
    (" 未知類型 ", "自訂"), (" 自訂 ", "自訂"),
    ("受電箱", "受電箱"), ("金庫型", "金庫型"), (None, ""),
))
def test_legacy_baseline_model_public_engine_parity_and_no_input_mutation(model, expected):
    source = {"model": model}
    before = deepcopy(source)
    assert api.operator_normalize_custom_model_name(source["model"]) == expected
    assert api.operator_normalize_custom_model_name(source["model"]) == normalize_custom_model_name(model)
    assert ae_engine.operator_normalize_custom_model_name is normalize_custom_model_name
    assert "operator_normalize_custom_model_name" in ae_engine.__all__
    assert source == before


def test_bridge_registry_and_model_source_use_only_public_engine_api():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    prohibited = {
        ("ae_engine.certified_relief_registry", "load_external_relief_rule_records"),
        ("ae_engine.corner_type_ui", "normalize_custom_model_name"),
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert all((node.module, alias.name) not in prohibited for alias in node.names)
    calls = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    }
    assert {"operator_normalize_custom_model_name"} <= calls
    assert any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "manufacturing_api"
        and node.attr == "operator_load_certified_relief_rule_records"
        for node in ast.walk(tree)
    )

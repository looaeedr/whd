"""#2517: baseline manufacturing Family and saved-model codec only from public Engine."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types.registry import resolve_cabinet_type
from ae_engine.corner_type_ui import normalize_custom_model_name
from gui_modules.application import lifecycle


@pytest.mark.parametrize("model,expected", [
    ("金庫型", "金庫型"),
    ("VAULT", "金庫型"),
    ("vault", "金庫型"),
    ("受電箱", "受電箱"),
    ("RECEIVING", "受電箱"),
    (" receiving ", "受電箱"),
    ("RO", "RO"),
    (" 落地盤 ", "RO"),
    ("自訂", "金庫型"),
    ("未知類型", "金庫型"),
    (" 未註冊基準箱 ", "金庫型"),
    ("", "金庫型"),
    (None, "金庫型"),
])
def test_public_legacy_baseline_family_matches_exact_original_registry_route(model, expected):
    source = {"model": model, "features": [{"x": 10}]}
    prior = deepcopy(source)
    value = normalize_custom_model_name(model)
    try:
        original = resolve_cabinet_type(value).canonical_name
    except (KeyError, ValueError):
        original = "金庫型"
    assert original == expected
    assert api.operator_resolve_legacy_baseline_manufacturing_family(source["model"]) == original
    assert source == prior


@pytest.mark.parametrize("model", ["受電箱", " 自訂 ", "未知類型", "VAULT", None])
def test_actual_lifecycle_main_gui_family_uses_public_engine(monkeypatch, model):
    seen = []
    def public(value):
        seen.append(value)
        return "CANONICAL_SENTINEL"
    monkeypatch.setattr(api, "operator_resolve_legacy_baseline_manufacturing_family", public)
    host = SimpleNamespace(baseline_var=SimpleNamespace(get=lambda: model))
    assert lifecycle._current_cabinet_type_name(host) == "CANONICAL_SENTINEL"
    assert seen == [model]


def test_missing_or_inaccessible_baseline_keeps_original_gui_vault_fallback():
    class Broken:
        def get(self):
            raise RuntimeError("widget unavailable")
    host = SimpleNamespace(baseline_var=Broken())
    assert lifecycle._current_cabinet_type_name(host) == "金庫型"
    assert lifecycle._current_cabinet_type_name(SimpleNamespace()) == "金庫型"


def test_engine_rejection_surfaces_before_gui_changes_source(monkeypatch):
    saved = {"model": "受電箱", "box_body": {"w": 500}}
    prior = deepcopy(saved)
    host = SimpleNamespace(baseline_var=SimpleNamespace(get=lambda: saved["model"]))
    def reject(value):
        assert value == "受電箱"
        raise ValueError("FAMILY_SOURCE_INVALID")
    monkeypatch.setattr(api, "operator_resolve_legacy_baseline_manufacturing_family", reject)
    with pytest.raises(ValueError, match="FAMILY_SOURCE_INVALID"):
        lifecycle._current_cabinet_type_name(host)
    assert saved == prior


def test_saved_model_normalization_uses_same_original_public_engine_owner():
    for value in (None, "未知類型", " 自訂 ", "受電箱", "金庫型", "other"):
        assert api.operator_normalize_custom_model_name(value) == normalize_custom_model_name(value)
    assert ae_engine.operator_resolve_legacy_baseline_manufacturing_family is (
        api.operator_resolve_legacy_baseline_manufacturing_family
    )
    assert "operator_resolve_legacy_baseline_manufacturing_family" in ae_engine.__all__


def test_lifecycle_has_no_private_manufacturing_family_decision_or_model_codec():
    source = Path("gui_modules/application/lifecycle.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module in {"ae_engine.corner_type_ui", "ae_engine.cabinet_types"}
        and any(alias.name in {"normalize_custom_model_name", "resolve_cabinet_type"} for alias in node.names)
        for node in ast.walk(tree)
    )
    calls = [
        n.func.attr for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "manufacturing_api"
    ]
    assert calls.count("operator_resolve_legacy_baseline_manufacturing_family") == 1
    assert calls.count("operator_normalize_custom_model_name") == 2

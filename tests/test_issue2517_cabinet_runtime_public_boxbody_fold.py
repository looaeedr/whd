"""#2517 cabinet runtime BoxBody Fold materializes via one public Engine owner."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import box_body_fold_profile as owner
from gui_modules.application import cabinet_controller as gui
from phase6_fold_profiles import build_box_body_profile as legacy_gui_builder

SOURCE = Path(gui.__file__)


def _host(model):
    values = {
        "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "zl1": -24.0,
        "zl2": 24.0, "zr1": 15.0, "zr2": 18.0,
    }
    profile = {"value": None, "writes": []}
    workspace = SimpleNamespace(
        box_body_profile=lambda: profile["value"],
        set_box_body_profile=lambda value: (
            profile["writes"].append(deepcopy(value)),
            profile.update(value=value),
        ),
        box_body_structure_state=lambda: {"identity": "box"},
    )
    var_map = {key: SimpleNamespace(get=lambda value=value: value) for key, value in values.items()}
    host = SimpleNamespace(
        workspace_controller=workspace,
        _setting_var_map=lambda: var_map,
        _current_cabinet_type_name=lambda: model,
        _serialize_manual_corner_state=lambda: {},
        manual_corner_pair_same={},
        multi_door_enabled_var=SimpleNamespace(get=lambda: False),
        door_layout_columns=[],
    )
    return host, values, profile


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_actual_cabinet_runtime_capture_materializes_exact_public_fold_without_mutation(family):
    host, settings, state = _host(family)
    original = deepcopy(settings)
    runtime = gui._capture_cabinet_family_runtime(host)
    expected = api.build_box_body_fold_profile({**settings, "model": family})
    assert expected == owner.build_box_body_profile({**settings, "model": family})
    assert expected == legacy_gui_builder({**settings, "model": family})
    assert runtime["box_body_profile"] == expected
    assert state["value"] == expected
    assert state["writes"] == [expected]
    assert runtime["settings"] == settings
    assert settings == original


def test_cabinet_runtime_public_engine_failure_must_not_commit_partial_profile(monkeypatch):
    host, settings, state = _host("受電箱")
    before = deepcopy(settings)
    def refuse(_source):
        raise ValueError("BOX_BODY_OPERATOR_SOURCE_INVALID")
    monkeypatch.setattr(api, "build_box_body_fold_profile", refuse)
    with pytest.raises(ValueError, match="BOX_BODY_OPERATOR_SOURCE_INVALID"):
        gui._capture_cabinet_family_runtime(host)
    assert state["value"] is None
    assert state["writes"] == []
    assert settings == before


def test_cabinet_family_profile_callers_no_longer_use_gui_private_adapter():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "phase6_fold_profiles"
        and any(alias.name == "build_box_body_profile" for alias in node.names)
        for node in ast.walk(tree)
    )
    calls = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    ]
    assert calls.count("build_box_body_fold_profile") == 2

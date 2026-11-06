"""#2517 Receiving BasePlate settings, edge eligibility and reload via Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
import ae_engine.receiving_operator_projection as owner


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_aliases_never_show_free_base_shrink_edit_and_settings(model):
    snap = {"model": model, "receiving_base_plate": {
        "pattern": "LEFT_FLAT_SIDE", "shrink_left": 22,
    }}
    before = deepcopy(snap)
    assert api.operator_base_plate_edge_shrink_editable(snap) is False
    projected = api.project_operator_receiving_base_plate_settings(snap)
    assert projected == {
        "configured": True,
        "values": snap["receiving_base_plate"],
        "source_derived": False,
        "source_error": "",
    }
    projected["values"]["shrink_left"] = -99
    assert snap == before
    assert api.project_operator_receiving_base_plate_settings(snap, context="head") is None


def test_vault_unchanged_and_no_receiving_reload():
    snap = {"model": "金庫型", "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"}}
    assert api.operator_base_plate_edge_shrink_editable(snap) is True
    assert api.project_operator_receiving_base_plate_settings(snap) is None
    assert api.project_operator_receiving_base_plate_reload(snap, snap) == {
        "restore": False, "saved_base_plate": None,
        "refresh_derived_navigation": False,
    }


def test_settings_from_same_engine_source_and_source_error_are_preserved(monkeypatch):
    current = {"model": "受電箱", "nfb_config_submitted": True}
    resolved = {
        "receiving_bend_pattern": "LEFT_FLAT_SIDE", "h": 200,
        "base_plate_shrink_top": 20, "base_plate_shrink_bottom": 20,
        "base_plate_shrink_left": 40, "base_plate_shrink_right": 40,
        "base_plate_bend": 20,
    }
    monkeypatch.setattr(
        __import__("ae_engine.receiving_base_plate_config", fromlist=["receiving_base_plate_values"]),
        "receiving_base_plate_values", lambda _: resolved,
    )
    item = api.project_operator_receiving_base_plate_settings(current)
    assert item["values"]["pattern"] == "LEFT_FLAT_SIDE"
    assert item["values"]["shrink_top"] == 20
    assert item["source_derived"] is True
    assert item["configured"] is True
    assert item["source_error"] == ""

    from ae_engine import receiving_base_plate_config as source_owner
    def invalid(_):
        raise ValueError("CURRENT_NFB_SOURCE_INVALID")
    monkeypatch.setattr(source_owner, "receiving_base_plate_values", invalid)
    blocked = api.project_operator_receiving_base_plate_settings(current)
    assert blocked["configured"] is False
    assert blocked["values"] == {}
    assert blocked["source_error"] == "CURRENT_NFB_SOURCE_INVALID"


def test_save_reload_preserves_source_and_never_makes_unsupported_nfb_visible(monkeypatch):
    saved = {
        "model": "receiving", "nfb_config_submitted": True,
        "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"},
    }
    current = {"model": "RECEIVING", "nfb_config_submitted": True}
    before = deepcopy((saved, current))
    from ae_engine import receiving_base_plate_config as source_owner
    visited = []
    def source(values):
        visited.append(deepcopy(values))
        return values.get("receiving_base_plate")
    monkeypatch.setattr(source_owner, "receiving_base_plate_values", source)
    plan = api.project_operator_receiving_base_plate_reload(saved, current)
    assert plan["restore"] is True
    assert plan["refresh_derived_navigation"] is True
    assert visited[-1]["receiving_base_plate"] == saved["receiving_base_plate"]
    plan["saved_base_plate"]["pattern"] = "CHANGED"
    assert (saved, current) == before

    monkeypatch.setattr(source_owner, "receiving_base_plate_values", lambda _: None)
    assert not api.project_operator_receiving_base_plate_reload(saved, current)[
        "refresh_derived_navigation"
    ]
    def invalid(_):
        raise ValueError("unverified")
    monkeypatch.setattr(source_owner, "receiving_base_plate_values", invalid)
    assert not api.project_operator_receiving_base_plate_reload(saved, current)[
        "refresh_derived_navigation"
    ]


def test_gui_only_projects_baseplate_source_and_not_private_manufacturing_rules():
    from gui_modules.application import fold_designer_composition_settings as settings
    from gui_modules.application import fold_designer_composition_registry_edges as edges
    from gui_modules import project_actions
    source = inspect.getsource(settings.settings_context_extension_projection)
    assert "manufacturing_api.project_operator_receiving_base_plate_settings(" in source
    assert "from ae_engine.receiving_base_plate_config import" not in source
    for function in (edges.commit_base_plate_edge_shrink, edges.render_base_plate_edge_controls):
        code = inspect.getsource(function)
        assert "manufacturing_api.operator_base_plate_edge_shrink_editable(" in code
        assert 'snapshot.get("model")' not in code
    code = inspect.getsource(project_actions.load_phase6_project)
    assert "manufacturing_api.project_operator_receiving_base_plate_reload(" in code
    assert "from ae_engine.receiving_base_plate_config import" not in code
    assert "from phase6_" not in inspect.getsource(owner)

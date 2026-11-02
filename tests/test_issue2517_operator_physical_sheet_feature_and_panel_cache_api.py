"""#2517 physical-sheet features and inner-door raw preview cache use Engine API."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.inner_door_panels import InnerDoorPanelPart
from gui_modules.application import fold_designer_manufacturing_projection as gui
from gui_modules.application.state_sync import Phase6DerivedCacheOwner


def _panel():
    return InnerDoorPanelPart(
        stable_id="inner_door:operator:panel", inner_door_id="operator",
        cell_key="upper", width=670, height=950, thickness=2,
    )


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_engine_panel_signature_real_receiving_aliases_and_change(model):
    p = _panel()
    snapshot = {"model": model, "active_mode": "set_bay"}
    a = api.project_operator_inner_door_panel_preview_cache_signature(snapshot, p, ())
    b = api.project_operator_inner_door_panel_preview_cache_signature(snapshot, p, ())
    c = api.project_operator_inner_door_panel_preview_cache_signature(
        snapshot, replace(p, width=680), (),
    )
    assert a and a == b and a != c


def test_engine_rejects_false_family_mode_ghost_panel_and_unknown_feature():
    p = _panel()
    for snapshot in (
        {"model": "金庫型", "active_mode": "set_bay"},
        {"model": "受電箱", "active_mode": "quantity"},
        {"model": "受電箱"},
        None,
    ):
        assert api.project_operator_inner_door_panel_preview_cache_signature(
            snapshot, p, (),
        ) is None
    good = {"model": "受電箱", "active_mode": "set_bay"}
    assert api.project_operator_inner_door_panel_preview_cache_signature(
        good, object(), (),
    ) is None
    assert api.project_operator_inner_door_panel_preview_cache_signature(
        good, replace(p, stable_id="not-an-inner-door"), (),
    ) is None
    assert api.project_operator_inner_door_panel_preview_cache_signature(
        good, p, (object(),),
    ) is None


def test_gui_inner_door_preview_reuses_only_engine_signature(monkeypatch):
    panel = _panel()
    signature = ["source-A"]
    calls = []
    monkeypatch.setattr(gui, "_query_receiving_resolved_base_render_data",
                        lambda *_: None)
    monkeypatch.setattr(api, "resolve_fold_designer_panel_part", lambda *_: panel)
    monkeypatch.setattr(
        api, "project_operator_inner_door_panel_preview_cache_signature",
        lambda snapshot, physical, features: signature[0],
    )
    monkeypatch.setattr(
        api, "build_inner_door_panel_render_data",
        lambda physical, *, features: calls.append((physical, features)) or object(),
    )
    host = SimpleNamespace(
        _derived_cache_owner=Phase6DerivedCacheOwner(),
        _phase6_input_snapshot={"model": "受電箱", "active_mode": "set_bay"},
    )
    payload = {"features": ()}
    first = gui._query_fold_designer_render_data(
        host, panel.stable_id, payload,
    )
    assert gui._query_fold_designer_render_data(host, panel.stable_id, payload) is first
    assert len(calls) == 1
    signature[:] = ["source-B"]
    assert gui._query_fold_designer_render_data(host, panel.stable_id, payload) is not first
    assert len(calls) == 2


def test_gui_sheet_overlay_is_only_public_engine_api(monkeypatch):
    physical = object()
    result = object()
    calls = []
    monkeypatch.setattr(gui, "_query_receiving_resolved_base_render_data",
                        lambda *_: None)
    monkeypatch.setattr(api, "resolve_operator_receiving_pad_2d_source",
                        lambda *_: physical)
    monkeypatch.setattr(
        api, "with_physical_sheet_features",
        lambda key, render, features: calls.append((key, render, features)) or result,
    )
    key = "nfb_pad:physical"
    host = SimpleNamespace(_phase6_input_snapshot={"model": "受電箱"})
    assert gui._query_fold_designer_render_data(
        host, key, {"features": ("operator-feature",)},
    ) is result
    assert calls == [(key, physical, ("operator-feature",))]
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/fold_designer_manufacturing_projection.py"
              ).read_text(encoding="utf-8")
    section = source.split("def _query_fold_designer_render_data(")[1].split(
        "def _payload_topology_context(",
    )[0]
    assert "manufacturing_api.with_physical_sheet_features(" in section
    assert "manufacturing_api.project_operator_inner_door_panel_preview_cache_signature(" in section
    assert "from ae_engine.physical_sheet_features" not in section
    assert "from phase6_manufacturing_contracts" not in section
    assert 'snapshot.get("model")' not in section
    assert "manufacturing_fingerprint(" not in section

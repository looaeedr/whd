"""#2517: real Fold Designer physical identity now belongs to the Engine API."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import fold_designer_physical_selection as owner
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import derive_inner_door_frames
from gui_modules.application import fold_designer_manufacturing_projection as gui
from gui_modules.parts.panels.divider import collect_divider_input


def _divider_payload():
    return {
        "model": "受電箱", "d": 350, "t": 2,
        "door_layout_scope": "physical-2517",
        "door_layout_columns": [(800, [1100, 500])],
        "door_handle_edges": {"0:0": "LEFT"},
    }


def _receiving_inner_door_payload():
    return {
        "model": "受電箱", "t": 2, "multi_door_enabled": True,
        "door_layout_columns": [(800, [1100, 500])],
        "inner_doors": [
            {"stable_id": "upper", "cell_key": "0:0",
             "included_frame_sides": ("top",)}
        ],
    }


def test_real_divider_selection_matches_canonical_physical_topology_and_gui():
    payload = _divider_payload()
    original = deepcopy(payload)
    normalized = collect_divider_input("ignored", payload, default_depth=350, default_thickness=2)
    expected = derive_box_body_dividers(
        normalized["columns"], depth=normalized["depth"],
        thickness=normalized["thickness"], layout_scope=normalized["layout_scope"],
        handle_edges=normalized["handle_edges"], model_name=normalized["model_name"],
    )[0]
    assert api.resolve_fold_designer_divider_part(expected.stable_id, normalized) == expected
    assert gui._box_body_divider_from_payload(expected.stable_id, payload) == expected
    assert payload == original


def test_fallback_frame_source_is_explicit_and_stable_without_tk():
    payload = {
        "model": "Unregistered Custom Family", "t": 2,
        "inner_doors": [{
            "stable_id": "upper", "frame_spans": {
                "top": 500, "bottom": 500, "left": 800, "right": 800,
            },
            "included_frame_sides": ["top", "left", "right"],
        }],
    }
    expected = derive_inner_door_frames(
        "upper", spans=payload["inner_doors"][0]["frame_spans"],
        thickness=2, included_sides=["top", "left", "right"],
    )[0]
    assert api.resolve_fold_designer_frame_part(
        expected.stable_id, payload, default_thickness=2,
    ) == expected
    assert gui._inner_door_frame_from_payload(expected.stable_id, payload) == expected


def test_receiving_family_frame_and_panel_use_actual_current_door_grid():
    payload = _receiving_inner_door_payload()
    original = deepcopy(payload)
    frame = api.resolve_fold_designer_frame_part(
        "inner_door:upper:top_frame", payload, default_thickness=2,
    )
    panel = api.resolve_fold_designer_panel_part("inner_door:upper:panel", payload)
    assert frame.stable_id == "inner_door:upper:top_frame"
    assert frame.side == "top"
    assert panel.stable_id == "inner_door:upper:panel"
    assert panel.cell_key == "0:0"
    assert panel.width > 0 and panel.height > 0
    assert payload == original


@pytest.mark.parametrize("kind", ("divider", "frame", "panel"))
def test_stale_or_missing_physical_ids_never_fabricate_manufacturing(kind):
    if kind == "divider":
        normalized = collect_divider_input(
            "missing", _divider_payload(), default_depth=350, default_thickness=2,
        )
        call = lambda: api.resolve_fold_designer_divider_part("missing", normalized)
    elif kind == "frame":
        call = lambda: api.resolve_fold_designer_frame_part(
            "inner_door:upper:bottom_frame", _receiving_inner_door_payload(),
            default_thickness=2,
        )
    else:
        call = lambda: api.resolve_fold_designer_panel_part(
            "inner_door:ghost:panel", _receiving_inner_door_payload(),
        )
    with pytest.raises(ValueError, match="stable_id"):
        call()


def test_gui_forwards_real_part_selection_and_does_not_keep_topology_rules(monkeypatch):
    normalized_calls = []
    monkeypatch.setattr(api, "resolve_fold_designer_divider_part",
                        lambda key, data: normalized_calls.append((key, data)) or "divider-api")
    assert gui._box_body_divider_from_payload("sample", _divider_payload()) == "divider-api"
    assert normalized_calls[0][0] == "sample"
    assert normalized_calls[0][1]["columns"] == ((800.0, (1100.0, 500.0)),)
    monkeypatch.setattr(api, "resolve_fold_designer_frame_part",
                        lambda key, data, *, default_thickness: "frame-api")
    assert gui._inner_door_frame_from_payload("frame", {}) == "frame-api"

    sentinel = object()
    monkeypatch.setattr(api, "resolve_fold_designer_panel_part",
                        lambda key, data: sentinel)
    monkeypatch.setattr(api, "build_inner_door_panel_render_data",
                        lambda part, *, features: (part, tuple(features)))
    host = SimpleNamespace()
    result = gui._query_fold_designer_render_data(
        host, "inner_door:upper:panel", {"features": ("source",)},
    )
    assert result == (sentinel, ("source",))

    frame_source = inspect.getsource(gui._inner_door_frame_from_payload)
    panel_source = inspect.getsource(gui._query_fold_designer_render_data)
    assert "manufacturing_api.resolve_fold_designer_frame_part(" in frame_source
    assert "manufacturing_api.resolve_fold_designer_panel_part(" in panel_source
    assert "derive_all_inner_door_frames(" not in frame_source
    assert "cabinet_family_policy.derive_inner_door_panels(" not in panel_source
    assert "from gui_modules" not in inspect.getsource(owner)

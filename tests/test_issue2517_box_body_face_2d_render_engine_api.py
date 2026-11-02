"""#2517 BoxBody 2D face dimensions must cross the public Engine API."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import box_body_face_dimensions
from gui_modules.application import render_snapshots as gui


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_engine_face_sizes_equal_existing_core_and_preserve_fractional_mm(model):
    raw = {"model": model, "w": "800.25", "h": 1600.125, "d": "350.5"}
    faces = api.project_operator_box_body_face_dimensions(
        w=raw["w"], h=raw["h"], d=raw["d"],
    )
    assert faces == box_body_face_dimensions(w=800.25, h=1600.125, d=350.5)
    assert faces == {
        "left": (350.5, 1600.125),
        "back": (800.25, 1600.125),
        "right": (350.5, 1600.125),
    }


@pytest.mark.parametrize("key", ("w", "h", "d"))
@pytest.mark.parametrize("invalid", (False, True, 0, -1, "invalid", "", float("nan"), float("inf")))
def test_engine_rejects_invalid_dimensions_without_fabrication(key, invalid):
    values = {"w": 800., "h": 1600., "d": 350.}
    values[key] = invalid
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_box_body_face_dimensions(**values)


def make_host():
    return SimpleNamespace(
        fold_designer_app=None,
        _box_body_part_spec=lambda val: "box-body",
        _manufacturing_context=lambda **kwargs: "context",
        _authoritative_render_data=lambda spec, ctx: SimpleNamespace(
            material=SimpleNamespace(bounds=(0., 0., 500., 600.)),
            box_body_face_contexts={"left": object(), "back": object(), "right": object()},
        ),
        _refresh_box_body_piece_tabs_2d=lambda render_data: None,
        _baseline_source_model=lambda: "金庫型",
        box_body_face_selected_var=SimpleNamespace(get=lambda: "back"),
    )


def test_normal_renderer_invokes_public_api_not_private_geometry(monkeypatch):
    seen = []
    dimensions = {"left": (20., 40.), "back": (30., 40.), "right": (20., 40.)}
    def public_dimensions(**kwargs):
        seen.append(kwargs)
        return dimensions
    monkeypatch.setattr(api, "project_operator_box_body_face_dimensions", public_dimensions)
    monkeypatch.setattr(api, "project_box_body_2d_piece_inventory", lambda *a: ((), None))
    result = gui.box_body_render_snapshot(make_host(), {"w": 30., "h": 40., "d": 20.})
    assert result["dimensions"] == dimensions
    assert seen == [{"w": 30., "h": 40., "d": 20.}]


def test_legacy_mock_injection_still_supported(monkeypatch):
    monkeypatch.setattr(api, "project_box_body_2d_piece_inventory", lambda *a: ((), None))
    result = gui.box_body_render_snapshot(
        make_host(), {"w": 100., "h": 200., "d": 50.},
        face_dimensions_fn=lambda **v: {"mock": (v["w"], v["h"], v["d"])},
    )
    assert result["dimensions"] == {"mock": (100., 200., 50.)}


def test_gui_has_no_private_box_body_face_geometry_import():
    code=Path("gui_modules/application/render_snapshots.py").read_text(encoding="utf-8")
    assert "from ae_engine.sheetmetal_features import box_body_face_dimensions" not in code
    assert "manufacturing_api.project_operator_box_body_face_dimensions" in code

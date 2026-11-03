"""#2517 BoxBody Hole Editor physical face boundaries are Engine projections."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.rendering.interaction import open_box_body_face_editor


def _values():
    return {"w": 500., "h": 600., "d": 200., "t": 2., "fw": 25.}


@pytest.mark.parametrize("face_key,bounds,dimensions", (
    ("left", (2., 2., 198., 598.), (200., 600.)),
    ("back", (2., 2., 498., 598.), (500., 600.)),
    ("right", (2., 2., 198., 598.), (200., 600.)),
))
def test_engine_face_editor_geometry_matches_existing_whd_t_and_corner_source(
    face_key, bounds, dimensions,
):
    projection = api.project_operator_hole_editor_box_body_face(
        face_key, _values(),
    )
    assert (projection.width, projection.height) == dimensions
    assert tuple(projection.surface.polygon.bounds) == bounds
    assert (projection.reference_guide.min_point.x, projection.reference_guide.min_point.y) == (0., 0.)
    assert (projection.reference_guide.max_point.x, projection.reference_guide.max_point.y) == dimensions
    assert projection.baseline_scene is None


def test_engine_refuses_nonphysical_face_key():
    with pytest.raises(ValueError, match="未知箱身面"):
        api.project_operator_hole_editor_box_body_face("fictitious", _values())


def test_gui_delegates_box_body_face_geometry_without_physical_formula():
    calls, shown, selection = [], {}, []
    source = object()
    geometry = SimpleNamespace(
        surface=object(), width=250., height=600.,
        reference_guide=object(), baseline_scene=source,
        baseline_status="verified",
    )
    def project(*args, **kwargs):
        calls.append((args, kwargs))
        return geometry
    host = SimpleNamespace(
        get_float_values=_values,
        _box_body_corner_policies=lambda fw: ("head", "tail"),
        _box_body_face_baseline_scene=lambda face_key, val: source,
        baseline_var=SimpleNamespace(get=lambda: "金庫型"),
        box_body_face_selected_var=SimpleNamespace(set=selection.append),
        box_body_face_features={"left": []},
        fold_designer_app=None,
        _open_unified_hole_editor=lambda *a, **k: shown.update(args=a, kwargs=k) or "EDITOR",
    )
    result = open_box_body_face_editor(
        host, "left",
        messagebox_module=SimpleNamespace(showerror=lambda *a: pytest.fail(str(a))),
        editor_projection=project,
        baseline_label_fn=lambda model: "verified",
    )
    assert result == "EDITOR"
    assert calls == [(("left", _values()), {
        "head_corner_policy": "head",
        "tail_corner_policy": "tail",
        "baseline_scene": source,
        "baseline_status": "verified",
    })]
    assert shown["args"][2] is geometry.surface
    assert shown["kwargs"]["reference_guide"] is geometry.reference_guide
    assert shown["kwargs"]["feature_list_override"] is host.box_body_face_features["left"]
    assert shown["kwargs"]["baseline_scene"] is source
    assert selection == ["left"]


def test_gui_application_wires_only_public_engine_editor_projection():
    source = Path("gui.py").read_text(encoding="utf-8")
    assert "editor_projection=manufacturing_api.project_operator_hole_editor_box_body_face" in source
    assert "face_dimensions_fn=manufacturing_api.project_operator_box_body_face_dimensions" in source
    interaction = Path("gui_modules/rendering/interaction.py").read_text(encoding="utf-8")
    assert "vertical_offsets_fn" not in interaction
    assert "surface_builder" not in interaction

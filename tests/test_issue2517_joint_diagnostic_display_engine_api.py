"""#2517 Joint diagnostic display-source selection is Engine-owned."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest
from matplotlib.figure import Figure

from ae_engine import manufacturing_api, project_joint_diagnostic_display_sources
from ae_engine.joint_diagnostic_display import JointDiagnosticOverlaySource
from ae_engine.contracts import ResolvedJointDiagnostic
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _diag(id, **kwargs):
    return ResolvedJointDiagnostic(
        joint_id=id, subject_part="head", target_part="box_body",
        relation="WRAP", **kwargs,
    )


def _view(rows=(), selected=None):
    return SimpleNamespace(joint_diagnostics=rows, selected_joint_id=selected)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_reads_actual_solver_segments_and_selected_joint(family):
    red = _diag("red", penetration_segments=(
        ((1, 2, 3), (4, 6, 8)),
    ), direction_segment=((2, 4, 6), (3, 7, 10)))
    green = _diag("green", contact_segments=(((0, 0, 0), (0, 1, 0)),))
    before = (red, green)
    result = manufacturing_api.project_joint_diagnostic_display_sources(
        _view((red, green), "red"),
    )
    assert len(result) == 1
    overlay = result[0]
    assert isinstance(overlay, JointDiagnosticOverlaySource)
    assert overlay.joint_id == "red"
    assert overlay.groups[0] == ("contact_segments", ())
    assert overlay.groups[1] == (
        "penetration_segments", (((1., 2., 3.), (4., 6., 8.)),),
    )
    assert overlay.direction_origin == (2., 4., 6.)
    assert overlay.direction_delta == (1., 3., 4.)
    assert before == (red, green)
    assert manufacturing_api.project_joint_diagnostic_display_sources is (
        project_joint_diagnostic_display_sources
    )
    with pytest.raises(FrozenInstanceError):
        overlay.joint_id = "forged"


def test_no_selection_preserves_engine_diagnostic_order():
    left, right = _diag("left"), _diag("right")
    assert tuple(row.joint_id for row in project_joint_diagnostic_display_sources(
        _view((left, right)),
    )) == ("left", "right")
    assert project_joint_diagnostic_display_sources(_view((left, right), "missing")) == ()
    assert project_joint_diagnostic_display_sources(None) == ()


def test_invalid_world_coordinates_never_get_presented_as_physical_evidence():
    row = _diag(
        "bad",
        contact_segments=(
            ((0, 0, 0), (1, 2, 3)),
            ((0, 0), (1, 2, 3)),
            ((0, 0, 0), (float("nan"), 1, 1)),
            (object(),),
        ),
        relief_segments=(((5, 6, 7), (8, 9, 10)),),
        direction_segment=((0, 0), (1, 2, 3)),
    )
    output, = project_joint_diagnostic_display_sources(_view((row,)))
    assert output.groups[0] == (
        "contact_segments", (((0., 0., 0.), (1., 2., 3.)),),
    )
    assert output.groups[3] == (
        "relief_segments", (((5., 6., 7.), (8., 9., 10.)),),
    )
    assert output.direction_origin is None


def test_gui_only_draws_engine_world_rows_without_source_selection(monkeypatch):
    data = object()
    expected = (JointDiagnosticOverlaySource(
        "j",
        (
            ("contact_segments", (((0., 0., 0.), (1., 1., 1.)),)),
            ("penetration_segments", ()),
            ("preserve_segments", ()),
            ("relief_segments", (((3., 2., 1.), (4., 5., 6.)),)),
        ),
        (1., 2., 3.), (4., 5., 6.),
    ),)
    calls = []

    def port(value):
        calls.append(value)
        return expected

    monkeypatch.setattr(manufacturing_api, "project_joint_diagnostic_display_sources", port)
    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    arrows = []
    ax.quiver = lambda *args, **kwargs: arrows.append((args, kwargs))
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=ax))
    Phase6FinalSceneRenderHelpersMixin._draw_joint_diagnostic_overlays(host, data)
    assert calls == [data]
    assert len(ax.collections) == 2
    assert arrows[0][0] == (1., 2., 3., 4., 5., 6.)
    assert arrows[0][1]["arrow_length_ratio"] == 0.18
    source = inspect.getsource(
        Phase6FinalSceneRenderHelpersMixin._draw_joint_diagnostic_overlays,
    )
    assert "manufacturing_api.project_joint_diagnostic_display_sources(" in source
    assert "joint_diagnostics" not in source
    assert "selected_joint_id" not in source
    assert "direction_segment" not in source
    import ae_engine.joint_diagnostic_display as owner
    assert not any(x in inspect.getsource(owner) for x in (
        "from phase6_", "import phase6_", "tkinter", "matplotlib", "gui_modules",
    ))

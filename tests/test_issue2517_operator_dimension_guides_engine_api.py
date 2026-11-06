"""#2517 FinalScene operator 3D guide positions have one headless Engine owner."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    manufacturing_api, project_operator_dimension_guides,
    OperatorDimensionGuidePlan,
)
from ae_engine.display_dimensions import folded_outside_envelope
from phase6_final_scene_contracts import FinalSceneViewRequest
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _profiles():
    return (({"len": 100., "core": "W"},),
            ({"len": 80., "core": "H"},))


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_reuses_fold_core_guides_for_both_families(family):
    x, y = _profiles()
    x_before, y_before = repr(x), repr(y)
    plan = project_operator_dimension_guides(x, y)
    assert isinstance(plan, OperatorDimensionGuidePlan)
    assert plan.width_segments[0] == ((-50., -45.5, 0.), (50., -45.5, 0.))
    assert plan.height_segments[0] == ((-55.5, -40., 0.), (-55.5, 40., 0.))
    assert plan.width_label_position == (0., -45.5, 0.)
    assert plan.height_label_position == (-55.5, 0., 0.)
    assert len(plan.width_segments) == len(plan.height_segments) == 3
    assert repr(x) == x_before and repr(y) == y_before
    assert manufacturing_api.project_operator_dimension_guides is (
        project_operator_dimension_guides
    )
    assert manufacturing_api.OperatorDimensionGuidePlan is (
        OperatorDimensionGuidePlan
    )
    with pytest.raises(FrozenInstanceError):
        plan.width_segments = ()


def test_actual_formed_outside_envelope_overrides_core_without_guessing():
    x, y = _profiles()
    tris = (
        ((0., 0., 0.), (100., 0., 0.), (100., 80., 0.)),
        ((0., 0., 0.), (100., 80., 0.), (0., 80., 0.)),
    )
    physical = folded_outside_envelope(tris, 2.)
    assert physical is not None
    assert physical[1][0] == (0., 100.)
    assert physical[1][1] == (0., 80.)
    plan = project_operator_dimension_guides(
        x, y, triangles=tris, thickness=2.,
    )
    assert plan.width_segments[0] == ((0., -5.5, 0.), (100., -5.5, 0.))
    assert plan.height_segments[0] == ((-5.5, 0., 0.), (-5.5, 80., 0.))
    assert plan.width_label_position == (50., -5.5, 0.)
    assert plan.height_label_position == (-5.5, 40., 0.)


@pytest.mark.parametrize("bad", (
    (((False, 0, 0), (2, 0, 0), (0, 3, 0)),),
    (((float("nan"), 0, 0), (2, 0, 0), (0, 3, 0)),),
    (((0., 0., 0.), (1., 1., 1.)),),
))
def test_malformed_physical_mesh_is_never_a_dimension_guide_source(bad):
    x, y = _profiles()
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        project_operator_dimension_guides(x, y, triangles=bad, thickness=2.)


def test_gui_only_consumes_engine_plan_and_renders_unchanged_labels(monkeypatch):
    x, y = _profiles()
    plan = project_operator_dimension_guides(x, y)
    observed = []
    def api(x_profile, y_profile, *, triangles, thickness):
        observed.append((x_profile, y_profile, triangles, thickness))
        return plan
    monkeypatch.setattr(manufacturing_api, "project_operator_dimension_guides", api)
    plotted, texts, labels = [], [], []
    axes = object()
    ax = SimpleNamespace(
        plot=lambda *args, **kw: plotted.append((args, kw)),
        text=lambda *args, **kw: texts.append((args, kw)),
        text2D=lambda *args, **kw: labels.append((args, kw)),
        transAxes=axes,
    )
    request = FinalSceneViewRequest(
        render_data=None, x_profile=x, y_profile=y, part_key="door",
        finished_dimensions=(335., 535.), thickness=2.,
    )
    host = SimpleNamespace(
        renderer=SimpleNamespace(ax3d=ax),
        _resolved_finished_dimensions=lambda r, tris: (335., 535.),
        _number_text=lambda value: str(int(value)),
    )
    Phase6FinalSceneRenderHelpersMixin._draw_operator_dimensions(
        host, request, [],
    )
    assert observed == [(x, y, [], 2.)]
    assert len(plotted) == 6
    assert len(texts) == 2 and len(labels) == 1
    assert texts[0][0][:3] == plan.width_label_position
    assert texts[1][0][:3] == plan.height_label_position
    assert "W 335 mm" in texts[0][0][3]
    assert "H 535 mm" in texts[1][0][3]
    assert labels[0][1]["transform"] is axes

    source = inspect.getsource(
        Phase6FinalSceneRenderHelpersMixin._draw_operator_dimensions,
    )
    assert "manufacturing_api.project_operator_dimension_guides(" in source
    assert "_phase6_profile_geometry(" not in source
    assert "_phase6_profile_base_index(" not in source
    assert "_phase6_folded_outside_envelope(" not in source
    assert "span =" not in source

"""#2517 Joint contact world MARKING: Engine source owner, GUI draw only."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    manufacturing_api,
    project_joint_marking_world_segments,
    joint_marking_flat_signatures,
)
from ae_engine import final_scene_box_body_bend_lines as engine_owner
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _render_data(*rows, family="金庫型"):
    return SimpleNamespace(
        model_name=family, metadata={"joint_markings": rows},
    )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_actual_world_points_preserve_joint_source_for_both_families(family):
    source = _render_data(
        {
            "source": "JOINT_PLACEMENT_MARKING",
            "p1": (50.0, 20.0), "p2": (60.0, 20.0),
            "world_p1": (10.5, -12.0, 20.0),
            "world_p2": (15.5, -12.0, 20.0),
        },
        {
            "source": "JOINT_PLACEMENT_MARKING",
            "world_p1": (0.0, 0.0, 3.0),
            "world_p2": (0.0, 0.0, 7.0),
        },
        family=family,
    )
    expected = (
        ((10.5, -12.0, 20.0), (15.5, -12.0, 20.0)),
        ((0.0, 0.0, 3.0), (0.0, 0.0, 7.0)),
    )
    before = repr(source.metadata)
    result = manufacturing_api.project_joint_marking_world_segments(source)
    assert result == expected
    assert isinstance(result, tuple)
    assert repr(source.metadata) == before
    assert manufacturing_api.project_joint_marking_world_segments is (
        project_joint_marking_world_segments
    )
    assert engine_owner.project_joint_marking_world_segments is (
        project_joint_marking_world_segments
    )


def test_skip_unowned_flat_only_and_invalid_metadata_without_reprojection():
    source = _render_data(
        {"source": "OTHER", "world_p1": (1, 2, 3), "world_p2": (4, 5, 6)},
        {"source": "JOINT_PLACEMENT_MARKING", "p1": (1, 2), "p2": (3, 4)},
        {"source": "JOINT_PLACEMENT_MARKING", "world_p1": (1, 2),
         "world_p2": (3, 4, 5)},
        {"source": "JOINT_PLACEMENT_MARKING", "world_p1": None,
         "world_p2": (3, 4, 5)},
        "invalid-map",
        [
            ("source", "JOINT_PLACEMENT_MARKING"),
            ("world_p1", (7, 8, 9)),
            ("world_p2", (10, 11, 12)),
        ],
    )
    assert project_joint_marking_world_segments(source) == (
        ((7.0, 8.0, 9.0), (10.0, 11.0, 12.0)),
    )
    assert project_joint_marking_world_segments(
        SimpleNamespace(metadata={}),
    ) == ()
    # 2D flat signatures still come from the same source filter, and are
    # independent of the 3D world-position presentation.
    assert joint_marking_flat_signatures(_render_data(
        {"source": "JOINT_PLACEMENT_MARKING",
         "p1": (1, 2), "p2": (3, 4)},
    ))


def test_gui_draws_only_engine_world_rows(monkeypatch):
    world = (((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),)
    recorded = []
    def engine_port(value):
        recorded.append(value)
        return world

    monkeypatch.setattr(manufacturing_api,
                        "project_joint_marking_world_segments", engine_port)
    plotted = []
    ax = SimpleNamespace(plot=lambda *args, **kw: plotted.append((args, kw)))
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=ax))
    sample = object()
    Phase6FinalSceneRenderHelpersMixin._draw_joint_marking_world_rows(host, sample)
    assert recorded == [sample]
    assert plotted == [
        (([1.0, 4.0], [2.0, 5.0], [3.0, 6.0]),
         {"color": "#f59e0b", "linewidth": 2.2,
          "linestyle": "-", "alpha": 1.0, "zorder": 20}),
    ]
    source = inspect.getsource(
        Phase6FinalSceneRenderHelpersMixin._draw_joint_marking_world_rows
    )
    assert "manufacturing_api.project_joint_marking_world_segments(" in source
    assert "joint_markings" not in source
    assert "JOINT_PLACEMENT_MARKING" not in source
    assert "world_p1" not in source
    assert all(name not in inspect.getsource(engine_owner)
               for name in ("phase6_", "tkinter", "matplotlib"))

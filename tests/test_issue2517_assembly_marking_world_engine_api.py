"""#2517: Assembly non-contact MARKING world source must be Engine-owned."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from ae_engine import (
    manufacturing_api, marking_line_signature, joint_marking_flat_signatures,
    project_assembly_scene_marking_segments,
)
from ae_engine.assembly_geometry import place_assembly_points
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _scene():
    scene = DrawingScene()
    scene.add_line((20, 10), (40, 10), layer="MARKING")
    scene.add_line((30, 20), (70, 20), layer="MARKING")
    scene.add_line((0, 30), (100, 30), layer="BEND")
    return scene


def _ref():
    return (((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 80.0, 0.0)),)


def _source():
    return SimpleNamespace(metadata={"joint_markings": (
        {"source": "JOINT_PLACEMENT_MARKING", "p1": (40, 10), "p2": (20, 10)},
        {"source": "OTHER", "p1": (30, 20), "p2": (70, 20)},
        {"source": "JOINT_PLACEMENT_MARKING", "p1": None, "p2": (0, 0)},
    )})


def _kwargs():
    return dict(
        scene=_scene(), x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 80.0, "core": "D"},),
        fold_guides=(), local_reference=_ref(),
        placement="box_body", dimensions=(100.0, 80.0, 30.0),
        offset=(7.0, 8.0, 9.0),
    )


def test_joint_marking_flat_identity_is_unordered_and_9_decimal():
    sig = marking_line_signature((20, 10), (40, 10))
    assert sig == marking_line_signature((40, 10), (20, 10))
    assert sig == marking_line_signature((20 + 1e-10, 10), (40, 10))
    assert joint_marking_flat_signatures(_source()) == frozenset({sig})
    assert manufacturing_api.marking_line_signature is marking_line_signature
    assert manufacturing_api.joint_marking_flat_signatures is joint_marking_flat_signatures


def test_real_assembly_marking_uses_canonical_fold_and_skips_joint_duplicate():
    kwargs = _kwargs()
    result = project_assembly_scene_marking_segments(
        **kwargs, joint_marking_signatures=joint_marking_flat_signatures(_source()),
    )
    assert len(result) == 1 and isinstance(result, tuple)
    # Flat 30..70 maps to Fold-core-centered local (-20..+20).
    expected_local = ((-20.0, -20.0, 0.0), (20.0, -20.0, 0.0))
    expected = place_assembly_points(
        expected_local, _ref(), "box_body", (100, 80, 30), (7, 8, 9),
    )
    assert result == (expected,)
    assert manufacturing_api.project_assembly_scene_marking_segments is (
        project_assembly_scene_marking_segments
    )
    # No duplicate suppression: exactly two actual flat MARKING, not BEND.
    assert len(project_assembly_scene_marking_segments(**kwargs)) == 2


def test_head_tail_never_get_noncontact_guess_and_empty_mesh_is_not_a_datum():
    for part in ("head", "tail", "top", "bottom"):
        assert project_assembly_scene_marking_segments(
            **dict(_kwargs(), placement=part),
        ) == ()
    assert project_assembly_scene_marking_segments(
        **dict(_kwargs(), local_reference=()),
    ) == ()


def test_phase6_draw_and_legacy_signatures_are_public_api_only(monkeypatch):
    fake_segments = (((1, 2, 3), (4, 5, 6)),)
    seen = []
    def port(*args, **kwargs):
        seen.append((args, kwargs))
        return fake_segments
    monkeypatch.setattr(
        manufacturing_api, "project_assembly_scene_marking_segments", port,
    )
    called = []
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=SimpleNamespace(
        plot=lambda *args, **kw: called.append((args, kw)),
    )))
    args = _kwargs()
    Phase6FinalSceneRenderHelpersMixin._draw_assembly_scene_markings(
        host, *[args[k] for k in (
            "scene", "x_profile", "y_profile", "fold_guides", "local_reference",
            "placement", "dimensions", "offset",
        )], joint_marking_signatures={"sentinel"},
    )
    assert seen[0][1] == {"joint_marking_signatures": {"sentinel"}}
    assert len(called) == 1
    assert called[0] == (([1, 4], [2, 5], [3, 6]), {
        "color": "#f59e0b", "linewidth": 2.2, "linestyle": "-",
        "alpha": 1.0, "zorder": 20,
    })
    src = inspect.getsource(
        Phase6FinalSceneRenderHelpersMixin._draw_assembly_scene_markings,
    )
    assert "manufacturing_api.project_assembly_scene_marking_segments(" in src
    assert "self._map_xy(" not in src
    assert "place_assembly_points(" not in src
    assert Phase6FinalSceneRenderHelpersMixin._marking_line_signature((1, 2), (3, 4)) == (
        marking_line_signature((1, 2), (3, 4))
    )
    assert Phase6FinalSceneRenderHelpersMixin._joint_marking_flat_signatures(host, _source()) == (
        joint_marking_flat_signatures(_source())
    )


def test_source_engine_remains_headless():
    from ae_engine import final_scene_box_body_bend_lines as owner
    text = inspect.getsource(owner)
    assert "tkinter" not in text and "matplotlib" not in text
    assert "phase6_final_scene" not in text

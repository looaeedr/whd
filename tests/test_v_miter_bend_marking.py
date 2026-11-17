"""V-miter slanted-bend physical mark segments (not CUTTING certification)."""
from __future__ import annotations

import math

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _scene(p1=(0.0, 0.0), p2=(144.0, 108.0)):
    bend = LinePrimitive(Vec2(*p1), Vec2(*p2), layer="BEND")
    cut = LinePrimitive(Vec2(-10.0, -10.0), Vec2(200.0, -10.0), layer="CUTTING")
    return DrawingScene([cut, bend]), cut, bend


def _length(line):
    return math.hypot(line.p2.x - line.p1.x, line.p2.y - line.p1.y)


def _along(point):
    # The 144:108 slanted bend is exactly 180 mm with (0.8, 0.6) direction.
    return 0.8 * point.x + 0.6 * point.y


def test_slanted_bend_markings_are_real_symmetric_segments_from_source_bend():
    original, cutting, bend = _scene()
    resolved = manufacturing_api.with_v_miter_bend_markings(original, bend)
    assert resolved is not original
    assert original.primitives == [cutting, bend]
    assert resolved.primitives[:2] == original.primitives
    segments = resolved.primitives[2:]
    assert len(segments) == 3
    assert all(s.layer == "MARKING" and s.color == 211 for s in segments)
    assert [_length(s) for s in segments] == pytest.approx([20, 20, 20])
    assert [_along(s.p1) for s in segments] == pytest.approx([0, 80, 160])
    assert [_along(s.p2) for s in segments] == pytest.approx([20, 100, 180])
    assert all(abs(s.p1.x * 0.6 - s.p1.y * 0.8) < 1e-8 for s in segments)
    # This is marking only: it cannot silently replace or modify CUTTING.
    assert [p for p in resolved.primitives if p.layer == "CUTTING"] == [cutting]


@pytest.mark.parametrize(
    "length,expected",
    [
        (30.0, ((0.0, 30.0),)),
        (40.0, ((0.0, 40.0),)),
        (70.0, ((0.0, 20.0), (50.0, 70.0))),
        (90.0, ((0.0, 20.0), (70.0, 90.0))),
        (180.0, ((0.0, 20.0), (80.0, 100.0), (160.0, 180.0))),
    ],
)
def test_marking_short_lines_and_symmetric_remainders(length, expected):
    scene, _, bend = _scene((0.0, 0.0), (length, 0.0))
    marked = manufacturing_api.with_v_miter_bend_markings(scene, bend)
    assert [(s.p1.x, s.p2.x) for s in marked.primitives[2:]] == pytest.approx(expected)


@pytest.mark.parametrize(
    "stroke,gap",
    [(True, 50), (20, False), (float("nan"), 50), (20, float("inf")),
     (-1, 50), (20, 0), ("bad", 50)],
)
def test_invalid_marking_inputs_fail_without_mutating_source(stroke, gap):
    scene, _, bend = _scene()
    before = list(scene.primitives)
    with pytest.raises(GeometryError):
        manufacturing_api.with_v_miter_bend_markings(
            scene, bend, stroke_mm=stroke, clear_gap_mm=gap,
        )
    assert scene.primitives == before


def test_cannot_mark_a_guessed_bend_not_in_source_scene():
    scene, _, _ = _scene()
    fake = LinePrimitive(Vec2(0, 0), Vec2(100, 100), layer="BEND")
    with pytest.raises(GeometryError, match="source scene"):
        manufacturing_api.with_v_miter_bend_markings(scene, fake)
    with pytest.raises(GeometryError, match="canonical BEND"):
        manufacturing_api.project_v_miter_bend_markings(
            LinePrimitive(Vec2(0, 0), Vec2(100, 100), layer="CUTTING")
        )


def test_source_slanted_marking_dxf_has_actual_line_entities_save_and_reopen(tmp_path):
    scene, cutting, bend = _scene()
    marked = manufacturing_api.with_v_miter_bend_markings(scene, bend)
    path = tmp_path / "v_miter_marking.dxf"
    save_scene_dxf(path, marked)
    reloaded = ezdxf.readfile(path)
    lines = [row for row in reloaded.modelspace() if row.dxftype() == "LINE"]
    marking = [row for row in lines if row.dxf.layer == "MARKING"]
    assert len(marking) == 3
    assert len([row for row in lines if row.dxf.layer == "BEND"]) == 1
    assert len([row for row in lines if row.dxf.layer == "CUTTING"]) == 1
    assert reloaded.layers.get("MARKING").dxf.linetype == "CONTINUOUS"
    assert all(row.dxf.color == 211 for row in marking)
    expected = marked.primitives[2:]
    for row, source in zip(marking, expected):
        assert (row.dxf.start.x, row.dxf.start.y) == pytest.approx(
            (source.p1.x, source.p1.y))
        assert (row.dxf.end.x, row.dxf.end.y) == pytest.approx(
            (source.p2.x, source.p2.y))


def test_only_engine_public_api_exposes_v_miter_marking_without_changing_catalog():
    from ae_engine.sheetmetal_geometry_core import EDITABLE_CORNER_TYPE_IDS
    assert callable(manufacturing_api.with_v_miter_bend_markings)
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4  # Not a fake fifth CUTTING type.

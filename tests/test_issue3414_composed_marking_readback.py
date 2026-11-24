"""Verify actual combined MARKING ink, not only its independently saved sources."""
from math import sqrt

import ezdxf
import pytest

from ae_engine import composed_panel_dxf, manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3414_manual_marking_batch_witness import _marked, _one


def _actual_panels(actual_sheet):
    _source, render, context, bend, _angle = actual_sheet
    # Authored solid oblique line through the real first BEND, not an
    # invented fold or manufacturing file. Circle is on distinct stock.
    oblique = api.create_physical_manual_marking(
        "base_plate", context, (), midpoint=bend, length=12,
        angle_deg=37,
    )
    assert oblique.points[0].y < bend.y < oblique.points[1].y
    circle_center = Vec2(100, 100)
    circle = api.create_physical_manual_round_marking(
        "base_plate", context, (), centre=circle_center, diameter=25,
    )
    straight = api.with_physical_sheet_features("base_plate", render, (oblique,))
    group = _marked(actual_sheet)
    round_panel = api.with_physical_sheet_features("base_plate", render, (circle,))
    return tuple((name, _one(row)) for name, row in (
        ("A Oblique", straight), ("B Group", group), ("C Circle", round_panel),
    )), oblique, circle_center


@pytest.mark.parametrize("drift", (
    "group_elevation", "circle_normal", "stroke_bulge", "stroke_width",
    "stroke_linetype", "circle_thickness", "marking_layer_linetype",
    "stroke_thickness",
))
def test_actual_composed_final_only_marking_drift_keeps_prior_file(
    actual_sheet, tmp_path, monkeypatch, drift,
):
    panels, oblique, circle_center = _actual_panels(actual_sheet)
    target = tmp_path / "combined.dxf"
    save = composed_panel_dxf.save_scene_dxf
    def export():
        return api.save_composed_panel_dxf(
            panels, target, pre_commit_guard=lambda: None, overwrite=True,
            quantity_summary=True,
        )

    accepted = export()
    expected = target.read_bytes()  # Real known-good combined DXF.
    assert len(accepted.sheets) == 3
    dx, dy = accepted.sheets[0].offset
    cx, cy = accepted.sheets[2].offset
    doc = ezdxf.readfile(target)
    assert doc.header["$INSUNITS"] == 4
    ink = list(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
    assert len(ink) > 1
    start, end = [tuple(v) for v in ink[0].get_points("xy")]
    assert start == pytest.approx((oblique.points[0].x+dx, oblique.points[0].y+dy))
    assert end == pytest.approx((oblique.points[1].x+dx, oblique.points[1].y+dy))
    assert sqrt(sum((u-v)**2 for u, v in zip(start, end))) == pytest.approx(12)
    ring, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
    assert tuple(ring.dxf.center) == pytest.approx((circle_center.x+cx, circle_center.y+cy, 0))
    assert ring.dxf.radius == pytest.approx(12.5)
    assert cy > dy

    staged = []
    def corrupt(path, scene):
        save(path, scene)
        staged.append(path.name)
        if path.name != target.name:
            return
        doc = ezdxf.readfile(path)
        rows = list(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
        circle, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
        if drift == "group_elevation":
            rows[-1].dxf.elevation = 4
        elif drift == "circle_normal":
            circle.dxf.extrusion = (0, 0, -1)
        elif drift == "stroke_bulge":
            x, y, sw, ew, _bulge = rows[0].get_points("xyseb")[0]
            rows[0][0] = (x, y, sw, ew, .3)
        elif drift == "stroke_width":
            rows[0].dxf.const_width = .25
        elif drift == "stroke_linetype":
            rows[0].dxf.linetype = "CENTER"
        elif drift == "stroke_thickness":
            rows[0].dxf.thickness = 4
        elif drift == "circle_thickness":
            circle.dxf.thickness = 2
        elif drift == "marking_layer_linetype":
            doc.layers.get("MARKING").dxf.linetype = "CENTER"
        doc.saveas(path)

    monkeypatch.setattr(composed_panel_dxf, "save_scene_dxf", corrupt)
    with pytest.raises(ValueError, match="COMPOSED_DXF_MARKING_READBACK_MISMATCH"):
        export()
    assert staged == ["source-0.dxf", "source-1.dxf", "source-2.dxf", target.name]
    assert target.read_bytes() == expected
    assert sorted(p.name for p in tmp_path.iterdir()) == [target.name]
    # A clean retry uses the same translated geometry and remains publishable.
    monkeypatch.setattr(composed_panel_dxf, "save_scene_dxf", save)
    assert export().sheets == accepted.sheets

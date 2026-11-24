from math import cos, sin, pi
from pathlib import Path
import pytest
from shapely.geometry import Point
from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_drawing import CirclePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _configured, _part_spec


@pytest.fixture
def sheet():
    _, spec = _part_spec(_configured("受電箱"))
    render = api.build_part_render_data(spec, ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]))
    centre = render.material.representative_point()
    assert render.material.boundary.distance(centre) > 20
    c = Vec2(centre.x, centre.y)
    return render, c


def project(render, centre, diameter):
    context = api.resolve_physical_sheet_editor_context("base_plate", render)
    mark = api.create_physical_manual_round_marking("base_plate", context, (), centre=centre, diameter=diameter)
    planned = api.with_physical_sheet_features("base_plate", render, (mark,))
    return next(p for p in planned.scene.primitives if p.layer == "MARKING")


def cut_circle(render, centre, diameter, layer="CUTTING"):
    feature = CircleFeature(diameter, FeatureAnchor.ABSOLUTE_FINISHED_FACE, centre, layer=layer)
    return api.with_physical_sheet_features("base_plate", render, (feature,))


def test_round_edge_geometry_is_exact_and_does_not_cut(sheet):
    original, c = sheet
    render = cut_circle(original, c, 6)
    original_scene = tuple(render.scene.primitives)
    assert not render.material.covers(Point(c.x,c.y))
    result = project(render, c, 30)
    assert isinstance(result, CirclePrimitive)
    assert result.center == c and result.radius == 15 and result.layer == "MARKING"
    assert tuple(render.scene.primitives) == original_scene
    assert render.material.area < original.material.area
    assert not any(result is row for row in render.scene.primitives)


def test_reject_exact_circle_crossing_hidden_by_cut_chord(sheet):
    original,c = sheet
    render = cut_circle(original,c,6)
    # Near the middle of an existing Engine 128-chord cut representation,
    # the true CUTTING circle crosses the mark but its polygonized chord does not.
    a=pi/128
    xy=Vec2(c.x+(5-.0002)*cos(a),c.y+(5-.0002)*sin(a))
    assert Point(xy.x,xy.y).distance(render.material.interiors[0])>2
    with pytest.raises(ValueError,match="ROUND_MARKING_CIRCUMFERENCE"):
        project(render,xy,4)


def test_reject_edges_crossing_inside_hole_and_bad_diameter(sheet):
    render,c=sheet
    x0=render.material.bounds[0]
    with pytest.raises(ValueError,match="ROUND_MARKING_CIRCUMFERENCE"):
        project(render,Vec2(x0+1,c.y),4)
    with pytest.raises(ValueError,match="ROUND_MARKING_CIRCUMFERENCE"):
        project(cut_circle(render,c,6),c,2)
    with pytest.raises(ValueError,match="ROUND_MARKING_CIRCUMFERENCE"):
        project(cut_circle(render,c,6,"BLIND_HOLE"),Vec2(c.x+4,c.y),4)
    for d in (0, True, float("nan")):
        with pytest.raises(ValueError):
            project(render,c,d)


def test_genuine_bend_may_cross_circle_and_identity_cannot_drift(sheet):
    render, _ = sheet
    guide = render.fold_guides[0]
    assert guide.axis == "y" and guide.span_end > guide.span_start
    centre = Vec2((guide.span_start+guide.span_end)/2, guide.position)
    mark = project(render, centre, 8)
    assert mark.radius == 4 and mark.center == centre
    context = api.resolve_physical_sheet_editor_context("base_plate",render)
    with pytest.raises(ValueError,match="OWNER_MISMATCH"):
        api.create_physical_manual_round_marking("tail",context,(),centre=centre,diameter=8)


def test_stale_copy_cannot_override_canonical_cutting(sheet):
    from dataclasses import replace
    render,c=sheet
    cut=cut_circle(render,c,6)
    broken=replace(cut,material=render.material)
    with pytest.raises(ValueError,match="MATERIAL_SOURCE_MISMATCH"):
        project(broken,c,30)


def test_saved_circle_with_enclosed_hole_and_stale_or_wrong_owner_are_atomic(sheet, tmp_path, monkeypatch):
    from dataclasses import replace
    import ezdxf
    from ae_engine import manufacturing_api as api
    original, c = sheet
    hole = CircleFeature(6, FeatureAnchor.ABSOLUTE_FINISHED_FACE, c)
    holed = cut_circle(original, c, 6)
    context = api.resolve_physical_sheet_editor_context("base_plate", holed)
    create = api.create_physical_manual_round_marking
    mark = create("base_plate", context, (), centre=c, diameter=30)
    with pytest.raises(ValueError, match="OWNER_MISMATCH"):
        create("tail", context, (), centre=c, diameter=30)
    with pytest.raises(ValueError, match="重複"):
        create("base_plate", context, (mark,), centre=c, diameter=30)
    with pytest.raises(ValueError, match="ROUND_MARKING_CIRCUMFERENCE"):
        api.with_physical_sheet_features("base_plate", original,
            (mark, replace(hole, offset=Vec2(c.x + 14, c.y))))
    render = api.with_physical_sheet_features("base_plate", original, (mark, hole))
    assert render.material.equals(holed.material)
    dest = tmp_path / "real.dxf"
    api.save_part_render_data_dxf(render, dest)
    old = dest.read_bytes()
    for field in ("center", "radius", "layer", "linetype", "extrusion", "thickness"):
        doc = ezdxf.readfile(dest)
        row, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
        val = {"center": (c.x + 1, c.y, 0), "radius": 16, "layer": "CHECK",
               "linetype": "DASHED", "extrusion": (0, 0, -1), "thickness": 1}[field]
        setattr(row.dxf, field, val)
        bad = tmp_path / f"{field}.dxf"
        doc.saveas(bad)
        assert not api.verify_saved_part_render_data_dxf(render, bad).ok, field

    real_save = api.save_scene_dxf
    def corrupt(target, scene):
        real_save(target, scene)
        doc = ezdxf.readfile(target)
        row, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
        row.dxf.radius += 1
        doc.saveas(target)
    monkeypatch.setattr(api, "save_scene_dxf", corrupt)
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        api.save_part_render_data_dxf(render, dest, overwrite=True)
    assert dest.read_bytes() == old


def test_genuine_bend_form_projection_uses_exact_circle_crossings(sheet):
    from math import sqrt, dist
    render, _ = sheet
    guide = render.fold_guides[0]
    c = Vec2(355, guide.position + .37)
    context = api.resolve_physical_sheet_editor_context("base_plate", render)
    mark = api.create_physical_manual_round_marking("base_plate", context, (), centre=c, diameter=8)
    marked = api.with_physical_sheet_features("base_plate", render, (mark,))
    profiles = api.build_standard_part_fold_profiles(_configured("受電箱"), "base_plate")
    path, = [points for layer, points in api.project_independent_scene_annotation_paths(
        marked.scene, profiles["X"], profiles["Y"], marked.fold_guides,
    ) if layer == "MARKING"]
    bend, *_other = api.project_independent_scene_bend_segments(
        render.scene, profiles["X"], profiles["Y"], render.fold_guides,
    )
    for side in (-1, 1):
        cross = c.x + side * sqrt(4**2 - .37**2)
        t = (cross - guide.span_start) / (guide.span_end - guide.span_start)
        exact = tuple(a + t*(b-a) for a, b in zip(*bend))
        assert min(dist(p, exact) for p in path) < 1e-8
    assert dist(path[0], path[-1]) < 1e-8
    assert all(
        abs((p[1]+q[1])/2 - bend[0][1]) < 1e-8
        or abs((p[2]+q[2])/2 - bend[0][2]) < 1e-8
        for p, q in zip(path,path[1:])
    )


def test_same_stage_accepts_circle_and_open_ink_then_checks_each(sheet, tmp_path):
    import ezdxf
    render, c = sheet
    context = api.resolve_physical_sheet_editor_context("base_plate", render)
    line = api.create_physical_manual_marking(
        "base_plate", context, (), midpoint=c, length=8, angle_deg=90,
    )
    circle = api.create_physical_manual_round_marking(
        "base_plate", context, (line,), centre=c, diameter=30,
    )
    composed = api.with_physical_sheet_features("base_plate", render, (circle, line))
    good = tmp_path / "circle-with-prior-open-ink.dxf"
    api.save_part_render_data_dxf(composed, good)
    assert api.verify_saved_part_render_data_dxf(composed, good).ok
    for wrong in ("circle_z", "circle_color", "marking_layer_color", "line_plane"):
        doc = ezdxf.readfile(good)
        poly, = doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]')
        ring, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
        if wrong == "circle_z":
            ring.dxf.center = (c.x, c.y, .25)
        elif wrong == "circle_color":
            ring.dxf.color = 7
        elif wrong == "marking_layer_color":
            doc.layers.get("MARKING").dxf.color = 7
        else:
            poly.dxf.elevation = .25
        path = tmp_path / f"{wrong}.dxf"
        doc.saveas(path)
        result = api.verify_saved_part_render_data_dxf(composed, path)
        assert not result.ok
        findings = [i.detail for i in result.issues if i.category == "MARKING_MISMATCH"]
        if wrong != "line_plane":
            assert any("CIRCLE" in f for f in findings)
        if wrong in {"line_plane", "marking_layer_color"}:
            assert any("LWPOLYLINE" in f for f in findings)

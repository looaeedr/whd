# -*- coding: utf-8 -*-
import ezdxf

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _render_data():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        layer="CUTTING",
        closed=True,
    ))
    scene.add(LinePrimitive(Vec2(20, 0), Vec2(20, 60), "BEND"))
    scene.add(CirclePrimitive(Vec2(50, 30), 5.0, "CUTTING"))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=api.fold_guides_from_final_scene(scene),
    )


def _verifier():
    verifier = getattr(api, "verify_saved_part_render_data_dxf", None)
    assert callable(verifier), (
        "R3: missing independent saved-DXF acceptance seam; "
        "production DXF cannot currently be reopened and compared with canonical render data"
    )
    return verifier


def test_saved_dxf_acceptance_passes_exact_roundtrip(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    result = _verifier()(render, path)

    assert result.ok is True
    assert result.issues == ()


def test_saved_dxf_acceptance_detects_removed_bend(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    bends = list(msp.query('LINE[layer=="BEND"]'))
    assert len(bends) == 1
    msp.delete_entity(bends[0])
    doc.saveas(path)

    result = _verifier()(render, path)

    assert result.ok is False
    assert any(issue.category == "BEND_MISMATCH" for issue in result.issues)


def test_saved_dxf_acceptance_reports_layer_mismatch(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    bends = list(msp.query('LINE[layer=="BEND"]'))
    assert len(bends) == 1
    bends[0].dxf.layer = "CUTTING"
    doc.saveas(path)

    result = _verifier()(render, path)

    assert result.ok is False
    assert any(issue.category == "LAYER_MISMATCH" for issue in result.issues)


def test_saved_dxf_acceptance_detects_cutting_shape_change(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    outlines = list(msp.query('LWPOLYLINE[layer=="CUTTING"]'))
    assert len(outlines) == 1
    pts = list(outlines[0].get_points())
    pts[1] = (95.0, pts[1][1], *pts[1][2:])
    outlines[0].set_points(pts)
    doc.saveas(path)

    result = _verifier()(render, path)

    assert result.ok is False
    assert any(issue.category == "CUTTING_MISMATCH" for issue in result.issues)


def test_saved_dxf_acceptance_detects_removed_hole(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    circles = list(msp.query('CIRCLE[layer=="CUTTING"]'))
    assert len(circles) == 1
    msp.delete_entity(circles[0])
    doc.saveas(path)

    result = _verifier()(render, path)

    assert result.ok is False
    assert any(issue.category == "HOLE_MISMATCH" for issue in result.issues)


def test_saved_dxf_acceptance_detects_extra_bend(tmp_path):
    render = _render_data()
    path = tmp_path / "part.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    msp.add_line((80, 0), (80, 60), dxfattribs={"layer": "BEND"})
    doc.saveas(path)

    result = _verifier()(render, path)

    assert result.ok is False
    cats = {issue.category for issue in result.issues}
    assert "BEND_MISMATCH" in cats
    assert "ENTITY_COUNT_MISMATCH" in cats


def _segmented_cutout_render(endpoint_gap):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(100, 0), Vec2(100, 120), Vec2(0, 120)),
        layer="CUTTING",
        closed=True,
    ))
    scene.add(PolylinePrimitive(
        points=(Vec2(15.0, 110.0), Vec2(11.5, 113.5), Vec2(8.0, 110.0)),
        layer="CUTTING", closed=False,
    ))
    scene.add(PolylinePrimitive(
        points=(Vec2(8.0, 8.0), Vec2(11.5000000006, 4.5), Vec2(15.0, 8.0)),
        layer="CUTTING", closed=False,
    ))
    g = float(endpoint_gap)
    scene.extend([
        LinePrimitive(Vec2(8.0, 110.0 + g), Vec2(8.0, 105.0), "CUTTING"),
        LinePrimitive(Vec2(15.0, 105.0 - g), Vec2(15.0, 110.0), "CUTTING"),
        LinePrimitive(Vec2(15.0, 105.0), Vec2(23.0, 105.0 - g), "CUTTING"),
        LinePrimitive(Vec2(0.0, 105.0 + g), Vec2(8.0, 105.0), "CUTTING"),
        LinePrimitive(Vec2(8.0, 13.0), Vec2(0.0, 13.0 + g), "CUTTING"),
        LinePrimitive(Vec2(23.0, 13.0 - g), Vec2(15.0, 13.0), "CUTTING"),
        LinePrimitive(Vec2(23.0, 105.0), Vec2(23.0, 13.0), "CUTTING"),
        LinePrimitive(Vec2(0.0, 13.0), Vec2(0.0, 105.0), "CUTTING"),
        LinePrimitive(Vec2(8.0, 8.0), Vec2(8.0, 13.0 + g), "CUTTING"),
        LinePrimitive(Vec2(15.0, 13.0 - g), Vec2(15.0, 8.0), "CUTTING"),
    ])
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )


def test_saved_dxf_acceptance_uses_verifier_tolerance_for_segmented_cutout(tmp_path):
    render = _segmented_cutout_render(2e-12)
    path = tmp_path / "segmented-door-like-cutout.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    result = _verifier()(render, path, coordinate_tolerance=1e-6)

    assert result.ok is True
    assert result.issues == ()


def test_saved_dxf_acceptance_does_not_heal_gap_above_verifier_tolerance(tmp_path):
    render = _segmented_cutout_render(2e-12)
    path = tmp_path / "segmented-door-like-cutout-real-gap.dxf"
    api.save_part_render_data_dxf(render, path, overwrite=True)

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    cutting_lines = list(msp.query('LINE[layer=="CUTTING"]'))
    assert cutting_lines
    cutting_lines[0].dxf.start = (8.0, 110.0 + 1e-4, 0.0)
    doc.saveas(path)

    result = _verifier()(render, path, coordinate_tolerance=1e-6)

    assert result.ok is False
    assert any(issue.category == "CUTTING_MISMATCH" for issue in result.issues)

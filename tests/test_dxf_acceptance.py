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

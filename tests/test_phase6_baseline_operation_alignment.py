# -*- coding: utf-8 -*-
from types import SimpleNamespace

import ezdxf
import pytest
from shapely.geometry import Point

from ae_engine import ae, manufacturing_api
from ae_engine.contracts import EndCapPartSpec
from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene, LinePrimitive
import fold_designer_bridge as bridge


def _write_door_baseline(path, *, outside_marking=False):
    doc = ezdxf.new('R2010')
    for name, color in [('CUTTING', 3), ('BEND', 5), ('MARKING', 211), ('BLIND_HOLE', 1)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={'color': color})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True, dxfattribs={'layer': 'CUTTING'})
    for x in (20, 380):
        msp.add_line((x, 0), (x, 600), dxfattribs={'layer': 'BEND'})
    for y in (20, 580):
        msp.add_line((0, y), (400, y), dxfattribs={'layer': 'BEND'})
    msp.add_circle((25, 25), 6.5, dxfattribs={'layer': 'MARKING', 'color': 256})
    msp.add_circle((25, 25), 3.0, dxfattribs={'layer': 'CUTTING'})
    msp.add_circle((45, 45), 4.0, dxfattribs={'layer': 'BLIND_HOLE', 'color': 256})
    if outside_marking:
        msp.add_circle((-100, -100), 6.5, dxfattribs={'layer': 'MARKING', 'color': 256})
    doc.saveas(path)


def test_door_baseline_preserves_explicit_marking_and_blind_hole_layers(tmp_path, monkeypatch):
    path = tmp_path / '門.dxf'
    _write_door_baseline(path)
    monkeypatch.setattr(ae, 'baseline_part_path', lambda model, filename: str(path))
    monkeypatch.setattr(ae, 'baseline_expected_path', lambda model, filename: str(path))

    data = ae.get_stretched_door_data('TEST', 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30)
    circles = [p for p in data.scene.primitives if isinstance(p, CirclePrimitive)]
    by_radius = {round(float(p.radius), 3): p for p in circles}

    assert by_radius[6.5].layer == 'MARKING'
    assert by_radius[4.0].layer == 'BLIND_HOLE'
    assert by_radius[3.0].layer == 'CUTTING'



def test_door_baseline_preserves_exploded_cutting_handle_profile_inside_legacy_region(tmp_path, monkeypatch):
    path = tmp_path / '門.dxf'
    doc = ezdxf.new('R2010')
    for name, color in [('CUTTING', 3), ('BEND', 5)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={'color': color})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True, dxfattribs={'layer': 'CUTTING'})
    for x in (20, 380):
        msp.add_line((x, 0), (x, 600), dxfattribs={'layer': 'BEND'})
    for y in (20, 580):
        msp.add_line((0, y), (400, y), dxfattribs={'layer': 'BEND'})

    # Door-handle cutout deliberately sits inside the old X=100..260 / Y=50..330
    # suppression rectangle. Explicit CUTTING geometry must never be discarded by location.
    handle = [(140, 120), (200, 120), (200, 200), (140, 200)]
    for a, b in zip(handle, handle[1:] + handle[:1]):
        msp.add_line(a, b, dxfattribs={'layer': 'CUTTING'})
    doc.saveas(path)

    monkeypatch.setattr(ae, 'baseline_part_path', lambda model, filename: str(path))
    monkeypatch.setattr(ae, 'baseline_expected_path', lambda model, filename: str(path))

    scene = ae.get_stretched_door_data('TEST', 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30).scene
    handle_lines = [
        p for p in scene.primitives
        if isinstance(p, LinePrimitive) and str(p.layer).upper() == 'CUTTING'
    ]

    assert len(handle_lines) == 4
    cx = sum(float(p.p1.x) + float(p.p2.x) for p in handle_lines) / (2.0 * len(handle_lines))
    cy = sum(float(p.p1.y) + float(p.p2.y) for p in handle_lines) / (2.0 * len(handle_lines))
    material = manufacturing_api.material_polygon_from_final_scene(scene)
    assert not material.contains(Point(cx, cy))

def test_door_baseline_marking_outside_sheet_does_not_shift_cut_hole_anchor(tmp_path, monkeypatch):
    path = tmp_path / '門.dxf'
    _write_door_baseline(path, outside_marking=True)
    monkeypatch.setattr(ae, 'baseline_part_path', lambda model, filename: str(path))
    monkeypatch.setattr(ae, 'baseline_expected_path', lambda model, filename: str(path))

    data = ae.get_stretched_door_data('TEST', 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30)
    cut = next(p for p in data.scene.primitives if isinstance(p, CirclePrimitive) and abs(float(p.radius) - 3.0) < 1e-9)
    assert float(cut.center.x) == pytest.approx(35.0)
    assert float(cut.center.y) == pytest.approx(35.0)


def test_final_scene_operation_ownership_controls_material_without_3d_reclassification():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer='CUTTING', closed=True)
    scene.add_circle((30, 30), 6.5, layer='MARKING')
    scene.add_circle((50, 30), 4.0, layer='BLIND_HOLE')
    scene.add_circle((70, 30), 3.0, layer='CUTTING')

    material = manufacturing_api.material_polygon_from_final_scene(scene)

    assert material.contains(Point(30, 30))
    assert material.contains(Point(50, 30))
    assert not material.contains(Point(70, 30))


def test_manufacturing_scene_endcap_uses_orientation_normalized_builder(monkeypatch, tmp_path):
    baseline_path = tmp_path / '封頭尾.dxf'
    baseline_path.write_text('stub', encoding='utf-8')
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer='CUTTING', closed=True)
    captured = {}

    monkeypatch.setattr(manufacturing_api, '_baseline_path', lambda model, filename, context: baseline_path)

    def fake_builder(model, W, H, D, T, FW_val=None, **kwargs):
        captured.update(model=model, is_tail=kwargs.get('is_tail'), normalized=True)
        return SimpleNamespace(scene=scene)

    monkeypatch.setattr(ae, '_build_stretched_end_cap_scene', fake_builder)
    monkeypatch.setattr(ae, 'get_stretched_end_cap_data', lambda *a, **k: (_ for _ in ()).throw(AssertionError('raw endcap scene must not be used')))

    spec = EndCapPartSpec(
        width=500.0, height=600.0, depth=200.0, thickness=2.0, frame_width=25.0,
        model_name='PW', is_tail=False, fold_left=20.0, fold_right=20.0,
        fold_top=20.0, fold_bottom=20.0,
    )
    got = manufacturing_api.build_part_scene(spec)

    assert got is scene
    assert captured == {'model':'PW','is_tail':False,'normalized':True}


def test_marking_drawer_projects_marking_but_not_cutting_circle():
    scene = DrawingScene()
    scene.add_circle((30, 30), 6.5, layer='MARKING')
    scene.add_circle((70, 30), 3.0, layer='CUTTING')
    plotted = []
    class Ax:
        def plot(self, xs, ys, zs, **kwargs):
            plotted.append((xs, ys, zs, kwargs))
    app = SimpleNamespace(renderer=SimpleNamespace(ax3d=Ax()))
    bridge._phase6_draw_scene_markings(app, scene, [{'len':100.0}], [{'len':60.0}])
    assert len(plotted) == 1
    assert len(plotted[0][0]) == 65


def test_door_final_baseline_scene_marking_stays_material_and_cutting_is_removed(tmp_path, monkeypatch):
    path = tmp_path / '門.dxf'
    doc = ezdxf.new('R2010')
    for name, color in [('CUTTING', 3), ('BEND', 5), ('MARKING', 211)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={'color': color})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True, dxfattribs={'layer': 'CUTTING'})
    for x in (20, 380):
        msp.add_line((x, 0), (x, 600), dxfattribs={'layer': 'BEND'})
    for y in (20, 580):
        msp.add_line((0, y), (400, y), dxfattribs={'layer': 'BEND'})
    msp.add_circle((25, 100), 6.5, dxfattribs={'layer': 'MARKING', 'color': 256})
    msp.add_circle((45, 100), 3.0, dxfattribs={'layer': 'CUTTING'})
    doc.saveas(path)
    monkeypatch.setattr(ae, 'baseline_part_path', lambda model, filename: str(path))
    monkeypatch.setattr(ae, 'baseline_expected_path', lambda model, filename: str(path))

    scene = ae.get_stretched_door_data('TEST', 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30).scene
    circles = [p for p in scene.primitives if isinstance(p, CirclePrimitive)]
    mark = next(p for p in circles if abs(float(p.radius) - 6.5) < 1e-9)
    cut = next(p for p in circles if abs(float(p.radius) - 3.0) < 1e-9)
    material = manufacturing_api.material_polygon_from_final_scene(scene)

    assert mark.layer == 'MARKING'
    assert (float(mark.center.x), float(mark.center.y)) == pytest.approx((35.0, 110.0))
    assert material.contains(Point(mark.center.x, mark.center.y))
    assert cut.layer == 'CUTTING'
    assert (float(cut.center.x), float(cut.center.y)) == pytest.approx((55.0, 110.0))
    assert not material.contains(Point(cut.center.x, cut.center.y))

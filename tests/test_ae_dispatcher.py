import ezdxf
import pytest

import ae_engine.ae as ae
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _layers(scene):
    return [p.layer for p in scene.primitives]


def test_save_scene_dxf_round_trip(tmp_path):
    scene = DrawingScene()
    scene.add(LinePrimitive(Vec2(0, 0), Vec2(10, 0), layer='BEND'))
    path = tmp_path / 'scene.dxf'

    ae._save_scene_dxf(str(path), scene)

    doc = ezdxf.readfile(path)
    entities = list(doc.modelspace())
    assert len(entities) == 1
    assert entities[0].dxf.layer == 'BEND'


def test_build_door_scene_contains_structural_check_and_stock():
    scene = ae._build_door_scene(
        w=400.0, h=600.0, t=2.0, fw=25.0,
        gw=4.0, gh=4.0,
        fl=25.0, fr=25.0, ft=25.0, fb=25.0,
        draw_stock=True,
    )
    layers = _layers(scene)
    assert layers.count('BEND') == 4
    assert 'CUTTING' in layers
    assert 'CHECK' in layers
    assert 'STOCK' in layers


def test_build_box_body_scene_contains_eight_bends():
    scene = ae._build_box_body_scene(
        w=400.0, h=600.0, d=250.0, t=2.0, fw=25.0,
        zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=2.0,
        draw_stock=True, model_name=None,
    )
    layers = _layers(scene)
    assert layers.count('BEND') == 8
    assert 'CUTTING' in layers
    assert 'CHECK' in layers
    assert 'STOCK' in layers


def test_export_part_dxf_dispatches_alias(monkeypatch, tmp_path):
    calls = []

    def fake_door(filepath, **kwargs):
        calls.append((filepath, kwargs))

    monkeypatch.setattr(ae, 'export_door_dxf', fake_door)
    target = tmp_path / 'door.dxf'

    ae.export_part_dxf('door', str(target), W_val=123.0)

    assert calls == [(str(target), {'W_val': 123.0})]


def test_export_part_dxf_rejects_unknown_type(tmp_path):
    with pytest.raises(ValueError, match='Unsupported part type'):
        ae.export_part_dxf('mystery-part', str(tmp_path / 'x.dxf'))


def test_build_end_cap_scene_contains_five_bends_and_fixed_features():
    scene = ae._build_end_cap_scene(
        w=400.0, d=250.0, t=2.0, fw=25.0,
        yl1=15.0, yr1=15.0, ytop1=16.0, ybottom1=15.0,
        draw_stock=True, is_tail=False, holes=None,
    )
    layers = _layers(scene)
    assert layers.count('BEND') == 5
    assert 'CUTTING' in layers
    assert 'CHECK' in layers
    assert 'STOCK' in layers


def test_build_indicator_scene_contains_four_bends():
    scene = ae._build_indicator_box_scene([2, 3], 2.0, draw_stock=True)
    layers = _layers(scene)
    assert layers.count('BEND') == 4
    assert 'CUTTING' in layers
    assert 'CHECK' in layers
    assert 'STOCK' in layers


def test_build_base_plate_scene_contains_datum():
    scene = ae._build_base_plate_scene(
        w=400.0, h=600.0, t=2.0,
        st=15.0, sb=15.0, sl=15.0, sr=15.0,
        bend=25.0, draw_stock=True,
    )
    layers = _layers(scene)
    assert layers.count('BEND') == 4
    assert 'DATUM' in layers
    assert 'CHECK' in layers
    assert 'STOCK' in layers


def test_export_part_dxf_tail_sets_tail_semantics(monkeypatch, tmp_path):
    calls = []

    def fake_endcap(filepath, **kwargs):
        calls.append((filepath, kwargs))

    monkeypatch.setattr(ae, 'export_end_cap_dxf', fake_endcap)
    target = tmp_path / 'tail.dxf'
    ae.export_part_dxf('tail', str(target), W_val=321.0)

    assert calls == [(str(target), {'W_val': 321.0, 'is_tail': True})]

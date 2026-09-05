import importlib
import inspect

import pytest

from ae_engine.sheetmetal_geometry import Vec2, EndCapGeometry, ReliefConfig, calculate_endcap_relief_dimensions
from ae_engine.sheetmetal_features import DoorIndicatorPosition


def _mod():
    import ae_engine.sheetmetal_drawing
    return ae_engine.sheetmetal_drawing


def test_stock_outline_is_generic_closed_rectangle():
    m = _mod()
    p = m.build_stock_outline(100.0, 50.0)
    assert p.layer == 'STOCK'
    assert p.closed is False
    assert p.points == (
        Vec2(0.0, 0.0), Vec2(100.0, 0.0), Vec2(100.0, 50.0),
        Vec2(0.0, 50.0), Vec2(0.0, 0.0),
    )


def test_base_plate_datum_preserves_existing_reference_rectangle():
    m = _mod()
    p = m.build_base_plate_datum(
        w=400.0, h=600.0, shrink_left=12.0, shrink_bottom=18.0, bend=10.0
    )
    assert p.layer == 'DATUM'
    assert p.color == 6
    assert p.points == (
        Vec2(-2.0, -8.0), Vec2(398.0, -8.0), Vec2(398.0, 592.0),
        Vec2(-2.0, 592.0), Vec2(-2.0, -8.0),
    )


def test_base_plate_check_preserves_text_and_placement():
    m = _mod()
    (p,) = m.build_base_plate_check(
        total_width=420.0, total_height=620.0, bend=10.0,
        shrink_top=5.0, shrink_bottom=6.0, shrink_left=7.0, shrink_right=8.0,
    )
    assert p.layer == 'CHECK'
    assert p.insert == Vec2(210.0, 670.0)
    assert p.char_height == 30.0
    assert p.attachment_point == 8
    assert 'Part: Base Plate' in p.text
    assert '折邊: 10 mm' in p.text
    assert '縮量: 上5 下6 左7 右8 mm' in p.text


def test_door_check_uses_passed_indicator_position_verbatim():
    m = _mod()
    position = DoorIndicatorPosition(
        reference_x=20.0, reference_y=500.0,
        target_x=120.0, target_y=300.0,
        distance_x=100.0, distance_y=200.0,
    )
    items = m.build_door_check(
        total_width=450.0, total_height=650.0,
        finished_w=400.0, finished_h=600.0, thickness=2.0,
        fold_left=25.0, fold_right=25.0, fold_top=25.0, fold_bottom=25.0,
        indicator_position=position,
    )
    assert items[0].layer == 'CHECK'
    lines = [x for x in items if isinstance(x, m.LinePrimitive)]
    texts = [x for x in items if isinstance(x, m.TextPrimitive)]
    assert any(x.p1 == Vec2(20.0, 320.0) and x.p2 == Vec2(120.0, 320.0) for x in lines)
    assert any(x.p1 == Vec2(100.0, 500.0) and x.p2 == Vec2(100.0, 300.0) for x in lines)
    assert any(x.text == 'X = 100.0' for x in texts)
    assert any(x.text == 'Y = 200.0' for x in texts)


def test_endcap_check_formats_relief_from_geometry_engine_result():
    m = _mod()
    geometry = EndCapGeometry(
        total_width=420.0, total_depth=300.0, thickness=2.0, fw=25.0,
        left_fold=15.0, right_fold=20.0, top_first_fold=16.0, bottom_fold=15.0,
    )
    relief = calculate_endcap_relief_dimensions(geometry, ReliefConfig())
    (p,) = m.build_endcap_check(
        geometry=geometry, relief=relief, finished_width=400.0, finished_depth=250.0,
        part_label='End Cap (Y)',
    )
    assert p.layer == 'CHECK'
    assert p.insert == Vec2(210.0, 350.0)
    assert 'Part: End Cap (Y)' in p.text
    assert '上方大截角:' in p.text
    assert '二級截角:' in p.text
    assert '下方截角:' in p.text


def test_box_and_indicator_check_builders_are_pure_annotations():
    m = _mod()
    (box,) = m.build_box_body_check(
        total_length=1000.0, total_height=500.0,
        panel_width=400.0, panel_depth=250.0, thickness=2.0,
        fold_values=(15.0, 20.0, 25.0, 246.0, 396.0, 246.0, 25.0, 20.0, 15.0),
    )
    assert 'Part: Box Body (Z)' in box.text
    assert '折彎: 15 20 25 246 396 246 25 20 15' in box.text

    (indicator,) = m.build_indicator_box_check(300.0, 400.0, group_count=3, fold=49.0)
    assert 'Part: Indicator Box (3 groups)' in indicator.text
    assert '折邊: 上下左右各折 49 mm' in indicator.text


def test_drawing_module_has_no_cad_or_boolean_dependency():
    m = _mod()
    source = inspect.getsource(m)
    assert 'import ezdxf' not in source
    assert 'import tkinter' not in source
    assert 'import shapely' not in source.lower()


def test_drawing_scene_preserves_primitive_order_and_circle_data():
    m = _mod()
    circle = m.CirclePrimitive(center=Vec2(12.0, 34.0), radius=5.5, layer='CUTTING', color=3)
    line = m.LinePrimitive(Vec2(0.0, 0.0), Vec2(1.0, 2.0), 'BEND')
    scene = m.DrawingScene()
    scene.add(circle)
    scene.extend((line,))
    assert scene.primitives == [circle, line]
    assert scene.primitives[0].radius == 5.5


def test_structural_result_to_primitives_converts_outline_and_bends():
    m = _mod()
    from ae_engine.sheetmetal_part_adapters import StructuralGeometryResult
    from ae_engine.sheetmetal_geometry import BendLine

    result = StructuralGeometryResult(
        outline=(Vec2(0, 0), Vec2(10, 0), Vec2(10, 5), Vec2(0, 5), Vec2(0, 0)),
        bends=(BendLine('b1', Vec2(2, 0), Vec2(2, 5)), BendLine('b2', Vec2(8, 0), Vec2(8, 5))),
        width=10,
        height=5,
    )
    items = m.structural_result_to_primitives(result)
    assert len(items) == 3
    assert isinstance(items[0], m.PolylinePrimitive)
    assert items[0].layer == 'CUTTING'
    assert items[0].points[1] == Vec2(10, 0)
    assert [x.layer for x in items[1:]] == ['BEND', 'BEND']


def test_resolved_features_to_primitives_preserves_layers_and_centerline():
    m = _mod()
    from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect

    features = [
        ResolvedCircle(center=Vec2(5, 6), radius=2.0, layer='MARKING', add_centerline=True),
        ResolvedRect(center=Vec2(2, 1.5), width=4.0, height=3.0, layer='CUTTING'),
    ]
    items = m.resolved_features_to_primitives(features)
    assert isinstance(items[0], m.CirclePrimitive)
    assert items[0].layer == 'MARKING'
    assert items[0].color == 211
    assert isinstance(items[1], m.LinePrimitive)
    assert items[1].p1 == Vec2(3, 6)
    assert items[1].p2 == Vec2(7, 6)
    assert isinstance(items[2], m.PolylinePrimitive)
    assert items[2].closed is True
    assert items[2].color == 3


def test_scene_data_keeps_scene_params_and_metadata_separate():
    m = _mod()
    scene = m.DrawingScene()
    scene.add(m.CirclePrimitive(Vec2(1, 2), 3.0, 'CUTTING'))
    data = m.SceneData(scene=scene, params={'w': 100.0}, metadata={'tag': 'x'})
    assert data.scene is scene
    assert data.params == {'w': 100.0}
    assert data.metadata == {'tag': 'x'}


def test_scene_convenience_methods_create_typed_primitives_directly():
    m = _mod()
    scene = m.DrawingScene()
    scene.add_polyline([(0, 0), (4, 0)], layer='CUTTING', closed=True)
    scene.add_line((1, 1), (3, 1), layer='MARKING')
    scene.add_circle((2, 2), 1.25, layer='MARKING')
    assert isinstance(scene.primitives[0], m.PolylinePrimitive)
    assert scene.primitives[0].points == (Vec2(0, 0), Vec2(4, 0))
    assert scene.primitives[0].closed is True
    assert isinstance(scene.primitives[1], m.LinePrimitive)
    assert scene.primitives[1].color == 211
    assert isinstance(scene.primitives[2], m.CirclePrimitive)
    assert scene.primitives[2].center == Vec2(2, 2)
    assert scene.primitives[2].color == 211


def test_blind_hole_circle_defaults_to_red_and_centerline_is_datum():
    from ae_engine.sheetmetal_features import ResolvedCircle
    feature = ResolvedCircle(center=Vec2(10,20), radius=5, layer='BLIND_HOLE', add_centerline=True, source_type='管孔')
    primitives = _mod().resolved_features_to_primitives([feature])
    assert primitives[0].layer == 'BLIND_HOLE'
    assert primitives[0].color == 1
    assert primitives[1].layer == 'DATUM'
    assert primitives[1].color == 6


def test_resolved_profile_becomes_closed_polyline():
    from ae_engine.sheetmetal_features import ResolvedProfile
    feature = ResolvedProfile((Vec2(0,0), Vec2(10,0), Vec2(10,5), Vec2(0,5)), layer='CUTTING', source_type='custom')
    primitives = _mod().resolved_features_to_primitives([feature])
    assert len(primitives) == 1
    assert isinstance(primitives[0], _mod().PolylinePrimitive)
    assert primitives[0].closed is True
    assert primitives[0].layer == 'CUTTING'

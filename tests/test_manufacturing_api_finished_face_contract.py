from pathlib import Path

import pytest

import ae_engine.ae as ae
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide


def test_door_part_spec_defaults_to_finished_face_and_api_maps_to_legacy_unfolded(monkeypatch, tmp_path):
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.manufacturing_api import generate_part

    feature = CircleFeature(22.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100.0, 120.0))
    spec = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
        features=(feature,),
    )
    assert spec.feature_space == 'finished_face'

    seen = {}
    def fake_export(path, **kwargs):
        seen.update(kwargs)
        Path(path).write_text('ok', encoding='utf-8')
    monkeypatch.setattr(ae, 'export_door_dxf', fake_export)

    generate_part(spec, tmp_path / 'door.dxf')

    finished_w, finished_h = ae.calculate_door_finished_size(500, 600, 25, 3.5, 3.5, 2)
    result = build_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
    )
    guide = build_finished_reference_guide('door', result, finished_width=finished_w, finished_height=finished_h)
    mapped = seen['user_features'][0]
    assert mapped.anchor is FeatureAnchor.ABSOLUTE_FINISHED_FACE
    assert mapped.offset.x == pytest.approx(guide.min_point.x + 100.0)
    assert mapped.offset.y == pytest.approx(guide.min_point.y + 120.0)


def test_door_legacy_unfolded_feature_space_preserves_gui_coordinates(monkeypatch, tmp_path):
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.manufacturing_api import generate_part

    feature = CircleFeature(22.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(133.0, 144.0))
    spec = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        feature_space='legacy_unfolded', features=(feature,),
    )
    seen = {}
    def fake_export(path, **kwargs):
        seen.update(kwargs)
        Path(path).write_text('ok', encoding='utf-8')
    monkeypatch.setattr(ae, 'export_door_dxf', fake_export)
    generate_part(spec, tmp_path / 'door.dxf')
    assert seen['user_features'][0] == feature


def test_endcap_feature_objects_are_normalized_to_existing_hole_contract(monkeypatch, tmp_path):
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.manufacturing_api import generate_part

    feature = CircleFeature(12.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(80.0, 60.0), layer='MARKING')
    spec = EndCapPartSpec(width=500, depth=200, thickness=2, frame_width=25, holes=(feature,))
    seen = {}
    def fake_export(path, **kwargs):
        seen.update(kwargs)
        Path(path).write_text('ok', encoding='utf-8')
    monkeypatch.setattr(ae, 'export_end_cap_dxf', fake_export)
    generate_part(spec, tmp_path / 'head.dxf')
    hole = seen['holes'][0]
    assert hole['x'] == pytest.approx(80.0)
    assert hole['y'] == pytest.approx(60.0)
    assert hole['params']['diameter'] == pytest.approx(12.0)
    assert hole['params']['layer'] == 'MARKING'


def test_expected_baseline_path_for_is_public_and_caller_root_owned(tmp_path):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    import ae_engine.manufacturing_api as manufacturing_api

    shared = tmp_path / "基準檔" / "任意共用名稱"
    shared.mkdir(parents=True)
    (shared / "盒子.dxf").write_text("box", encoding="utf-8")
    (shared / "小門.dxf").write_text("door", encoding="utf-8")
    spec = manufacturing_api.indicator_small_door_spec((1,), thickness=2)
    path = manufacturing_api.expected_baseline_path_for(
        spec, ManufacturingContext(resource_root=tmp_path)
    )
    assert path == shared / "小門.dxf"

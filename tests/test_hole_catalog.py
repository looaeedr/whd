from pathlib import Path
import ezdxf

from ae_engine.hole_catalog import load_hole_catalog, load_pipe_catalog, load_profile_points


def test_load_hole_catalog_parses_circle_rectangle_and_profile(tmp_path):
    base = tmp_path / '基準檔' / '開孔'
    base.mkdir(parents=True)
    (base / '開孔.csv').write_text('\ufeff器具開孔名稱,加工孔徑尺寸,\n圓孔22,22,\n插座盒,90,50\nAS&VS,AS&VS.dxf,\n', encoding='utf-8')
    defs = load_hole_catalog(base)
    by_name = {d.name: d for d in defs}
    assert by_name['圓孔22'].shape == 'circle'
    assert by_name['圓孔22'].diameter == 22
    assert by_name['圓孔22'].process == 'CUTTING'
    assert by_name['插座盒'].shape == 'rectangle'
    assert (by_name['插座盒'].width, by_name['插座盒'].height) == (90, 50)
    assert by_name['AS&VS'].shape == 'profile'
    assert by_name['AS&VS'].profile_path == base / 'AS&VS.dxf'


def test_load_pipe_catalog_is_blind_hole(tmp_path):
    base = tmp_path / '開孔'
    base.mkdir()
    (base / '管孔尺寸清單.csv').write_text('\ufeff圖塊代號,加工孔徑尺寸\n*D1,116\n', encoding='utf-8')
    defs = load_pipe_catalog(base)
    assert len(defs) == 1
    assert defs[0].name == '*D1'
    assert defs[0].diameter == 116
    assert defs[0].process == 'BLIND_HOLE'
    assert defs[0].shape == 'circle'


def test_load_profile_points_reads_closed_cutting_polyline_and_centers_it(tmp_path):
    path = tmp_path / 'profile.dxf'
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_lwpolyline([(10,20),(40,20),(40,70),(10,70)], close=True, dxfattribs={'layer':'CUTTING'})
    doc.saveas(path)
    pts = load_profile_points(path)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    assert min(xs) == -15
    assert max(xs) == 15
    assert min(ys) == -25
    assert max(ys) == 25


def test_definition_builds_blind_circle_and_rotated_rectangle(tmp_path):
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.hole_catalog import HoleDefinition, feature_from_definition
    blind = HoleDefinition('*D1','circle','BLIND_HOLE',diameter=116,source_code='*D1')
    f = feature_from_definition(blind, Vec2(50,60), 200, 200, rotation_deg=360)
    assert f.layer == 'BLIND_HOLE'
    assert f.add_centerline is True
    assert f.source_type == '管孔'
    rect = HoleDefinition('插座盒','rectangle','CUTTING',width=90,height=50)
    r = feature_from_definition(rect, Vec2(100,100), 300, 300, rotation_deg=90)
    assert r.rotation_deg == 90
    assert r.source_type == '插座盒'


def test_load_pipe_catalog_accepts_diameter_symbol_prefix(tmp_path):
    base = tmp_path / '開孔'
    base.mkdir()
    (base / '管孔尺寸清單.csv').write_text('\ufeff圖塊代號,加工孔徑尺寸\n*D1,Ø 116.0000\n', encoding='utf-8')
    defs = load_pipe_catalog(base)
    assert len(defs) == 1
    assert defs[0].diameter == 116.0

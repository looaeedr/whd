import ezdxf
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import feature_surface_from_rect, resolve_surface_features
from ae_engine.sheetmetal_drawing import resolved_features_to_primitives
from ae_engine.hole_catalog import HoleDefinition, feature_from_definition


def test_dxf_profile_preserves_entity_layers(tmp_path):
    path = tmp_path / 'combo.dxf'
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_lwpolyline([(-20,-10),(20,-10),(20,10),(-20,10)], close=True, dxfattribs={'layer':'CUTTING'})
    msp.add_lwpolyline([(-5,-5),(5,-5),(5,5),(-5,5)], close=True, dxfattribs={'layer':'BLIND_HOLE'})
    msp.add_lwpolyline([(-15,0),(15,0),(15,1),(-15,1)], close=True, dxfattribs={'layer':'MARKING'})
    doc.saveas(path)

    definition = HoleDefinition('combo', 'profile', 'FROM_DXF', profile_path=path)
    feature = feature_from_definition(definition, Vec2(100,100), 300, 300, rotation_deg=90)
    resolved = resolve_surface_features(feature_surface_from_rect('s', Vec2(0,0), Vec2(300,300)), [feature], 300, 300)
    primitives = resolved_features_to_primitives(resolved)
    assert {p.layer for p in primitives} >= {'CUTTING','BLIND_HOLE','MARKING'}

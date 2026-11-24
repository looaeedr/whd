from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def test_view_filter_removes_only_operator_sources_without_mutating_original_scene():
    p, q = Vec2(1, 1), Vec2(2, 2)
    automatic = (LinePrimitive(p, q, "MARKING"), CirclePrimitive(p, 2, "MARKING"))
    stock = (LinePrimitive(p, q, "BEND"), CirclePrimitive(q, 3, "CUTTING"),
             CirclePrimitive(q, 2, "BLIND_HOLE"))
    manual = (PolylinePrimitive((p, q), "MARKING", semantic_id="WHD_MANUAL_MARKING_V1"),
              CirclePrimitive(p, 4, "MARKING", source_type="WHD_MANUAL_ROUND_MARKING_V1"))
    original = DrawingScene([*automatic, *stock, *manual])
    shown = api.project_scene_without_operator_marking(original)
    assert tuple(shown.primitives) == (*automatic, *stock)
    assert tuple(original.primitives) == (*automatic, *stock, *manual)
    assert api.project_scene_without_operator_marking(shown) is shown

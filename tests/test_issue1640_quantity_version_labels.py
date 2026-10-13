"""Quantity/assignment workflow must persist the same per-Bay version labels as direct Apply."""
from ae_engine.receiving_hole_candidates import create_candidate
from ae_engine.receiving_inner_door_candidates import create_inner_candidate
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _adapter():
    return ReceivingSetBayAdapter(resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    ))


def test_quantity_allocation_preserves_two_distinct_head_versions_in_2d():
    adapter = _adapter()
    library, v1 = create_candidate(None, "head", [{"tag": "left"}])
    library, v2 = create_candidate(library, "head", [{"tag": "right"}])
    assigned = {(0, 0): v1, (0, 1): v2}
    assert adapter.apply_quantity_configuration(
        "head", library, {v1: 1, v2: 1}, assigned, expected_counts=(2,),
    ) == 2
    row = adapter.layout["sets"][0]
    assert [setting_value(row, bi, "head_version_id") for bi in range(2)] == [v1, v2]
    assert [setting_value(row, bi, "tail_version_id") for bi in range(2)] == [None, None]
    assert setting_value(row, 0, "head_features") == [{"tag": "left"}]
    assert setting_value(row, 1, "head_features") == [{"tag": "right"}]


def test_inner_door_quantity_also_persists_selected_version_per_bay():
    adapter = _adapter()
    library, a = create_inner_candidate(None, {
        "layers": 1, "models": ["A.dxf", ""],
    })
    library, b = create_inner_candidate(library, {
        "layers": 2, "models": ["B.dxf", "C.dxf"],
    })
    assigned = {(0, 0): b, (0, 1): a}
    assert adapter.apply_inner_door_quantity_configuration(
        library, {a: 1, b: 1}, assigned, expected_counts=(2,),
    ) == 2
    row = adapter.layout["sets"][0]
    assert [setting_value(row, i, "inner_door_version_id") for i in range(2)] == [b, a]
    assert [setting_value(row, i, "inner_door_layers") for i in range(2)] == [2, 1]
    assert setting_value(row, 0, "inner_door_models") == ["B.dxf", "C.dxf"]
    assert setting_value(row, 1, "inner_door_models") == ["A.dxf", ""]

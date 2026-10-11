"""#1640: real Bay version identities survive normalization and drive 2D labels."""
import tkinter as tk

import pytest

from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays, normalize_receiving_layout
from ae_engine.receiving_shared_settings import setting_value, validate_setting
from gui_modules.application.receiving_multi_settings_window import paint_connected_bays
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _adapter():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )
    return ReceivingSetBayAdapter(layout)


def test_candidate_version_identity_is_saved_per_real_bay_not_per_dropdown():
    adapter = _adapter()
    payload = [{"tag": "hole-A"}]
    assert adapter.apply_candidate_to_bays(
        "head", 0, (0, 2), payload, version_id="head-v2",
    ) == (0, 2)
    adapter.apply_candidate_to_bays(
        "tail", 0, (1,), [{"tag": "hole-B"}], version_id="tail-v1",
    )
    row = normalize_receiving_layout(adapter.layout)["sets"][0]
    assert [setting_value(row, i, "head_version_id") for i in range(3)] == [
        "head-v2", None, "head-v2",
    ]
    assert [setting_value(row, i, "tail_version_id") for i in range(3)] == [
        None, "tail-v1", None,
    ]
    assert setting_value(row, 1, "head_features") == []
    assert setting_value(row, 0, "head_features") == payload

    # "即時" changes ONLY the explicit version display label.
    adapter.mark_live_version_for_bays("head", 0, (2,))
    row = normalize_receiving_layout(adapter.layout)["sets"][0]
    assert setting_value(row, 0, "head_version_id") == "head-v2"
    assert setting_value(row, 2, "head_version_id") == ""
    assert setting_value(row, 2, "head_features") == payload


def test_inner_door_real_bay_candidate_and_version_label_do_not_touch_other_roles():
    adapter = _adapter()
    adapter.apply_inner_door_candidate_to_bays(
        {"layers": 1, "models": ["A.dxf", ""]},
        0, (1,), version_id="inner-door-v3",
    )
    row = normalize_receiving_layout(adapter.layout)["sets"][0]
    assert setting_value(row, 1, "inner_door_version_id") == "inner-door-v3"
    assert setting_value(row, 1, "inner_door_models") == ["A.dxf", ""]
    assert setting_value(row, 0, "inner_door_version_id") is None
    assert setting_value(row, 1, "head_version_id") is None


@pytest.mark.parametrize("kind,value", [
    ("head_version_id", "inner-door-v1"),
    ("tail_version_id", "head-v2"),
    ("inner_door_version_id", "tail-v1"),
    ("head_version_id", "head-v0"),
    ("tail_version_id", 1),
])
def test_version_identity_has_strict_role_validation(kind, value):
    with pytest.raises(ValueError):
        validate_setting(kind, value)


def test_2d_text_comes_from_actual_saved_bay_identity():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=560, height=320)
        canvas.pack()
        source = (
            {"head": "head-v2", "tail": None, "inner-door": ""},
            {"head": None, "tail": "tail-v3", "inner-door": None},
        )
        paint_connected_bays(canvas, 2, (), version_labels=source)
        assert canvas._receiving_selected_bays == frozenset()
        labels = tuple(
            canvas.itemcget(i, "text")
            for i in canvas.find_withtag("applied_version")
        )
        assert "封頭：版本二" in labels
        assert "內門：即時" in labels
        assert "封尾：版本三" in labels
        paint_connected_bays(canvas, 2, (), version_labels=({}, {}))
        assert not canvas.find_withtag("applied_version")
    finally:
        root.destroy()

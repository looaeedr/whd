from types import SimpleNamespace

import pytest

import gui
import fold_designer_bridge as bridge
from ae_engine.corner_type_ui import (
    CUSTOM_MODEL_NAME,
    is_unknown_model,
    known_model_corner_state,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    with_unknown_model,
)
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CrossCornerMode,
)


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_custom_name_is_user_facing_and_legacy_unknown_name_is_compatible():
    assert CUSTOM_MODEL_NAME == "自訂"
    assert is_unknown_model("自訂")
    assert is_unknown_model("未知類型")
    assert with_unknown_model(["金庫型", "未知類型", "自訂"]) == ["金庫型", "自訂"]


def test_known_model_corner_state_matches_current_fixed_manufacturing_rules():
    state = known_model_corner_state(["head", "tail", "door", "base_plate"])

    head_top = state["head"]["top_left"]
    head_bottom = state["head"]["bottom_left"]
    assert head_top.type_id is CornerTypeId.INSERT_OVERLAY
    assert head_top.amount_t == pytest.approx(1.0)
    assert head_top.secondary_retain_t == pytest.approx(0.5)
    assert head_top.secondary_depth_t == pytest.approx(2.0)
    assert head_bottom.type_id is CornerTypeId.CROSS
    assert head_bottom.cross_mode is CrossCornerMode.EXTRA_CUT
    assert head_bottom.direction is CornerDirection.BOTH
    assert head_bottom.amount_t == pytest.approx(0.5)

    door = state["door"]["top_left"]
    assert door.type_id is CornerTypeId.CROSS
    assert door.cross_mode is CrossCornerMode.RETAIN
    assert door.direction is CornerDirection.WIDTH
    assert door.amount_t == pytest.approx(1.0)

    base = state["base_plate"]["top_left"]
    assert base.type_id is CornerTypeId.CROSS
    assert base.cross_mode is CrossCornerMode.STANDARD


def test_main_gui_switching_known_model_to_custom_copies_current_corner_rules_without_resetting_data():
    app = object.__new__(gui.BoxCalculatorGUI)
    part_keys = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
    app.manual_corner_state = new_manual_corner_state(part_keys)
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(part_keys)
    app.baseline_var = DummyVar("自訂")
    app._baseline_last_value = "金庫型"
    app._fold_designer_baseline_commit_guard = False
    app.refresh_corner_type_panel = lambda: None
    app.update_calculations = lambda: None
    app._door_layout_baseline_cache = {"keep": 1}
    app._box_body_baseline_face_cache = {"keep": 2}

    # Existing editable data must stay as-is when only the model mode changes.
    app.w_var = DummyVar("487")
    app.yl1_var = DummyVar("17")
    app.head_holes = [{"type": "圓孔", "x": 12.0, "y": 34.0, "d1": 8.0}]
    app.surface_features = {"head": [object()]}
    holes_ref = app.head_holes
    feature_ref = app.surface_features["head"]

    app.on_baseline_changed()

    assert app._baseline_last_value == "自訂"
    assert app.w_var.get() == "487"
    assert app.yl1_var.get() == "17"
    assert app.head_holes is holes_ref
    assert app.surface_features["head"] is feature_ref
    assert app.manual_corner_state["head"]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY
    assert app.manual_corner_state["head"]["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT
    assert app.manual_corner_state["door"]["top_left"].cross_mode is CrossCornerMode.RETAIN


def test_bridge_switching_known_model_to_custom_reseeds_from_known_rules_not_old_custom_draft():
    stale_custom = bridge._phase6_selection_to_raw(
        bridge.CornerTypeSelection(bridge.CornerTypeId.INSERT, amount_t=3.0)
    )
    holder = SimpleNamespace(
        baseline_model_var=DummyVar("自訂"),
        _phase6_baseline_last_model="金庫型",
        _baseline_unknown_value="自訂",
        _phase6_baseline_guard=False,
        _phase6_corner_guard=False,
        _phase6_corner_state={
            "head": {key: dict(stale_custom) for key in bridge._CORNER_KEYS},
            "tail": {key: dict(stale_custom) for key in bridge._CORNER_KEYS},
        },
        _phase6_corner_pair_same={
            "head": {"top": True, "bottom": True},
            "tail": {"top": True, "bottom": True},
        },
        _corner_transaction_unknown_state={
            "head": {key: dict(stale_custom) for key in bridge._CORNER_KEYS}
        },
        _corner_transaction_unknown_pairs={"head": {"top": True, "bottom": True}},
        _settings_page_cache={},
        _phase6_input_snapshot={"model": "金庫型"},
        designer_workspace=SimpleNamespace(box_body_structure_state=lambda: {}),
        active_part_key=None,
    )

    bridge._phase6_on_baseline_model_changed(holder)

    top = bridge._phase6_selection_from_raw(holder._phase6_corner_state["head"]["top_left"])
    bottom = bridge._phase6_selection_from_raw(holder._phase6_corner_state["head"]["bottom_left"])
    assert top.type_id is CornerTypeId.INSERT_OVERLAY
    assert top.secondary_retain_t == pytest.approx(0.5)
    assert bottom.type_id is CornerTypeId.CROSS
    assert bottom.cross_mode is CrossCornerMode.EXTRA_CUT
    assert holder._corner_editable is True
    assert holder._phase6_baseline_last_model == "自訂"


def test_bridge_treats_legacy_unknown_text_as_custom_even_when_explicit_name_is_custom():
    holder = SimpleNamespace(_baseline_unknown_value="自訂")
    assert bridge._phase6_is_unknown_baseline(holder, "未知類型")
    assert bridge._phase6_is_unknown_baseline(holder, "自訂")

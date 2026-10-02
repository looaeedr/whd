from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine.corner_type_ui import new_manual_corner_pair_same_state, new_manual_corner_state
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
)
import phase6_settings_center as settings
import fold_designer_bridge as bridge
import gui
from phase6_workspace_controller import Phase6WorkspaceController


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def semantic_state(selection):
    return {
        "head": {
            key: selection for key in ("top_left", "top_right", "bottom_left", "bottom_right")
        }
    }


def test_corner_ini_roundtrip_preserves_semantic_parameters(tmp_path):
    ini = tmp_path / "config.ini"
    ae = SimpleNamespace(INI_PATH=str(ini))
    raw = {
        "head": {
            "top_left": {
                "type_id": "INSERT_OVERLAY",
                "rotation_quadrants": 0,
                "amount_t": 1.25,
                "secondary_retain_t": 0.75,
                "secondary_depth_t": 3.0,
                "direction": "height",
            },
            "top_right": {
                "type_id": "INSERT_OVERLAY",
                "rotation_quadrants": 0,
                "amount_t": 1.25,
                "secondary_retain_t": 0.75,
                "secondary_depth_t": 3.0,
                "direction": "height",
            },
            "bottom_left": {
                "type_id": "CROSS",
                "rotation_quadrants": 0,
                "cross_mode": "extra_cut",
                "direction": "both",
                "amount_t": 0.8,
            },
            "bottom_right": {
                "type_id": "CROSS",
                "rotation_quadrants": 0,
                "cross_mode": "extra_cut",
                "direction": "both",
                "amount_t": 0.8,
            },
        }
    }
    pairs = {"head": {"top": True, "bottom": True}}

    settings.save_corner_defaults_to_ini(ae, raw, pairs, context="head")
    loaded, loaded_pairs = settings.load_corner_defaults_from_ini(ae)

    assert loaded_pairs["head"] == pairs["head"]
    assert loaded["head"]["top_left"]["type_id"] == "INSERT_OVERLAY"
    assert loaded["head"]["top_left"]["amount_t"] == pytest.approx(1.25)
    assert loaded["head"]["top_left"]["secondary_retain_t"] == pytest.approx(0.75)
    assert loaded["head"]["top_left"]["secondary_depth_t"] == pytest.approx(3.0)
    assert loaded["head"]["bottom_left"]["cross_mode"] == "extra_cut"
    assert loaded["head"]["bottom_left"]["direction"] == "both"
    assert loaded["head"]["bottom_left"]["amount_t"] == pytest.approx(0.8)


def test_main_gui_corner_snapshot_preserves_semantic_parameters():
    app = object.__new__(gui.BoxCalculatorGUI)
    app.manual_corner_state = new_manual_corner_state(["head"])
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(["head"])
    app.refresh_corner_type_panel = lambda: None

    selection = CornerTypeSelection(
        CornerTypeId.INSERT_OVERLAY,
        amount_t=1.25,
        secondary_retain_t=0.75,
        secondary_depth_t=3.0,
    )
    app.manual_corner_state["head"]["top_left"] = selection
    snapshot = app._serialize_manual_corner_state()

    assert snapshot["head"]["top_left"]["amount_t"] == pytest.approx(1.25)
    assert snapshot["head"]["top_left"]["secondary_retain_t"] == pytest.approx(0.75)
    assert snapshot["head"]["top_left"]["secondary_depth_t"] == pytest.approx(3.0)

    restored = object.__new__(gui.BoxCalculatorGUI)
    restored.manual_corner_state = new_manual_corner_state(["head"])
    restored.manual_corner_pair_same = new_manual_corner_pair_same_state(["head"])
    restored.refresh_corner_type_panel = lambda: None
    restored._apply_manual_corner_snapshot(snapshot, app.manual_corner_pair_same)
    got = restored.manual_corner_state["head"]["top_left"]
    assert got.type_id is CornerTypeId.INSERT_OVERLAY
    assert got.amount_t == pytest.approx(1.25)
    assert got.secondary_retain_t == pytest.approx(0.75)
    assert got.secondary_depth_t == pytest.approx(3.0)


def test_bridge_state_normalization_keeps_new_semantic_fields():
    holder = SimpleNamespace(
        _phase6_corner_state={
            "head": {
                "top_left": {
                    "type_id": "CROSS",
                    "cross_mode": "retain",
                    "direction": "height",
                    "amount_t": 1.5,
                }
            }
        },
        _phase6_corner_pair_same={"head": {"top": False, "bottom": True}},
    )
    state, pairs = bridge._phase6_ensure_corner_part(holder, "head")
    got = state["top_left"]
    assert got["type_id"] == "CROSS"
    assert got["cross_mode"] == "retain"
    assert got["direction"] == "height"
    assert got["amount_t"] == pytest.approx(1.5)
    assert pairs["top"] is False


def test_box_body_part_spec_receives_head_and_tail_corner_policies():
    app = object.__new__(gui.BoxCalculatorGUI)
    app.workspace_controller = Phase6WorkspaceController()
    app.manual_corner_state = new_manual_corner_state(["head", "tail"])
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(["head", "tail"])
    insert = CornerTypeSelection(CornerTypeId.INSERT, amount_t=1.0)
    overlay = CornerTypeSelection(CornerTypeId.INSERT_OVERLAY)
    for key in app.manual_corner_state["head"]:
        app.manual_corner_state["head"][key] = insert
        app.manual_corner_state["tail"][key] = overlay
    app.baseline_var = DummyVar("未知類型")
    app.surface_features = {"box_body": []}
    app.box_body_face_features = {"left": [], "back": [], "right": []}
    app._baseline_source_model = lambda: None

    spec = app._box_body_part_spec({
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 3.0,
    })
    assert spec.head_corner_policy is not None
    assert spec.tail_corner_policy is not None
    assert spec.head_corner_policy.top_left.type_id is CornerTypeId.INSERT
    assert spec.tail_corner_policy.top_left.type_id is CornerTypeId.INSERT_OVERLAY


def test_new_ui_source_does_not_offer_legacy_rotation_or_c05():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    assert 'C05' not in source
    assert 'values=("0°", "90°")' not in source

def test_main_gui_cross_mode_switch_uses_mode_defaults_not_stale_direction():
    app = object.__new__(gui.BoxCalculatorGUI)
    app.manual_corner_state = new_manual_corner_state(["head"])
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(["head"])
    app.baseline_var = DummyVar("未知類型")
    app.manual_active_corner_var = DummyVar("top")
    app.manual_corner_cross_mode_var = DummyVar("多切")
    app.manual_corner_direction_var = DummyVar("寬")  # stale value from another mode
    app.manual_corner_amount_var = DummyVar("1")
    app.manual_corner_secondary_retain_var = DummyVar("0.5")
    app.manual_corner_secondary_depth_var = DummyVar("2")
    app._manual_corner_param_guard = False
    app._manual_corner_param_unlocked = {"head": True}
    app.refresh_corner_type_panel = lambda: None
    app._notify_fold_designer_corner_state = lambda: None
    app.update_calculations = lambda: None
    app._current_manual_corner_part_key = lambda: "head"

    app.on_manual_corner_mode_changed()
    got = app.manual_corner_state["head"]["top_left"]
    assert got.type_id is CornerTypeId.CROSS
    assert got.cross_mode is CrossCornerMode.EXTRA_CUT
    assert got.direction is CornerDirection.BOTH
    assert got.amount_t == pytest.approx(0.5)

def _make_gui_box_spec_app(head_selection, tail_selection):
    app = object.__new__(gui.BoxCalculatorGUI)
    app.workspace_controller = Phase6WorkspaceController()
    app.manual_corner_state = new_manual_corner_state(["head", "tail"])
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(["head", "tail"])
    for key in app.manual_corner_state["head"]:
        app.manual_corner_state["head"][key] = head_selection
        app.manual_corner_state["tail"][key] = tail_selection
    app.baseline_var = DummyVar("未知類型")
    app.surface_features = {"box_body": []}
    app.box_body_face_features = {"left": [], "back": [], "right": []}
    app._baseline_source_model = lambda: None
    return app


def test_gui_spec_to_manufacturing_api_uses_corner_types_for_real_box_body_height(tmp_path):
    import ezdxf
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    insert = CornerTypeSelection(CornerTypeId.INSERT, amount_t=1.0)
    app = _make_gui_box_spec_app(insert, insert)
    spec = app._box_body_part_spec({
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 3.0,
    })
    out = tmp_path / "box_body_insert.dxf"
    generate_part(spec, out, ManufacturingContext(draw_stock=False))
    doc = ezdxf.readfile(out)
    ys = []
    for ent in doc.modelspace():
        if str(ent.dxf.layer).upper() != "CUTTING":
            continue
        if ent.dxftype() == "LWPOLYLINE":
            ys.extend(float(y) for _x, y, *_ in ent.get_points())
        elif ent.dxftype() == "LINE":
            ys.extend([float(ent.dxf.start.y), float(ent.dxf.end.y)])
    assert ys
    assert max(ys) - min(ys) == pytest.approx(600.0)

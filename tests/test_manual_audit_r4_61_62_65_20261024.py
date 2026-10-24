"""Independent safeguards following manual R4 #61/#62/#64/#65 source review.

Real source code was examined first. These tests prevent a corrected function
from regressing; they do NOT substitute for the manual source audit.
"""
from copy import deepcopy
import math
import pytest

from ae_engine.sheetmetal_geometry_core import CornerTypeSelection, GeometryError
from ae_engine.sheetmetal_four_side_geometry import FourSideFlangeGeometry, _validate_four_side_geometry
from ae_engine.sheetmetal_geometry import EndCapGeometry, calculate_endcap_relief_dimensions
from ae_engine.sheetmetal_strip_geometry import FoldSegment, StripFoldChain, build_strip_outline
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import inner_door_frame_formed_occupation, derive_inner_door_frames
from ae_engine.inner_door_panels import InnerDoorPanelPart, derive_inner_door_panel
from phase6_custom_parts import custom_part_only_change
from phase6_manufacturing_adapter import build_manufacturing_request, build_scene_payload_for_app
from types import SimpleNamespace
from gui_modules.application.fold_designer_manufacturing_projection import (
    _read_live_receiving_snapshot, _query_fold_designer_render_data,
)
from phase6_box_body_structure import (
    BoxBodyStructureType, reconcile_box_body_structure_for_total_w_change,
)


def test_r4_64_existing_width_edit_reconciles_default_and_discarded_inactive_values():
    two = BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    other = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    result = reconcile_box_body_structure_for_total_w_change({
        "active_type": two,
        "configs": {two: {"left_w": 300.0, "right_w": 300.0, "driver": "default"}},
    }, 800.)
    assert result["configs"][two]["left_w"] == 400.
    assert result["configs"][two]["right_w"] == 400.
    result = reconcile_box_body_structure_for_total_w_change({
        "active_type": other,
        "configs": {two: {"left_w": 700., "right_w": 100., "driver": "left"}},
    }, 500.)
    assert result["configs"][two]["left_w"] is None
    assert result["configs"][two]["right_w"] is None


def _custom_snapshot():
    return {
        "available_parts": ["box_body", "custom:1"],
        "custom_parts": {"next_id": 2, "items": {
            "custom:1": {
                "display_name": "外掛板1",
                "fold_axis": "X", "transverse_length": 300.,
                "per_box_count": 1,
            }
        }},
        "part_profiles": {
            "box_body": [{"id": "B1", "len": 20.}],
            "custom:1": [{"id": "C1", "len": 15.}],
        },
        "part_features": {},
        "part_face_features": {},
    }


def test_r4_65_only_custom_part_edits_leave_entire_box_scene_unchanged():
    before = _custom_snapshot()
    after = deepcopy(before)
    after["part_profiles"]["custom:1"][0]["len"] = 30.
    after["part_features"] = None
    after["part_face_features"] = None
    saved_before = deepcopy(before)
    saved_after = deepcopy(after)
    assert custom_part_only_change(before, after) is True
    assert (before, after) == (saved_before, saved_after)  # comparison cannot mutate callers
    after["part_profiles"]["box_body"][0]["len"] = 21.
    assert custom_part_only_change(before, after) is False
    after = deepcopy(before)
    after["custom_parts"]["items"]["custom:1"]["per_box_count"] = 2
    assert custom_part_only_change(before, after) is True
    after = deepcopy(before)
    after["custom_parts"]["items"]["custom:2"] = {"display_name": "new"}
    assert custom_part_only_change(before, after) is False


def test_r4_61_rejects_nonfinite_corner_endcap_fourside_and_strip_source_dimensions():
    for invalid in (True, float("nan"), float("inf")):
        with pytest.raises(GeometryError):
            CornerTypeSelection(type_id="C01", amount_t=invalid)
        with pytest.raises(GeometryError):
            calculate_endcap_relief_dimensions(EndCapGeometry(
                total_width=invalid, total_depth=100.,
                left_fold=15., right_fold=15., top_first_fold=15.,
                fw=25., bottom_fold=15., thickness=1.5,
            ))
        with pytest.raises(GeometryError):
            _validate_four_side_geometry(FourSideFlangeGeometry(
                total_width=300., total_height=400., thickness=invalid,
                left_fold=15., right_fold=15., top_fold=15., bottom_fold=15.,
            ))
        with pytest.raises(GeometryError):
            build_strip_outline(StripFoldChain(
                segments=(FoldSegment("A", 50.), FoldSegment("B", 50.)),
                height=invalid,
            ))


def test_r4_62_dividers_and_inner_door_frames_do_not_make_nan_geometry():
    for bad in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            derive_box_body_dividers(
                [(300., [800.]), (300., [800.])],
                depth=bad, thickness=1.5, layout_scope="box_body",
            )
        with pytest.raises(ValueError):
            inner_door_frame_formed_occupation(bad)
        with pytest.raises(ValueError):
            derive_inner_door_frames(
                "1", spans={"left": 300., "right": 300., "top": 200.},
                thickness=bad,
            )
        with pytest.raises(ValueError):
            derive_inner_door_panel("1", cell_key="0:0", width=200.,
                                    height=300., thickness=bad)
        with pytest.raises(ValueError):
            InnerDoorPanelPart(
                stable_id="inner_door:1:panel", inner_door_id="1", cell_key="0:0",
                width=bad, height=300., thickness=1.5,
                fold_left=19., fold_right=19., fold_top=19., fold_bottom=19.,
            )


def test_r4_62_still_derives_true_frame_web_without_bend_compensation():
    assert inner_door_frame_formed_occupation(2.0) == 50.0
    assert inner_door_frame_formed_occupation(1.5) == 49.0


def test_r4_63_live_fold_designer_app_owns_receiving_authorization():
    live = {"model": "戶外箱", "w": 600., "h": 800., "d": 250., "t": 1.5}
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=live),
        _phase6_input_snapshot={"model": "受電箱", "w": 800., "t": 2.},
    )
    assert _read_live_receiving_snapshot(host) is live
    with pytest.raises(ValueError, match="BASE_FIXING_PLATE"):
        _query_fold_designer_render_data(
            host, "base_plate:fixing_plate:unknown", {})


def test_r4_52_real_box_dimensions_are_owned_by_manufacturing_request():
    seen = []
    def operator_dimensions(key=None):
        seen.append(key)
        return (600., 800., 250.)
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "戶外箱"},
        _settings_values={"t": 1.6},
        _phase6_box_whd={"w": 600., "h": 800., "d": 250.},
        _phase6_corner_state={}, _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        designer_workspace=SimpleNamespace(available_parts=()),
        _phase6_operator_finished_dimensions=operator_dimensions,
    )
    req = build_manufacturing_request(app)
    assert (req.input_snapshot["w"], req.input_snapshot["h"],
            req.input_snapshot["d"], req.input_snapshot["t"]) == (600., 800., 250., 1.6)
    assert req.operator_finished_dimensions == (600., 800., 250.)
    assert "box_body" in seen


def test_receiving_specific_door_and_nfb_owner_survives_secondary_payload_overlay():
    projected = {
        "model": "受電箱", "active_mode": "set_bay",
        "_receiving_runtime_selection": {
            "set_index": 0, "bay_index": 2,
            "set_id": "set1", "bay_id": "bay3",
        },
        "w": 900., "h": 1700., "d": 400., "t": 2.,
        "multi_door_enabled": True,
        "door_layout_columns": [[900., [1100., 600.]]],
        "nfb_config_submitted": False,
    }
    # Root settings can be from a DIFFERENT Bay; these must not steal the
    # part-specific Door cell or NFB identity during actual material creation.
    app = SimpleNamespace(
        _phase6_input_snapshot=projected,
        _settings_values={
            "door_layout_columns": [[800., [1100., 500.]]],
            "nfb_config_submitted": True, "nfb_config": {"layer_count": 2},
            "w": 800., "h": 1600., "d": 350., "t": 2.,
        },
        _phase6_box_whd={"w": 900., "h": 1700., "d": 400.},
        state=SimpleNamespace(profiles_vault={"箱身": ()}, profiles={}),
        designer_workspace=SimpleNamespace(active_part="box_body"),
        _phase6_baseline_initial_model="受電箱",
        _phase6_endcap_fw_state={}, _phase6_endcap_bottom_wrap_state={},
    )
    values = build_scene_payload_for_app(app, "box_body")
    assert values["door_layout_columns"] == [[900., [1100., 600.]]]
    assert values["nfb_config_submitted"] is False
    assert "nfb_config" not in values
    assert (values["w"], values["h"], values["d"]) == (900., 1700., 400.)


@pytest.mark.parametrize("field", [
    "width", "height", "thickness", "fold_left", "fold_right", "fold_top", "fold_bottom",
])
def test_r4_62_saved_inner_door_panel_oversized_numeric_source_fails_closed(field):
    """JSON-valid giant physical dimensions must not escape as OverflowError."""
    data = {
        "width": 723., "height": 900., "thickness": 2.,
        "fold_left": 19., "fold_right": 19., "fold_top": 19., "fold_bottom": 19.,
    }
    data[field] = 10 ** 400
    with pytest.raises(ValueError, match="inner-door panel dimensions must be finite"):
        derive_inner_door_panel("upper", cell_key="0:0", **data)
    with pytest.raises(ValueError, match="inner-door panel dimensions must be finite"):
        InnerDoorPanelPart(
            stable_id="inner_door:upper:panel", inner_door_id="upper",
            cell_key="0:0", **data,
        )
    valid = derive_inner_door_panel(
        "upper", cell_key="0:0", width=723., height=900., thickness=2.,
    )
    assert valid.width == pytest.approx(723.)
    assert valid.unfolded_width == pytest.approx(757.)
    assert valid.fold_left == valid.fold_right == 19.


@pytest.mark.parametrize("source,field", [
    ("thickness", "thickness"),
    ("left", "left"),
    ("right", "right"),
    ("top", "top"),
])
def test_r4_62_saved_inner_door_frame_numeric_overflow_has_typed_error(source, field):
    """Same signed 46/22 frame source, no unhandled float conversion."""
    spans = {"left": 900., "right": 900., "top": 723.}
    t = 2.
    if source == "thickness":
        t = 10 ** 400
        with pytest.raises(ValueError, match="inner-door frame material thickness must be a finite"):
            inner_door_frame_formed_occupation(t)
    else:
        spans[field] = 10 ** 400
    with pytest.raises(ValueError, match="inner-door frame (thickness|span) must be"):
        derive_inner_door_frames("upper", spans=spans, thickness=t)
    assert inner_door_frame_formed_occupation(2.) == pytest.approx(50.)

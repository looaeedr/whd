# -*- coding: utf-8 -*-
"""#2517 Door indicator double-click uses an atomic public Engine position candidate."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
import gui
from ae_engine import manufacturing_api as api
from ae_engine import door_indicator_position_transactions as source
from ae_engine import sheetmetal_features as owner
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = owner.DoorIndicatorContext(
    finished_width=800.0, finished_height=1000.0,
    left_fold=18.0, bottom_fold=20.0,
)
GROUPS = (2,)
FRAME = DoorFrameEdges()
MEASURE = dict(frame_width=62.0, thickness=2.0, gap_w=3.5, gap_h=3.5)


def _layout(offset=Vec2(0.0, 0.0)):
    return owner.resolve_door_indicator_layout(CONTEXT, GROUPS, offset)


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _host(*, xy, box_distance):
    events = []
    def dialog(old_x, old_y):
        events.append(("dialog", old_x, old_y))
        return xy
    host = SimpleNamespace(
        last_door_draw_params=dict(
            indicator_context=CONTEXT, indicator_groups=GROUPS,
            indicator_layout=_layout(), frame_edges=FRAME,
        ),
        t_var=_var("2"), fw_z_var=_var("62"),
        is_box_dist_var=_var(box_distance),
        door_gap_w_var=_var("3.5"), door_gap_h_var=_var("3.5"),
        door_indicator_offset_x=41.0, door_indicator_offset_y=-23.0,
        ask_xy_dialog=dialog,
        draw_preview=lambda: events.append("draw"),
    )
    return host, events


def test_public_engine_ports_and_root_exports_have_single_owner():
    assert api.project_operator_door_indicator_position is source.project_operator_door_indicator_position
    assert api.propose_operator_door_indicator_offset_candidate is source.propose_operator_door_indicator_offset_candidate
    for name in ("project_operator_door_indicator_position",
                 "propose_operator_door_indicator_offset_candidate"):
        assert getattr(ae_engine, name) is getattr(api, name)
        assert name in ae_engine.__all__


@pytest.mark.parametrize("box_distance", (False, True))
@pytest.mark.parametrize("x_shift,y_shift", ((0., 0.), (12.25, -7.5), (-22.0, 18.75)))
def test_engine_canonical_measure_and_offset_match_direct_original_owner(box_distance, x_shift, y_shift):
    layout = _layout()
    original = deepcopy((CONTEXT, GROUPS, layout))
    kwargs = dict(MEASURE, use_box_distance=box_distance, frame_edges=FRAME)
    read = api.project_operator_door_indicator_position(layout, CONTEXT, **kwargs)
    assert read == owner.measure_door_indicator_position(layout, CONTEXT, **kwargs)
    target_x = read.distance_x + x_shift
    target_y = read.distance_y + y_shift
    candidate = api.propose_operator_door_indicator_offset_candidate(
        CONTEXT, GROUPS, x_distance=target_x, y_distance=target_y, **kwargs,
    )
    expected = owner.door_indicator_offset_for_position(
        CONTEXT, GROUPS, x_distance=target_x, y_distance=target_y, **kwargs,
    )
    assert candidate == expected
    assert (CONTEXT, GROUPS, layout) == original
    assert api.normalize_fold_designer_indicator_offsets(candidate.x, candidate.y) == (
        candidate.x, candidate.y,
    )
    # Simulate persisted source -> JSON Save -> Reload -> canonical physical hole positions.
    snapshot = json.loads(json.dumps({"door_indicator_offset": [candidate.x, candidate.y]}))
    restored = Vec2(*snapshot["door_indicator_offset"])
    assert owner.resolve_door_indicator_layout(CONTEXT, GROUPS, restored).features == (
        owner.resolve_door_indicator_layout(CONTEXT, GROUPS, candidate).features
    )


@pytest.mark.parametrize("box_distance", (False, True))
def test_gui_double_click_matches_engine_candidate_and_updates_two_axes(box_distance):
    kwargs = dict(MEASURE, use_box_distance=box_distance, frame_edges=FRAME)
    position = owner.measure_door_indicator_position(_layout(), CONTEXT, **kwargs)
    x, y = position.distance_x + 11.5, position.distance_y - 8.25
    host, events = _host(xy=(x, y), box_distance=box_distance)
    expected = owner.door_indicator_offset_for_position(
        CONTEXT, GROUPS, x_distance=x, y_distance=y, **kwargs,
    )
    gui.Phase6ApplicationHost.on_double_click_indicator(host)
    assert (host.door_indicator_offset_x, host.door_indicator_offset_y) == (
        expected.x, expected.y
    )
    assert events == [("dialog", position.distance_x, position.distance_y), "draw"]


@pytest.mark.parametrize("bad", ("NaN", "Infinity", float("-inf"), True, "oops"))
@pytest.mark.parametrize("axis", (0, 1))
def test_invalid_operator_distance_rejects_before_gui_state_mutation(bad, axis):
    xy = (bad, 15.0) if axis == 0 else (15.0, bad)
    host, events = _host(xy=xy, box_distance=False)
    old = (host.door_indicator_offset_x, host.door_indicator_offset_y)
    with pytest.raises(ValueError):
        gui.Phase6ApplicationHost.on_double_click_indicator(host)
    assert (host.door_indicator_offset_x, host.door_indicator_offset_y) == old
    assert len(events) == 1 and events[0][0] == "dialog"


def test_cancelled_indicator_edit_does_not_commit_or_redraw():
    host, events = _host(xy=(None, 12.), box_distance=False)
    gui.Phase6ApplicationHost.on_double_click_indicator(host)
    assert (host.door_indicator_offset_x, host.door_indicator_offset_y) == (41.0, -23.0)
    assert len(events) == 1


@pytest.mark.parametrize("overrides", (
    {"frame_width": float("nan")},
    {"thickness": 0.0},
    {"thickness": True},
    {"gap_w": -1.0},
    {"gap_h": float("inf")},
    {"use_box_distance": "true"},
))
def test_bad_physical_source_never_returns_position_candidate(overrides):
    kwargs = dict(MEASURE, use_box_distance=False, frame_edges=FRAME)
    kwargs.update(overrides)
    with pytest.raises(ValueError):
        api.propose_operator_door_indicator_offset_candidate(
            CONTEXT, GROUPS, x_distance=10.0, y_distance=15.0, **kwargs,
        )


@pytest.mark.parametrize("groups", ((True,), (0,), ("bad",), ()))
def test_invalid_physical_lamp_groups_cannot_submit_any_offset(groups):
    with pytest.raises(ValueError):
        api.propose_operator_door_indicator_offset_candidate(
            CONTEXT, groups, x_distance=10., y_distance=20.,
            use_box_distance=False, frame_edges=FRAME, **MEASURE,
        )


def test_live_gui_does_not_call_internal_door_position_owner():
    source_text = (ROOT / "gui.py").read_text(encoding="utf-8")
    assert "    measure_door_indicator_position," not in source_text
    assert "    door_indicator_offset_for_position," not in source_text
    assert "manufacturing_api.project_operator_door_indicator_position(" in source_text
    assert "manufacturing_api.propose_operator_door_indicator_offset_candidate(" in source_text

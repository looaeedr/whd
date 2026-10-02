from __future__ import annotations

from dataclasses import replace

import pytest

import ae_engine.ae as ae


def test_contract_exposes_typed_policy_and_context_accepts_injection():
    from ae_engine.contracts import ManufacturingContext, ManufacturingPolicy

    policy = ManufacturingPolicy(
        default_thickness=2.3,
        frame_width=30.0,
        door_gap_w=3.0,
        door_gap_h=4.0,
        door_fold_left=19.0,
        door_fold_right=20.0,
        door_fold_top=21.0,
        door_fold_bottom=22.0,
        indicator_box_fold=49.0,
        indicator_small_door_fold=19.0,
    )
    ctx = ManufacturingContext(policy=policy)

    assert ctx.policy is policy
    assert policy.frame_width == 30.0
    assert policy.indicator_box_fold == 49.0


def test_resolve_policy_reads_wrapped_ae_defaults_only_at_api_boundary(monkeypatch):
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import resolve_policy

    monkeypatch.setattr(ae, "T", 2.7, raising=False)
    monkeypatch.setattr(ae, "FW", 31.0, raising=False)
    monkeypatch.setattr(ae, "door_gap_w_def", 3.1, raising=False)
    monkeypatch.setattr(ae, "door_gap_h_def", 3.2, raising=False)
    monkeypatch.setattr(ae, "door_fold_left_def", 18.1, raising=False)
    monkeypatch.setattr(ae, "door_fold_right_def", 18.2, raising=False)
    monkeypatch.setattr(ae, "door_fold_top_def", 18.3, raising=False)
    monkeypatch.setattr(ae, "door_fold_bottom_def", 18.4, raising=False)
    monkeypatch.setattr(ae, "indicator_box_fold_def", 48.5, raising=False)

    policy = resolve_policy(ManufacturingContext())
    assert policy.default_thickness == pytest.approx(2.7)
    assert policy.frame_width == pytest.approx(31.0)
    assert policy.door_gap_w == pytest.approx(3.1)
    assert policy.door_gap_h == pytest.approx(3.2)
    assert policy.door_fold_left == pytest.approx(18.1)
    assert policy.door_fold_right == pytest.approx(18.2)
    assert policy.door_fold_top == pytest.approx(18.3)
    assert policy.door_fold_bottom == pytest.approx(18.4)
    assert policy.indicator_box_fold == pytest.approx(48.5)
    assert policy.indicator_small_door_fold == pytest.approx(19.0)


def test_resolve_policy_prefers_explicit_context_policy(monkeypatch):
    from ae_engine.contracts import ManufacturingContext, ManufacturingPolicy
    from ae_engine.manufacturing_api import resolve_policy

    explicit = ManufacturingPolicy(
        default_thickness=1.6,
        frame_width=26.0,
        door_gap_w=1.0,
        door_gap_h=2.0,
        door_fold_left=15.0,
        door_fold_right=16.0,
        door_fold_top=17.0,
        door_fold_bottom=18.0,
        indicator_box_fold=47.0,
        indicator_small_door_fold=20.0,
    )
    monkeypatch.setattr(ae, "FW", 999.0, raising=False)

    assert resolve_policy(ManufacturingContext(policy=explicit)) is explicit


def test_policy_helpers_match_existing_finished_face_and_indicator_geometry():
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext, ManufacturingPolicy
    from ae_engine.manufacturing_api import (
        door_finished_face_size,
        indicator_box_opening_feature,
        indicator_small_door_spec,
    )
    from ae_engine.sheetmetal_features import feature_finished_point
    from ae_engine.sheetmetal_geometry import Vec2

    policy = ManufacturingPolicy(
        default_thickness=2.0,
        frame_width=25.0,
        door_gap_w=2.0,
        door_gap_h=2.0,
        door_fold_left=19.0,
        door_fold_right=19.0,
        door_fold_top=19.0,
        door_fold_bottom=19.0,
        indicator_box_fold=49.0,
        indicator_small_door_fold=19.0,
    )
    ctx = ManufacturingContext(policy=policy)
    door = DoorPartSpec(width=500, height=600, thickness=2.0, frame_width=25.0)

    finished = door_finished_face_size(door, ctx)
    expected = ae.calculate_door_finished_size(500, 600, 25.0, 2.0, 2.0, 2.0)
    assert finished == pytest.approx(expected)

    center = Vec2(200.0, 300.0)
    opening = indicator_box_opening_feature((2, 3), thickness=2.0, center=center, context=ctx)
    data = ae.get_indicator_box_data((2, 3), 2.0)
    expected_w = float(data.params["w"]) - 2.0 * 49.0 - 2.0
    expected_h = float(data.params["h"]) - 2.0 * 49.0 - 2.0
    assert opening.width == pytest.approx(expected_w)
    assert opening.height == pytest.approx(expected_h)
    assert feature_finished_point(opening, 999.0, 999.0) == center

    small = indicator_small_door_spec((2, 3), thickness=2.0, context=ctx)
    assert small.model_name is None
    assert small.frame_width == pytest.approx(25.0)
    assert small.gap_w == pytest.approx(2.0)
    assert small.gap_h == pytest.approx(2.0)
    assert (small.fold_left, small.fold_right, small.fold_top, small.fold_bottom) == (19.0, 19.0, 19.0, 19.0)
    # Existing bridge formula: box blank -> outside finished face -> inner opening,
    # then subtract the explicit small-door gap per side.  Do not reuse the
    # regular Door gap as the small-door gap oracle.
    opening_w = float(data.params["w"]) - 2.0 * policy.indicator_box_fold - 2.0
    opening_h = float(data.params["h"]) - 2.0 * policy.indicator_box_fold - 2.0
    finished_w = opening_w - 2.0 * policy.indicator_small_door_gap
    finished_h = opening_h - 2.0 * policy.indicator_small_door_gap
    expected_source_w = finished_w + (policy.frame_width + 2.0 * 2.0) * 2.0 + policy.door_gap_w * 2.0
    expected_source_h = finished_h + (policy.frame_width + 2.0 * 2.0) * 2.0 + policy.door_gap_h * 2.0
    assert (small.width, small.height) == pytest.approx((expected_source_w, expected_source_h))


def test_direct_indicator_center_offset_is_owned_by_api():
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext, ManufacturingPolicy
    from ae_engine.manufacturing_api import door_indicator_offset_for_finished_center, door_finished_face_size
    from ae_engine.sheetmetal_geometry import Vec2

    policy = ManufacturingPolicy(
        default_thickness=2.0, frame_width=25.0,
        door_gap_w=2.0, door_gap_h=2.0,
        door_fold_left=19.0, door_fold_right=19.0,
        door_fold_top=19.0, door_fold_bottom=19.0,
        indicator_box_fold=49.0, indicator_small_door_fold=19.0,
    )
    ctx = ManufacturingContext(policy=policy)
    spec = DoorPartSpec(width=700, height=650, thickness=2.0, frame_width=25.0,
                        gap_w=2.0, gap_h=2.0,
                        fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0)
    finished_w, finished_h = door_finished_face_size(spec, ctx)
    desired = Vec2(finished_w / 2.0 + 7.0, finished_h / 2.0 - 11.0)

    # For groups with g_max > 1 the existing AE default local center is
    # finished_center + (-18, -25). Desired - default gives the exporter offset.
    offset = door_indicator_offset_for_finished_center(spec, (2,), desired, ctx)
    assert offset == Vec2(25.0, 14.0)

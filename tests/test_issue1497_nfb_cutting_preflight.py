# -*- coding: utf-8 -*-
"""#1497 source-centered, fail-closed NFB inner-Door material preflight."""
from dataclasses import replace

import pytest

from ae_engine.inner_door_panels import derive_inner_door_panel
from ae_engine.receiving_nfb_cutting_preflight import (
    BLOCKED,
    PREVIEW_ONLY,
    NfbExistingCuttingClaim,
    NfbUpperOpeningRequest,
    preflight_nfb_inner_door_opening,
    preflight_nfb_inner_door_batch,
)


CENTER = (3771.967234, 2608.809181)
SOURCE_SHA = "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
PROFILE_150 = (
    (CENTER[0] - 28.5, CENTER[1] - 48),
    (CENTER[0] + 28.5, CENTER[1] - 48),
    (CENTER[0] + 28.5, CENTER[1] + 48),
    (CENTER[0] - 28.5, CENTER[1] + 48),
)


def _panel():
    return derive_inner_door_panel(
        "upper", cell_key="0:0", width=689, height=1041, thickness=2,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
    )


def _source(**updates):
    args = dict(
        physical_hole_id="nfb:upper:layer:1:unit:1",
        target_part_id="inner_door:upper:panel",
        source_sha256=SOURCE_SHA,
        source_handle="585",
        source_region="UPPER",
        source_aci=150,
        source_outline_xy=PROFILE_150,
        source_center_xy=CENTER,
        source_profile_closed=True,
        source_bulges=(0.0, 0.0, 0.0, 0.0),
        rotation_deg=0,
        # These values demonstrate geometry only. They are *not* a
        # manufacturing-certified X/X_rule revision for this model.
        uv_center_x=None,
        uv_center_y=563.5,
        x_rule_revision=None,
        y_rule_revision="WHD-RECEIVING-NFB-Y-1100-V1",
        model_filename="400_140X257_107.dxf",
    )
    args.update(updates)
    return NfbUpperOpeningRequest(**args)


def test_unresolved_x_never_generates_a_fake_center_or_manufacturable_hole():
    panel = _panel()
    assert (panel.unfolded_width, panel.unfolded_height) == (723, 1075)
    result = preflight_nfb_inner_door_opening(panel, _source())
    assert result.status == BLOCKED
    assert "OPEN_X_NOT_CERTIFIED" in result.diagnostics
    assert result.preview_outline_uv_xy == ()
    assert result.manufacturing_ready is False
    assert result.source_handle == "585"


@pytest.mark.parametrize("angle,span", [
    (0, (57, 96)), (90, (96, 57)), (180, (57, 96)), (270, (96, 57)),
])
def test_explicit_x_with_stated_revision_only_provides_preview_not_cutting(angle, span):
    panel = _panel()
    p = _source(
        uv_center_x=361.5, uv_center_y=563.5,
        x_rule_revision="SOURCE_W800_X_SHADOW_NOT_CERTIFIED",
        rotation_deg=angle,
    )
    result = preflight_nfb_inner_door_opening(panel, p)
    assert result.status == PREVIEW_ONLY
    assert result.diagnostics == ("MANUFACTURING_CAPABILITY_NOT_REGISTERED",)
    points = result.preview_outline_uv_xy
    xs, ys = [x for x, y in points], [y for x, y in points]
    assert max(xs) - min(xs) == pytest.approx(span[0])
    assert max(ys) - min(ys) == pytest.approx(span[1])
    assert (max(xs) + min(xs)) / 2 == pytest.approx(361.5)
    assert (max(ys) + min(ys)) / 2 == pytest.approx(563.5)
    assert result.manufacturing_ready is False


def test_source_requires_real_upper_150_and_correct_stable_door_part():
    panel = _panel()
    for kwargs, reason in [
        ({"target_part_id": "inner_door:other:panel"}, "TARGET_PART_MISMATCH"),
        ({"uv_center_y": None, "y_rule_revision": None}, "OPEN_Y_NOT_CERTIFIED"),
        ({"model_filename": ""}, "INDEXED_MODEL_FILENAME_UNRESOLVED"),
    ]:
        output = preflight_nfb_inner_door_opening(panel, _source(**kwargs))
        assert output.status == BLOCKED and reason in output.diagnostics
    for kw in (
        {"source_region": "LOWER"},
        {"source_aci": 3},
        {"source_aci": 30},
    ):
        with pytest.raises(ValueError, match="upper Color 150"):
            preflight_nfb_inner_door_opening(panel, _source(**kw))
    for kw in (
        {"source_handle": ""},
        {"source_sha256": "bad"},
        {"source_center_xy": (0.0, 0.0)},
        {"source_outline_xy": PROFILE_150[:3]},
        {"source_outline_xy": ((0.0, 0.0), (1.0, 2.0), (1.0, 3.0), (0.0, 2.0))},
        {"rotation_deg": 45},
        {"source_profile_closed": False},
        {"source_bulges": (0.0, 0.2, 0.0, 0.0)},
        {"source_bulges": ()},
        {"source_outline_xy": (
            PROFILE_150[0], PROFILE_150[2],
            PROFILE_150[1], PROFILE_150[3],
        )},
    ):
        with pytest.raises(ValueError):
            preflight_nfb_inner_door_opening(panel, _source(**kw))


@pytest.mark.parametrize("x,y,angle", [
    (20.0, 563.5, 0), (703, 563.5, 0),
    (361.5, 20.0, 0), (361.5, 1055.0, 0),
    (40.0, 100.0, 90),
])
def test_folded_flange_or_outer_cutting_area_cannot_host_cutting(x, y, angle):
    p = _source(uv_center_x=x, uv_center_y=y,
                x_rule_revision="SHADOW", rotation_deg=angle)
    res = preflight_nfb_inner_door_opening(_panel(), p)
    assert res.status == BLOCKED
    assert "OPENING_OUTSIDE_FINISHED_DOOR_CORE" in res.diagnostics


def test_legacy_same_physical_hole_is_not_cut_again_and_collision_blocks():
    panel = _panel()
    request = _source(uv_center_x=361.5, uv_center_y=563.5,
                      x_rule_revision="SHADOW")
    old = NfbExistingCuttingClaim(
        physical_hole_id=request.physical_hole_id,
        part_id=panel.stable_id,
        outline_uv_xy=((340, 530), (383, 530), (383, 596), (340, 596)),
    )
    report = preflight_nfb_inner_door_opening(panel, request, existing_claims=(old,))
    assert report.status == BLOCKED
    assert "LEGACY_PHYSICAL_HOLE_ALREADY_OWNED" in report.diagnostics
    assert "LEGACY_CUTTING_FOOTPRINT_COLLISION" in report.diagnostics
    # Same geometry on a *different* physical part is not duplicate ownership.
    unrelated = replace(old, part_id="inner_door:lower:panel")
    preview = preflight_nfb_inner_door_opening(
        panel, request, existing_claims=(unrelated,))
    assert preview.status == PREVIEW_ONLY
    # An overlap on the same part blocks even when the legacy ID differs.
    overlap = replace(old, physical_hole_id="legacy:user-hole:1")
    blocked = preflight_nfb_inner_door_opening(
        panel, request, existing_claims=(overlap,))
    assert "LEGACY_CUTTING_FOOTPRINT_COLLISION" in blocked.diagnostics


def test_preflight_never_changes_existing_inner_door_finalscene_or_dxf():
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    panel = _panel()
    baseline = build_inner_door_panel_render_data(panel)
    before = baseline.scene.primitives
    request = _source(uv_center_x=361.5, x_rule_revision="SHADOW")
    preflight_nfb_inner_door_opening(panel, request)
    after = build_inner_door_panel_render_data(panel)
    assert after.scene.primitives == before
    assert after.metadata == baseline.metadata
    cutouts = [p for p in after.scene.primitives
               if isinstance(p, PolylinePrimitive)
               and p.closed and p.layer.upper() == "CUTTING"]
    assert len(cutouts) == 1
    x = [point.x for point in cutouts[0].points]
    y = [point.y for point in cutouts[0].points]
    assert max(x) - min(x) == pytest.approx(723)
    assert max(y) - min(y) == pytest.approx(1075)


def test_two_independent_upper_units_require_unique_physical_claims_and_no_overlap():
    panel = _panel()
    one = _source(
        uv_center_x=220, uv_center_y=563.5,
        x_rule_revision="SHADOW",
    )
    two = replace(
        one, physical_hole_id="nfb:upper:layer:1:unit:2",
        uv_center_x=500,
    )
    batch = preflight_nfb_inner_door_batch(panel, (one, two))
    assert batch.status == PREVIEW_ONLY
    assert len(batch.items) == 2
    assert batch.manufacturing_ready is False
    assert len(batch.items[0].preview_outline_uv_xy) == 4
    assert len(batch.items[1].preview_outline_uv_xy) == 4
    repeated = replace(two, physical_hole_id=one.physical_hole_id)
    denied = preflight_nfb_inner_door_batch(panel, (one, repeated))
    assert denied.status == BLOCKED
    assert "DUPLICATE_NEW_NFB_PHYSICAL_HOLE_OWNER" in denied.diagnostics
    colliding = replace(two, uv_center_x=220)
    denied_overlap = preflight_nfb_inner_door_batch(panel, (one, colliding))
    assert denied_overlap.status == BLOCKED
    assert "NEW_NFB_CUTTING_FOOTPRINT_COLLISION" in denied_overlap.diagnostics


def test_q16_invalid_model_change_blocks_whole_batch_without_moving_other_hole():
    panel = _panel()
    original = _source(
        uv_center_x=361.5, uv_center_y=563.5,
        x_rule_revision="SHADOW",
    )
    other = replace(
        original, physical_hole_id="nfb:upper:layer:2:unit:1",
        uv_center_x=560, uv_center_y=823.5,
    )
    initial = preflight_nfb_inner_door_batch(panel, (original, other))
    assert initial.status == PREVIEW_ONLY
    # Replacing only 'other' with an out-of-core placement must NOT
    # move 'original' or apply half of the batch.
    illegal = replace(other, uv_center_y=1040)
    denied = preflight_nfb_inner_door_batch(panel, (original, illegal))
    assert denied.status == BLOCKED
    assert "OPENING_OUTSIDE_FINISHED_DOOR_CORE" in denied.diagnostics
    assert denied.items[0].preview_outline_uv_xy == initial.items[0].preview_outline_uv_xy
    assert denied.manufacturing_ready is False
    assert preflight_nfb_inner_door_batch(panel, ()).diagnostics == (
        "NO_NEW_NFB_CUTTING",
    )

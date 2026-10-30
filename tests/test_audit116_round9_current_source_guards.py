"""Current-localX focused witnesses for audit116 Round 9 source guards.

Do not port obsolete Round 9 fold signs or claim that preview = MFG-2.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ae_engine.receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_nfb_pad_preview_cache import pad_preview_source_fingerprint


@pytest.mark.parametrize(
    ("source", "invalid"),
    [
        ("w", True),
        ("w", float("nan")),
        ("t", False),
        ("t", float("inf")),
        ("h", float("-inf")),
        ("base_plate_bend", 0.0),
        ("base_plate_bend", float("nan")),
    ],
)
def test_r9_3d_base_profiles_fail_closed_on_invalid_physical_dimensions(
    source, invalid,
):
    snapshot = {"w": 800.0, "t": 2.0}
    physical = {"h": 240.0, "base_plate_bend": 23.0}
    (snapshot if source in snapshot else physical)[source] = invalid
    # Deliberately incomplete *other* fields: the guard must run before
    # invoking a real manufacturing source adapter with invalid dimensions.
    with pytest.raises(ValueError, match="positive finite"):
        receiving_base_plate_3d_profiles(snapshot, physical)


@pytest.mark.parametrize(
    ("field", "invalid", "message"),
    [
        ("w", True, "NONFINITE_SOURCE_DIMENSIONS"),
        ("t", float("nan"), "NONFINITE_SOURCE_DIMENSIONS"),
        ("base_plate_shrink_left", float("inf"), "NONFINITE_SOURCE_DIMENSIONS"),
        ("base_plate_bend", False, "NONFINITE_SOURCE_DIMENSIONS"),
        ("receiving_nfb_depth_pair_mm", (True, 72.0), "INVALID_NFB_DEPTH_PAIR"),
        ("receiving_nfb_depth_pair_mm", (107.0, float("inf")), "INVALID_NFB_DEPTH_PAIR"),
        ("receiving_nfb_depth_pair_mm", (107.0,), "INVALID_NFB_DEPTH_PAIR"),
    ],
)
def test_r9_true_base_skin_source_rejects_corrupt_inputs_before_geometry(
    field, invalid, message,
):
    snapshot = {"w": 800.0, "t": 2.0}
    physical = {
        "h": 240.0,
        "base_plate_shrink_top": 0.0,
        "base_plate_shrink_bottom": 0.0,
        "base_plate_shrink_left": 0.0,
        "base_plate_shrink_right": 0.0,
        "base_plate_bend": 23.0,
        "receiving_bend_pattern": "CENTER",
        "receiving_nfb_depth_pair_mm": (107.0, 72.0),
    }
    (snapshot if field in snapshot else physical)[field] = invalid
    with pytest.raises(ValueError, match=message):
        receiving_base_actual_local_nfb_skins(snapshot, physical)


def test_r9_pad_preview_key_changes_with_placement_rotation_and_offset():
    render = SimpleNamespace(
        material=SimpleNamespace(is_empty=False, wkb=b"source-material"),
        fold_guides=(), unfolded_topology=None, metadata={"source": "current"},
    )

    def part(*, placement="set-1", rotation=(0, 0, 0), offset=(0, 0, 0)):
        return SimpleNamespace(
            part_key="base_plate",
            placement=placement,
            rotation=rotation,
            offset=offset,
            render_data=render,
        )

    source = {"model": "受電箱"}
    base = pad_preview_source_fingerprint(source, (part(),))
    assert base == pad_preview_source_fingerprint(source, (part(),))
    assert base != pad_preview_source_fingerprint(
        source, (part(placement="set-2"),)
    )
    assert base != pad_preview_source_fingerprint(
        source, (part(rotation=(0, 0, 90)),)
    )
    assert base != pad_preview_source_fingerprint(
        source, (part(offset=(0, 0, 5)),)
    )


@pytest.mark.parametrize("invalid_mode", [[], ["set_bay"], {}, {"active_mode": "quantity"}])
def test_r9_unhashable_mode_is_rejected_with_stable_contract(invalid_mode):
    from phase6_receiving_modes import ReceivingModeSession, fresh_receiving_mode

    with pytest.raises(ValueError, match="不合法的受電箱操作模式"):
        ReceivingModeSession._check_mode(invalid_mode)
    with pytest.raises(ValueError, match="不合法的受電箱操作模式"):
        fresh_receiving_mode(invalid_mode, {"w": 800, "h": 1600, "d": 350})

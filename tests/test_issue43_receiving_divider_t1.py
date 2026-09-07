from __future__ import annotations

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.door_dividers import derive_box_body_dividers


def _divider(*, fw: float = 29.0):
    snapshot = receiving.apply_family_defaults({})
    parts = derive_box_body_dividers(
        tuple((float(row[0]), tuple(float(v) for v in row[1])) for row in snapshot["door_layout_columns"]),
        depth=float(snapshot["d"]),
        thickness=float(snapshot.get("t", 2.0)),
        frame_width=float(fw),
        layout_scope=str(snapshot["door_layout_scope"]),
        handle_edges=dict(snapshot.get("door_handle_edges") or {}),
        model_name="受電箱",
    )
    assert len(parts) == 1
    return parts[0]


def test_r1_receiving_divider_default_is_four_segment_18_fw_106_17():
    divider = _divider(fw=29.0)
    assert tuple(abs(v) for v in divider.signed_fold_chain) == pytest.approx(
        (18.0, 29.0, 106.0, 17.0)
    )
    assert divider.material_lengths == pytest.approx((16.0, 25.0, 102.0, 15.0))
    assert divider.formed_core_depth == pytest.approx(106.0)
    assert divider.core_segment_index == 2
    assert divider.span == pytest.approx(796.0)


def test_r5_receiving_divider_fw_is_live_family_authority():
    default = _divider(fw=29.0)
    wider = _divider(fw=31.0)
    assert tuple(abs(v) for v in default.signed_fold_chain) == pytest.approx(
        (18.0, 29.0, 106.0, 17.0)
    )
    assert tuple(abs(v) for v in wider.signed_fold_chain) == pytest.approx(
        (18.0, 31.0, 106.0, 17.0)
    )
    assert wider.material_lengths == pytest.approx((16.0, 27.0, 102.0, 15.0))
    assert sum(float(row.length) for row in wider.fold_profile[: wider.core_segment_index]) == pytest.approx(43.0)

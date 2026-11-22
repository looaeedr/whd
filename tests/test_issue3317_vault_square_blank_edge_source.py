# -*- coding: utf-8 -*-
"""#3317: Vault's source square uses the BLANK left/bottom datum, never Y BEND.

The original WHD "封頭尾.dxf" is read by the real baseline-stretch Engine.
Only the Engine's pre-existing VaultEndCapFeaturePolicy and live advanced
settings may position the fixed square. No synthetic hole masking or V edits.
"""
from dataclasses import replace

import pytest

from ae_engine import ae
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _stretched(lower_fold):
    return ae.get_stretched_end_cap_data(
        "金庫型", 620., 600., 185., 2., 25., True,
        target_fold_left=15., target_fold_right=15.,
        target_fold_top=16., target_fold_bottom=lower_fold,
    )


def _physical_square(scene):
    closed = tuple(p for p in scene.primitives
                   if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
                   and p.closed and len(p.points) == 4)
    assert len(closed) == 1, "baseline square must be unique"
    p = closed[0]
    return (min(v.x for v in p.points), min(v.y for v in p.points),
            max(v.x for v in p.points), max(v.y for v in p.points))


def test_vault_real_baseline_square_unchanged_when_lower_fold_is_48():
    policy = ae.VAULT_ENDCAP_FEATURE_POLICY
    expected = (
        policy.square_hole_origin.x,
        policy.square_hole_origin.y,
        policy.square_hole_origin.x + policy.square_hole_size.x,
        policy.square_hole_origin.y + policy.square_hole_size.y,
    )
    fifteen = _stretched(15.)
    forty_eight = _stretched(48.)
    assert fifteen.params["ybottom1"] == pytest.approx(15.)
    assert forty_eight.params["ybottom1"] == pytest.approx(48.)
    assert forty_eight.params["total_depth"] == pytest.approx(268.)
    assert _physical_square(fifteen.scene) == pytest.approx(expected)
    assert _physical_square(forty_eight.scene) == pytest.approx(expected)
    # WHD's documented default is (3,18)-(7,22), never (3,51)-(7,55).
    if (policy.square_hole_origin == Vec2(3., 18.)
            and policy.square_hole_size == Vec2(4., 4.)):
        assert _physical_square(forty_eight.scene) == pytest.approx((3., 18., 7., 22.))


def test_stretched_fixed_square_uses_live_advanced_settings_not_old_fold_map(monkeypatch):
    before = ae.VAULT_ENDCAP_FEATURE_POLICY
    moved = replace(before, square_hole_origin=Vec2(9.25, 26.75),
                    square_hole_size=Vec2(5.5, 3.25))
    monkeypatch.setattr(ae, "VAULT_ENDCAP_FEATURE_POLICY", moved)
    new = _stretched(48.)
    assert _physical_square(new.scene) == pytest.approx((9.25, 26.75, 14.75, 30.))
    # Fold and mother geometry still come from the same actual DXF/Factory.
    assert new.params["ybottom1"] == pytest.approx(48.)
    assert new.params["total_depth"] == pytest.approx(268.)
    assert all(p.layer != "STOCK" for p in new.scene.primitives)

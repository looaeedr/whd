# -*- coding: utf-8 -*-
"""#3317 Vault factory square-hole origin is the blank left/bottom datum.

The existing advanced-settings policy, never Y bend-proximity mapping,
owns this fixed hole. These are source/preview checks, not machining release.
"""
from dataclasses import replace

import pytest

from ae_engine import ae
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import Vec2


def _baseline_square_bbox(scene, expected):
    matches = []
    for p in scene.primitives:
        if not (isinstance(p, PolylinePrimitive)
                and p.layer == "CUTTING" and p.closed and len(p.points) == 4):
            continue
        x = [v.x for v in p.points]
        y = [v.y for v in p.points]
        bbox = (min(x), min(y), max(x), max(y))
        if all(abs(a - b) <= 1e-7 for a, b in zip(bbox, expected)):
            matches.append(p)
    assert len(matches) == 1, f"VAULT_FIXED_SQUARE_NOT_UNIQUE: {expected}"
    return matches[0]


def _stretched_vault_tail(bottom):
    return ae.get_stretched_end_cap_data(
        "金庫型", 620., 600., 185., 2., 25.,
        is_tail=True, target_fold_left=15., target_fold_right=15.,
        target_fold_bottom=bottom, target_fold_top=16.,
    )


@pytest.mark.parametrize("bottom", (15., 48.))
def test_vault_baseline_square_keeps_true_sheet_bottom_datum(bottom):
    policy = ae.VAULT_ENDCAP_FEATURE_POLICY
    data = _stretched_vault_tail(bottom)
    o = policy.square_hole_origin
    wh = policy.square_hole_size
    _baseline_square_bbox(
        data.scene, (o.x, o.y, o.x + wh.x, o.y + wh.y)
    )
    assert data.params["ybottom1"] == pytest.approx(bottom)
    assert data.params["total_width"] == pytest.approx(642.)
    assert data.params["total_depth"] == pytest.approx(220. + bottom)
    # The old nearest-fold mapping had shifted the same square up by
    # bottom-15 (to y51..55 for bottom=48); that is not its physical datum.
    if bottom == 48.:
        wrong_y = o.y + (48. - 15.)
        assert not any(
            isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
            and p.closed and len(p.points) == 4
            and abs(min(v.y for v in p.points) - wrong_y) <= 1e-7
            and abs(min(v.x for v in p.points) - o.x) <= 1e-7
            for p in data.scene.primitives
        )


def test_advanced_vault_square_settings_are_live_without_hardcoding(monkeypatch):
    original = ae.VAULT_ENDCAP_FEATURE_POLICY
    altered = replace(
        original,
        square_hole_origin=Vec2(
            original.square_hole_origin.x + 1.25,
            original.square_hole_origin.y + 2.5,
        ),
        square_hole_size=Vec2(
            original.square_hole_size.x + 0.5,
            original.square_hole_size.y + 0.75,
        ),
    )
    monkeypatch.setattr(ae, "VAULT_ENDCAP_FEATURE_POLICY", altered)
    data = _stretched_vault_tail(48.)
    _baseline_square_bbox(
        data.scene,
        (
            altered.square_hole_origin.x, altered.square_hole_origin.y,
            altered.square_hole_origin.x + altered.square_hole_size.x,
            altered.square_hole_origin.y + altered.square_hole_size.y,
        ),
    )
    # Restore before the other source tests (monkeypatch also performs this).
    monkeypatch.setattr(ae, "VAULT_ENDCAP_FEATURE_POLICY", original)

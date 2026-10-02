# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import Polygon, box

from ae_engine import manufacturing_api
from ae_engine.certified_relief_registry import lookup_certified_endcap_relief
from ae_engine.contracts import EndCapPartSpec, FoldProfileSegment
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    FourCornerTypePolicy,
)
from ae_engine.sheetmetal_part_adapters import build_unknown_endcap_result


def _overlay_policy():
    bottom = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    top = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    return FourCornerTypePolicy(bottom, bottom, top, top, 25.0)


def _parts(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return list(geom.geoms)


def test_flat_x_overlay_has_no_x_bends_and_top_cut_uses_nominal_material_fold_basis():
    result = build_unknown_endcap_result(
        w=400, d=250, t=2, fw=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        corner_policy=_overlay_policy(), x_topology="flat",
        box_body_formed_fw_left=29, box_body_formed_fw_right=29,
    )

    assert result.topology.left_fold == pytest.approx(0.0)
    assert result.topology.right_fold == pytest.approx(0.0)
    assert {bend.name for bend in result.bends}.isdisjoint({"left", "right"})

    material = Polygon([(p.x, p.y) for p in result.outline])
    removed = box(0, 0, result.width, result.height).difference(material)
    top_left = max(
        (part for part in _parts(removed) if part.bounds[0] <= 1e-8),
        key=lambda part: part.bounds[3],
    )
    minx, miny, maxx, maxy = map(float, top_left.bounds)
    assert maxx - minx == pytest.approx(40.0)
    assert maxy - miny == pytest.approx(39.0)


def test_flat_x_overlay_bottom_extra_cut_uses_zero_physical_x_fold_basis():
    bottom = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction="width",
        amount_t=1.5,
    )
    top = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, 25.0)

    result = build_unknown_endcap_result(
        w=400, d=250, t=2, fw=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        corner_policy=policy, x_topology="flat",
        box_body_formed_fw_left=29, box_body_formed_fw_right=29,
    )

    material = Polygon([(p.x, p.y) for p in result.outline])
    minx, miny, maxx, maxy = map(float, material.bounds)

    # OVERLAY has no physical X side bends, so the lower CROSS relief must not
    # inherit the legacy/nominal 15 mm side-fold basis.  1.5T at T=2 is 3 mm
    # per side, leaving 400 - 3 - 3 = 394 mm.
    y = miny + 1.0
    lower = material.intersection(box(minx, miny, maxx, y))
    assert lower.bounds[0] == pytest.approx(3.0)
    assert lower.bounds[2] == pytest.approx(397.0)
    assert lower.bounds[2] - lower.bounds[0] == pytest.approx(394.0)

    # The upper OVERLAY relief uses the nominal material fold evidence even
    # though the physical X bend is absent: side_fold(15) + FW(25) = 40 mm.
    y = maxy - 1.0
    upper = material.intersection(box(minx, y, maxx, maxy))
    assert upper.bounds[0] == pytest.approx(40.0)
    assert upper.bounds[2] == pytest.approx(360.0)
    assert upper.bounds[2] - upper.bounds[0] == pytest.approx(320.0)


def test_certified_overlay_registry_uses_standard_material_fold_basis():
    spec = EndCapPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        is_tail=True,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        fold_profile_x=(FoldProfileSegment(400, phase6_key="endcap_w_flat"),),
        fold_profile_y=(
            FoldProfileSegment(15, angle=-90, phase6_key="ybottom1"),
            FoldProfileSegment(244, angle=-90, phase6_key="endcap_d_core", core="D-T"),
            FoldProfileSegment(25, angle=-90, phase6_key="fw"),
            FoldProfileSegment(16, phase6_key="ytop1"),
        ),
        corner_policy=_overlay_policy(),
    )
    render = manufacturing_api.build_part_render_data(spec)
    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.OVERLAY,
        endcap_render_data=render,
        box_body_x_profile=(
            {"len": 15, "angle": 90, "phase6_key": "zl1"},
            {"len": 20, "angle": -90, "phase6_key": "zl2"},
            {"len": 25, "angle": -90, "phase6_key": "fw_left"},
            {"len": 246, "angle": -90, "phase6_key": "d_left", "core": "D"},
            {"len": 396, "angle": -90, "phase6_key": "w", "core": "W"},
            {"len": 246, "angle": -90, "phase6_key": "d_right", "core": "D"},
            {"len": 25, "angle": -90, "phase6_key": "fw_right"},
            {"len": 20, "angle": 90, "phase6_key": "zr2"},
            {"len": 15, "phase6_key": "zr1"},
        ),
        endcap_x_profile=({"len": 400, "phase6_key": "endcap_w_flat"},),
        endcap_y_profile=(
            {"len": 15, "angle": -90, "phase6_key": "ybottom1"},
            {"len": 244, "angle": -90, "phase6_key": "endcap_d_core", "core": "D-T"},
            {"len": 25, "angle": -90, "phase6_key": "fw"},
            {"len": 16, "phase6_key": "ytop1"},
        ),
        sheet_thickness=2,
    )
    assert result is not None
    assert result.rule_id == "ENDCAP_TOP_OVERLAY_STANDARD_V1"
    for relief in result.corner_reliefs:
        assert relief.measurement.primary_u == pytest.approx(40.0)
        assert relief.measurement.primary_v == pytest.approx(39.0)
        assert relief.measurement.secondary_u == pytest.approx(15.0)
        assert relief.measurement.secondary_depth == pytest.approx(2.0)

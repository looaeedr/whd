# -*- coding: utf-8 -*-
"""Canonical CI hard gate: 3D operator OUTSIDE -> material/BEND -> OUTSIDE.

The 3D operator's outside lengths/angles are the authoritative input.  They can
be converted both ways, but rendered assembly results never overwrite the
input.  No bend-allowance/k-factor model is introduced by this dimensional
contract: only real adjacent folds and sheet thickness T participate.
"""
from __future__ import annotations

from itertools import accumulate

import pytest

from ae_engine.assembly_geometry_folded_mesh import _profile_geometry
from ae_engine.sheetmetal_strip_geometry import (
    FoldSegment, StripFoldChain, build_strip_bend_segments,
)
from phase6_fold_profiles import (
    _outside_profile_to_material,
    _has_real_bend,
    apply_outside_dimension_compensation,
    engine_segment_length_to_ui,
)


def _operator_profile(outside, turns):
    assert len(turns) == len(outside) - 1
    return [
        {"len": float(value), **({"angle": float(turns[i])} if i < len(turns) else {})}
        for i, value in enumerate(outside)
    ]


@pytest.mark.parametrize(
    "outside, turns, expected_stock, expected_bends",
    [
        ((24, 24, 29, 350, 18), (-90, 90, -90, -90),
         (22, 20, 25, 346, 16), (22, 42, 67, 413)),
        ((17, 29, 17), (-90, 90), (15, 25, 15), (15, 40)),
        # Remove one physical fold: the adjacent stock changes, not outside.
        ((17, 29, 17), (-90, 0), (15, 27, 17), (15,)),
        ((17, 29, 17), (0, 0), (17, 29, 17), ()),
        ((16, 346, 22), (90, -90), (14, 342, 20), (14, 356)),
    ],
)
def test_outside_material_bend_roundtrip_is_identical_in_2d_and_3d(
    outside, turns, expected_stock, expected_bends
):
    thickness = 2.0
    source = _operator_profile(outside, turns)
    before = [dict(item) for item in source]

    material = _outside_profile_to_material(source, thickness, preserve_precision=True)
    assert source == before, "Derived manufacturing must not mutate operator 3D input"
    lengths = tuple(float(row["len"]) for row in material)
    assert lengths == pytest.approx(expected_stock)
    assert [row.get("angle") for row in material] == [row.get("angle") for row in source]

    # 3D folded-mesh geometry must use exactly the same material prefix sums.
    boundaries, _folded = _profile_geometry(material)
    all_stations = (0.0, *tuple(accumulate(lengths)))
    assert boundaries == pytest.approx(all_stations)

    actual_bends = tuple(
        boundaries[i + 1]
        for i, row in enumerate(material[:-1])
        if _has_real_bend(row)
    )
    assert actual_bends == pytest.approx(expected_bends)

    # Reconstruct outside from the 3D/2D flat boundaries + original topology/T.
    recovered_stock = tuple(boundaries[i + 1] - boundaries[i] for i in range(len(material)))
    assert recovered_stock == pytest.approx(expected_stock)
    copied = apply_outside_dimension_compensation(
        [{**row, "len": length} for row, length in zip(material, recovered_stock)],
        thickness,
    )
    restored = tuple(
        float(row["len"]) + float(row.get("ui_len_add", 0.0))
        for row in copied
    )
    assert restored == pytest.approx(outside)
    assert tuple(engine_segment_length_to_ui(row) for row in copied) == outside

    # For an uninterrupted chain each fold station must also equal DXF/2D BEND.
    if all(_has_real_bend(row) for row in material[:-1]):
        chain = StripFoldChain(
            tuple(FoldSegment(str(i), length) for i, length in enumerate(lengths)),
            100.0,
        )
        dxf_bends = tuple(b.p1.x for b in build_strip_bend_segments(chain))
        assert dxf_bends == pytest.approx(actual_bends)


def test_changing_fold_topology_recomputes_stock_and_bends_not_3d_outside():
    source = _operator_profile((24, 24, 29), (-90, -90))
    original = _outside_profile_to_material(source, 2.0, preserve_precision=True)
    without_last = _operator_profile((24, 24, 29), (-90, 0))
    updated = _outside_profile_to_material(without_last, 2.0, preserve_precision=True)
    assert tuple(row["len"] for row in original) == (22.0, 20.0, 27.0)
    assert tuple(row["len"] for row in updated) == (22.0, 22.0, 29.0)
    assert tuple(
        engine_segment_length_to_ui(row) for row in updated
    ) == (24, 24, 29)
    assert tuple(
        p for i, p in enumerate(_profile_geometry(updated)[0][1:-1])
        if _has_real_bend(updated[i])
    ) == (22.0,)


def test_identical_outside_different_thickness_produces_different_stations():
    source = _operator_profile((24, 29, 18), (-90, 90))
    t1 = _outside_profile_to_material(source, 1.0, preserve_precision=True)
    t2 = _outside_profile_to_material(source, 2.0, preserve_precision=True)
    assert tuple(x["len"] for x in t1) == (23.0, 27.0, 17.0)
    assert tuple(x["len"] for x in t2) == (22.0, 25.0, 16.0)
    for rows, thickness in ((t1, 1), (t2, 2)):
        restored = apply_outside_dimension_compensation(
            [dict(row) for row in rows], thickness
        )
        assert tuple(
            float(row["len"]) + float(row.get("ui_len_add", 0))
            for row in restored
        ) == (24, 29, 18)

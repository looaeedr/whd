# -*- coding: utf-8 -*-
"""DXF-backed receiving large-ear physical mounting dimensions.

Independent acceptance numbers were measured from the ORIGINAL user drawing
受電耳朵.dxf and plate drawing 受電箱底板.dxf; these are not computed by the
policy under test. The source-file fingerprints are in the manufacturing spec.
"""
from __future__ import annotations

import pytest

from ae_engine.receiving_weld_ear_policy import resolve_receiving_large_weld_ear_fit


@pytest.mark.parametrize(
    "row_pitch,expected_slot_pair",
    [(210.0, (0, 3)), (140.0, (1, 2))],
)
def test_big_receiving_weld_ear_mates_either_bottom_plate(row_pitch, expected_slot_pair):
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800.0,
        box_side_thickness_mm=2.0,
        fixing_hole_pitch_x_mm=670.0,
        fixing_hole_pitch_y_mm=row_pitch,
    )
    # Independent DXF facts: 670 assembled transverse fixing centers,
    # single large ear longitudinal slot positions 0/35/175/210 and 86 mm
    # from the nominated welding edge to the slot center. Ear stock is T3.
    assert fit.fixing_center_from_outer_side_mm == pytest.approx(65.0)
    assert fit.fixing_center_from_inside_skin_mm == pytest.approx(63.0)
    assert fit.ear_weld_edge_to_hole_center_mm == pytest.approx(86.0)
    assert fit.nominal_fold_from_weld_edge_mm == pytest.approx(23.0)
    assert fit.ear_thickness_mm == pytest.approx(3.0)
    assert fit.slot_pair_indexes == expected_slot_pair


def test_ear_65_mm_is_outside_datum_not_bend_or_inside_skin_dimension():
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800.0, box_side_thickness_mm=2.0,
        fixing_hole_pitch_x_mm=670.0, fixing_hole_pitch_y_mm=210.0,
    )
    assert fit.fixing_center_from_outer_side_mm - fit.fixing_center_from_inside_skin_mm == 2
    assert fit.nominal_fold_from_weld_edge_mm != 65
    assert fit.nominal_fold_from_weld_edge_mm != 63
    assert fit.nominal_fold_from_weld_edge_mm + fit.fixing_center_from_inside_skin_mm == 86


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"box_outer_width_mm": 750.0}, "W=800"),
        ({"box_side_thickness_mm": -2.0}, "positive"),
        ({"box_side_thickness_mm": 3.0}, "T=2"),
        ({"fixing_hole_pitch_x_mm": 732.0}, "ASSEMBLED.*670"),
        ({"fixing_hole_pitch_y_mm": 200.0}, "210 or 140"),
        ({"ear_thickness_mm": 2.0}, "T=3"),
        ({"ear_weld_edge_to_hole_center_mm": 85.0}, "86"),
    ],
)
def test_weld_ear_unverified_dimensions_fail_closed(kwargs, reason):
    source = {
        "box_outer_width_mm": 800.0,
        "box_side_thickness_mm": 2.0,
        "fixing_hole_pitch_x_mm": 670.0,
        "fixing_hole_pitch_y_mm": 140.0,
    }
    source.update(kwargs)
    with pytest.raises(ValueError, match=reason):
        resolve_receiving_large_weld_ear_fit(**source)


def test_bottom_fixing_plate_part_identity_and_original_2d_source():
    from ae_engine.receiving_base_fixing_plate import (
        receiving_base_fixing_plate_previews, MANUFACTURING_STATUS,
    )
    snapshot = {"model": "受電箱", "w": 800, "t": 2,
                "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"}}
    parts = receiving_base_fixing_plate_previews(
        snapshot, available_parts=("box_body", "base_plate"),
    )
    assert [p.part_id for p in parts] == [
        "base_plate:fixing_plate:left", "base_plate:fixing_plate:right",
    ]
    assert [p.display_name for p in parts] == [
        "底板固定片（左）", "底板固定片（右）",
    ]
    for part in parts:
        assert part.parent_part_id == "base_plate"
        assert part.stock_thickness_mm == 3
        assert part.nominal_source_outline_mm == (256, 105)
        assert part.nominal_source_slot_centers_mm == (
            (23, 86), (58, 86), (198, 86), (233, 86),
        )
        assert part.source_slot_size_mm == (25, 11)
        assert part.source_top_corner_radius_mm == 5
        assert part.nominal_fold_from_weld_edge_mm == 23
        assert part.applicable_slot_pair_indexes == (0, 3)
        assert part.manufacturing_status == MANUFACTURING_STATUS
        assert part.manufacturing_ready is False
    # Same physical fixing plate, only an alternative hole pair for center base.
    center = receiving_base_fixing_plate_previews(
        {**snapshot, "receiving_base_plate": {"pattern": "CENTER_DOUBLE_SIDE_FOLD"}},
        available_parts=("box_body", "base_plate"),
    )
    assert [p.part_id for p in center] == [p.part_id for p in parts]
    assert all(p.applicable_slot_pair_indexes == (1, 2) for p in center)


@pytest.mark.parametrize("snapshot,available", [
    ({"model": "金庫型", "w": 800, "t": 2}, ("base_plate",)),
    ({"model": "受電箱", "w": 750, "t": 2}, ("base_plate",)),
    ({"model": "受電箱", "w": 800, "t": 3}, ("base_plate",)),
    ({"model": "受電箱", "w": 800, "t": 2}, ("box_body",)),
])
def test_bottom_fixing_plate_not_invented_for_other_families_or_unknown_geometry(
    snapshot, available,
):
    from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
    assert receiving_base_fixing_plate_previews(snapshot, available_parts=available) == ()


def test_fixing_plate_unconfigured_base_does_not_invent_mounting_pair():
    from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
    plates = receiving_base_fixing_plate_previews(
        {"model": "受電箱", "w": 800, "t": 2},
        available_parts=("box_body", "base_plate"),
    )
    assert len(plates) == 2
    assert all(p.applicable_slot_pair_indexes is None for p in plates)
    assert all(not p.manufacturing_ready for p in plates)

def test_original_source_large_and_small_are_actual_independent_cutting_geometry():
    from math import pi
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
        LARGE_PATTERN, SMALL_PATTERN, source_pattern,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive, LinePrimitive
    big = build_fixing_plate_source_render_data("base_plate:fixing_plate:left")
    small = build_fixing_plate_source_render_data(
        "base_plate:fixing_plate:small_source", source_kind="small",
    )
    assert source_pattern("large") is LARGE_PATTERN
    assert source_pattern("small") is SMALL_PATTERN
    assert big.metadata["stable_id"] == "base_plate:fixing_plate:left"
    assert big.metadata["thickness"] == 3
    assert big.unfolded_topology.width == 256
    assert big.unfolded_topology.height == 105
    assert small.unfolded_topology.width == 90
    assert small.unfolded_topology.height == 90
    assert len([p for p in big.scene.primitives if isinstance(p, PolylinePrimitive)]) == 5
    assert len([p for p in small.scene.primitives if isinstance(p, PolylinePrimitive)]) == 3
    assert len([p for p in small.scene.primitives if isinstance(p, LinePrimitive)]) == 1
    assert all(p.layer != "BEND" for p in small.scene.primitives)
    assert small.metadata["weld_z_verified"] is False
    assert big.metadata["formed_geometry_verified"] is False
    # Source native arcs are tessellated at sub-hundredth-mm error, but the
    # same *material* is returned to 2D, 3D and the independent DXF sink.
    expected_big = (256 * 105 - 2 * (25 - pi*25/4)
                    - 4 * (14*11 + pi * (5.5**2)))
    expected_small = (90 * 90 - 2 * (25 - pi*25/4)
                      - 2 * (19*11 + pi * (5.5**2)))
    assert big.material.area == pytest.approx(expected_big, abs=0.15)
    assert small.material.area == pytest.approx(expected_small, abs=0.15)


def test_fixing_plate_source_dxf_is_independent_and_reopens(tmp_path):
    from ae_engine.receiving_base_fixing_plate_geometry import (
        save_independent_source_flat_dxf,
    )
    import ezdxf
    for part_id in ("base_plate:fixing_plate:left", "base_plate:fixing_plate:right",
                    "base_plate:fixing_plate:small_source"):
        filepath = tmp_path / (part_id.rsplit(":", 1)[1] + ".dxf")
        actual = save_independent_source_flat_dxf(part_id, filepath)
        assert str(actual) == str(filepath)
        source = ezdxf.readfile(filepath)
        assert len(source.modelspace()) >= 3
        with pytest.raises(FileExistsError):
            save_independent_source_flat_dxf(part_id, filepath)


def test_fixing_plate_derived_selector_and_parent_stable_ids():
    from phase6_part_navigation import project_hierarchy, operator_part_selector_keys, operator_part_label
    from phase6_designer_workspace import Phase6DesignerWorkspace
    parts=("box_body","base_plate","base_plate:fixing_plate:left","base_plate:fixing_plate:right","head")
    rows=project_hierarchy(parts)
    assert tuple((r.part_key,r.parent_key) for r in rows) == (
        ("box_body",None),("base_plate",None),
        ("base_plate:fixing_plate:left","base_plate"),
        ("base_plate:fixing_plate:right","base_plate"),("head",None),
    )
    assert operator_part_selector_keys(parts)==("box_body","base_plate","head")
    assert operator_part_label("base_plate:fixing_plate:left")=="底板固定片（左）"
    assert operator_part_label("base_plate:fixing_plate:right")=="底板固定片（右）"
    ws=Phase6DesignerWorkspace.from_snapshot(
        {"model":"受電箱","existing_parts":("box_body","base_plate")})
    assert "base_plate:fixing_plate:left" not in ws.available_parts
    ws.sync_derived_parts(namespace="base_plate:fixing_plate:", part_profiles={
        "base_plate:fixing_plate:left": {"X":[{"len":256}], "Y":[{"len":105}]},
        "base_plate:fixing_plate:right":{"X":[{"len":256}], "Y":[{"len":105}]},
    })
    assert set(ws.available_parts) >= {"base_plate:fixing_plate:left","base_plate:fixing_plate:right"}
    ws.sync_derived_parts(namespace="base_plate:fixing_plate:",part_profiles={})
    assert all(not p.startswith("base_plate:fixing_plate:") for p in ws.available_parts)


def test_independent_unformed_fixing_plates_do_not_poison_whole_cabinet_export():
    from types import SimpleNamespace
    from ae_engine.manufacturing_export import resolved_physical_render_parts
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
    )
    left_id="base_plate:fixing_plate:left"
    source=build_fixing_plate_source_render_data(left_id)
    real_base=SimpleNamespace(part_key="base_plate",
                              placement="offset",render_data=SimpleNamespace(metadata={}))
    source_part=SimpleNamespace(part_key=left_id,
                                placement="standalone",render_data=source)
    rows=resolved_physical_render_parts(
        SimpleNamespace(parts=(real_base,source_part)))
    assert [key for key,_ in rows]==["base_plate"]
    # The separate flat source is still a complete geometry object; it is
    # excluded only from the *whole-cabinet* production DXF inventory.
    assert source.material.area > 0
    assert source.metadata["quantity_of_this_part"] == 1
    # A forged unsupported part with the same key must not disappear silently.
    forged=SimpleNamespace(part_key=left_id,placement="offset",render_data=source)
    assert resolved_physical_render_parts(SimpleNamespace(parts=(forged,))) == (
        (left_id,source),
    )

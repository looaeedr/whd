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


@pytest.mark.parametrize(
    "pattern,chosen_pair,expected_y",
    [
        ("LEFT_FLAT_SIDE", (0, 3), (-105.0, 105.0)),
        ("RIGHT_FLAT_SIDE", (0, 3), (-105.0, 105.0)),
        ("CENTER_DOUBLE_SIDE_FOLD", (1, 2), (-70.0, 70.0)),
    ],
)
def test_original_large_fixing_plate_left_right_xy_mates_both_base_patterns(
    pattern, chosen_pair, expected_y,
):
    from ae_engine.receiving_base_fixing_plate_mating import (
        resolve_base_fixing_pair_xy_mating,
    )
    snapshot = {"model": "受電箱", "w": 800.0, "t": 2.0,
                "receiving_base_plate": {"pattern": pattern}}
    left, right = resolve_base_fixing_pair_xy_mating(snapshot)
    assert left.part_id == "base_plate:fixing_plate:left"
    assert right.part_id == "base_plate:fixing_plate:right"
    assert (left.inside_skin_world_x_mm, right.inside_skin_world_x_mm) == (-398.0, 398.0)
    assert (left.selected_fixing_world_x_mm, right.selected_fixing_world_x_mm) == (-335.0, 335.0)
    assert left.slot_world_y_mm == right.slot_world_y_mm == (-105.0, -70.0, 70.0, 105.0)
    assert left.selected_slot_indexes == right.selected_slot_indexes == chosen_pair
    assert left.selected_fixing_world_y_mm == right.selected_fixing_world_y_mm == expected_y
    assert right.selected_fixing_world_x_mm - left.selected_fixing_world_x_mm == 670.0
    assert left.selected_fixing_world_y_mm[1] - left.selected_fixing_world_y_mm[0] == (
        140.0 if chosen_pair == (1, 2) else 210.0
    )
    for part in (left, right):
        assert part.nominal_fold_from_weld_edge_mm == 23.0
        assert part.source_weld_edge_to_slot_center_mm == 86.0
        assert part.factory_bend_compensation_mm == 0.0
        assert part.xy_mating_proven is True
        assert part.manufacturing_approved is False
        assert not part.bend_line_confirmed
        assert not part.formed_direction_confirmed
        assert not part.weld_z_confirmed


def test_unconfigured_base_does_not_guess_xy_mating_or_enable_mfg():
    from ae_engine.receiving_base_fixing_plate_mating import (
        resolve_base_fixing_pair_xy_mating,
    )
    from ae_engine.receiving_base_fixing_plate_geometry import build_fixing_plate_source_render_data
    snapshot = {"model": "受電箱", "w": 800, "t": 2}
    with pytest.raises(ValueError, match="CONFIGURED_BASE_PATTERN"):
        resolve_base_fixing_pair_xy_mating(snapshot)
    flat = build_fixing_plate_source_render_data(
        "base_plate:fixing_plate:left", snapshot=snapshot,
    )
    assert flat.metadata["xy_mating_proven"] is False
    assert flat.metadata["nominal_base_fixing_hole_world_y_mm"] == ()
    assert flat.metadata["formed_geometry_verified"] is False
    assert flat.metadata["factory_bend_compensation_required"] is False


@pytest.mark.parametrize("bad", [
    {"model": "金庫型", "w": 800.0, "t": 2.0},
    {"model": "受電箱", "w": 750.0, "t": 2.0},
    {"model": "受電箱", "w": 800.0, "t": 3.0},
])
def test_fixing_plate_x_y_mating_rejects_unproven_cabinets(bad):
    from ae_engine.receiving_base_fixing_plate_mating import (
        resolve_base_fixing_pair_xy_mating,
    )
    from ae_engine.receiving_base_fixing_plate_geometry import build_fixing_plate_source_render_data
    snap = {**bad, "receiving_base_plate": {"pattern": "CENTER_DOUBLE_SIDE_FOLD"}}
    with pytest.raises(ValueError, match="W800_T2"):
        resolve_base_fixing_pair_xy_mating(snap)
    with pytest.raises(ValueError, match="CABINET_MISMATCH"):
        build_fixing_plate_source_render_data(
            "base_plate:fixing_plate:left", snapshot=snap,
        )


def test_correct_mating_evidence_flows_into_physical_render_data():
    from ae_engine.receiving_base_fixing_plate_geometry import build_fixing_plate_source_render_data
    s = {"model": "受電箱", "w": 800.0, "t": 2.0,
         "receiving_base_plate": {"pattern": "CENTER_DOUBLE_SIDE_FOLD"}}
    left = build_fixing_plate_source_render_data("base_plate:fixing_plate:left", snapshot=s)
    right = build_fixing_plate_source_render_data("base_plate:fixing_plate:right", snapshot=s)
    assert left.metadata["nominal_weld_inside_skin_x_mm"] == -398.0
    assert left.metadata["nominal_base_fixing_hole_world_x_mm"] == -335.0
    assert right.metadata["nominal_weld_inside_skin_x_mm"] == 398.0
    assert right.metadata["nominal_base_fixing_hole_world_x_mm"] == 335.0
    assert left.metadata["nominal_base_fixing_hole_world_y_mm"] == (-70.0,70.0)
    assert right.metadata["nominal_slot_pair_indexes"] == (1,2)
    assert all(part.metadata["xy_mating_proven"] for part in (left, right))
    assert all(not part.metadata["manufacturing_ready"] for part in (left, right))
    assert all(part.metadata["thickness"] == 3.0 for part in (left, right))


@pytest.mark.parametrize("box_count", [1, 3])
def test_bom_counts_both_independent_fixing_plates_without_unsafe_export(box_count):
    from types import SimpleNamespace
    from ae_engine.manufacturing_quantity import (
        ResolvedQuantityVersion, resolved_quantity_physical_demands,
    )
    from ae_engine.manufacturing_export import resolved_physical_render_parts
    from ae_engine.receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
    )
    snapshot = {"model": "受電箱", "w": 800, "t": 2,
                "receiving_base_plate": {"pattern": "LEFT_FLAT_SIDE"}}
    parts = tuple(
        SimpleNamespace(
            part_key="base_plate:fixing_plate:" + side,
            placement="standalone",
            render_data=build_fixing_plate_source_render_data(
                "base_plate:fixing_plate:" + side, snapshot=snapshot,
            ),
        )
        for side in ("left", "right")
    )
    geometry = SimpleNamespace(parts=parts)
    # The all-material BOM must not use the *production output* whitelist.
    bom = resolved_quantity_physical_demands(
        (ResolvedQuantityVersion("v1", box_count, geometry),),
    )
    assert {item.physical_id: item.quantity for item in bom} == {
        "base_plate:fixing_plate:left": box_count,
        "base_plate:fixing_plate:right": box_count,
    }
    assert sum(item.quantity for item in bom) == 2 * box_count
    assert all(item.render_data.metadata["thickness"] == 3 for item in bom)
    # Formal full-cabinet export remains closed for unformed fixing plates.
    assert resolved_physical_render_parts(geometry) == ()
    all_parts = resolved_physical_render_parts(
        geometry, include_unreleased_source_flats=True,
    )
    assert {key for key, _ in all_parts} == {item.physical_id for item in bom}

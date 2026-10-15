# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

import pytest
from shapely.affinity import translate
from shapely.geometry import Polygon, Point, box as shapely_box
from shapely.ops import unary_union
import fold_designer_bridge as bridge
from ae_engine.assembly_collision import (
    _barycentric_world_to_flat,
    _triangle_pair_crossing_segment,
)
from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot


def _piece_bands(body):
    result = {}
    for piece in tuple(body.render_data.pieces or ()):
        key = f"box_body:{piece.role}"
        cursor = 0.0
        bands = []
        for row in tuple(piece.fold_profile or ()):
            end = cursor + float(row.length)
            bands.append((str(row.phase6_key or ""), cursor, end))
            cursor = end
        result[key] = tuple(bands)
    return result


def _crossing_sides_by_source_band(world, divider_key, source_key, bands, *, tolerance=1e-7):
    """Independent validation: classify source Fold bands by physical skin crossings.

    This intentionally does not call the production Divider relief classifier.
    A source Fold band is a true-thickness penetration witness only when both
    physical skins of that source band cross the retained Divider physical skins.
    """
    targets = tuple(world["mapped_skin_triangles_by_part"][divider_key])
    sources = tuple(world["mapped_skin_triangles_by_part"][source_key])
    result = {}
    for name, u0, u1 in bands:
        sides = defaultdict(int)
        divider_points = []
        for source in sources:
            source_u = [float(point[0]) for point in source.flat]
            if max(source_u) < u0 - tolerance or min(source_u) > u1 + tolerance:
                continue
            for target in targets:
                crossing = _triangle_pair_crossing_segment(
                    source.world, target.world, tolerance=tolerance
                )
                if crossing is None:
                    continue
                try:
                    source_uv = [
                        _barycentric_world_to_flat(point, source.world, source.flat)
                        for point in crossing
                    ]
                    target_uv = [
                        _barycentric_world_to_flat(point, target.world, target.flat)
                        for point in crossing
                    ]
                except ValueError:
                    continue
                midpoint_u = sum(float(point[0]) for point in source_uv) / len(source_uv)
                if midpoint_u < u0 - 1e-5 or midpoint_u > u1 + 1e-5:
                    continue
                sides[int(source.side)] += 1
                divider_points.extend(target_uv)
        bounds = None if not divider_points else (
            min(float(point[0]) for point in divider_points),
            max(float(point[0]) for point in divider_points),
            min(float(point[1]) for point in divider_points),
            max(float(point[1]) for point in divider_points),
        )
        through = bool(sides.get(-1) and sides.get(1))
        footprint = None
        if through and bounds is not None:
            x0, x1, y0, y1 = map(float, bounds)
            if x1 > x0 and y1 > y0:
                footprint = shapely_box(x0, y0, x1, y1)
        result[name] = {
            "sides": dict(sides),
            "through": bool(through and footprint is not None),
            "divider_uv_bounds": bounds,
            "physical_footprint": footprint,
        }
    return result


def test_issue74_post_solve_has_zero_positive_area_in_source_solid_footprints():
    """Post-refold world collision must have zero positive-area penetration.

    Boundary skin crossings are legal. This intentionally does not rebuild the
    superseded pre-cut target-T/2 UV footprint.
    """
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics
    diagnostic = diagnostics[0]
    post = dict(diagnostic.evidence["post"])
    print("ISSUE74_POST_REFOLD_TRUE_THICKNESS=", post)

    assert diagnostic.illegal_penetration is False
    assert post["verified"] is True
    assert int(post["true_thickness_penetrating_band_count"]) == 0
    minx, miny, maxx, maxy = map(float, divider_part.render_data.material.bounds)
    assert float(post["positive_overlap_area"]) <= max(
        1.0e-12,
        1.0e-6 * max(maxx - minx, maxy - miny, 1.0),
    )
    for row in dict(post["by_source"]).values():
        assert tuple(row["true_thickness_penetrating_bands"]) == ()

def test_issue74_presolve_mating_fw_and_d_are_single_skin_contacts():
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)
    left = _crossing_sides_by_source_band(
        world, divider.stable_id, "box_body:left_side", bands["box_body:left_side"]
    )
    right = _crossing_sides_by_source_band(
        world, divider.stable_id, "box_body:right_side", bands["box_body:right_side"]
    )
    print("ISSUE74_PRESOLVE_CONTACT_CLASS=", {"left": left, "right": right})

    # Semantic keys come from the authoritative source Fold profiles; no measured
    # UV value is used as an oracle. These mating bands must not be promoted just
    # because one physical skin intersects the Divider.
    for row in (left["fw_left"], left["d_left"], right["fw_right"], right["d_right"]):
        assert row["through"] is False

    # The actual regression witnesses are likewise identified by source Fold
    # identity + both-skin physical crossing, never by hard-coded 62/61/57.
    # Original, program-generated +90 first fold and adjacent zl2 BOTH
    # physically cross the Divider before the 7mm U-notch is machined.
    # This is verified from both thickness skins, not a profile name alone.
    left_piece = next(p for p in body.render_data.pieces if p.role=="left_side")
    assert left_piece.fold_profile[0].length == pytest.approx(22.)
    assert left_piece.fold_profile[0].angle == pytest.approx(90.)
    assert left["zl1"]["through"] is True
    assert left["zl2"]["through"] is True
    assert left["side_rear_bend_left"]["through"] is False
    assert right["zr2"]["through"] is True


def test_issue74_collision_is_shadow_only_for_certified_divider_cross():
    """Certified CROSS parameters own manufacturing; collision remains shadow evidence."""
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])

    raw_world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snap["t"]
    )
    bands = _piece_bands(body)
    pre = {
        source_key: _crossing_sides_by_source_band(
            raw_world, divider.stable_id, source_key, bands[source_key]
        )
        for source_key in ("box_body:left_side", "box_body:right_side")
    }

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics and diagnostics[0].illegal_penetration is False
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    evidence = dict(relief["evidence"])
    formula = dict(evidence["formula_values"])

    assert relief["trust_level"] == "CERTIFIED"
    assert relief["rule_id"] == "RECEIVING_DIVIDER_CROSS_STANDARD_V1"
    assert relief["corner_type"] == "CROSS"
    assert evidence["manufacturing_dimensions_source"] == "CERTIFIED_REGISTRY_CROSS_PARAMETERS"
    assert evidence["slot_end_selector"] == "OBJECT_MATING_FOLD_SIGN_NEGATIVE"
    assert evidence["slot_end"] == "MIN_Y"
    assert formula == pytest.approx({
        "slotted_fold_u": 66.0,  # original pre-DXF physical fold, no mirrored terminal +T
        "plain_fold_u": 60.0,
        "fold_v": 27.0,
        "slot_width": 7.0,
        "slot_straight_depth": 24.0,
        "slot_radius": 3.5,
    })

    orientation = dict(evidence["mating_fold_orientation"])
    assert dict(orientation["sign_by_end"]) == {"MIN_Y": -1.0, "MAX_Y": 0.0}
    assert orientation["evidence"]["MIN_Y"]["phase6_key"] == "zl1"
    assert orientation["evidence"]["MIN_Y"]["angle"] == pytest.approx(90.0)

    # Collision remains a separate true-thickness witness, not the final
    # 66/60 mm certified CUTTING parameter source. No reflected +T
    # terminal is present in the restored canonical left fold.
    shadow = dict(evidence["collision_shadow"])
    by_source = dict(shadow["projection_by_source"])
    left_stages = dict(by_source["box_body:left_side"]["physical_stages"])
    right_stages = dict(by_source["box_body:right_side"]["physical_stages"])
    assert float(left_stages["zl2"]["stage_u_span"]) == pytest.approx(61.0, abs=1e-5)
    assert float(left_stages["zl1"]["stage_v_span"]) == pytest.approx(23.0, abs=1e-5)
    assert float(right_stages["zr2"]["stage_u_span"]) == pytest.approx(57.0, abs=1e-5)
    # Collision shadow spans are independent diagnostics, never the 66mm
    # source-certified CUTTING width or its 7mm slot dimension.
    assert float(left_stages["zl2"]["stage_u_span"]) != pytest.approx(formula["slotted_fold_u"])
    assert float(right_stages["zr2"]["stage_u_span"]) != pytest.approx(formula["plain_fold_u"])

    # Independent pre-cut both-skin positive footprint witnesses. Neither
    # original first fold is incorrectly classified as legal/no-collision.
    assert pre["box_body:left_side"]["zl1"]["through"] is True
    assert pre["box_body:left_side"]["zl2"]["through"] is True
    assert pre["box_body:left_side"]["side_rear_bend_left"]["through"] is False
    assert pre["box_body:right_side"]["zr2"]["through"] is True


@pytest.mark.parametrize(
    "width, thickness", [(800.0, 2.0), (900.0, 2.0), (900.0, 1.5)]
)
def test_receiving_boxbody_fw_world_occupation_matches_formed_contract(width, thickness):
    """True physical FW occupies formed width WITHOUT exceeding cabinet outside W."""
    snap = _snapshot()
    snap.update({
        "w": float(width), "t": float(thickness),
        "door_layout_columns": [[float(width), [1100.0, 500.0]]],
    })
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    contract = dict(divider_part.render_data.metadata["physical_geometry_contract"])
    expected_formed_fw = float(contract["fw_physical_face"]["outside_dimension"])
    bands = _piece_bands(body)

    observed = {}
    for source_key, fw_name in (
        ("box_body:left_side", "fw_left"),
        ("box_body:right_side", "fw_right"),
    ):
        u0, u1 = next(
            (u0, u1) for name, u0, u1 in bands[source_key] if name == fw_name
        )
        points = []
        for tri in tuple(world["mapped_skin_triangles_by_part"][source_key]):
            centroid_u = sum(float(point[0]) for point in tri.flat) / 3.0
            if u0 - 1.0e-7 <= centroid_u <= u1 + 1.0e-7:
                points.extend(tuple(map(float, point)) for point in tri.world)
        assert points, f"no physical FW geometry for {source_key}"
        x0 = min(point[0] for point in points)
        x1 = max(point[0] for point in points)
        occupation = x1 - x0
        observed[source_key] = {
            "world_x_bounds": (x0, x1),
            "formed_occupation": occupation,
            "expected_formed_fw": expected_formed_fw,
        }
        assert occupation == pytest.approx(expected_formed_fw, abs=1.0e-6), (
            "Receiving 3D FW uses material length instead of formed outside occupation",
            observed,
        )
        # Measure real assembled skin faces, not any 27-mm CUTTING-depth
        # projection. Outboard hinge stays on the physical side sheet;
        # W800/T2 must be +/-400, not +/-401. Width/T vary independently.
        if source_key == "box_body:left_side":
            assert x0 == pytest.approx(-float(width) / 2.0, abs=1.0e-5), observed
        else:
            assert x1 == pytest.approx(float(width) / 2.0, abs=1.0e-5), observed

    print("RECEIVING_FW_FORMED_OCCUPATION=", observed)


def test_receiving_reference_fixture_independently_matches_22_27_step_oracle():
    """Measure the PRE-RELIEF world projection only; not the final mating/CUTTING.

    World-axis bounding-box intersection is diagnostic, not a final material
    dimension or a physical contact witness. The independently certified 27-mm
    CUTTING depth is measured from final material against the DXF below.
    A thickness-derived ad-hoc correction to make them match is forbidden.
    """
    REFERENCE_ZL1_MATERIAL_LENGTH = 22.0
    REFERENCE_TRUE_THICKNESS = 2.0

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)

    # Independent collision witness for the narrow left stage.
    left = _crossing_sides_by_source_band(
        world,
        divider.stable_id,
        "box_body:left_side",
        bands["box_body:left_side"],
    )
    # The pre-DXF original program's first 22mm panel leg is a TRUE
    # interference before cutting. Check its independent positive area.
    first = next(row for row in body.render_data.pieces if row.role=="left_side").fold_profile[0]
    assert first.length == pytest.approx(REFERENCE_ZL1_MATERIAL_LENGTH)
    first_footprint = left["zl1"]["physical_footprint"]
    assert first_footprint is not None and first_footprint.area > 0
    crossing = left["zl2"]["physical_footprint"]
    assert crossing is not None
    _x0,y0,_x1,y1 = map(float,crossing.bounds)
    observed_solid_thickness = y1-y0

    def band_world_x_bounds(source_key, band_name):
        u0, u1 = next(
            (u0, u1) for name, u0, u1 in bands[source_key] if name == band_name
        )
        xs = []
        for skin in tuple(world["mapped_skin_triangles_by_part"][source_key]):
            centroid_u = sum(float(point[0]) for point in skin.flat) / 3.0
            if u0 + 1.0e-6 < centroid_u < u1 - 1.0e-6:
                xs.extend(float(point[0]) for point in skin.world)
        assert xs, f"no world FW geometry for {source_key}:{band_name}"
        return min(xs), max(xs)

    divider_x = [
        float(point[0])
        for skin in tuple(world["mapped_skin_triangles_by_part"][divider.stable_id])
        for point in skin.world
    ]
    assert divider_x
    divider_bounds = (min(divider_x), max(divider_x))

    left_fw = band_world_x_bounds("box_body:left_side", "fw_left")
    right_fw = band_world_x_bounds("box_body:right_side", "fw_right")

    def overlap_1d(a, b):
        return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

    projected_left = overlap_1d(left_fw, divider_bounds)
    projected_right = overlap_1d(right_fw, divider_bounds)

    observed = {
        "zl1_material_length": first.length,
        "true_thickness_collision_band": observed_solid_thickness,
        "divider_x_bounds": divider_bounds,
        "left_fw_x_bounds": left_fw,
        "right_fw_x_bounds": right_fw,
        "left_fw_divider_projection_only": projected_left,
        "right_fw_divider_projection_only": projected_right,
        "dimension_authority": "PRE_RELIEF_WORLD_AXIS_PROJECTION_DIAGNOSTIC_ONLY",
    }
    print("RECEIVING_REFERENCE_22_27_ORACLE=", observed)

    assert observed_solid_thickness == pytest.approx(
        REFERENCE_TRUE_THICKNESS, abs=1.0e-5
    )
    # Both values are projections in the PRE-RELIEF world, not a claim about
    # the post-solve physical contact or cutting depth.  In particular do not
    # "repair" them by adding fixed 1 mm, T/2, or a certified 27-mm oracle.
    assert 0 < projected_left < left_fw[1] - left_fw[0]
    assert 0 < projected_right < right_fw[1] - right_fw[0]
    assert projected_left == pytest.approx(projected_right, abs=1.0e-5)



def test_receiving_reference_fixture_final_cutting_matches_certified_dxf_oracle():
    """Validation-only OUTER CUTTING oracle for certified 中隔.dxf end shapes."""
    # Independent certified C source, prior to the left-panel DXF mirror:
    # original first fold -> 66mm slotted C profile with 7mm relief.
    # No reflected rear terminal exists to justify +T=68.
    SLOTTED_W = 66.0
    PLAIN_W = 60.0
    PRIMARY_D = 27.0
    SLOT_W = 7.0
    SLOT_STRAIGHT = 24.0
    SLOT_R = 3.5

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics and diagnostics[0].illegal_penetration is False
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    assert relief["evidence"]["slot_end"] == "MIN_Y"

    # Independent validation geometry: the DXF certifies two end shapes.
    # Runtime orientation is judged separately from the object Fold sign.
    nominal_shell = Polygon(divider_part.render_data.material.exterior)
    retained_shell = Polygon(solved.render_data.material.exterior)
    removed = nominal_shell.difference(retained_shell)
    minx, miny, maxx, maxy = map(float, nominal_shell.bounds)

    slotted_primary = shapely_box(
        minx, miny,
        minx + SLOTTED_W, miny + PRIMARY_D,
    )
    slot_x0 = minx + SLOTTED_W - SLOT_W
    slot_x1 = minx + SLOTTED_W
    tangent_y = miny + PRIMARY_D + SLOT_STRAIGHT
    slot_rect = shapely_box(
        slot_x0, miny + PRIMARY_D,
        slot_x1, tangent_y,
    )
    slot_cap = Point(
        (slot_x0 + slot_x1) / 2.0, tangent_y
    ).buffer(SLOT_R).intersection(
        shapely_box(slot_x0, tangent_y, slot_x1, tangent_y + SLOT_R + 1e-9)
    )
    plain_primary = shapely_box(
        minx, maxy - PRIMARY_D,
        minx + PLAIN_W, maxy,
    )
    expected = unary_union((slotted_primary, slot_rect, slot_cap, plain_primary))

    missing = expected.difference(removed)
    extra = removed.difference(expected)
    print("RECEIVING_CERTIFIED_DXF_CUTTING_ORACLE=", {
        "removed_area": float(removed.area),
        "expected_area": float(expected.area),
        "missing_area": float(missing.area),
        "extra_area": float(extra.area),
        "slotted_end": "MIN_Y",
        "slotted": (SLOTTED_W, PRIMARY_D, SLOT_W, SLOT_STRAIGHT, SLOT_R),
        "plain": (PLAIN_W, PRIMARY_D),
    })

    assert float(missing.area) <= 1.0e-4
    assert float(extra.area) <= 1.0e-4


def test_receiving_operator_inputs_are_authority_and_material_fold_is_one_way_derived():
    """Operator/outside inputs are authority; material Fold is one-way derived."""
    from phase6_fold_profiles import build_box_body_profile, read_box_body_profile

    snap = _snapshot()
    assert (
        float(snap["zl1"]),
        float(snap["zl2"]),
        float(snap["fw"]),
        float(snap["zr2"]),
    ) == (-24.0, 24.0, 29.0, 18.0)

    profile = build_box_body_profile(snap)
    by_key = {
        str(row.get("phase6_key") or ""): row
        for row in profile
        if str(row.get("phase6_key") or "")
    }
    material = (
        float(by_key["zl1"]["len"]),
        float(by_key["zl2"]["len"]),
        float(by_key["fw_left"]["len"]),
        float(by_key["zr2"]["len"]),
    )
    assert material == (22.0, 20.0, 25.0, 16.0)

    roundtrip = read_box_body_profile(profile, snap)
    assert (
        float(roundtrip["zl1"]),
        float(roundtrip["zl2"]),
        float(roundtrip["fw"]),
        float(roundtrip["zr2"]),
    ) == (-24.0, 24.0, 29.0, 18.0)

    print("RECEIVING_INPUT_AUTHORITY=", {
        "operator_outside": (-24.0, 24.0, 29.0, 18.0),
        "derived_material": material,
        "roundtrip_operator": (
            float(roundtrip["zl1"]),
            float(roundtrip["zl2"]),
            float(roundtrip["fw"]),
            float(roundtrip["zr2"]),
        ),
    })


def test_receiving_final_solid_divider_contacts_are_reverse_mapped_from_real_side_skins():
    """POST-relief physical terminal/skin contact, not a pre-relief FW projection."""
    from shapely.geometry import LineString
    from ae_engine.contracts import ResolvedManufacturingGeometry
    from ae_engine.receiving_joint_marking import (
        _divider_side_contact, _backproject_contact_boundary,
    )
    from ae_engine.side_sheet_datum import SideSheetDatum

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics and diagnostics[0].illegal_penetration is False
    world = bridge._phase6_build_joint_world_geometry(
        solved_parts, dims, snap["t"],
    )
    geometry = ResolvedManufacturingGeometry(parts=tuple(solved_parts))
    sides = SideSheetDatum.from_outside_width(snap["w"], snap["t"])
    owner_pieces = {
        str(piece.role): piece.render_data
        for piece in body.render_data.pieces
    }
    for role, side in (("left_side", -1), ("right_side", +1)):
        contact = _divider_side_contact(
            geometry=geometry, world=world, divider=divider,
            locator_id=f"box_body:{role}", dimensions=dims,
            sheet_thickness=snap["t"],
        )
        assert float(contact.evidence["plane_separation"]) == pytest.approx(0.0, abs=1e-6)
        assert all(
            float(p[0]) == pytest.approx(sides.inside_face(side), abs=1e-6)
            for p in contact.overlap_world
        )
        _world_line, flat_line = _backproject_contact_boundary(contact)
        assert owner_pieces[role].material.covers(LineString(flat_line))



def test_issue74_inverse_full_solid_reprojection_matches_final_material():
    """Canonical product regression includes independent full-solid inverse validation."""
    from tests.test_issue1702_reverse_geometry_probe import (
        test_issue1702_independent_full_thickness_reverse_cut_probe,
    )
    test_issue1702_independent_full_thickness_reverse_cut_probe()


def test_receiving_left_first22_X_and_C_notch_source_regression():
    """Canonical suite executes the correct X-only 22mm witness, not Z."""
    from tests.test_receiving_C_slot_22mm_real_world_debug import (
        test_first_22mm_left_fold_has_actual_X_contact_at_C_notched_end,
    )
    test_first_22mm_left_fold_has_actual_X_contact_at_C_notched_end()

from __future__ import annotations

import importlib.util

import pytest

from ae_engine.contracts import ResolvedPhysicalMatingRegion


def _region(
    *,
    part_id: str,
    normal=(0.0, 1.0, 0.0),
    plane_y: float = 0.0,
    flat_mapping=None,
):
    polygon = (
        (-10.0, plane_y, -5.0),
        (10.0, plane_y, -5.0),
        (10.0, plane_y, 5.0),
        (-10.0, plane_y, 5.0),
    )
    return ResolvedPhysicalMatingRegion(
        part_id=part_id,
        region_id="REGION",
        region_role="MATING_FACE",
        physical_face_kind="MAPPED_SKIN" if flat_mapping is not None else "TERMINAL_BOUNDARY_WALL",
        supporting_plane=((0.0, plane_y, 0.0), tuple(normal)),
        outward_normal=tuple(normal),
        world_polygon=polygon,
        flat_mapping=flat_mapping,
        provenance={"source": "authoritative_test_region"},
    )


def _api():
    spec = importlib.util.find_spec("ae_engine.assembly_contact")
    assert spec is not None, "R2: neutral legal coplanar contact module is missing"
    from ae_engine import assembly_contact

    resolver = getattr(assembly_contact, "resolve_legal_coplanar_contact", None)
    assert callable(resolver), "R2: legal coplanar contact resolver is missing"
    return assembly_contact, resolver


def test_r2_single_production_assembly_geometry_tolerance_owner_exists():
    import ae_engine.contracts as contracts

    owner_type = getattr(contracts, "AssemblyGeometryToleranceContract", None)
    owner = getattr(contracts, "PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES", None)

    assert owner_type is not None, "R2: AssemblyGeometryToleranceContract is missing"
    assert owner is not None, "R2: single production assembly geometry tolerance owner is missing"
    assert isinstance(owner, owner_type)


def test_r2_legal_contact_result_contract_exists():
    import ae_engine.contracts as contracts

    result_type = getattr(contracts, "LegalContactResult", None)
    contact_type = getattr(contracts, "ResolvedLegalContact", None)

    assert result_type is not None, "R2: LegalContactResult contract is missing"
    assert contact_type is not None, "R2: ResolvedLegalContact contract is missing"


def test_exact_coplanar_terminal_contact_is_legal_and_preserves_locator_mapping():
    contracts, resolver = _api()
    locator_mapping = {"source": "canonical_locator_uv"}
    locator = _region(
        part_id="divider",
        normal=(0.0, 1.0, 0.0),
        flat_mapping=locator_mapping,
    )
    attached = _region(
        part_id="inner-door-frame",
        normal=(0.0, -1.0, 0.0),
        flat_mapping=None,
    )

    result = resolver(locator, attached)

    assert result.status == "LEGAL_CONTACT"
    assert result.diagnostic_code is None
    assert result.contact is not None
    assert isinstance(result.contact, contracts.ResolvedLegalContact)
    assert result.contact.locator_part_id == "divider"
    assert result.contact.attached_part_id == "inner-door-frame"
    assert result.contact.locator_flat_mapping is locator_mapping
    assert result.contact.overlap_world
    assert result.contact.evidence["normal_residual"] <= result.contact.evidence["normal_residual_limit"]


def test_displaced_actual_face_fails_not_coplanar_before_overlap_projection():
    _contracts, resolver = _api()
    locator = _region(part_id="divider", normal=(0.0, 1.0, 0.0), flat_mapping={"uv": True})
    attached = _region(part_id="frame", normal=(0.0, -1.0, 0.0), plane_y=0.25)

    result = resolver(locator, attached)

    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "CONTACT_NOT_COPLANAR"
    assert result.contact is None


def test_same_direction_normals_fail_normative_opposed_residual_contract():
    _contracts, resolver = _api()
    locator = _region(part_id="divider", normal=(0.0, 1.0, 0.0), flat_mapping={"uv": True})
    attached = _region(part_id="frame", normal=(0.0, 1.0, 0.0))

    result = resolver(locator, attached)

    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "CONTACT_NORMAL_MISMATCH"
    assert result.evidence["normal_residual"] > result.evidence["normal_residual_limit"]


def test_authoritative_through_thickness_penetration_is_not_reclassified_as_contact():
    contracts, resolver = _api()
    penetration_type = getattr(contracts, "TrueSolidPenetrationEvidence", None)
    assert penetration_type is not None, "R2: neutral true-solid penetration evidence contract is missing"

    locator = _region(part_id="divider", normal=(0.0, 1.0, 0.0), flat_mapping={"uv": True})
    attached = _region(part_id="frame", normal=(0.0, -1.0, 0.0))
    penetration = penetration_type(
        detected=True,
        through_thickness=True,
        positive_volume=True,
        source="AUTHORITATIVE_TRUE_SOLID_ASSEMBLY_GEOMETRY",
    )

    result = resolver(locator, attached, penetration_evidence=penetration)

    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "PENETRATION_NOT_CONTACT"
    assert result.contact is None


def test_production_contact_module_does_not_import_dxf_verifier_or_renderer():
    _contracts, resolver = _api()
    import ast
    import inspect
    from ae_engine import assembly_contact

    tree = ast.parse(inspect.getsource(assembly_contact))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    source = inspect.getsource(resolver)

    assert not any("dxf_acceptance" in name for name in imported | imported_from)
    assert not any("render" in name.lower() for name in imported | imported_from)
    assert "coordinate_tolerance" not in source
    assert "area_tolerance" not in source



def test_coplanar_distance_is_controlled_by_injected_geometry_owner():
    import dataclasses
    import ae_engine.contracts as contracts
    _module, resolver = _api()

    locator = _region(part_id="divider", normal=(0.0, 1.0, 0.0), flat_mapping={"uv": True})
    attached = _region(part_id="frame", normal=(0.0, -1.0, 0.0), plane_y=0.25)

    default_result = resolver(locator, attached)
    assert default_result.diagnostic_code == "CONTACT_NOT_COPLANAR"

    permissive_for_contract_test = dataclasses.replace(
        contracts.PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
        coplanar_distance_tolerance=0.30,
    )
    relaxed_result = resolver(
        locator,
        attached,
        tolerances=permissive_for_contract_test,
    )
    assert relaxed_result.status == "LEGAL_CONTACT"
    assert relaxed_result.contact.evidence["coplanar_distance_limit"] == pytest.approx(0.30)



def _triangle_normal3(triangle):
    import math

    a, b, c = triangle
    u = tuple(float(b[i]) - float(a[i]) for i in range(3))
    v = tuple(float(c[i]) - float(a[i]) for i in range(3))
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    mag = math.sqrt(sum(value * value for value in n))
    assert mag > 1e-12
    return tuple(value / mag for value in n)


def _dot3(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _sub3(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add3(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale3(v, k):
    return tuple(float(v[i]) * float(k) for i in range(3))


def _norm3(v):
    import math

    return math.sqrt(sum(float(value) * float(value) for value in v))


def _plane_basis3(normal):
    n = tuple(float(value) for value in normal)
    reference = min(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        key=lambda axis: abs(_dot3(axis, n)),
    )
    u = (
        reference[1] * n[2] - reference[2] * n[1],
        reference[2] * n[0] - reference[0] * n[2],
        reference[0] * n[1] - reference[1] * n[0],
    )
    um = _norm3(u)
    u = tuple(value / um for value in u)
    v = (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )
    vm = _norm3(v)
    return u, tuple(value / vm for value in v)


def _actual_divider_core_support_region(
    divider,
    render_data,
    placement,
    *,
    dimensions,
    sheet_thickness,
    attached_outward_normal,
):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from ae_engine.assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon,
        world_skin_with_flat_uv,
    )
    from ae_engine.contracts import ResolvedPhysicalMatingRegion, FoldProfileSegment

    x_profile = tuple(divider.fold_profile)
    y_profile = (
        FoldProfileSegment(
            length=float(divider.span),
            angle=None,
            phase6_key="divider_span",
        ),
    )
    mapped = tuple(folded_mesh_with_flat_uv_from_polygon(
        render_data.material,
        x_profile,
        y_profile,
        fold_guides=tuple(render_data.fold_guides or ()),
    ))
    skins = tuple(world_skin_with_flat_uv(
        mapped,
        placement.placement_kind,
        dimensions,
        offset=placement.world_offset,
        sheet_thickness=sheet_thickness,
    ))
    core = divider.physical_geometry_contract["core_physical_segment"]
    band_start, band_end = map(float, core["flat_band"])

    selected = []
    selected_normal = None
    for record in skins:
        centroid_x = sum(float(point[0]) for point in record.flat) / 3.0
        if not (band_start + 1e-8 < centroid_x < band_end - 1e-8):
            continue
        mid_normal = _triangle_normal3(record.world)
        outward = tuple(float(record.side) * value for value in mid_normal)
        if _norm3(_add3(outward, attached_outward_normal)) <= 1e-6:
            selected.append(record)
            selected_normal = outward

    assert selected, "actual Divider core support skin opposite the frame terminal normal was not found"
    assert selected_normal is not None

    origin = tuple(float(v) for v in selected[0].world[0])
    axis_u, axis_v = _plane_basis3(selected_normal)

    def project(point):
        delta = _sub3(point, origin)
        return (_dot3(delta, axis_u), _dot3(delta, axis_v))

    polygons = [
        Polygon(tuple(project(point) for point in record.world))
        for record in selected
    ]
    face = unary_union(polygons)
    assert str(getattr(face, "geom_type", "")) == "Polygon"
    assert float(face.area) > 0.0

    world_polygon = tuple(
        _add3(
            origin,
            _add3(
                _scale3(axis_u, float(x)),
                _scale3(axis_v, float(y)),
            ),
        )
        for x, y in tuple(face.exterior.coords)[:-1]
    )
    return ResolvedPhysicalMatingRegion(
        part_id=str(divider.stable_id),
        region_id="CORE_PHYSICAL_SEGMENT",
        region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=(origin, tuple(selected_normal)),
        outward_normal=tuple(selected_normal),
        world_polygon=world_polygon,
        flat_mapping=tuple(selected),
        provenance={
            "source": "DIVIDER_CORE_PHYSICAL_SEGMENT_MAPPED_SKIN",
            "flat_band": (band_start, band_end),
            "placement_kind": str(placement.placement_kind),
        },
    )


def test_receiving_left_frame_terminal_wall_contacts_actual_shared_divider_support_face():
    from ae_engine.assembly_contact import resolve_legal_coplanar_contact
    from ae_engine.assembly_geometry import resolve_physical_mating_region
    from ae_engine.assembly_placement import resolve_assembly_placement
    from ae_engine.contracts import FoldProfileSegment
    from ae_engine.door_dividers import derive_box_body_dividers
    from ae_engine.inner_door_frames import (
        LOWER_TERMINAL_FACE,
        derive_inner_door_frames,
        inner_door_frame_mating_region,
    )
    from ae_engine.manufacturing_api import (
        build_box_body_divider_render_data,
        build_inner_door_frame_render_data,
    )

    snapshot = {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    }
    dimensions = (800.0, 1600.0, 350.0)
    thickness = 2.0

    frame = derive_inner_door_frames(
        "upper",
        spans={"left": 1014.0},
        thickness=thickness,
        included_sides=("left",),
    )[0]
    frame_data = build_inner_door_frame_render_data(frame)
    frame_placement = resolve_assembly_placement(snapshot, frame.stable_id)
    attached = resolve_physical_mating_region(
        part_id=frame.stable_id,
        semantic=inner_door_frame_mating_region(frame, LOWER_TERMINAL_FACE),
        render_data=frame_data,
        x_profile=tuple(frame.fold_profile),
        y_profile=(
            FoldProfileSegment(
                length=float(frame.span),
                angle=None,
                phase6_key="frame_span",
            ),
        ),
        placement=frame_placement.placement_kind,
        dimensions=dimensions,
        offset=frame_placement.world_offset,
        sheet_thickness=thickness,
    )

    divider = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])],
        depth=350.0,
        thickness=thickness,
        layout_scope="receiving-main",
        model_name="受電箱",
        frame_width=29.0,
    )[0]
    assert divider.stable_id == "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    divider_data = build_box_body_divider_render_data(divider)
    divider_placement = resolve_assembly_placement(snapshot, divider.stable_id)
    locator = _actual_divider_core_support_region(
        divider,
        divider_data,
        divider_placement,
        dimensions=dimensions,
        sheet_thickness=thickness,
        attached_outward_normal=attached.outward_normal,
    )

    result = resolve_legal_coplanar_contact(locator, attached)

    assert result.status == "LEGAL_CONTACT"
    assert result.diagnostic_code is None
    assert result.contact is not None
    assert result.contact.locator_part_id == divider.stable_id
    assert result.contact.attached_part_id == frame.stable_id
    assert result.contact.locator_region.region_id == "CORE_PHYSICAL_SEGMENT"
    assert result.contact.attached_region.region_id == LOWER_TERMINAL_FACE
    assert result.contact.locator_flat_mapping
    assert result.contact.evidence["plane_separation"] <= result.contact.evidence["coplanar_distance_limit"]
    assert result.contact.evidence["normal_residual"] <= result.contact.evidence["normal_residual_limit"]

from __future__ import annotations

import ast
import importlib.util
import inspect
import math

import pytest

from ae_engine.assembly_geometry import MappedSkinTriangle
from ae_engine.contracts import ResolvedLegalContact, ResolvedPhysicalMatingRegion


def _api():
    spec = importlib.util.find_spec("ae_engine.assembly_marking_geometry")
    assert spec is not None, "R3: neutral assembly marking-geometry module is missing"
    from ae_engine import assembly_marking_geometry as geometry

    frame = getattr(geometry, "resolve_contact_local_frame", None)
    pair = getattr(geometry, "resolve_side_boundary_pair", None)
    backproject = getattr(geometry, "backproject_locator_world_points", None)
    assert callable(frame), "R3: CONTACT_LOCAL_FRAME_V1 resolver is missing"
    assert callable(pair), "R3: semantic SIDE_BOUNDARY_PAIR resolver is missing"
    assert callable(backproject), "R3: locator-only world->flat backprojection is missing"
    return geometry, frame, pair, backproject


def _region(*, mapping, normal=(0.0, 0.0, 1.0), world_polygon=None):
    return ResolvedPhysicalMatingRegion(
        part_id="locator",
        region_id="CORE_PHYSICAL_SEGMENT",
        region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=((0.0, 0.0, 0.0), tuple(normal)),
        outward_normal=tuple(normal),
        world_polygon=tuple(world_polygon or (
            (-2.0, -1.0, 0.0),
            (2.0, -1.0, 0.0),
            (2.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
        )),
        flat_mapping=mapping,
        provenance={"source": "authoritative_locator_mapping"},
    )


def _contact(*, mapping, world_polygon=None, normal=(0.0, 0.0, 1.0)):
    locator = _region(
        mapping=mapping,
        normal=normal,
        world_polygon=world_polygon,
    )
    attached = ResolvedPhysicalMatingRegion(
        part_id="attached",
        region_id="LOWER_TERMINAL_FACE",
        region_role="TERMINAL_MATING_FACE",
        physical_face_kind="TERMINAL_BOUNDARY_WALL",
        supporting_plane=((0.0, 0.0, 0.0), tuple(-float(v) for v in normal)),
        outward_normal=tuple(-float(v) for v in normal),
        world_polygon=(
            (-2.0, -1.0, 0.0),
            (2.0, -1.0, 0.0),
            (2.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
        ),
        flat_mapping=None,
        provenance={"source": "authoritative_attached_terminal_wall"},
    )
    return ResolvedLegalContact(
        locator_part_id="locator",
        attached_part_id="attached",
        locator_region=locator,
        attached_region=attached,
        contact_plane=((0.0, 0.0, 0.0), tuple(normal)),
        locator_outward_normal=tuple(normal),
        attached_outward_normal=tuple(-float(v) for v in normal),
        overlap_world=tuple(world_polygon or locator.world_polygon),
        locator_flat_mapping=mapping,
        evidence={"source": "legal-contact-test"},
    )


def _identity_mapping():
    return (
        MappedSkinTriangle(
            flat=((0.0, 0.0), (4.0, 0.0), (0.0, 2.0)),
            world=((-2.0, -1.0, 0.0), (2.0, -1.0, 0.0), (-2.0, 1.0, 0.0)),
            side=1,
        ),
        MappedSkinTriangle(
            flat=((4.0, 0.0), (4.0, 2.0), (0.0, 2.0)),
            world=((2.0, -1.0, 0.0), (2.0, 1.0, 0.0), (-2.0, 1.0, 0.0)),
            side=1,
        ),
    )


def _mirrored_mapping():
    return (
        MappedSkinTriangle(
            flat=((0.0, 0.0), (4.0, 0.0), (0.0, 2.0)),
            world=((2.0, -1.0, 0.0), (-2.0, -1.0, 0.0), (2.0, 1.0, 0.0)),
            side=1,
        ),
        MappedSkinTriangle(
            flat=((4.0, 0.0), (4.0, 2.0), (0.0, 2.0)),
            world=((-2.0, -1.0, 0.0), (-2.0, 1.0, 0.0), (2.0, 1.0, 0.0)),
            side=1,
        ),
    )


def _assert_vec(actual, expected):
    assert tuple(actual) == pytest.approx(tuple(expected), abs=1e-9)


def _transform_mapping(mapping, transform):
    return tuple(
        MappedSkinTriangle(
            flat=record.flat,
            world=tuple(transform(point) for point in record.world),
            side=record.side,
        )
        for record in mapping
    )


def _rotate_z_90(point):
    x, y, z = map(float, point)
    return (-y, x, z)


def _current_horizontal_inward_transform(mapping, points):
    from ae_engine.assembly_geometry import place_assembly_points

    reference = tuple(record.world for record in mapping)
    placed = place_assembly_points(
        tuple(points),
        reference,
        "divider_horizontal_inward",
        (800.0, 1600.0, 350.0),
        (0.0, 0.0, 0.0),
    )
    assert len(placed) == len(tuple(points))
    return tuple(placed)


def test_r3_contact_local_frame_contract_exists():
    geometry, frame_resolver, _pair, _backproject = _api()
    import ae_engine.contracts as contracts

    assert getattr(contracts, "ContactLocalFrame", None) is not None
    assert getattr(contracts, "SemanticBoundaryPair", None) is not None
    assert getattr(contracts, "LocatorBackprojectionResult", None) is not None
    assert getattr(geometry, "CONTACT_LOCAL_FRAME_VERSION", None) == "CONTACT_LOCAL_FRAME_V1"
    assert callable(frame_resolver)


def test_signed_locator_flat_basis_defines_l_c_and_positive_parity():
    _geometry, frame_resolver, _pair, _backproject = _api()
    result = frame_resolver(
        _contact(mapping=_identity_mapping()),
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )

    assert result.status == "RESOLVED", repr(result)
    assert result.diagnostic_code is None
    assert result.frame.frame_version == "CONTACT_LOCAL_FRAME_V1"
    _assert_vec(result.frame.normal, (0.0, 0.0, 1.0))
    _assert_vec(result.frame.longitudinal, (1.0, 0.0, 0.0))
    _assert_vec(result.frame.cross, (0.0, 1.0, 0.0))
    assert result.frame.handedness_parity == 1


def test_mirror_changes_handedness_parity_but_not_semantic_side_roles():
    _geometry, frame_resolver, pair_resolver, _backproject = _api()
    contact = _contact(
        mapping=_mirrored_mapping(),
        world_polygon=(
            (2.0, -1.0, 0.0),
            (-2.0, -1.0, 0.0),
            (-2.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
        ),
    )
    frame_result = frame_resolver(
        contact,
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame_result.status == "RESOLVED", repr(frame_result)
    assert frame_result.frame.handedness_parity == -1
    _assert_vec(frame_result.frame.longitudinal, (-1.0, 0.0, 0.0))
    _assert_vec(frame_result.frame.cross, (0.0, 1.0, 0.0))

    pair = pair_resolver(contact, frame_result.frame)
    assert pair.status == "RESOLVED", repr(pair)
    assert pair.pair.negative.role == "SIDE_NEGATIVE"
    assert pair.pair.positive.role == "SIDE_POSITIVE"
    assert pair.pair.negative.signed_cross < pair.pair.positive.signed_cross


def test_attached_terminal_without_flat_mapping_is_legal_for_locator_frame_and_backprojection():
    _geometry, frame_resolver, _pair, backproject = _api()
    contact = _contact(mapping=_identity_mapping())
    assert contact.attached_region.flat_mapping is None

    frame = frame_resolver(
        contact,
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame.status == "RESOLVED", repr(frame)

    projected = backproject(
        contact,
        ((-1.0, -0.5, 0.0), (1.5, 0.75, 0.0)),
    )
    assert projected.status == "RESOLVED", repr(projected)
    assert projected.diagnostic_code is None
    assert projected.flat_points[0] == pytest.approx((1.0, 0.5), abs=1e-8)
    assert projected.flat_points[1] == pytest.approx((3.5, 1.75), abs=1e-8)
    assert projected.evidence["mapping_owner"] == "LOCATOR"


def test_missing_locator_mapping_fails_backprojection_without_attached_fallback():
    _geometry, _frame, _pair, backproject = _api()
    contact = _contact(mapping=None)

    result = backproject(contact, ((0.0, 0.0, 0.0),))

    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.diagnostic_code == "BACKPROJECTION_FAILED"
    assert result.flat_points == ()


def test_side_boundary_pair_uses_semantic_cross_axis_not_world_left_right():
    _geometry, frame_resolver, pair_resolver, _backproject = _api()
    contact = _contact(mapping=_identity_mapping())
    frame = frame_resolver(
        contact,
        longitudinal_flat_axis="+Y",
        cross_flat_axis="-X",
    )
    assert frame.status == "RESOLVED", repr(frame)

    pair = pair_resolver(contact, frame.frame)
    assert pair.status == "RESOLVED", repr(pair)
    assert pair.pair.negative.role == "SIDE_NEGATIVE"
    assert pair.pair.positive.role == "SIDE_POSITIVE"
    assert pair.pair.negative.signed_cross < pair.pair.positive.signed_cross


def test_production_module_has_no_bbox_renderer_or_world_axis_fallback():
    geometry, frame_resolver, pair_resolver, backproject = _api()
    tree = ast.parse(inspect.getsource(geometry))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    source = "\n".join(
        inspect.getsource(fn)
        for fn in (frame_resolver, pair_resolver, backproject)
    ).lower()

    assert "renderer" not in names
    assert "bounds" not in attrs
    assert ".bounds" not in source
    assert "world_x" not in source
    assert "world_y" not in source
    assert "world_z" not in source
    assert "left" not in source
    assert "right" not in source


def test_rigid_rotation_preserves_semantic_roles_and_rotates_signed_basis():
    _geometry, frame_resolver, pair_resolver, backproject = _api()
    base_mapping = _identity_mapping()
    mapping = _transform_mapping(base_mapping, _rotate_z_90)
    polygon = tuple(
        _rotate_z_90(point)
        for point in (
            (-2.0, -1.0, 0.0),
            (2.0, -1.0, 0.0),
            (2.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
        )
    )
    contact = _contact(
        mapping=mapping,
        world_polygon=polygon,
        normal=(0.0, 0.0, 1.0),
    )

    frame = frame_resolver(
        contact,
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame.status == "RESOLVED", repr(frame)
    _assert_vec(frame.frame.longitudinal, (0.0, 1.0, 0.0))
    _assert_vec(frame.frame.cross, (-1.0, 0.0, 0.0))
    assert frame.frame.handedness_parity == 1

    pair = pair_resolver(contact, frame.frame)
    assert pair.status == "RESOLVED", repr(pair)
    assert pair.pair.negative.role == "SIDE_NEGATIVE"
    assert pair.pair.positive.role == "SIDE_POSITIVE"
    assert pair.pair.negative.signed_cross < pair.pair.positive.signed_cross

    projected = backproject(
        contact,
        (_rotate_z_90((-1.0, -0.5, 0.0)),),
    )
    assert projected.status == "RESOLVED", repr(projected)
    assert projected.flat_points == pytest.approx(((1.0, 0.5),), abs=1e-8)


def test_current_horizontal_inward_orientation_preserves_semantic_roles():
    _geometry, frame_resolver, pair_resolver, _backproject = _api()
    base_mapping = _identity_mapping()
    reference = tuple(record.world for record in base_mapping)
    all_points = tuple(point for record in base_mapping for point in record.world)
    placed_points = _current_horizontal_inward_transform(
        base_mapping,
        all_points,
    )
    chunks = tuple(
        tuple(placed_points[index:index + 3])
        for index in range(0, len(placed_points), 3)
    )
    mapping = tuple(
        MappedSkinTriangle(
            flat=record.flat,
            world=world,
            side=record.side,
        )
        for record, world in zip(base_mapping, chunks)
    )
    source_polygon = (
        (-2.0, -1.0, 0.0),
        (2.0, -1.0, 0.0),
        (2.0, 1.0, 0.0),
        (-2.0, 1.0, 0.0),
    )
    polygon = _current_horizontal_inward_transform(
        base_mapping,
        source_polygon,
    )
    normal_probe = _current_horizontal_inward_transform(
        base_mapping,
        ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    )
    normal_delta = tuple(
        float(normal_probe[1][i]) - float(normal_probe[0][i])
        for i in range(3)
    )
    magnitude = math.sqrt(sum(value * value for value in normal_delta))
    normal = tuple(value / magnitude for value in normal_delta)

    contact = _contact(
        mapping=mapping,
        world_polygon=polygon,
        normal=normal,
    )
    frame = frame_resolver(
        contact,
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame.status == "RESOLVED", repr(frame)
    _assert_vec(frame.frame.normal, (0.0, 1.0, 0.0))
    _assert_vec(frame.frame.longitudinal, (0.0, 0.0, -1.0))
    _assert_vec(frame.frame.cross, (1.0, 0.0, 0.0))
    assert frame.frame.handedness_parity == -1

    pair = pair_resolver(contact, frame.frame)
    assert pair.status == "RESOLVED", repr(pair)
    assert pair.pair.negative.role == "SIDE_NEGATIVE"
    assert pair.pair.positive.role == "SIDE_POSITIVE"
    assert pair.pair.negative.signed_cross < pair.pair.positive.signed_cross


def test_locator_region_mapping_is_authority_and_stale_contact_copy_fails_closed():
    from dataclasses import replace

    _geometry, frame_resolver, _pair, backproject = _api()
    contact = _contact(mapping=_identity_mapping())
    stale = replace(contact, locator_flat_mapping=_mirrored_mapping())

    frame = frame_resolver(
        stale,
        longitudinal_flat_axis="+X",
        cross_flat_axis="+Y",
    )
    assert frame.status == "SKIPPED_FAIL_CLOSED"
    assert frame.diagnostic_code == "BOUNDARY_FRAME_UNRESOLVED"

    projected = backproject(stale, ((0.0, 0.0, 0.0),))
    assert projected.status == "SKIPPED_FAIL_CLOSED"
    assert projected.diagnostic_code == "BACKPROJECTION_FAILED"

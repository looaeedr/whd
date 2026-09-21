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

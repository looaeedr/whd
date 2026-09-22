from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
import inspect

import pytest

from ae_engine.contracts import ResolvedPhysicalMatingRegion


EXPECTED_DIAGNOSTIC_CODES = {
    "POLICY_NOT_FOUND",
    "LOCATOR_MISSING",
    "ATTACHED_MISSING",
    "STALE_STABLE_ID",
    "PLACEMENT_UNRESOLVED",
    "MATING_REGION_UNRESOLVED",
    "CONTACT_NOT_FOUND",
    "CONTACT_NOT_COPLANAR",
    "CONTACT_NORMAL_MISMATCH",
    "CONTACT_SPAN_BELOW_MINIMUM",
    "CONTACT_NOT_UNIQUE",
    "PENETRATION_NOT_CONTACT",
    "OVERLAP_AUTHORITY_MISSING",
    "BOUNDARY_FRAME_UNRESOLVED",
    "FOOTPRINT_MODE_MISMATCH",
    "BACKPROJECTION_FAILED",
    "BOUNDARY_PAIR_AMBIGUOUS",
    "MARK_OUTSIDE_FINAL_MATERIAL",
}


def _api():
    spec = importlib.util.find_spec("ae_engine.joint_marking_policy")
    assert spec is not None, "R3: JointMarkingPolicy registry module is missing"
    from ae_engine import joint_marking_policy as policy
    import ae_engine.contracts as contracts

    required_contracts = (
        "JointMarkingPolicy",
        "JointMarkingPolicyLookupResult",
        "ResolvedJointMarkingResult",
        "ContactSpanValidationResult",
    )
    for name in required_contracts:
        assert getattr(contracts, name, None) is not None, f"R3: {name} contract is missing"

    registry_type = getattr(policy, "JointMarkingPolicyRegistry", None)
    stable_id = getattr(policy, "stable_joint_mark_id", None)
    coverage = getattr(policy, "validate_expected_region_coverage", None)
    assert registry_type is not None, "R3: JointMarkingPolicyRegistry is missing"
    assert callable(stable_id), "R3: stable semantic mark identity helper is missing"
    assert callable(coverage), "R3: EXPECTED_REGION_COVERAGE validator is missing"
    return policy, contracts, registry_type, stable_id, coverage


def _receiving_policy(contracts):
    return contracts.JointMarkingPolicy(
        policy_id="RECEIVING_INNER_DOOR_VERTICAL_FRAME_TO_SHARED_DIVIDER_V1",
        revision=1,
        enabled=True,
        locator_selector="RECEIVING_SHARED_HORIZONTAL_DIVIDER",
        attached_selector="RECEIVING_INNER_DOOR_VERTICAL_FRAME",
        locator_contact_region="CORE_PHYSICAL_SEGMENT",
        attached_contact_region="LOWER_TERMINAL_FACE",
        footprint_mode="SIDE_BOUNDARY_PAIR",
        boundary_frame_contract={
            "frame_version": "CONTACT_LOCAL_FRAME_V1",
            "basis_part": "LOCATOR",
            "basis_contact_region": "CORE_PHYSICAL_SEGMENT",
            "longitudinal_flat_axis": "+X",
            "cross_flat_axis": "+Y",
            "normal_rule": "LOCATOR_TO_ATTACHED",
            "handedness_rule": "FLAT_BASIS_PRESERVING",
            "negative_role": "SIDE_NEGATIVE",
            "positive_role": "SIDE_POSITIVE",
        },
        contact_span_contract="EXPECTED_REGION_COVERAGE",
        allowed_overlap_contract="NONE",
    )


def _region(world_polygon):
    return ResolvedPhysicalMatingRegion(
        part_id="receiving:divider:shared-1",
        region_id="LOWER_TERMINAL_FACE",
        region_role="EXPECTED_MATING_REGION",
        physical_face_kind="TERMINAL_BOUNDARY_WALL",
        supporting_plane=((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        outward_normal=(0.0, 0.0, 1.0),
        world_polygon=tuple(world_polygon),
        flat_mapping=None,
        provenance={"source": "authoritative_terminal_region"},
    )


def test_r3_policy_registry_contracts_exist_and_are_immutable():
    _policy, contracts, _registry_type, _stable_id, _coverage = _api()
    value = _receiving_policy(contracts)

    with pytest.raises(FrozenInstanceError):
        value.revision = 2


def test_policy_routing_has_exact_three_states_without_no_policy_noise():
    _policy, contracts, registry_type, _stable_id, _coverage = _api()
    receiving = _receiving_policy(contracts)
    registry = registry_type((receiving,))

    matched = registry.resolve(
        locator_selector=receiving.locator_selector,
        attached_selector=receiving.attached_selector,
    )
    assert matched.status == "MATCHED"
    assert matched.policy == receiving
    assert matched.diagnostic_code is None

    ordinary = registry.resolve(
        locator_selector="UNRELATED_LOCATOR",
        attached_selector="UNRELATED_ATTACHED",
    )
    assert ordinary.status == "NO_POLICY_REQUIRED"
    assert ordinary.policy is None
    assert ordinary.diagnostic_code is None

    missing = registry.resolve(policy_id="DOES_NOT_EXIST")
    assert missing.status == "EXPLICIT_POLICY_ID_MISSING"
    assert missing.policy is None
    assert missing.diagnostic_code == "POLICY_NOT_FOUND"


def test_expected_region_coverage_rejects_fragment_contact_without_mm_threshold():
    _policy, _contracts, _registry_type, _stable_id, coverage = _api()
    expected = _region(
        (
            (-2.0, -1.0, 0.0),
            (2.0, -1.0, 0.0),
            (2.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
        )
    )

    full = coverage(expected, expected.world_polygon)
    assert full.status == "COVERED"
    assert full.diagnostic_code is None

    fragment = coverage(
        expected,
        (
            (-2.0, -1.0, 0.0),
            (-1.0, -1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
        ),
    )
    assert fragment.status == "SKIPPED_FAIL_CLOSED"
    assert fragment.diagnostic_code == "CONTACT_SPAN_BELOW_MINIMUM"


def test_stable_mark_id_uses_only_policy_parts_and_boundary_role():
    _policy, _contracts, _registry_type, stable_id, _coverage = _api()

    mark = stable_id(
        "P1",
        "locator:divider:stable",
        "attached:left-frame:stable",
        "SIDE_NEGATIVE",
    )
    assert mark == (
        "jointmark:P1:locator:divider:stable:"
        "attached:left-frame:stable:SIDE_NEGATIVE"
    )
    assert stable_id(
        "P1",
        "locator:divider:stable",
        "attached:left-frame:stable",
        "SIDE_NEGATIVE",
    ) == mark
    assert stable_id(
        "P1",
        "locator:divider:stable",
        "attached:left-frame:stable",
        "SIDE_POSITIVE",
    ) != mark


def test_all_v13_diagnostic_codes_are_owned_by_policy_core():
    policy, _contracts, _registry_type, _stable_id, _coverage = _api()
    actual = set(getattr(policy, "MARKING_DIAGNOSTIC_CODES", ()))
    assert EXPECTED_DIAGNOSTIC_CODES <= actual


def test_resolved_result_keeps_export_disposition_unresolved_until_open1_decision():
    _policy, contracts, _registry_type, _stable_id, _coverage = _api()
    result = contracts.ResolvedJointMarkingResult(
        policy_id="P1",
        policy_revision=1,
        locator_part_id="locator",
        attached_part_id="attached",
        status="SKIPPED_FAIL_CLOSED",
        mark_ids=(),
        diagnostic_code="CONTACT_NOT_FOUND",
        diagnostic_detail="no legal contact candidate",
    )
    assert result.export_disposition == "UNRESOLVED"


def test_registry_layer_emits_no_drawing_primitives_or_export_side_effects():
    policy, _contracts, _registry_type, _stable_id, _coverage = _api()
    source = inspect.getsource(policy)

    forbidden = (
        "DrawingScene",
        "LinePrimitive",
        ".add_line(",
        "save_part_render_data_dxf",
        "ezdxf",
        "renderer",
    )
    assert all(token not in source for token in forbidden)

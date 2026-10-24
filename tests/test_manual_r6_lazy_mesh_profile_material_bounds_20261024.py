"""R6 actual request-to-assembly profile ownership: lazy material fallbacks."""
from types import SimpleNamespace

import pytest

from phase6_manufacturing_geometry import _phase6_request_profiles_for_material


def part(key, x=(), y=()):
    return SimpleNamespace(part_key=key, x_profile=list(x), y_profile=list(y))


@pytest.mark.parametrize("key", [
    "box_body:left_side", "door", "endcap_head", "box_body:back",
])
def test_r6_explicit_two_axis_profiles_do_not_depend_on_unrelated_bounds(key):
    x = [{"len": 20.0, "core": False}, {"len": 800.0, "core": True}]
    y = [{"len": 1600.0, "core": True}]
    original = part(key, x, y)
    # A malformed edge-view or empty material envelope must not prevent the
    # complete immutable source profiles from being passed to assembly.
    result_x, result_y = _phase6_request_profiles_for_material(
        original, SimpleNamespace(bounds=(0.0, 0.0))
    )
    assert (result_x, result_y) == (x, y)
    assert result_x is not original.x_profile
    assert result_y is not original.y_profile


@pytest.mark.parametrize("key", ["box_body:divider:top", "inner_door:bay:left_frame"])
def test_r6_frame_falls_back_to_y_span_only_if_y_profile_missing(key):
    result = _phase6_request_profiles_for_material(
        part(key, [{"len": 90.0}]),
        SimpleNamespace(bounds=(10.0, 20.0, 110.0, 270.0)),
    )
    assert result == ([{"len": 90.0}], [{"len": 250.0}])


def test_r6_frame_falls_back_to_x_span_only_if_x_profile_missing():
    result = _phase6_request_profiles_for_material(
        part("inner_door:bay:top_frame", y=[{"len": 46.0}]),
        SimpleNamespace(bounds=(10.0, 20.0, 710.0, 270.0)),
    )
    assert result == ([{"len": 700.0}], [{"len": 46.0}])


def test_r6_whole_body_always_uses_actual_material_height():
    result = _phase6_request_profiles_for_material(
        part("box_body", x=[{"len": 100.0}], y=[{"len": 1.0}]),
        SimpleNamespace(bounds=(-40.0, 10.0, 160.0, 330.0)),
    )
    assert result == ([{"len": 100.0}], [{"len": 320.0}])


@pytest.mark.parametrize("bounds", [
    (), (0.0, 0.0), (0.0, 0.0, 100.0, 0.0),
    (0.0, 0.0, float("nan"), 300.0),
    (0.0, 0.0, float("inf"), 300.0),
    (0.0, True, 100.0, 300.0),
])
def test_r6_required_material_fallback_fails_closed_on_invalid_bounds(bounds):
    with pytest.raises(ValueError, match="physical material bounds unavailable"):
        _phase6_request_profiles_for_material(
            part("box_body:divider:mid", x=[{"len": 80.0}]),
            SimpleNamespace(bounds=bounds),
        )


def test_r6_complete_divider_profiles_ignore_non_authoritative_bad_material_bounds():
    x = [{"len": 80.0}]
    y = [{"len": 500.0}]
    assert _phase6_request_profiles_for_material(
        part("box_body:divider:mid", x, y),
        SimpleNamespace(bounds=(0.0, 0.0)),
    ) == (x, y)


def test_r6_side_fw_mapped_triangle_index_cannot_exceed_world_mesh_rows():
    from phase6_manufacturing_geometry import _phase6_expand_box_body_fw_world_mid

    triangle = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.))
    physical_rows = (triangle,)
    piece = SimpleNamespace(
        role="left_side", fold_profile=(
            SimpleNamespace(length=10., phase6_key="fw_left", formed_length=20., core=None),
            SimpleNamespace(length=100., phase6_key="d_left", formed_length=None, core="D"),
        ),
    )
    mapped = (
        SimpleNamespace(flat=((12., 0.), (13., 0.), (12., 1.))),
        SimpleNamespace(flat=((2., 0.), (3., 0.), (2., 1.))),
    )
    # Only mapped index 1 belongs to the FW; physical world has index 0.
    # Missing physical triangles are never synthesized or indexed out of range.
    assert _phase6_expand_box_body_fw_world_mid(
        piece, mapped, physical_rows, sheet_thickness=2.,
    ) == physical_rows


def test_r6_multistage_terminal_world_mapping_cannot_index_missing_triangle():
    from phase6_manufacturing_geometry import _phase6_shift_multistage_terminal_fold_world_mid

    triangle = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.))
    physical_rows = (triangle,)
    piece = SimpleNamespace(
        role="right_side", fold_profile=(
            SimpleNamespace(length=10., formed_length=12., phase6_key="zr1", core=None),
            SimpleNamespace(length=10., formed_length=None, phase6_key="zr2", core=None),
            SimpleNamespace(length=10., formed_length=None, phase6_key="fw_right", core=None),
            SimpleNamespace(length=100., formed_length=None, phase6_key="d_right", core="D"),
        ),
    )
    mapped = (
        SimpleNamespace(flat=((20., 0.), (21., 0.), (20., 1.))),
        SimpleNamespace(flat=((2., 0.), (3., 0.), (2., 1.))),
    )
    assert _phase6_shift_multistage_terminal_fold_world_mid(
        piece, mapped, physical_rows,
    ) == physical_rows

@pytest.mark.parametrize("invalid", [True, False, float("nan"), float("inf"), -100.])
def test_r6_door_placement_does_not_project_invalid_layout_width(invalid):
    from phase6_manufacturing_geometry import _phase6_door_part_assembly_placement
    source = {"door_layout_columns": ((invalid, (500., 600.)), (400., (1100.,)))}
    with pytest.raises(ValueError):
        _phase6_door_part_assembly_placement(source, "door_c1_r1")


@pytest.mark.parametrize("axis,invalid", [
    ("w", True), ("h", False),
    ("w", float("nan")), ("h", float("inf")),
    ("w", -1.), ("h", 0.),
])
def test_r6_door_placement_rejects_nonphysical_outer_dimensions(axis, invalid):
    from phase6_manufacturing_geometry import _phase6_door_part_assembly_placement
    source = {
        "door_layout_columns": ((400., (500., 600.)), (400., (1100.,))),
        axis: invalid,
    }
    with pytest.raises(ValueError):
        _phase6_door_part_assembly_placement(source, "door_c1_r1")


def test_r6_door_placement_missing_optional_outer_size_uses_actual_layout():
    from phase6_manufacturing_geometry import _phase6_door_part_assembly_placement
    source = {
        "door_layout_columns": ((400., (500., 600.)), (400., (1100.,))),
        "w": None, "h": None,
    }
    assert _phase6_door_part_assembly_placement(source, "door_c1_r1") == (
        "front", (-200., 300., 0.),
    )
    assert _phase6_door_part_assembly_placement(source, "door_c2_r1") == (
        "front", (200., 0., 0.),
    )


@pytest.mark.parametrize("verified", ["false", "true", 1, 0, None, False])
def test_r6_saved_unverified_joint_cannot_reuse_physical_relief(verified):
    from shapely.geometry import box
    from phase6_manufacturing_geometry import _phase6_joint_relief_state_item_matches
    joint = SimpleNamespace(joint_id="joint-1", subject_part="door",
                            target_part="box_body", relation="WRAP")
    saved = {
        "joint_id": "joint-1", "subject_part": "door",
        "target_part": "box_body", "relation": "WRAP",
        "verified": verified, "source_material_bounds": (0., 0., 10., 10.),
        "source_material_area": 100.,
    }
    assert _phase6_joint_relief_state_item_matches(saved, joint, box(0, 0, 10, 10)) is False
    saved["verified"] = True
    assert _phase6_joint_relief_state_item_matches(saved, joint, box(0, 0, 10, 10)) is True

def test_r6_immutable_set_uses_same_canonical_manufacturing_signature_as_mutable_set():
    from phase6_manufacturing_geometry import _phase6_signature_canonical_value

    live = {"head", "tail", "door"}
    immutable = frozenset(reversed(sorted(live)))
    assert _phase6_signature_canonical_value(live) == _phase6_signature_canonical_value(immutable)
    assert _phase6_signature_canonical_value(immutable) == ("door", "head", "tail")


def test_r6_immutable_set_cannot_hide_nonfinite_manufacturing_signature_value():
    from phase6_manufacturing_geometry import _phase6_signature_canonical_value

    with pytest.raises(ValueError, match="nonfinite manufacturing signature value"):
        _phase6_signature_canonical_value(frozenset((float("inf"),)))

@pytest.mark.parametrize("field,bad", [
    ("source_material_area", True),
    ("source_material_area", False),
    ("source_material_area", float("nan")),
    ("source_material_area", float("inf")),
    ("source_material_bounds", (0., 0., True, 1.)),
    ("source_material_bounds", (0., 0., 1., False)),
    ("source_material_bounds", (0., 0., float("inf"), 1.)),
])
def test_r6_saved_relief_cut_cannot_reuse_corrupt_material_evidence(field, bad):
    from shapely.geometry import box
    from phase6_manufacturing_geometry import _phase6_joint_relief_state_item_matches

    source = box(0., 0., 1., 1.)
    joint = SimpleNamespace(
        joint_id="cut-physical-1", subject_part="door",
        target_part="box_body", relation="OVERLAY",
    )
    evidence = {
        "joint_id": joint.joint_id,
        "subject_part": joint.subject_part,
        "target_part": joint.target_part,
        "relation": joint.relation,
        "verified": True,
        "source_material_bounds": (0., 0., 1., 1.),
        "source_material_area": 1.,
    }
    assert _phase6_joint_relief_state_item_matches(evidence, joint, source) is True
    evidence[field] = bad
    assert _phase6_joint_relief_state_item_matches(evidence, joint, source) is False

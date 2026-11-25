"""CHECK-only surface pair classification; no manufacturing verdict."""
from ae_engine.assembly_geometry import (
    detect_world_mesh_surface_interference,
    inspect_native_d4_assembly_world,
)


def test_surface_pair_classification_preserves_legacy_segments_and_indices():
    body = (((0, 0, 0), (4, 0, 0), (0, 4, 0)),)
    strict = ((1, 0, -1), (1, 3, -1), (1, 1, 1))
    edge = ((1, 1, 0), (1, 2, 0), (1, 1, 1))
    near_parallel = ((0, 0, 1e-8), (4, 0, 1e-8), (0, 4, 1e-8))
    current = (strict, edge, near_parallel)
    legacy = detect_world_mesh_surface_interference(body, current)
    check = inspect_native_d4_assembly_world(body, current, original_tail_world=(strict,))
    assert check.crossing_pair_count == legacy.pair_count == 2
    assert check.crossing_segments == legacy.intersection_segments
    assert check.crossing_points == legacy.intersection_points
    assert check.crossing_target_face_indices == legacy.target_face_indices == (0, 1)
    assert [(x.body_triangle_index, x.tail_triangle_index, x.kind)
            for x in check.classified_surface_pairs] == [
        (0, 0, "STRICT_TRIANGLE_INTERIOR"), (0, 1, "TAIL_TRIANGLE_EDGE"),
    ]
    assert [x.kind for x in check.original_classified_surface_pairs] == [
        "STRICT_TRIANGLE_INTERIOR",
    ]
    assert inspect_native_d4_assembly_world(
        body, current,
    ).original_classified_surface_pairs is None
    assert check.volume_verdict == "VOLUME_INTERFERENCE_UNVERIFIABLE_BODY_OPEN"
    assert not check.manufacturing_approved

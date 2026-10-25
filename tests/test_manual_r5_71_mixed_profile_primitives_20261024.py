"""R5 #71 source contract: standalone primary contour survives extra process layers."""
from ae_engine.sheetmetal_features import ResolvedProfile, Vec2
from ae_engine.sheetmetal_drawing import PolylinePrimitive, resolved_features_to_primitives


PRIMARY = (
    Vec2(0., 0.), Vec2(50., 0.), Vec2(50., 40.), Vec2(0., 40.)
)
EXTRA = (Vec2(5., 5.), Vec2(45., 35.))


def test_r5_71_primary_cutting_and_aux_marking_emit_both_distinct_processes():
    source = ResolvedProfile(
        points=PRIMARY, layer="CUTTING", source_type="custom",
        layered_profiles=(("MARKING", EXTRA, False),),
    )
    drawings = resolved_features_to_primitives([source])
    assert len(drawings) == 2
    assert all(isinstance(row, PolylinePrimitive) for row in drawings)
    assert [(row.layer, row.closed, row.color) for row in drawings] == [
        ("CUTTING", True, 3), ("MARKING", False, 211)
    ]
    assert drawings[0].points == PRIMARY
    assert drawings[1].points == EXTRA


def test_r5_71_existing_primary_repeated_in_same_layer_is_not_duplicate_cutting():
    # Canonical side-plate clipping can represent the same CUTTING contour
    # as both main points and a closed layer (including a trailing first point).
    source = ResolvedProfile(
        points=PRIMARY, layer="CUTTING", source_type="clipped",
        layered_profiles=(("CUTTING", PRIMARY + (PRIMARY[0],), True),),
    )
    drawings = resolved_features_to_primitives([source])
    assert len(drawings) == 1
    assert drawings[0].layer == "CUTTING"
    assert drawings[0].closed is True


def test_r5_71_from_dxf_source_bounds_are_not_extra_manufacturing_cuts():
    source = ResolvedProfile(
        points=PRIMARY, layer="FROM_DXF", source_type="catalog",
        layered_profiles=(("CUTTING", PRIMARY, True), ("MARKING", EXTRA, False)),
    )
    drawings = resolved_features_to_primitives([source])
    assert len(drawings) == 2
    assert [row.layer for row in drawings] == ["CUTTING", "MARKING"]
    assert all(row.layer != "FROM_DXF" for row in drawings)


def test_r5_71_primary_only_and_open_segments_remain_unchanged():
    primary = resolved_features_to_primitives(
        [ResolvedProfile(points=PRIMARY, layer="CUTTING")]
    )
    assert len(primary) == 1 and primary[0].closed is True
    open_stroke = resolved_features_to_primitives(
        [ResolvedProfile(points=EXTRA, layer="MARKING")]
    )
    assert len(open_stroke) == 1 and open_stroke[0].closed is False


def test_r5_71_one_point_extra_is_not_exported_but_primary_is():
    source = ResolvedProfile(
        points=PRIMARY, layer="CUTTING",
        layered_profiles=(("MARKING", (Vec2(4., 4.),), False),),
    )
    drawings = resolved_features_to_primitives([source])
    assert len(drawings) == 1
    assert drawings[0].layer == "CUTTING"


def test_r5_71_closed_primary_cut_deduplicates_rotated_or_reversed_import():
    """The same CNC closed cut must not be emitted twice with another start point."""
    for shifted in (
        PRIMARY[2:] + PRIMARY[:2],
        tuple(reversed(PRIMARY)),
    ):
        source = ResolvedProfile(
            points=PRIMARY, layer="CUTTING", source_type="clipped",
            layered_profiles=(("CUTTING", shifted + (shifted[0],), True),),
        )
        drawings = resolved_features_to_primitives((source,))
        assert len(drawings) == 1
        assert drawings[0].layer == "CUTTING"
        assert drawings[0].closed is True
    # A different physical cut on the same layer remains a separate contour.
    another = tuple(Vec2(pt.x + 100., pt.y) for pt in PRIMARY)
    different = ResolvedProfile(
        points=PRIMARY, layer="CUTTING", source_type="clipped",
        layered_profiles=(("CUTTING", another + (another[0],), True),),
    )
    assert len(resolved_features_to_primitives((different,))) == 2

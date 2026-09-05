import pytest


def _snapshot():
    return {
        "w": 500.0,
        "h": 300.0,
        "door_layout_columns": [
            [200.0, [100.0, 200.0]],
            [300.0, [300.0]],
        ],
    }


def test_vertical_divider_placement_uses_left_boundary_not_right_column_end():
    from ae_engine.assembly_placement import resolve_divider_placement

    placement = resolve_divider_placement(
        _snapshot(),
        "box_body:divider:main:VERTICAL:C0|C1",
    )

    # W=500 => left edge=-250; first column is 200 wide, so the divider is x=-50.
    assert placement.world_offset == pytest.approx((-50.0, 0.0, 0.0))
    assert placement.semantic_position == pytest.approx((-50.0, 0.0, 0.0))


def test_horizontal_divider_placement_uses_upper_cell_boundary():
    from ae_engine.assembly_placement import resolve_divider_placement

    placement = resolve_divider_placement(
        _snapshot(),
        "box_body:divider:main:HORIZONTAL:C0:R0|R1",
    )

    # H=300 => top edge=150; the first row is 100 high, so the divider is y=50.
    assert placement.world_offset == pytest.approx((-150.0, 50.0, 0.0))


def test_non_adjacent_divider_boundary_is_rejected():
    from ae_engine.assembly_placement import resolve_divider_placement

    with pytest.raises(ValueError, match="non-adjacent"):
        resolve_divider_placement(
            _snapshot(),
            "box_body:divider:main:VERTICAL:C0|C2",
        )

def test_horizontal_divider_span_deducts_thickness_at_outer_boundaries():
    from ae_engine.door_dividers import derive_box_body_dividers

    # Single column receiving box: W=800, T=2 => span must be W - 2T = 796
    dividers = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])],
        depth=350.0,
        thickness=2.0,
        layout_scope="receiving-main",
    )
    assert len(dividers) == 1
    assert dividers[0].span == pytest.approx(796.0)


def test_horizontal_divider_x_position_centers_on_its_column():
    from ae_engine.assembly_placement import resolve_divider_placement

    # Col 0 (width 200, from x=-250 to x=-50): center is x=-150
    placement = resolve_divider_placement(
        _snapshot(),
        "box_body:divider:main:HORIZONTAL:C0:R0|R1",
    )
    assert placement.world_offset[0] == pytest.approx(-150.0)
    assert placement.world_offset[1] == pytest.approx(50.0)
    assert placement.placement_kind == "divider_horizontal"


def test_3d_assembly_places_divider_with_correct_orientation():
    from ae_engine.assembly_geometry import place_assembly_points

    sample_points = (
        (0.0, -398.0, -12.5),
        (0.0, 398.0, -12.5),
        (-171.0, 0.0, -12.5),
        (171.0, 0.0, -12.5),
    )
    ref_triangles = (
        ((-171.0, -398.0, -25.0), (171.0, 398.0, 0.0), (0.0, 0.0, -12.5)),
    )
    placed = place_assembly_points(
        sample_points,
        ref_triangles,
        "divider_horizontal",
        (800.0, 1600.0, 350.0),
        offset=(0.0, -300.0, 0.0),
    )
    xs = [p[0] for p in placed]
    ys = [p[1] for p in placed]
    zs = [p[2] for p in placed]
    assert min(xs) == pytest.approx(-398.0)
    assert max(xs) == pytest.approx(398.0)
    assert min(ys) == pytest.approx(-300.0)
    assert max(ys) == pytest.approx(-300.0)
    assert min(zs) == pytest.approx(-171.0)
    assert max(zs) == pytest.approx(171.0)

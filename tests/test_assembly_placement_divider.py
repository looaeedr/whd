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
    assert placement.world_offset == pytest.approx((0.0, 50.0, 0.0))


def test_non_adjacent_divider_boundary_is_rejected():
    from ae_engine.assembly_placement import resolve_divider_placement

    with pytest.raises(ValueError, match="non-adjacent"):
        resolve_divider_placement(
            _snapshot(),
            "box_body:divider:main:VERTICAL:C0|C2",
        )

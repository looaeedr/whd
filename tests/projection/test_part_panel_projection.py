import pytest

import gui


@pytest.mark.parametrize(
    ('existing_parts', 'logical_key', 'expected'),
    [
        (['box_body:left_side'], 'box_body', True),
        (['box_body:back'], 'box_body', True),
        (['door_c1_r2'], 'door', True),
        (['base_plate_c1_r2'], 'base_plate', True),
        (['head'], 'tail', False),
        (['indicator_box'], 'indicator_box', True),
    ],
)
def test_logical_part_presence_projects_physical_ids_without_redefining_identity(
    existing_parts, logical_key, expected
):
    assert gui.BoxCalculatorGUI._phase6_logical_part_present(
        existing_parts, logical_key
    ) is expected

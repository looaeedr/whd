"""T5 relocation guard: manifest destination paths must own their durable lane.

This is a taxonomy-only contract.  It does not alter test outcomes, production
behavior, geometry, DXF authority, or runtime identity.
"""

import pytest

from tools.test_lane_policy import classify_test


@pytest.mark.parametrize(
    ("path", "expected_primary"),
    [
        ("tests/governance/test_semantic_doc_status.py", "governance"),
        ("tests/ui/test_box_body_physical_child_navigation.py", "ui"),
        ("tests/architecture/test_box_body_single_source.py", "architecture"),
        ("tests/projection/test_part_panel_projection.py", "projection"),
        ("tests/ui/test_gui_drawing_contract.py", "ui"),
        ("tests/ui/test_gui_toolbar_contract.py", "ui"),
        ("tests/architecture/test_project_actions_ownership.py", "architecture"),
        ("tests/projection/test_renderer_behavior.py", "projection"),
        ("tests/architecture/test_renderer_ownership.py", "architecture"),
    ],
)
def test_issue280_manifest_destination_directory_owns_primary_lane(path, expected_primary):
    classification = classify_test(path=path, nodeid="test_contract", requires_display=False)
    assert classification.primary == expected_primary

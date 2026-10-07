from __future__ import annotations

import inspect

from ae_engine import manufacturing_api
from ae_engine import manufacturing_render_data


def test_issue1343_render_data_owner_is_extracted_and_public_api_is_preserved():
    assert manufacturing_api.PartRenderData is manufacturing_render_data.PartRenderData
    assert manufacturing_api.UnfoldedBlankTopology is manufacturing_render_data.UnfoldedBlankTopology
    assert manufacturing_api.measure_unfolded_blanks is manufacturing_render_data.measure_unfolded_blanks
    assert manufacturing_api.material_polygon_from_final_scene is manufacturing_render_data.material_polygon_from_final_scene


def test_issue1343_manufacturing_api_shrinks_without_second_authority():
    source = inspect.getsource(manufacturing_api)
    owner = inspect.getsource(manufacturing_render_data)
    assert len(source.splitlines()) < 2100
    assert len(owner.splitlines()) < 600
    assert "class PartRenderData" not in source
    assert "class PartRenderData" in owner
    assert "def build_part_render_data" in source
    assert "def generate_part" in source
    assert "import ae_engine.manufacturing_api" not in owner
    assert "from .manufacturing_api import" not in owner


def test_issue1343_baseline_policy_owner_is_extracted_one_way():
    from ae_engine import manufacturing_baseline_policy
    assert manufacturing_api.resolve_policy is manufacturing_baseline_policy.resolve_policy
    assert manufacturing_api.expected_baseline_path_for is manufacturing_baseline_policy.expected_baseline_path_for
    assert len(inspect.getsource(manufacturing_api).splitlines()) < 1800
    owner = inspect.getsource(manufacturing_baseline_policy)
    assert "import ae_engine.manufacturing_api" not in owner
    assert "from .manufacturing_api import" not in owner


def test_issue1343_door_indicator_owner_is_extracted_one_way():
    from ae_engine import manufacturing_door_indicator
    assert manufacturing_api.door_finished_face_size is manufacturing_door_indicator.door_finished_face_size
    assert manufacturing_api.validate_door_indicator_fit is manufacturing_door_indicator.validate_door_indicator_fit
    assert manufacturing_api.indicator_box_opening_size is manufacturing_door_indicator.indicator_box_opening_size
    assert len(inspect.getsource(manufacturing_api).splitlines()) < 1550
    owner = inspect.getsource(manufacturing_door_indicator)
    assert "import ae_engine.manufacturing_api" not in owner
    assert "from .manufacturing_api import" not in owner

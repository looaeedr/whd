from __future__ import annotations

import inspect

from ae_engine import manufacturing_api
from ae_engine import manufacturing_scene_orchestration


def test_issue1368_scene_orchestration_is_reexported():
    assert manufacturing_api.build_part_scene is manufacturing_scene_orchestration.build_part_scene
    assert manufacturing_api.build_part_render_data is manufacturing_scene_orchestration.build_part_render_data
    assert manufacturing_api.generate_box_body_structure_parts is manufacturing_scene_orchestration.generate_box_body_structure_parts


def test_issue1368_owner_is_one_way_and_api_shrinks():
    facade = inspect.getsource(manufacturing_api)
    owner = inspect.getsource(manufacturing_scene_orchestration)
    assert len(facade.splitlines()) < 550
    assert "from .manufacturing_api import" not in owner
    assert "import ae_engine.manufacturing_api" not in owner
    assert "_manufacturing_export.save_part_render_data_dxf" in owner


def test_issue1368_render_data_compat_exports_stay_on_public_api():
    from ae_engine import manufacturing_render_data
    assert manufacturing_api.measure_unfolded_blanks is manufacturing_render_data.measure_unfolded_blanks
    assert manufacturing_api.material_polygon_from_final_scene is manufacturing_render_data.material_polygon_from_final_scene
    assert manufacturing_api._exploded_box_body_preview is manufacturing_render_data._exploded_box_body_preview

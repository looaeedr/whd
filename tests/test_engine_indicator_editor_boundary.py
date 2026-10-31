"""Engine-owned indicator editor projections: GUI may format but never solve."""
import inspect

from ae_engine import manufacturing_api
from gui_modules.application import manufacturing_adapter


def test_engine_resolves_shared_indicator_box_and_small_door_editor_geometry():
    groups = (2,)
    spec = manufacturing_api.indicator_small_door_spec(groups, thickness=2.0)
    result = manufacturing_api.resolve_indicator_editor_components(
        groups, thickness=2.0, door_spec=spec,
    )
    assert set(result) == {"indicator_box", "indicator_door"}
    for item in result.values():
        assert item.width > 0 and item.height > 0
        assert item.surface is not None
        assert item.reference_guide is not None
        assert item.baseline_scene is not None


def test_gui_only_forwards_indicator_inputs_and_formats_engine_result():
    source = inspect.getsource(manufacturing_adapter._indicator_component_editor_contexts)
    assert "resolve_indicator_editor_components(" in source
    for forbidden in (
        "get_stretched_indicator_box_data(",
        "get_stretched_door_data(",
        "build_unknown_door_result(",
        "build_indicator_box_result(",
        "build_finished_reference_guide(",
    ):
        assert forbidden not in source

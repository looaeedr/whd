"""Source-verified R5 CADCraft preview and Door/Divider input safety."""
from types import SimpleNamespace
import pytest
from gui_modules.editors.cadcraft_control_bridge import CadcraftControlClient, CadcraftControlError
from gui_modules.editors.cadcraft_command_preview_bridge import (
    CadcraftCommandProofError, focus_started_cadcraft_window, prepare_whd_cadcraft_commands,
)
from gui_modules.parts.panels.door import _parse_layout_value, normalize_door_indicator_state
from gui_modules.parts.panels.divider import collect_divider_input


def test_r5_92_cadcraft_bool_transport_and_physical_dimensions():
    with pytest.raises(CadcraftControlError, match="INVALID_CONTROL_TIMEOUT"):
        CadcraftControlClient(12345, timeout=True)
    assert focus_started_cadcraft_window(True) is False
    assert focus_started_cadcraft_window(False) is False
    with pytest.raises(CadcraftCommandProofError, match="INVALID_WHD_FINISHED_FACE_DIMENSIONS"):
        prepare_whd_cadcraft_commands(surface=None, features=(), width=True, height=100.)


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -1, 0])
def test_r5_94_door_dimension_must_be_finite_positive(bad):
    with pytest.raises(ValueError):
        _parse_layout_value(SimpleNamespace(get=lambda: bad), "欄寬")
    assert _parse_layout_value(SimpleNamespace(get=lambda: 400.5), "欄寬") == 400.5


def test_r5_94_indicator_corrupt_settings_restore_safe_defaults():
    state = normalize_door_indicator_state({
        "layers": True, "groups": "123456",
        "offset_x": float("nan"), "offset_y": True,
    })
    assert state["layers"] == 1
    assert state["groups"] == [2] * 6
    assert state["offset_x"] == 0.0
    assert state["offset_y"] == 0.0
    valid = normalize_door_indicator_state({
        "layers": 2, "groups": [2, 3, 4, 5, 6, 7],
        "offset_x": -15.25, "offset_y": 31.75,
    })
    assert valid["layers"] == 2
    assert valid["groups"] == [2, 3, 4, 5, 6, 7]
    assert (valid["offset_x"],valid["offset_y"]) == (-15.25,31.75)


def test_r5_95_divider_null_depth_and_thickness_use_parent_defaults():
    result = collect_divider_input(
        "divider",
        {"door_layout_columns": [(400., (600.,))], "d": None, "t": None},
        default_depth=250., default_thickness=2.,
    )
    assert result["depth"] == 250.0
    assert result["thickness"] == 2.0
    assert result["columns"] == ((400., (600.,)),)
    for bad in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            collect_divider_input(
                "divider", {"door_layout_columns": [(bad, (600.,))]},
                default_depth=250., default_thickness=2.,
            )


@pytest.mark.parametrize("bad_mode", [[], {}, ["indicator"], {"kind": "indicator"}])
def test_r5_94_unhashable_saved_indicator_mode_recovers_without_type_error(bad_mode):
    """Saved presentation state is not authoritative geometry and must recover safely."""
    state = normalize_door_indicator_state({
        "mode": bad_mode, "enabled": True, "groups": [2, 3],
    })
    assert state["mode"] == "indicator"
    assert state["enabled"] is True
    assert state["groups"] == [2, 3, 2, 2, 2, 2]


def test_r5_73_readonly_mapping_is_converted_to_real_sheet_feature(monkeypatch):
    """The physical-sheet owner must accept a read-only Mapping, not only dict."""
    from dataclasses import dataclass
    from types import MappingProxyType
    import ae_engine.physical_sheet_features as physical
    from ae_engine.sheetmetal_features import CircleFeature

    @dataclass(frozen=True)
    class _Render:
        scene: object
        material: object = None

    captured = {}

    def resolve_surface(_surface, features, _width, _height):
        captured["features"] = features
        return ()

    monkeypatch.setattr(physical, "physical_sheet_feature_context", lambda *_: (None, 800., 1600., None))
    monkeypatch.setattr(physical.ae, "resolve_surface_features", resolve_surface)
    monkeypatch.setattr(physical, "resolved_features_to_primitives", lambda _: ())
    monkeypatch.setattr(physical, "material_polygon_from_final_scene", lambda _: None)
    hole = MappingProxyType({"type": "圓形", "x": 70., "y": 80., "params": {"diameter": 12.}})
    result = physical.with_physical_sheet_features("door", _Render(physical.DrawingScene()), (hole,))
    assert isinstance(captured["features"][0], CircleFeature)
    assert captured["features"][0].diameter == 12.
    assert result.scene is not None

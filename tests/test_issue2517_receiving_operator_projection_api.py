"""#2517 Receiving GUI operator projections must route through public Engine API."""
from pathlib import Path

from ae_engine import manufacturing_api as api
from gui_modules.application.receiving_multi_settings_window import default_preview_dimensions

SPLIT = {"active_type": "three_piece_side_back_split"}
INTEGRAL = {"active_type": "integral"}


def test_receiving_family_defaults_are_copied_and_shared_between_modes():
    defaults = api.receiving_default_box_dimensions()
    assert defaults == {"w": 800, "h": 1600, "d": 350}
    defaults["w"] = 999
    assert api.receiving_default_box_dimensions()["w"] == 800
    assert api.receiving_default_preview_dimensions({}) == (800.0, 1600.0, 350.0)
    assert default_preview_dimensions({"active_mode": "quantity"}) == (800.0, 1600.0, 350.0)
    assert default_preview_dimensions({
        "active_mode": "quantity",
        "receiving_quantity_box": {"w": 825, "h": 1800, "d": 420},
    }) == (825.0, 1800.0, 420.0)
    assert default_preview_dimensions({
        "active_mode": "set_bay",
        "receiving_layout": {"sets": [{"bays": [
            {"width": 900, "height": 1700, "depth": 390}
        ]}]},
    }) == (900.0, 1700.0, 390.0)


def test_back_panel_mode_capability_uses_family_registry_and_physical_topology():
    for family in ("受電箱", "RECEIVING", "receiving"):
        snapshot = {"model": family}
        assert api.receiving_family_supports_back_panel_mode(snapshot)
        assert api.receiving_back_panel_mode_control_applicable(snapshot, SPLIT)
        assert not api.receiving_back_panel_mode_control_applicable(snapshot, INTEGRAL)
    for family in ("金庫型", "RO", ""):
        snapshot = {"model": family}
        assert not api.receiving_family_supports_back_panel_mode(snapshot)
        assert not api.receiving_back_panel_mode_control_applicable(snapshot, SPLIT)


def test_receiving_gui_only_delegates_family_and_dimension_projection():
    root = Path(__file__).resolve().parents[1]
    composer = (root / "gui_modules/application/fold_designer_composition_receiving.py").read_text(encoding="utf-8")
    window = (root / "gui_modules/application/receiving_multi_settings_window.py").read_text(encoding="utf-8")
    assert "cabinet_family_policy.canonical_family_name" not in composer
    assert "receiving_back_panel_mode_control_applicable(snapshot, state)" in composer
    assert "manufacturing_api.receiving_default_box_dimensions()" in composer
    assert "from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS" not in composer
    assert "BOX_BODY_DEFAULTS" not in window
    assert "manufacturing_api.receiving_default_preview_dimensions(snapshot)" in window

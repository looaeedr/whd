"""Versioned NFB physical manufacturing belongs to WHD Engine, not GUI."""
import inspect

from ae_engine import manufacturing_api
from ae_engine import receiving_nfb_quantity_partial as engine
from gui_modules.application import receiving_nfb_quantity_partial as old_gui
from gui_modules.project import export_actions


def test_quantity_nfb_physically_versioned_selection_is_public_engine_api():
    assert manufacturing_api.select_quantity_nfb_partial is engine.select_quantity_nfb_partial
    assert manufacturing_api.QuantityNfbPartialSelection is engine.QuantityNfbPartialSelection
    assert manufacturing_api.verify_quantity_nfb_inner_door is engine.verify_quantity_nfb_inner_door
    assert manufacturing_api.quantity_partial_live_manifests is engine.quantity_partial_live_manifests


def test_headless_quantity_result_reports_actual_inventory_without_gui():
    selection = manufacturing_api.QuantityNfbPartialSelection((), ())
    receipt = selection.report()
    assert receipt["kind"] == "NFB_QUANTITY_PARTIAL_MANUFACTURING"
    assert receipt["actual_export_count"] == 0
    assert receipt["whole_cabinet_complete"] is False
    assert selection.held_piece_count == 0


def test_gui_only_submits_quantity_snapshot_to_engine():
    source = inspect.getsource(export_actions._export_selected_resolved_parts)
    assert "manufacturing_api.select_quantity_nfb_partial(" in source
    assert "manufacturing_api.QuantityNfbPartialSelection(" in source
    assert "manufacturing_api.quantity_partial_live_manifests(" in source
    assert "from gui_modules.application.receiving_nfb_quantity_partial" not in source
    assert old_gui.select_quantity_nfb_partial is engine.select_quantity_nfb_partial
    assert old_gui.QuantityNfbPartialSelection is engine.QuantityNfbPartialSelection


def test_engine_versioned_nfb_module_has_no_gui_or_tk_dependencies():
    from pathlib import Path
    source = Path(engine.__file__).read_text(encoding="utf-8")
    assert "gui_modules" not in source
    assert "tkinter" not in source
    assert "from ae_engine.manufacturing_api import" not in source
    assert "manufacturing_scene_orchestration" in source

def test_engine_quantity_version_model_is_single_owner():
    from ae_engine import receiving_quantity_versions as owner
    from phase6_quantity_model import QuantityModel as adapter
    assert adapter is manufacturing_api.QuantityModel is owner.QuantityModel
    assert "from phase6_" not in inspect.getsource(owner)
    assert "from phase6_" not in inspect.getsource(engine)


def test_engine_thaw_of_canonical_frozen_input_matches_existing_request_value():
    from phase6_manufacturing_contracts import (
        freeze_manufacturing_value, thaw_manufacturing_value as existing,
    )
    from ae_engine.manufacturing_value_thaw import thaw_manufacturing_value
    original = {"w": 800.5, "slots": (1, 2), "version": {"n": 3}}
    frozen = freeze_manufacturing_value(original)
    assert thaw_manufacturing_value(frozen) == existing(frozen)
    assert thaw_manufacturing_value(frozen)["version"] is not original["version"]

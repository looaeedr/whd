# -*- coding: utf-8 -*-
"""#2517 canonical Receiving NFB physical inner-door PART_ONLY Engine API."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_inner_door_partial_export as engine
from gui_modules.application import receiving_nfb_partial_export_action as gui
from tests.test_issue1501_receiving_nfb_partial_ui_export import _case


def test_engine_owns_inner_door_actual_export_without_gui_imports():
    assert api.export_verified_receiving_nfb_inner_door is engine.export_verified_receiving_nfb_inner_door
    assert gui.export_verified_receiving_nfb_inner_door is engine.export_verified_receiving_nfb_inner_door
    assert gui.nfb_verification_geometry_changed is api.nfb_verification_geometry_changed
    assert "gui_modules" not in inspect.getsource(engine)
    assert "phase6_" not in inspect.getsource(engine)
    assert "def export_verified_receiving_nfb_inner_door" not in inspect.getsource(gui)
    assert "from ae_engine.manufacturing_api import" in inspect.getsource(gui)


def test_headless_export_preserves_live_saved_world_x_and_actual_part(monkeypatch):
    bundle, kwargs, writes = _case(monkeypatch)
    path, manifest = api.export_verified_receiving_nfb_inner_door(bundle, **kwargs)
    assert path == str(kwargs["output_path"])
    assert manifest.actual_export_count == 1
    assert len(writes) == 1
    assert writes[0][3]["holes"][0].world_x_mm == 0.
    assert writes[0][3]["physical_scope"].inner_door_part_id == "inner-part"
    assert writes[0][3]["overwrite"] is False


def test_headless_export_rejects_stale_physical_source_without_writer(monkeypatch):
    bundle, kwargs, writes = _case(monkeypatch)
    kwargs["layout"]["sets"][0]["switch_brand"] = "不同廠牌"
    with pytest.raises(ValueError, match="品牌已變更"):
        api.export_verified_receiving_nfb_inner_door(bundle, **kwargs)
    assert writes == []

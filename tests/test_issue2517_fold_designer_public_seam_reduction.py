"""#2517: actual Fold Designer GUI manufacturing seam uses public Engine only."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_quantity_box as owner
from ae_engine.corner_type_ui import is_unknown_model
from gui_modules.application import fold_designer_manufacturing_projection as gui


@pytest.mark.parametrize("model", ("金庫型", "受電箱", "自訂", "未知類型", ""))
def test_custom_model_readonly_baseline_selects_existing_engine_label_policy(model):
    assert api.is_unknown_operator_model(model) == is_unknown_model(model)


def test_public_quantity_guard_exercises_real_engine_noop_without_source():
    assert api.require_valid_operator_quantity_features({}) is None


def test_public_quantity_guard_preserves_original_rejection(monkeypatch):
    monkeypatch.setattr(owner, "quantity_feature_errors",
                        lambda snapshot: ("實體封頭特徵越界",))
    with pytest.raises(ValueError, match="不能輸出 DXF.*實體封頭特徵越界"):
        api.require_valid_operator_quantity_features({"active_mode": "quantity"})


def test_operator_export_stops_before_render_or_file_save_on_quantity_rejection(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "require_valid_operator_quantity_features",
                        lambda snapshot: (_ for _ in ()).throw(ValueError("DXF refused")))
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: calls.append("flush"),
        workspace_controller=SimpleNamespace(
            workspace_snapshot=lambda: {"receiving_quantity_box": {"w": 800}},
        ),
        _make_original_fold_designer_snapshot=lambda: {"active_mode": "quantity"},
        _require_verified_baseline_sources_for_manufacturing=lambda: calls.append("certify"),
        _authoritative_render_data=lambda spec, ctx: calls.append("render"),
    )
    with pytest.raises(ValueError, match="DXF refused"):
        gui._export_authoritative_part(host, object(), "never-write.dxf")
    assert calls == ["flush"]


def test_current_gui_directly_invokes_public_fw_and_quantity_without_internal_imports():
    source = Path(inspect.getfile(gui)).read_text(encoding="utf-8")
    assert "manufacturing_api.formed_box_body_fw_widths(" in source
    assert "manufacturing_api.require_valid_operator_quantity_features(" in source
    assert "manufacturing_api.is_unknown_operator_model(" in source
    assert "from ae_engine.receiving_quantity_box" not in source
    assert "from ae_engine.corner_type_ui" not in source
    assert "from ae_engine.sheetmetal_part_adapters" not in source
    assert "from ae_engine.cabinet_types" not in source
    assert "from phase6_fold_profiles import formed_box_body_fw_widths" not in source
    assert "BoxBodyPartSpec, EndCapPartSpec" not in source


def test_fw_projection_remains_existing_engine_callable_for_real_profile():
    profile = (
        {"phase6_key": "zl1", "len": 15, "angle": -90},
        {"phase6_key": "box_w", "len": 500, "core": "W"},
        {"phase6_key": "zr1", "len": 15, "angle": 90},
    )
    # The public Engine itself computes the formed extent, independent of UI.
    assert api.formed_box_body_fw_widths(profile, 2) == api.formed_box_body_fw_widths(profile, 2)

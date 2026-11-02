"""#2517 No fallback to AE factory size when operator physical fields are invalid."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_snapshot_projection as gui


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
@pytest.mark.parametrize("bad", ("", "invalid", 0, -1, True, None, float("inf"), float("nan")))
def test_bad_physical_source_never_uses_factory_dimension(field, bad):
    var = SimpleNamespace(get=lambda: bad)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(bad, field=field)
    with pytest.raises(ValueError, match="包外尺寸"):
        gui._read_snapshot_numeric_control(var, 999., physical_field=field)


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
def test_broken_tk_read_rejected_for_physical_fields_and_unrelated_ui_keeps_fallback(field):
    def broken():
        raise ValueError("unavailable")
    var = SimpleNamespace(get=broken)
    with pytest.raises(ValueError, match="禁止使用預設值"):
        gui._read_snapshot_numeric_control(var, 999., physical_field=field)
    assert gui._read_snapshot_numeric_control(var, 999.) == 999.0


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_engine_normalizes_physical_save_reload_snapshot_without_rounding(model):
    source = {"model": model, "w": "800.25", "h": 1600.125,
              "d": "350.5", "t": "2.25", "fw": "28.75"}
    old = deepcopy(source)
    normalized = api.normalize_operator_source_dimensions(source)
    assert normalized == {
        "w": 800.25, "h": 1600.125, "d": 350.5, "t": 2.25, "fw": 28.75
    }
    assert source == old
    for key, value in normalized.items():
        assert gui._read_snapshot_numeric_control(
            SimpleNamespace(get=lambda v=value: str(v)),
            -1, physical_field=key
        ) == value


def test_settings_overlay_must_be_revalidated_at_last_snapshot_readback():
    original = {"w": 800., "h": 1600., "d": 350., "t": 2., "fw": 25.}
    for field in original:
        altered = dict(original, **{field: "invalid"})
        with pytest.raises(ValueError, match="包外尺寸"):
            api.normalize_operator_source_dimensions(altered)


def test_gui_delegates_both_control_read_and_settings_overlay_to_public_engine():
    src = Path("gui_modules/application/fold_designer_snapshot_projection.py").read_text(encoding="utf-8")
    base = src.split("def _snapshot_base_state(", 1)[1].split(
        "def _snapshot_workspace_state(", 1
    )[0]
    helper = src.split("def _read_snapshot_numeric_control(", 1)[1].split(
        "def _snapshot_base_state(", 1
    )[0]
    assert "manufacturing_api.normalize_operator_source_dimension(" in helper
    assert "manufacturing_api.normalize_operator_source_dimensions(" in base
    for field in ("w", "h", "d", "t", "fw"):
        assert 'physical_field="' + field + '"' in base
    assert "settings.update({" in base
    engine = Path("ae_engine/operator_settings_transactions.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine
